"""The harness's replay mode: a recorded reviewer reply stands in for the
reviewer model, so a cross-examiner runs with only its own model loaded and
the pipeline behaves exactly as it does live."""

import json
import sys
from pathlib import Path

import pytest

from config.settings import settings
from services.ai_reviewer import FileReviewer
from tests.conftest import DIFF
from tests.fakes import RecordingChatModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import prompt_eval as H  # noqa: E402

REVIEW = json.dumps({"findings": [
    {"category": "security", "severity": "critical", "title": "eval on user input", "line": 2,
     "evidence": "eval(user_input)", "recommendation": "Parse it.", "confidence": 0.95}], "summary": "One problem."})
CROSS = json.dumps({"verdicts": [{"index": 0, "verdict": "real", "severity": "high", "reason": "line 2", "confidence": 0.9}],
                    "additions": [], "summary_note": ""})


def _run_file(tmp_path: Path) -> Path:
    p = tmp_path / "pass1-new.json"
    p.write_text(json.dumps({"model": "qwen-recorded", "variant": "new", "prompt_words": 500, "rows": [
        {"case": "a", "model_texts": [REVIEW], "prompt_tokens": 800, "output_tokens": 150, "seconds": 9.5},
        {"case": "a", "model_texts": [REVIEW.replace("0.95", "0.6")], "prompt_tokens": 810, "output_tokens": 140, "seconds": 8.0},
    ], "summary": {}}))
    return p


async def test_a_replayed_reply_drives_the_real_pipeline_and_the_cross_model_is_the_only_live_call(tmp_path):
    run, texts, rows = H.load_replay(str(_run_file(tmp_path)))
    assert run["model"] == "qwen-recorded" and list(texts) == ["a"] and len(texts["a"]) == 2 and len(rows["a"]) == 2
    llm = H.ReplayChatModel(model=run["model"], texts=texts, key="a", repeat=1)
    cross = RecordingChatModel(model="gemma-fake", response=CROSS)
    result = await FileReviewer(llm, settings, cross_llm=cross).review_file("a.py", "python", "modified", DIFF)
    assert len(cross.calls) == 1, "the cross-examiner is the one live call"
    assert [f.line for f in result.review.findings] == [2]
    finding = result.review.findings[0]
    assert finding.source_model == "qwen-recorded" and finding.cross_verdict == "real"
    assert finding.confidence == 0.6, "the second repeat's reply was the one replayed"
    assert finding.severity.value == "high", "severity only goes down, exactly as it does live"


async def test_a_replay_beyond_the_recorded_repeats_reuses_the_last_reply(tmp_path):
    run, texts, _ = H.load_replay(str(_run_file(tmp_path)))
    llm = H.ReplayChatModel(model=run["model"], texts=texts, key="a", repeat=7)
    result = await FileReviewer(llm, settings).review_file("a.py", "python", "modified", DIFF)
    assert result.review.findings[0].confidence == 0.6


def test_recorder_sees_the_replayed_reply(tmp_path):
    run, texts, _ = H.load_replay(str(_run_file(tmp_path)))
    llm = H.ReplayChatModel(model=run["model"], texts=texts, key="a")
    recorder = H.Recorder()
    llm.callbacks = [recorder]
    llm.invoke("anything")
    assert recorder.texts == [REVIEW]


@pytest.mark.parametrize("missing", [{"case": "b", "model_texts": []}])
def test_a_row_with_no_recorded_reply_replays_an_empty_string_rather_than_crashing(tmp_path, missing):
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"model": "m", "variant": "new", "rows": [missing], "summary": {}}))
    _, texts, _ = H.load_replay(str(p))
    assert texts == {"b": [""]}
