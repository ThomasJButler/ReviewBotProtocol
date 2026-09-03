"""What the model is asked, and what we do with what it says.

The first test is the one that would have caught SR-03: the prompt must contain
the diff. It is a strict expected failure against the current code and flips
to a hard failure the moment the fix lands, at which point the marker is removed."""

import json

import pytest

from tests.fakes import RecordingChatModel

DIFF = "@@ -1,3 +1,4 @@\n import os\n+SENTINEL_9f3a = eval(user_input)\n+password = 'hunter2hunter2'\n"


@pytest.fixture
def reviewer_with_fake():
    from services.ai_reviewer import AIReviewer
    reviewer = AIReviewer(use_langgraph=False)
    fake = RecordingChatModel(response="[]")
    reviewer.llm = fake
    reviewer._setup_chains()
    return reviewer, fake


@pytest.mark.xfail(strict=True, reason="SR-03: ChatPromptTemplate built from message instances never substitutes {code_diff}")
async def test_diff_filename_and_language_reach_the_model(reviewer_with_fake):
    reviewer, fake = reviewer_with_fake
    await reviewer._run_security_analysis({"filename": "app.py", "language": "python", "code_diff": DIFF})
    seen = fake.seen_text
    assert fake.calls, "the model was never called"
    assert "SENTINEL_9f3a" in seen, "the diff text is not in the prompt"
    assert "app.py" in seen
    assert "python" in seen
    assert "{code_diff}" not in seen and "{filename}" not in seen


async def test_model_is_called_once_per_analysis(reviewer_with_fake):
    reviewer, fake = reviewer_with_fake
    await reviewer._run_security_analysis({"filename": "app.py", "language": "python", "code_diff": DIFF})
    assert len(fake.calls) == 1


class TestParseJsonResult:
    @pytest.fixture
    def parse(self, reviewer_with_fake):
        return reviewer_with_fake[0]._parse_json_result

    def test_bare_json_list(self, parse):
        assert parse('[{"type":"x","severity":"high"}]', "security") == [{"type": "x", "severity": "high"}]

    def test_json_fence_stripped(self, parse):
        assert parse('```json\n[{"type":"x"}]\n```', "security") == [{"type": "x"}]

    def test_prose_yields_no_findings(self, parse):
        assert parse("I could not find any code to analyse.", "security") == []

    def test_single_object_wrapped(self, parse):
        assert parse('{"type":"x"}', "security") == [{"type": "x"}]

    @pytest.mark.xfail(strict=True, reason="Phase 4 step 3: a bare fence without the json tag must still parse")
    def test_plain_fence_stripped(self, parse):
        assert parse('```\n[{"type":"x"}]\n```', "security") == [{"type": "x"}]

    @pytest.mark.xfail(strict=True, reason="Phase 4 step 3: scalar JSON is not a finding")
    def test_scalar_json_is_not_a_finding(self, parse):
        assert parse('"ok"', "security") == []
        assert parse("42", "security") == []


class TestCommentRendering:
    def test_basic_comment_shape(self):
        from utils.helpers import format_review_comment
        c = format_review_comment("security", "high", "SQL built with f-string", "Use parameters", 12)
        assert "Security Issue" in c and "HIGH" in c and "Line 12" in c and "Use parameters" in c

    @pytest.mark.xfail(strict=True, reason="Phase 4 step 6: model text must be sanitised before it is posted")
    def test_html_and_offsite_links_are_stripped(self):
        from utils.helpers import format_review_comment
        evil = 'Fix this <img src=x onerror=alert(1)> see [docs](https://evil.example/phish) and @everyone'
        c = format_review_comment("security", "high", evil, None, 1)
        assert "<img" not in c
        assert "evil.example" not in c
        assert "@everyone" not in c

    @pytest.mark.xfail(strict=True, reason="Phase 4 step 6: comment length must be bounded")
    def test_comment_length_is_bounded(self):
        from utils.helpers import format_review_comment
        c = format_review_comment("security", "high", "x" * 50_000, "y" * 50_000, 1)
        assert len(c) <= 8_000


class TestRedaction:
    @pytest.mark.xfail(strict=True, reason="Phase 4 step 3: services.redaction does not exist yet")
    def test_tokens_are_masked_before_the_model(self):
        from services.redaction import redact
        diff = "+OPENAI_API_KEY = 'sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGH'\n+token = 'ghp_" + "a" * 36 + "'\n"
        out = redact(diff)
        assert "sk-proj-abcdef" not in out
        assert "ghp_aaaa" not in out
        assert "[REDACTED" in out

    @pytest.mark.xfail(strict=True, reason="Phase 4 step 3: secret-bearing filenames must be excluded from review")
    def test_secret_filenames_are_excluded(self):
        from services.redaction import is_excluded_path
        for p in [".env", ".env.production", "certs/server.pem", "id_rsa", "infra/prod.tfvars", ".npmrc", "credentials.json"]:
            assert is_excluded_path(p), p
        assert not is_excluded_path("src/app.py")
