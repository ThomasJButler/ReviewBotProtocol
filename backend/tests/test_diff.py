from services.diff import locate_evidence, parse_patch
from tests.conftest import DIFF


def test_new_file_lines_and_added_lines():
    p = parse_patch(DIFF)
    assert p.hunks == 1
    assert p.new_lines == {1: "import os", 2: "SENTINEL_9f3a = eval(user_input)", 3: "password = 'hunter2hunter2'", 4: "def main():"}
    assert set(p.added_lines) == {2, 3}
    assert p.is_commentable(2) and p.is_commentable(4) and not p.is_commentable(5)


def test_multiple_hunks_and_no_newline_marker():
    patch = "@@ -1,2 +1,2 @@\n-a\n+b\n c\n@@ -10,2 +10,3 @@\n x\n+y\n z\n\\ No newline at end of file\n"
    p = parse_patch(patch)
    assert p.hunks == 2
    assert p.new_lines[1] == "b" and p.new_lines[2] == "c"
    assert p.new_lines[10] == "x" and p.new_lines[11] == "y" and p.new_lines[12] == "z"
    assert 13 not in p.new_lines


def test_empty_patch():
    assert parse_patch(None).new_lines == {} and parse_patch("").new_lines == {}


def test_locate_evidence_prefers_claimed_line_then_nearest_added_line():
    p = parse_patch(DIFF)
    assert locate_evidence(p, 2, "eval(user_input)") == 2
    assert locate_evidence(p, 4, "eval(user_input)") == 2          # wrong line, right quote: relocated
    assert locate_evidence(p, 1, "def main()") == 4                 # context line is still commentable
    assert locate_evidence(p, 2, "os.system('rm -rf /')") is None   # hallucinated quote
    assert locate_evidence(p, 2, "x") is None                       # too short to mean anything
    assert locate_evidence(p, 2, "= 'hun") is None                  # short and one token
    assert locate_evidence(p, 3, "password  =  'hunter2hunter2'") == 3  # whitespace-insensitive


def test_evidence_quoted_with_the_diff_marker_still_matches():
    p = parse_patch(DIFF)
    assert locate_evidence(p, 2, "+SENTINEL_9f3a = eval(user_input)") == 2
    assert locate_evidence(p, 9, "+password = 'hunter2hunter2'") == 3


def test_relocation_picks_the_nearest_matching_line():
    patch = "@@ -1,6 +1,6 @@\n x = 1\n+return value\n y = 2\n z = 3\n+return value\n w = 4\n"
    p = parse_patch(patch)
    assert locate_evidence(p, 6, "return value") == 5
    assert locate_evidence(p, 1, "return value") == 2


def test_multi_line_evidence_locates_by_its_first_line_in_the_diff():
    from tests.conftest import DIFF
    parsed = parse_patch(DIFF)
    quoted = "SENTINEL_9f3a = eval(user_input)\npassword = 'hunter2hunter2'"
    assert locate_evidence(parsed, 2, quoted) == 2
    assert locate_evidence(parsed, 9, "not here\nnor here") is None
    assert locate_evidence(parsed, 1, "import os\nSENTINEL_9f3a = eval(user_input)") == 1


def test_mixed_real_and_fabricated_multi_line_evidence_keeps_only_the_real_line():
    from tests.conftest import DIFF
    from services.diff import locate_evidence_part
    parsed = parse_patch(DIFF)
    line, part = locate_evidence_part(parsed, 2, "SENTINEL_9f3a = eval(user_input)\nos.system(user_input)  # invented")
    assert line == 2 and part == "SENTINEL_9f3a = eval(user_input)"


async def test_postprocess_trims_a_multi_line_quote_to_the_located_line():
    import json
    from config.settings import settings
    from services.ai_reviewer import FileReviewer
    from tests.conftest import DIFF
    from tests.fakes import RecordingChatModel
    reply = json.dumps({"findings": [{"category": "security", "severity": "high", "title": "eval", "line": 2,
                        "evidence": "SENTINEL_9f3a = eval(user_input)\nos.system(user_input)  # invented",
                        "recommendation": "x", "confidence": 0.9}], "summary": "s"})
    result = await FileReviewer(RecordingChatModel(response=reply), settings).review_file("a.py", "python", "modified", DIFF)
    (f,) = result.review.findings
    assert f.line == 2 and f.evidence == "SENTINEL_9f3a = eval(user_input)", "the invented line never reaches the comment"


