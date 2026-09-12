"""services/git_diff.py against the exact bytes git prints.

Every fixture below was produced by git 2.50 in a throwaway repository with
the flags scripts/review_diff.py passes (a/ and b/ prefixes, three lines of
context, renames found) and pasted in verbatim, so the committed test needs
no git and no subprocess. The tab after a name on a `---` or `+++` line and
the octal escapes in a quoted name are part of the fixture, not decoration.
"""

from config.settings import settings
from services.diff import parse_patch
from services.git_diff import (
    _names_from_header,
    _strip_prefix,
    _unquote,
    file_from_section,
    split_git_diff,
    split_sections,
)
from services.review_runner import _skip_reason, select_files

# Nine files in one `git diff --cached`: a deletion, a path with a space, a mode-only
# change, a C-quoted non-ASCII path, an addition, a file that lost its trailing
# newline, a binary addition, a pure rename, and a modification with two hunks.
MULTI = (
    "diff --git a/gone.py b/gone.py\n"
    "deleted file mode 100644\n"
    "index 0e8388b..0000000\n"
    "--- a/gone.py\n"
    "+++ /dev/null\n"
    "@@ -1,2 +0,0 @@\n"
    "-gone_a\n"
    "-gone_b\n"
    "diff --git a/has space.py b/has space.py\n"
    "index de98044..502fdbb 100644\n"
    "--- a/has space.py\t\n"
    "+++ b/has space.py\t\n"
    "@@ -1,3 +1,3 @@\n"
    " a\n"
    "-b\n"
    "+BB\n"
    " c\n"
    "diff --git a/mode_only.sh b/mode_only.sh\n"
    "old mode 100644\n"
    "new mode 100755\n"
    r'diff --git "a/na\303\257ve.py" "b/na\303\257ve.py"' "\n"
    "index e8bac53..6b411ca 100644\n"
    r'--- "a/na\303\257ve.py"' "\n"
    r'+++ "b/na\303\257ve.py"' "\n"
    "@@ -1,3 +1,3 @@\n"
    " NA = 1\n"
    "-NB = 2\n"
    "+NB = 222\n"
    " NC = 3\n"
    "diff --git a/new_file.py b/new_file.py\n"
    "new file mode 100644\n"
    "index 0000000..1b0eaf6\n"
    "--- /dev/null\n"
    "+++ b/new_file.py\n"
    "@@ -0,0 +1,2 @@\n"
    "+def added():\n"
    '+    return "new"\n'
    "diff --git a/nonewline.py b/nonewline.py\n"
    "index 9ef165e..e4c74bf 100644\n"
    "--- a/nonewline.py\n"
    "+++ b/nonewline.py\n"
    "@@ -1,3 +1,3 @@\n"
    " tail1\n"
    " tail2\n"
    "-tail3\n"
    "+TAIL3\n"
    "\\ No newline at end of file\n"
    "diff --git a/pic.png b/pic.png\n"
    "new file mode 100644\n"
    "index 0000000..e5d1ed1\n"
    "Binary files /dev/null and b/pic.png differ\n"
    "diff --git a/pure_old.py b/pure_new.py\n"
    "similarity index 100%\n"
    "rename from pure_old.py\n"
    "rename to pure_new.py\n"
    "diff --git a/two_hunks.py b/two_hunks.py\n"
    "index 929f84e..55c51ba 100644\n"
    "--- a/two_hunks.py\n"
    "+++ b/two_hunks.py\n"
    "@@ -1,5 +1,5 @@\n"
    " line1\n"
    "-line2\n"
    "+CHANGED2\n"
    " line3\n"
    " line4\n"
    " line5\n"
    "@@ -10,5 +10,5 @@ line9\n"
    " line10\n"
    " line11\n"
    " line12\n"
    "-line13\n"
    "+CHANGED13\n"
    " line14\n"
)

# The nine filenames MULTI carries, in git's order.
MULTI_NAMES = ["gone.py", "has space.py", "mode_only.sh", "naïve.py", "new_file.py",
               "nonewline.py", "pic.png", "pure_new.py", "two_hunks.py"]

