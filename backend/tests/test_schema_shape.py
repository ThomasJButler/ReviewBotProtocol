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