# ---- 2026-09-05: two ways a real finding was dropped as unlocatable ----------

_HTML = (
    "@@ -0,0 +1,4 @@\n"
    "+<!doctype html>\n"
    "+<html>\n"
    "+  <head><title>Statement</title></head>\n"
    "+</html>\n"
)
_KEY_LINE = 'FIELD_ENCRYPTION_KEY = "ZmFrZS1kZW1vLWtleS1ub3QtcmVhbC1hdC1hbGwtMDAwMD0="'
_KEY = (
    "@@ -1,2 +1,3 @@\n"
    " from cryptography.fernet import Fernet\n"
    f"+{_KEY_LINE}\n"
    "+cipher = Fernet(FIELD_ENCRYPTION_KEY.encode())\n"
)


def test_a_whole_short_line_quoted_at_its_own_line_is_evidence():
    parsed = parse_patch(_HTML)
    assert locate_evidence(parsed, 2, "<html>") == 2, "the lang finding quotes the html tag, six characters"
    assert locate_evidence(parsed, 2, "+<html>") == 2
    assert locate_evidence(parsed, 1, "<html>") is None, "a short quote is not searched for; it must be at its line"
    assert locate_evidence(parsed, 3, "<head>") is None, "part of a line is still too short to mean anything"


def test_a_long_literal_copied_with_a_slip_near_its_end_locates_at_the_named_line():
    parsed = parse_patch(_KEY)
    slipped = _KEY_LINE.replace("MDAwMD0=", "MDAwMDA9=")  # one extra character, as qwen3.5:9b wrote it
    assert slipped != _KEY_LINE
    assert locate_evidence(parsed, 2, slipped) == 2
    assert locate_evidence(parsed, 3, slipped) is None, "only the line the model named, never a search"
    assert locate_evidence(parsed, 2, 'FIELD_ENCRYPTION_KEY = "completely different value here"') is None


_REMOVAL = (
    "@@ -14,4 +14,6 @@\n"
    "   const [message, setMessage] = useState(\"\")\n"
    " \n"
    "   return (\n"
    "-    <p role=\"status\" className=\"cart-status\">{message}</p>\n"
    "+    <p className=\"cart-status\">\n"
    "+      {message}\n"
    "+    </p>\n"
    "   )\n"
)
_TRAILING = (
    "@@ -1,3 +1,2 @@\n"
    " import os\n"
    " x = 1\n"
    "-assert_authorised(user)\n"
)


def test_a_removed_line_is_kept_at_the_new_line_that_took_its_place():
    parsed = parse_patch(_REMOVAL)
    assert parsed.removed_lines == {17: ['    <p role="status" className="cart-status">{message}</p>']}
    assert parsed.replacement_line(17) == 17


def test_a_quote_of_a_removed_line_locates_at_its_replacement():
    parsed = parse_patch(_REMOVAL)
    assert locate_evidence(parsed, 17, '<p role="status" className="cart-status">{message}</p>') == 17
    assert locate_evidence(parsed, 14, '-    <p role="status" className="cart-status">{message}</p>') == 17
    assert locate_evidence(parsed, 17, "<p role=\"alert\">nothing like it</p>") is None, "a fabricated line is still nothing"


def test_a_removal_at_the_end_of_a_hunk_lands_on_the_last_line_before_it():
    parsed = parse_patch(_TRAILING)
    assert parsed.removed_lines == {3: ["assert_authorised(user)"]}
    assert locate_evidence(parsed, 3, "assert_authorised(user)") == 2