RENAME_WITH_HUNKS = (
    "diff --git a/handler_old.py b/handler_new.py\n"
    "similarity index 66%\n"
    "rename from handler_old.py\n"
    "rename to handler_new.py\n"
    "index b93cbf5..3ca86ce 100644\n"
    "--- a/handler_old.py\n"
    "+++ b/handler_new.py\n"
    "@@ -2,7 +2,7 @@ import os\n"
    " \n"
    " \n"
    " def alpha(a):\n"
    "-    return a + 1\n"
    "+    return a + 100\n"
    " \n"
    " \n"
    " def beta(b):\n"
    "@@ -10,4 +10,4 @@ def beta(b):\n"
    " \n"
    " \n"
    " def gamma(c):\n"
    "-    return c - 3\n"
    "+    return c - 300\n"
)

# `git show` of the commit that made the rename above: a commit line, an author,
# a date and the indented subject before the first section.
SHOW_PREAMBLE = (
    "commit c9a42d60d0a4d8515c51bae009c9f088c5441c19\n"
    "Author: t <t@example.com>\n"
    "Date:   Sat Sep 12 03:44:04 2026 +0100\n"
    "\n"
    "    Rename the handler and bump two constants\n"
    "\n"
) + RENAME_WITH_HUNKS

# A file whose added line is itself a `diff --git` line.
QUOTED_MARKER = (
    "diff --git a/quoted_marker.py b/quoted_marker.py\n"
    "index 59d6fb5..bd78cea 100644\n"
    "--- a/quoted_marker.py\n"
    "+++ b/quoted_marker.py\n"
    "@@ -1,3 +1,4 @@\n"
    " x = 1\n"
    "+diff --git a/x b/x\n"
    " y = 2\n"
    " z = 3\n"
)

# A path holding one literal backslash, which git doubles inside the quotes.
BACKSLASH_DIFF = (
    r'diff --git "a/we\\ird.py" "b/we\\ird.py"' "\n"
    "index 098cfab..2651e89 100644\n"
    r'--- "a/we\\ird.py"' "\n"
    r'+++ "b/we\\ird.py"' "\n"
    "@@ -1 +1 @@\n"
    "-q = 1\n"
    "+q = 2\n"
)

OCTAL_QUOTED_NAME = r'"a/na\303\257ve.py"'
BACKSLASH_QUOTED_NAME = r'"a/we\\ird.py"'

KEYS = {"filename", "status", "patch", "additions", "deletions", "previous_filename"}


def _by_name(files):
    return {f["filename"]: f for f in files}


def test_a_multi_file_git_diff_becomes_one_github_shaped_dict_per_section_in_order():
    files = split_git_diff(MULTI)
    assert [f["filename"] for f in files] == MULTI_NAMES
    assert all(set(f) == KEYS for f in files)
    assert [f["status"] for f in files] == ["removed", "modified", "modified", "modified", "added",
                                            "modified", "added", "renamed", "modified"]
    assert [f["previous_filename"] for f in files] == ["", "", "", "", "", "", "", "pure_old.py", ""]
    assert [(f["additions"], f["deletions"]) for f in files] == [(0, 2), (1, 1), (0, 0), (1, 1), (2, 0),
                                                                (1, 1), (0, 0), (0, 0), (2, 2)]


def test_every_split_patch_starts_at_a_hunk_header_so_parse_patch_numbers_it_the_way_github_does():
    """services/diff.py never resets its in_hunk flag, so one header line reaching
    a patch would number every line after it wrongly."""
    files = _by_name(split_git_diff(MULTI))
    for f in files.values():
        if f["patch"]:
            assert f["patch"].startswith("@@ ")
        for header in ("+++", "diff --git", "index "):
            assert header not in f["patch"], f["filename"]

    two = parse_patch(files["two_hunks.py"]["patch"])
    assert two.hunks == 2
    assert two.new_lines == {1: "line1", 2: "CHANGED2", 3: "line3", 4: "line4", 5: "line5",
                             10: "line10", 11: "line11", 12: "line12", 13: "CHANGED13", 14: "line14"}
    assert two.added_lines == {2: "CHANGED2", 13: "CHANGED13"}

    new = parse_patch(files["new_file.py"]["patch"])
    assert new.new_lines == {1: "def added():", 2: '    return "new"'}
    assert new.added_lines == {1: "def added():", 2: '    return "new"'}

    spaced = parse_patch(files["has space.py"]["patch"])
    assert spaced.new_lines == {1: "a", 2: "BB", 3: "c"}
    assert spaced.added_lines == {2: "BB"}

    accented = parse_patch(files["naïve.py"]["patch"])
    assert accented.new_lines == {1: "NA = 1", 2: "NB = 222", 3: "NC = 3"}
    assert accented.added_lines == {2: "NB = 222"}


