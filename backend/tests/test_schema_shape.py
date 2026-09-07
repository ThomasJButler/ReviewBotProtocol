"""The grammar handed to Ollama must not let the model close the review
before it has written its findings."""

from services.schemas import cross_schema, output_schema


def test_findings_is_required_so_a_truncated_summary_cannot_end_the_object():
    schema = output_schema()
    assert "findings" in schema["required"] and "summary" in schema["required"]


def test_cross_examination_verdicts_and_additions_are_required_too():
    assert {"verdicts", "additions"} <= set(cross_schema()["required"])


def test_the_summary_comes_before_the_findings_so_the_model_thinks_before_it_lists():
    assert list(output_schema()["properties"]) == ["summary", "findings"]


def test_the_cross_schema_can_put_the_note_first_and_keeps_every_key_required():
    default = cross_schema()
    assert list(default["properties"]) == ["verdicts", "additions", "summary_note"]
    first = cross_schema(note_first=True)
    assert list(first["properties"]) == ["summary_note", "verdicts", "additions"]
    assert first["required"] == ["summary_note", "verdicts", "additions"]
    assert first["properties"]["verdicts"] == default["properties"]["verdicts"]


async def test_the_reviewer_binds_the_note_first_order_from_the_setting_or_the_argument():
    from config.settings import settings
    from services.ai_reviewer import FileReviewer
    from tests.fakes import RecordingChatModel
    cross = RecordingChatModel(model="g", response='{"verdicts": [], "additions": [], "summary_note": ""}')
    reviewer = FileReviewer(RecordingChatModel(model="q"), settings.model_copy(update={"CROSS_EXAMINE_NOTE_FIRST": True}), cross_llm=cross)
    bound = reviewer.cross_chain.last.kwargs["format"]
    assert list(bound["properties"])[0] == "summary_note"
    reviewer = FileReviewer(RecordingChatModel(model="q"), settings, cross_llm=cross, cross_note_first=False)
    assert list(reviewer.cross_chain.last.kwargs["format"]["properties"])[0] == "verdicts"