_CAROUSEL = (
    "@@ -6,3 +6,8 @@\n"
    "   const [index, setIndex] = useState(0)\n"
    " \n"
    "+  useEffect(() => {\n"
    "+    const timer = setInterval(() => {\n"
    "+      setIndex((i) => (i + 1) % slides.length)\n"
    "+    }, 4000)\n"
    "+  }, [slides.length])\n"
)


def test_two_diff_lines_run_together_into_one_quote_locate_at_the_first():
    parsed = parse_patch(_CAROUSEL)
    flattened = "const timer = setInterval(() => { setIndex((i) => (i + 1) % slides.length)"
    assert locate_evidence(parsed, 10, flattened) == 9, "the quote begins with the whole of line 9"
    assert locate_evidence(parsed, 9, "const timer = setInterval(() => { rm -rf /") == 9, "a real first line still locates; the rest is not posted as evidence"
    assert locate_evidence(parsed, 9, "setIndex((i) => (i + 1) % slides.length) and then something invented") == 10
    assert locate_evidence(parsed, 9, "timer = setInterval(() => {") == 9, "a substring of one line still works as before"
    assert locate_evidence(parsed, 9, "useEffect(() => { fetch('https://evil.example')") == 8
    assert locate_evidence(parsed, 9, "} , 4000) nothing") is None, "a fragment too short to mean anything is still nothing"


def test_a_quote_that_starts_midway_through_one_line_and_runs_on_locates_at_the_line_it_contains_whole():
    """Round three, 2026-09-06: qwen3.5:9b quoted three lines of the carousel
    callback as one, dropping `const timer =` from the first, so no diff line
    began the quote and the finding was dropped as unlocatable in both repeats.
    Line 10 is inside the quote whole, so the quote is of line 10."""
    parsed = parse_patch(_CAROUSEL)
    joined = "setInterval(() => { setIndex((i) => (i + 1) % slides.length), 4000)"
    assert locate_evidence(parsed, 10, joined) == 10
    assert locate_evidence(parsed, 9, joined) == 10, "wherever the model put it, the line it quoted whole wins"
    assert locate_evidence(parsed, 10, "setInterval(() => { rm -rf / }, 4000)") is None, "no whole diff line inside: invented"
    assert locate_evidence(parsed, 12, "rm -rf / }, 4000) return (") is None, "a bracket line inside the quote is not enough to place it"


def test_prose_that_mentions_a_short_attribute_is_not_a_quote_of_that_line():
    """Round three: a praise-shaped addition's evidence read "the change adds
    aria-live="polite" to the status region, which is the correct pattern", and
    the attribute sits whole on a diff line, so the line-inside-the-quote rule
    placed a sentence of prose. A line quoted whole must make up most of the
    quote, as the flattened carousel callback does and a mention does not."""
    patch = ("@@ -4,3 +4,4 @@\n"
             "   <main>\n"
             "+    <div role=\"status\" aria-live=\"polite\">\n"
             "     <p>Saved</p>\n"
             "   </main>\n")
    parsed = parse_patch(patch)
    prose = 'The change adds aria-live="polite" to the status region, which is the correct pattern for announcements.'
    assert locate_evidence(parsed, 5, prose) is None
    assert locate_evidence(parsed, 5, '<div role="status" aria-live="polite"> on the status region') == 5, "the line makes up most of the quote"
    carousel = parse_patch(_CAROUSEL)
    assert locate_evidence(carousel, 10, "setInterval(() => { setIndex((i) => (i + 1) % slides.length), 4000)") == 10


def test_a_quote_that_swaps_the_quote_marks_is_the_same_line():
    """Round three: qwen3.5:9b quoted `url = request.args['url']` for a line written
    with double quotes and missed the near-copy gate by five characters. The two
    quote marks mean the same line in every language this reviews."""
    patch = ("@@ -1,2 +1,4 @@\n"
             " import requests\n"
             "+url = request.args[\"url\"]\n"
             "+resp = requests.get(url)\n"
             " print(resp)\n")
    parsed = parse_patch(patch)
    assert locate_evidence(parsed, 2, "url = request.args['url']") == 2
    assert locate_evidence(parsed, 3, "url = request.args['url']") == 2, "and it is found from a wrong line number too"
