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