def test_the_file_header_of_the_next_section_never_reaches_the_patch_of_the_one_before_it():
    files = _by_name(split_git_diff(MULTI))
    assert files["gone.py"]["patch"] == "@@ -1,2 +0,0 @@\n-gone_a\n-gone_b"
    assert files["two_hunks.py"]["patch"].endswith(" line14")
    assert files["nonewline.py"]["patch"].endswith("\\ No newline at end of file")
    for f in files.values():
        assert "has space" not in f["patch"] or f["filename"] == "has space.py"
        assert "new file mode" not in f["patch"]
        assert "Binary files" not in f["patch"]
    # and the boundary is the header line itself, not a line inside the body
    sections = split_sections(MULTI)
    assert len(sections) == 9
    assert all(s.startswith("diff --git ") for s in sections)
    assert all(s.count("diff --git ") == 1 for s in sections)


def test_a_new_file_is_added_and_a_deleted_file_is_removed():
    files = _by_name(split_git_diff(MULTI))
    added, removed = files["new_file.py"], files["gone.py"]
    assert added["status"] == "added" and added["additions"] == 2 and added["deletions"] == 0
    assert added["patch"] == '@@ -0,0 +1,2 @@\n+def added():\n+    return "new"'
    assert removed["status"] == "removed"
    assert removed["patch"].splitlines()[1:] == ["-gone_a", "-gone_b"]
    assert removed["additions"] == 0 and removed["deletions"] == 2


def test_a_rename_with_no_hunks_carries_its_previous_filename_and_an_empty_patch():
    pure = _by_name(split_git_diff(MULTI))["pure_new.py"]
    assert pure == {"filename": "pure_new.py", "status": "renamed", "patch": "",
                    "additions": 0, "deletions": 0, "previous_filename": "pure_old.py"}


def test_a_rename_with_hunks_keeps_the_new_name_the_previous_name_and_the_hunks():
    files = split_git_diff(RENAME_WITH_HUNKS)
    assert len(files) == 1
    f = files[0]
    assert f["filename"] == "handler_new.py"
    assert f["previous_filename"] == "handler_old.py"
    assert f["status"] == "renamed"
    assert f["additions"] == 2 and f["deletions"] == 2
    parsed = parse_patch(f["patch"])
    assert parsed.hunks == 2
    assert parsed.added_lines == {5: "    return a + 100", 13: "    return c - 300"}
    assert "rename from" not in f["patch"] and "similarity index" not in f["patch"]


def test_a_binary_file_and_a_mode_only_change_have_no_patch_and_the_runner_skips_them():
    files = _by_name(split_git_diff(MULTI))
    binary, mode_only = files["pic.png"], files["mode_only.sh"]
    assert binary["patch"] == "" and mode_only["patch"] == ""
    assert binary["status"] == "added" and mode_only["status"] == "modified"

    no_text = "no text diff available (binary or too large for GitHub)"
    assert _skip_reason(binary, settings) == no_text
    assert _skip_reason(mode_only, settings) == no_text
    selected, skipped = select_files([binary, mode_only], settings)
    assert selected == []
    assert skipped == [("pic.png", no_text), ("mode_only.sh", no_text)]


def test_the_no_newline_at_end_of_file_marker_does_not_shift_a_line_number():
    f = _by_name(split_git_diff(MULTI))["nonewline.py"]
    parsed = parse_patch(f["patch"])
    assert parsed.new_lines == {1: "tail1", 2: "tail2", 3: "TAIL3"}
    assert parsed.added_lines == {3: "TAIL3"}
    assert 4 not in parsed.new_lines
    assert f["additions"] == 1 and f["deletions"] == 1


def test_a_path_with_an_unquoted_space_keeps_its_whole_name_from_the_header_lines():
    assert _strip_prefix("a/has space.py\t") == "has space.py"
    assert _strip_prefix("b/has space.py\t") == "has space.py"
    assert _names_from_header("diff --git a/has space.py b/has space.py") == ("has space.py", "has space.py")
    f = _by_name(split_git_diff(MULTI))["has space.py"]
    assert f["status"] == "modified" and f["patch"].startswith("@@ -1,3 +1,3 @@")


