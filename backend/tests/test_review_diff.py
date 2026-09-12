"""scripts/review_diff.py: the offline review command, driven through main()
with the model factories replaced. Nothing here dials anything: the two model
factories, the health probe and the unload are monkeypatched on the script's
own namespace, and every test runs under the socket guard, so a test that
reached for the network would fail rather than pass quietly."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import DIFF
from tests.fakes import RecordingChatModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import review_diff as R  # noqa: E402

pytestmark = pytest.mark.usefixtures("no_egress")

REPLY = json.dumps({"findings": [
    {"category": "security", "severity": "critical", "title": "eval on user input", "line": 2,
     "evidence": "eval(user_input)", "recommendation": "Parse it.", "confidence": 0.95}], "summary": "One problem."})
TWO_FINDINGS = json.dumps({"findings": [
    {"category": "security", "severity": "critical", "title": "eval on user input", "line": 2,
     "evidence": "eval(user_input)", "recommendation": "Parse it.", "confidence": 0.95},
    {"category": "quality", "severity": "low", "title": "unused import", "line": 1,
     "evidence": "import os", "recommendation": "Remove it.", "confidence": 0.8}], "summary": "Two problems."})
CROSS_REPLY = json.dumps({"verdicts": [{"index": 0, "verdict": "real", "severity": "high", "reason": "line 2",
                                        "confidence": 0.9}], "additions": [], "summary_note": ""})
ESC = "\x1b"

MARKDOWN_PATCH = "@@ -1,2 +1,3 @@\n # Title\n+more words\n end\n"


def section(path: str, patch: str) -> str:
    """One file section of a git diff: the four header lines the pipeline never
    sees, then the hunks, which are all it sees."""
    return (f"diff --git a/{path} b/{path}\n"
            f"index 1111111..2222222 100644\n"
            f"--- a/{path}\n"
            f"+++ b/{path}\n") + patch


def huge_section(settings_limit: int = 32_000) -> str:
    body = "+    total = total + " + "x" * 180 + "\n"
    repeats = settings_limit // len(body) + 20
    return section("big.py", f"@@ -1,2 +1,{repeats + 2} @@\n import os\n" + body * repeats + " def main():\n")


def write_diff(tmp_path: Path, text: str, name: str = "change.diff") -> str:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def patch_seam(monkeypatch, reviewer=None, cross=None, health=None):
    """Replace the four things the script would otherwise take to Ollama, and
    hand back the reviewer model plus a dict that records the Settings the
    reviewer factory was handed."""
    llm = RecordingChatModel(model="qwen-fake", response=REPLY) if reviewer is None else reviewer
    captured = {}

    def chat_model(settings, model=None, keep_alive=None):
        captured["settings"] = settings
        return llm

    reported = {"reachable": True, "model_present": True, "cross_model_present": True} if health is None else health

    async def health_probe(settings):
        return dict(reported)

    async def unload(settings, model):
        return True

    monkeypatch.setattr(R, "build_chat_model", chat_model)
    monkeypatch.setattr(R, "build_cross_model", lambda settings: cross)
    monkeypatch.setattr(R, "ollama_health", health_probe)
    monkeypatch.setattr(R, "unload_model", unload)
    return llm, captured


def followed_by(argv, first: str, second: str) -> bool:
    return any(argv[i] == first and argv[i + 1] == second for i in range(len(argv) - 1))


def git_repo(tmp_path: Path, branch: str = "main") -> dict:
    env = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null", GIT_CONFIG_NOSYSTEM="1")

    def git(*args):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-C", str(tmp_path), *args],
                       capture_output=True, check=True, env=env)

    git("init", "-b", branch)
    return {"git": git}


def test_a_diff_file_is_reviewed_end_to_end_and_nothing_outside_loopback_is_dialled(tmp_path, monkeypatch, capsys):
    llm, _ = patch_seam(monkeypatch)
    code = R.main(["--file", write_diff(tmp_path, section("app.py", DIFF)), "--env-file", ""])
    out = capsys.readouterr().out
    assert code == 0
    assert "eval on user input" in out
    assert "eval(user_input)" in llm.seen_text


def test_the_text_format_prints_the_path_line_severity_category_title_evidence_and_recommendation_of_every_finding(
        tmp_path, monkeypatch, capsys):
    # the second finding quotes `import os`, a context line: this test measures the printing, so the
    # context-line rule is off for it
    monkeypatch.setenv("CONTEXT_LINE_FINDINGS", "keep")
    patch_seam(monkeypatch, reviewer=RecordingChatModel(model="qwen-fake", response=TWO_FINDINGS))
    code = R.main(["--file", write_diff(tmp_path, section("app.py", DIFF)), "--env-file", ""])
    out = capsys.readouterr().out
    assert code == 0
    assert "app.py:2  critical security  eval on user input" in out
    assert "    evidence: eval(user_input)" in out
    assert "    Parse it." in out
    assert "app.py:1  low quality  unused import" in out
    assert "    evidence: import os" in out
    assert "    Remove it." in out


def test_the_text_format_lists_the_skipped_files_with_the_reason_select_files_gave(tmp_path, monkeypatch, capsys):
    patch_seam(monkeypatch)
    diff = section("app.py", DIFF) + section("README.md", MARKDOWN_PATCH)
    code = R.main(["--file", write_diff(tmp_path, diff), "--env-file", ""])
    out = capsys.readouterr().out
    assert code == 0
    assert "Not reviewed:" in out
    assert "  README.md: not code" in out


def test_an_escape_sequence_in_a_finding_never_reaches_the_terminal(tmp_path, monkeypatch, capsys):
    # json.dumps writes the escape as , which is the only way a reply carrying one parses at all
    reply = json.dumps({"findings": [
        {"category": "security", "severity": "critical", "title": ESC + "[31meval on user input", "line": 2,
         "evidence": "eval(user_input)", "recommendation": "Parse it.", "confidence": 0.95}], "summary": "One problem."})
    patch_seam(monkeypatch, reviewer=RecordingChatModel(model="qwen-fake", response=reply))
    code = R.main(["--file", write_diff(tmp_path, section("app.py", DIFF)), "--env-file", ""])
    out = capsys.readouterr().out
    assert code == 0
    assert ESC not in out
    assert "[31meval on user input" in out


def test_the_markdown_format_is_the_body_render_review_builds_with_the_inline_comment_bodies_under_it(
        tmp_path, monkeypatch, capsys):
    patch_seam(monkeypatch)
    code = R.main(["--file", write_diff(tmp_path, section("app.py", DIFF)), "--env-file", "", "--format", "markdown"])
    out = capsys.readouterr().out
    assert code == 0
    assert "## ReviewBot review" in out
    assert "eval on user input" in out
    assert "### `app.py` line 2" in out


def test_the_json_format_is_one_object_per_file_with_its_kept_findings_and_the_run_totals(tmp_path, monkeypatch, capsys):
    patch_seam(monkeypatch)
    diff = section("app.py", DIFF) + section("README.md", MARKDOWN_PATCH)
    code = R.main(["--file", write_diff(tmp_path, diff), "--env-file", "", "--format", "json"])
    out = capsys.readouterr().out
    assert code == 0
    doc = json.loads(out)
    assert {"source", "model", "files", "skipped", "totals"} <= set(doc)
    assert [f["filename"] for f in doc["files"]] == ["app.py"]
    assert [f["line"] for f in doc["files"][0]["findings"]] == [2]
    assert doc["skipped"] == [["README.md", "not code"]]
    assert doc["totals"]["files"] == 1


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not on PATH")
def test_a_branch_range_is_read_from_a_temporary_git_repository_built_by_the_test(tmp_path, monkeypatch, capsys):
    git = git_repo(tmp_path)["git"]
    app = tmp_path / "app.py"
    app.write_text("import os\ndef main():\n    pass\n", encoding="utf-8")
    git("add", "app.py")
    git("commit", "-m", "first")
    git("checkout", "-b", "feature")
    app.write_text("import os\nSENTINEL_9f3a = eval(user_input)\ndef main():\n    pass\n", encoding="utf-8")
    git("add", "app.py")
    git("commit", "-m", "second")
    llm, _ = patch_seam(monkeypatch)
    code = R.main(["--repo", str(tmp_path), "--range", "main...feature", "--env-file", ""])
    capsys.readouterr()
    assert code == 0
    assert "eval(user_input)" in llm.seen_text


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not on PATH")
def test_the_default_range_is_the_three_dot_form_against_main_and_a_missing_main_is_refused_with_exit_code_two(
        tmp_path, monkeypatch, capsys):
    assert not [a for a in R.diff_argv(".", None) if "..." in a or ".." in a]
    git = git_repo(tmp_path, branch="trunk")["git"]
    (tmp_path / "app.py").write_text("import os\n", encoding="utf-8")
    git("add", "app.py")
    git("commit", "-m", "first")
    patch_seam(monkeypatch)
    code = R.main(["--repo", str(tmp_path), "--env-file", ""])
    err = capsys.readouterr().err
    assert code == 2
    assert "git diff failed" in err
    assert "main...HEAD" in err


def test_the_git_command_asks_for_three_lines_of_context_and_overrides_the_users_diff_configuration():
    argv = R.diff_argv("/tmp/repo", "main...HEAD")
    for flag in ("--unified=3", "--no-color", "--no-ext-diff", "--no-textconv", "--find-renames",
                 "--src-prefix=a/", "--dst-prefix=b/"):
        assert flag in argv, flag
    assert followed_by(argv, "-c", "core.quotepath=false")
    assert "--cached" not in argv
    assert "--cached" in R.diff_argv("/tmp/repo", None, staged=True)


def test_a_range_or_repo_beginning_with_a_dash_is_refused_before_git_is_called():
    with pytest.raises(R.CannotRun):
        R.diff_argv(".", "-foo")
    with pytest.raises(R.CannotRun):
        R.diff_argv("-foo", None)


def test_a_diff_with_no_eligible_file_prints_nothing_to_review_and_exits_zero(tmp_path, monkeypatch, capsys):
    def never(*args, **kwargs):
        raise AssertionError("no model may be built for a diff with nothing to review")

    async def never_probed(settings):
        raise AssertionError("Ollama may not be probed for a diff with nothing to review")

    monkeypatch.setattr(R, "build_chat_model", never)
    monkeypatch.setattr(R, "build_cross_model", never)
    monkeypatch.setattr(R, "ollama_health", never_probed)
    code = R.main(["--file", write_diff(tmp_path, section("README.md", MARKDOWN_PATCH)), "--env-file", ""])
    out = capsys.readouterr().out
    assert code == 0
    assert "Nothing to review" in out
    assert "  README.md: not code" in out


def test_a_cloud_model_tag_on_the_command_line_is_refused(tmp_path, monkeypatch, capsys):
    patch_seam(monkeypatch)
    code = R.main(["--file", write_diff(tmp_path, section("app.py", DIFF)),
                   "--model", "gemma4:31b-cloud", "--env-file", ""])
    err = capsys.readouterr().err
    assert code == 2
    assert "local-only" in err


def test_an_env_file_that_switches_strict_local_off_cannot_switch_it_off_for_this_command(tmp_path, monkeypatch, capsys):
    """OLLAMA_MODEL is dropped from the environment first because a real
    environment variable outranks any env file, and the test env sets one."""
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    env = tmp_path / "cloudy.env"
    env.write_text("STRICT_LOCAL=false\nOLLAMA_MODEL=gemma4:31b-cloud\n", encoding="utf-8")
    patch_seam(monkeypatch)
    code = R.main(["--file", write_diff(tmp_path, section("app.py", DIFF)), "--env-file", str(env)])
    err = capsys.readouterr().err
    assert code == 2
    assert "local-only" in err


def test_a_flag_the_user_did_not_give_leaves_the_env_files_value_alone(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    env = tmp_path / "local.env"
    env.write_text("OLLAMA_MODEL=custom-tag:1b\nMAX_FILES_PER_REVIEW=3\n", encoding="utf-8")
    _, captured = patch_seam(monkeypatch)
    path = write_diff(tmp_path, section("app.py", DIFF))
    assert R.main(["--file", path, "--env-file", str(env)]) == 0
    assert captured["settings"].OLLAMA_MODEL == "custom-tag:1b"
    assert captured["settings"].MAX_FILES_PER_REVIEW == 3
    assert R.main(["--file", path, "--env-file", str(env), "--max-files", "7"]) == 0
    capsys.readouterr()
    assert captured["settings"].MAX_FILES_PER_REVIEW == 7
    assert captured["settings"].OLLAMA_MODEL == "custom-tag:1b"


def test_the_command_runs_with_no_github_credentials_anywhere_in_the_environment(tmp_path, monkeypatch, capsys):
    for name in ("GITHUB_APP_ID", "GITHUB_PRIVATE_KEY", "GITHUB_WEBHOOK_SECRET"):
        monkeypatch.delenv(name, raising=False)
    patch_seam(monkeypatch)
    code = R.main(["--file", write_diff(tmp_path, section("app.py", DIFF)), "--env-file", ""])
    out = capsys.readouterr().out
    assert code == 0
    assert "eval on user input" in out


def test_a_configured_cross_model_that_is_not_pulled_stops_the_run_before_the_first_file(tmp_path, monkeypatch, capsys):
    llm, _ = patch_seam(monkeypatch, health={"reachable": True, "model_present": True, "cross_model_present": False})
    code = R.main(["--file", write_diff(tmp_path, section("app.py", DIFF)),
                   "--cross-model", "gemma-fake", "--env-file", ""])
    err = capsys.readouterr().err
    assert code == 2
    assert "gemma-fake" in err and "not pulled" in err
    assert llm.calls == []


def test_progress_goes_to_stderr_and_the_findings_go_to_stdout(tmp_path, monkeypatch, capsys):
    patch_seam(monkeypatch)
    code = R.main(["--file", write_diff(tmp_path, section("app.py", DIFF)), "--env-file", ""])
    captured = capsys.readouterr()
    assert code == 0
    assert "[1/1] review app.py" in captured.err
    assert "[1/1] review app.py" not in captured.out
    assert "eval on user input" in captured.out


def test_a_patch_over_the_byte_cap_is_listed_as_skipped_by_the_same_rule_the_app_uses(
        tmp_path, monkeypatch, capsys):
    patch_seam(monkeypatch)
    diff = section("app.py", DIFF) + huge_section()
    code = R.main(["--file", write_diff(tmp_path, diff), "--env-file", ""])
    out = capsys.readouterr().out
    assert code == 0
    assert "Not reviewed:" in out
    assert "patch larger than" in out
    assert "big.py" in out


def test_the_cross_examiner_runs_when_configured_and_its_provenance_is_printed(tmp_path, monkeypatch, capsys):
    cross = RecordingChatModel(model="gemma-fake", response=CROSS_REPLY)
    patch_seam(monkeypatch, cross=cross)
    code = R.main(["--file", write_diff(tmp_path, section("app.py", DIFF)),
                   "--cross-model", "gemma-fake", "--env-file", ""])
    out = capsys.readouterr().out
    assert code == 0
    assert len(cross.calls) == 1
    assert "cross-examined by gemma-fake" in out


def test_a_file_whose_model_call_fails_is_listed_as_not_reviewed_and_the_exit_code_is_one(tmp_path, monkeypatch, capsys):
    """The App's rule: a file the model did not come back usable for joins
    Not reviewed with the reason, and is never counted as reviewed."""
    patch_seam(monkeypatch, reviewer=RecordingChatModel(model="qwen-fake", fail_with="boom"))
    code = R.main(["--file", write_diff(tmp_path, section("app.py", DIFF)), "--env-file", ""])
    out = capsys.readouterr().out
    assert code == 1
    assert "0 findings in 0 files reviewed, 1 not reviewed" in out
    assert "did not return a usable review for 1 file" in out
    assert "Not reviewed:" in out and "app.py: the model did not return a usable review (" in out
    assert "Per file:" not in out


def test_an_unreadable_reply_is_not_reviewed_in_any_format(tmp_path, monkeypatch, capsys):
    """parse_ok False with no error is the shape a reply the pipeline could not
    read leaves behind; it must not pass for a clean file."""
    patch_seam(monkeypatch, reviewer=RecordingChatModel(model="qwen-fake", response="not json at all"))
    diff = write_diff(tmp_path, section("app.py", DIFF))
    assert R.main(["--file", diff, "--env-file", ""]) == 1
    text = capsys.readouterr().out
    assert "app.py: the model did not return a usable review (unreadable reply)" in text
    assert "0 files reviewed" in text and "Per file:" not in text
    assert R.main(["--file", diff, "--env-file", "", "--format", "markdown"]) == 1
    markdown = capsys.readouterr().out
    assert "did not return a usable review for 1 file" in markdown
    assert "### Not reviewed" in markdown and "unreadable reply" in markdown
    assert "No findings in 0 reviewed files" in markdown
    assert R.main(["--file", diff, "--env-file", "", "--format", "json"]) == 1
    doc = json.loads(capsys.readouterr().out)
    assert doc["files"][0]["parse_ok"] is False and doc["files"][0]["error"] is None
    assert doc["skipped"] == [["app.py", "the model did not return a usable review (unreadable reply)"]]


def test_a_diff_on_stdin_that_is_not_utf8_is_read_like_a_file_and_not_as_a_traceback(tmp_path, monkeypatch, capsys):
    """git prints a latin-1 source line byte for byte; the file branch replaces
    the byte, and stdin must do the same rather than crash with exit 1."""
    llm, _ = patch_seam(monkeypatch)
    raw = section("app.py", DIFF).encode("utf-8") + b"diff --git a/latin.py b/latin.py\nindex 1..2 100644\n--- a/latin.py\n+++ b/latin.py\n@@ -1 +1 @@\n-x\n+b = \"\xff\"\n"
    import io
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8"))
    assert R.main(["--file", "-", "--env-file", ""]) == 0
    assert "eval on user input" in capsys.readouterr().out


def test_an_empty_file_argument_is_refused_rather_than_reviewing_the_current_directory(tmp_path, monkeypatch, capsys):
    patch_seam(monkeypatch)
    assert R.main(["--file", "", "--env-file", ""]) == 2
    assert "--file needs a path" in capsys.readouterr().err


def test_a_named_env_file_that_does_not_exist_is_refused_instead_of_silently_ignored(tmp_path, monkeypatch, capsys):
    patch_seam(monkeypatch)
    code = R.main(["--file", write_diff(tmp_path, section("app.py", DIFF)), "--env-file", str(tmp_path / "typo.env")])
    assert code == 2
    assert "typo.env is not a file" in capsys.readouterr().err


def test_a_max_files_below_one_is_refused(tmp_path, monkeypatch, capsys):
    patch_seam(monkeypatch)
    code = R.main(["--file", write_diff(tmp_path, section("app.py", DIFF)), "--env-file", "", "--max-files", "0"])
    assert code == 2
    assert "--max-files must be at least 1" in capsys.readouterr().err


def test_a_unified_diff_that_is_not_git_output_is_refused_not_reported_as_empty(tmp_path, monkeypatch, capsys):
    """A plain diff -u has no diff --git sections; reviewing it as empty would
    hand a clean bill of health to a change nobody looked at."""
    patch_seam(monkeypatch)
    plain = "--- a/app.py\n+++ b/app.py\n@@ -1,2 +1,3 @@\n import os\n+eval(x)\n def main():\n"
    assert R.main(["--file", write_diff(tmp_path, plain), "--env-file", ""]) == 2
    assert "no `diff --git` section found" in capsys.readouterr().err


def test_a_combined_diff_of_a_merge_commit_is_refused_with_the_way_round_it(tmp_path, monkeypatch, capsys):
    patch_seam(monkeypatch)
    combined = ("diff --cc app.py\nindex 1111111,2222222..3333333\n--- a/app.py\n+++ b/app.py\n"
                "@@@ -1,2 -1,2 +1,3 @@@\n  import os\n +eval(x)\n  def main():\n")
    assert R.main(["--file", write_diff(tmp_path, combined), "--env-file", ""]) == 2
    err = capsys.readouterr().err
    assert "combined diff of a merge commit" in err and "app.py" in err and "--range" in err


@pytest.mark.parametrize("fmt", ["text", "markdown", "json"])
def test_an_escape_sequence_in_a_finding_never_reaches_the_terminal_in_any_format(tmp_path, monkeypatch, capsys, fmt):
    reply = json.dumps({"findings": [
        {"category": "security", "severity": "critical", "title": f"eval {ESC}[31mred{ESC}[0m on user input", "line": 2,
         "evidence": "eval(user_input)", "recommendation": f"Parse it {ESC}[2J.", "confidence": 0.95}], "summary": f"One {ESC}[0m problem."})
    patch_seam(monkeypatch, reviewer=RecordingChatModel(model="qwen-fake", response=reply))
    assert R.main(["--file", write_diff(tmp_path, section("app.py", DIFF)), "--env-file", "", "--format", fmt]) == 0
    out = capsys.readouterr().out
    assert ESC not in out
    assert "red" in out and "on user input" in out


def test_the_proxy_variables_are_dropped_so_a_shell_proxy_cannot_carry_a_model_call():
    """httpx honours HTTP_PROXY and friends by default; with them in the
    process every call, redacted diff included, would go to the proxy host."""
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        assert name in R.POPPED_VARS
    for name in ("LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING", "OPENAI_API_KEY", "SENTRY_DSN"):
        assert name in R.POPPED_VARS


async def test_the_cross_examiner_gate_tolerates_a_tag_pulled_as_latest(monkeypatch):
    """ollama_health let the reviewer's bare tag match name:latest but held the
    cross-examiner to an exact match, so --cross-model gemma4 against a pulled
    gemma4:latest was refused as not pulled."""
    import respx
    from httpx import Response
    from config.settings import settings
    probe = settings.model_copy(update={"OLLAMA_MODEL": "qwen3.5", "CROSS_EXAMINE_MODEL": "gemma4"})
    with respx.mock(base_url=settings.OLLAMA_BASE_URL.rstrip("/")) as mock:
        mock.get("/api/tags").mock(return_value=Response(200, json={"models": [{"name": "qwen3.5:latest"}, {"name": "gemma4:latest"}]}))
        mock.get("/api/ps").mock(return_value=Response(200, json={"models": []}))
        health = await R.ollama_health(probe)
    assert health["model_present"] is True
    assert health["cross_model_present"] is True, "the cross tag gets the same :latest fallback as the reviewer tag"