def test_a_quoted_path_is_unquoted_and_loses_only_its_a_or_b_prefix():
    assert _unquote(OCTAL_QUOTED_NAME) == "a/naïve.py"
    assert _unquote(BACKSLASH_QUOTED_NAME) == "a/we\\ird.py"
    assert _strip_prefix(OCTAL_QUOTED_NAME) == "naïve.py"
    assert _strip_prefix(BACKSLASH_QUOTED_NAME) == "we\\ird.py"
    assert _names_from_header(r'diff --git "a/na\303\257ve.py" "b/na\303\257ve.py"') == ("naïve.py", "naïve.py")

    octal = _by_name(split_git_diff(MULTI))["naïve.py"]
    assert octal["filename"] == "naïve.py" and octal["additions"] == 1
    backslash = split_git_diff(BACKSLASH_DIFF)
    assert [f["filename"] for f in backslash] == ["we\\ird.py"]
    assert backslash[0]["patch"] == "@@ -1 +1 @@\n-q = 1\n+q = 2"


def test_additions_and_deletions_are_counted_only_inside_hunks():
    files = _by_name(split_git_diff(MULTI))
    spaced = files["has space.py"]
    # a naive count over the whole section reads `+++ b/has space.py` as an added line
    section = [s for s in split_sections(MULTI) if "has space" in s][0]
    assert sum(1 for line in section.split("\n") if line.startswith("+")) == 2
    assert spaced["additions"] == 1 and spaced["deletions"] == 1
    assert (files["pure_new.py"]["additions"], files["pure_new.py"]["deletions"]) == (0, 0)
    assert (files["pic.png"]["additions"], files["pic.png"]["deletions"]) == (0, 0)
    assert (files["mode_only.sh"]["additions"], files["mode_only.sh"]["deletions"]) == (0, 0)


def test_text_before_the_first_section_is_dropped():
    files = split_git_diff(SHOW_PREAMBLE)
    assert len(files) == 1
    assert files[0] == split_git_diff(RENAME_WITH_HUNKS)[0]
    for dropped in ("commit c9a42d6", "Author:", "Date:", "Rename the handler"):
        assert dropped not in files[0]["patch"]


def test_a_diff_marker_quoted_inside_a_hunk_does_not_open_a_new_section():
    files = split_git_diff(QUOTED_MARKER)
    assert len(files) == 1
    f = files[0]
    assert f["filename"] == "quoted_marker.py" and f["additions"] == 1 and f["deletions"] == 0
    parsed = parse_patch(f["patch"])
    assert parsed.added_lines == {2: "diff --git a/x b/x"}
    assert parsed.new_lines == {1: "x = 1", 2: "diff --git a/x b/x", 3: "y = 2", 4: "z = 3"}


def test_an_empty_string_splits_into_no_files():
    assert split_sections("") == []
    assert split_git_diff("") == []
    assert split_git_diff("\n\n") == []
    assert file_from_section("") == {"filename": "", "status": "modified", "patch": "",
                                     "additions": 0, "deletions": 0, "previous_filename": ""}


def test_a_non_ascii_path_printed_raw_under_quotepath_off_is_kept_as_it_is():
    """The command passes -c core.quotepath=false, so an accented name arrives
    as raw UTF-8 without quotes; the quoted octal form is what a user's own
    git diff prints under the default quotepath."""
    raw = ("diff --git a/naïve.py b/naïve.py\nindex 587be6b..975fbec 100644\n--- a/naïve.py\n+++ b/naïve.py\n"
           "@@ -1 +1 @@\n-x\n+y\n")
    files = split_git_diff(raw)
    assert [f["filename"] for f in files] == ["naïve.py"]
    assert files[0]["patch"] == "@@ -1 +1 @@\n-x\n+y"


def test_a_combined_diff_section_is_named_and_carries_no_patch():
    combined = ("diff --cc app.py\nindex 1111111,2222222..3333333\n--- a/app.py\n+++ b/app.py\n"
                "@@@ -1,2 -1,2 +1,3 @@@\n  import os\n +eval(x)\n  def main():\n")
    text = "diff --git a/other.py b/other.py\nindex 1..2 100644\n--- a/other.py\n+++ b/other.py\n@@ -1 +1 @@\n-a\n+b\n" + combined
    files = split_git_diff(text)
    assert [(f["filename"], f["status"]) for f in files] == [("other.py", "modified"), ("app.py", "combined")]
    assert files[0]["patch"] == "@@ -1 +1 @@\n-a\n+b", "the combined section never leaks into the section before it"
    assert files[1]["patch"] == "" and files[1]["additions"] == 0

