"""The arithmetic and the listing: which shape the file is sent in, what the
block looks like, and what is refused before it can reach a prompt."""

import base64
import re
from pathlib import Path

import pytest

from config.settings import settings
from services import file_context

MARKER = "<<<DIFF_DATA_FILE_deadbeefdeadbeef>>>"
# two hunks, about forty lines apart, against whatever file the test builds
PATCH = ("@@ -20,4 +20,5 @@ def one():\n"
         "     a = 1\n"
         "     b = 2\n"
         "+    c = 3\n"
         "     return a\n"
         "@@ -60,3 +61,4 @@ def two():\n"
         "     d = 4\n"
         "+    e = 5\n"
         "     return d\n")


def _file(lines: int, width: int = 20) -> str:
    return "".join(f"line {i:04d} " + "x" * width + "\n" for i in range(1, lines + 1))


def _at(num_ctx: int, window: int = 60):
    return settings.model_copy(update={"OLLAMA_NUM_CTX": num_ctx, "OLLAMA_NUM_PREDICT": 2000,
                                       "FILE_CONTEXT": True, "FILE_CONTEXT_LINES": window})


def test_a_whole_file_that_fits_the_context_left_after_the_patch_is_sent_whole():
    rendered = file_context.render(_file(120), PATCH, _at(16384), MARKER)
    assert rendered.mode == "whole" and rendered.spans == [(1, 120)]
    assert rendered.block.count(MARKER) == 1
    assert "the whole file at this commit, 120 lines" in rendered.block
    assert "line 0001" in rendered.block and "line 0120" in rendered.block


def test_a_file_too_big_for_the_remaining_context_becomes_the_parts_around_each_hunk():
    rendered = file_context.render(_file(3000), PATCH, _at(16384), MARKER)
    assert rendered.mode == "window"
    assert rendered.spans == [(1, 124)], "the two hunks are within one merged window of each other"
    assert rendered.block.count(MARKER) == len(rendered.spans)
    assert "lines 1 to 124 of 3000" in rendered.block
    assert "line 0300" not in rendered.block


def test_two_hunks_further_apart_than_the_window_are_two_spans():
    rendered = file_context.render(_file(3000), PATCH, _at(16384, window=5), MARKER)
    assert rendered.mode == "window" and rendered.spans == [(15, 29), (56, 69)]
    assert rendered.block.count(MARKER) == 2


def test_a_file_too_big_even_for_one_window_leaves_the_patch_to_stand_alone():
    # a 30 KB patch leaves about 6 KB, and this file's lines are 400 bytes wide, so even the
    # narrowest merged window is larger than what is left
    fat = "@@ -1,1 +1,2 @@\n a\n+" + "z" * 30_000 + "\n"
    rendered = file_context.render(_file(3000, width=400), fat, _at(16384), MARKER)
    assert rendered.mode == "none" and rendered.block == "" and rendered.spans == []


def test_every_span_says_which_lines_of_the_file_it_is_and_how_many_the_file_has():
    rendered = file_context.render(_file(3000), PATCH, _at(16384, window=5), MARKER)
    labels = [line for line in rendered.block.split("\n") if line.startswith(MARKER)]
    assert labels == [f"{MARKER} lines 15 to 29 of 3000", f"{MARKER} lines 56 to 69 of 3000"]


def test_no_line_of_the_listing_carries_a_number_or_a_change_marker_a_file_could_forge():
    rendered = file_context.render(_file(120), PATCH, _at(16384), MARKER)
    body = [line for line in rendered.block.split("\n") if line and not line.startswith(MARKER)]
    assert body, "the listing must hold the file's own lines"
    assert not any(re.match(r"^\s*\d+\s*[|:]", line) for line in body), "no per-line number"
    assert not any(line.startswith(("+", "-")) for line in body), "no change markers"
    assert all(line.startswith("line ") for line in body), "the file's lines, verbatim"


@pytest.mark.parametrize("num_ctx", [16384, 32768])
def test_the_rendered_block_plus_the_patch_stays_inside_the_budget(num_ctx):
    at = _at(num_ctx)
    for lines in (50, 500, 5000, 40_000):
        rendered = file_context.render(_file(lines), PATCH, at, MARKER)
        total = len(rendered.block.encode("utf-8")) + len(PATCH.encode("utf-8"))
        assert total <= file_context.budget_bytes(at), (num_ctx, lines, rendered.mode)


def test_the_budget_is_the_window_less_the_reply_and_the_prompt_overhead():
    assert file_context.budget_bytes(_at(16384)) == 36355
    assert file_context.budget_bytes(_at(32768)) == 82230


def test_a_file_this_pull_request_added_is_not_sent_a_second_time_beside_its_own_diff():
    added = "@@ -0,0 +1,3 @@\n+one\n+two\n+three\n"
    rendered = file_context.render("one\ntwo\nthree\n", added, _at(16384), MARKER)
    assert rendered.mode == "none" and rendered.block == ""


def test_an_empty_file_and_a_patch_with_no_room_both_yield_nothing():
    assert file_context.render("", PATCH, _at(16384), MARKER).mode == "none"
    assert file_context.render("   \n\n", PATCH, _at(16384), MARKER).mode == "none"
    assert file_context.render(_file(50), PATCH, _at(2048), MARKER).mode == "none"


def test_a_binary_file_a_file_that_is_not_utf_8_and_a_file_over_the_size_limit_yield_no_context():
    assert file_context.decode(base64.b64encode(b"print('hi')\n").decode()) == "print('hi')\n"
    assert file_context.decode(base64.b64encode(b"\x89PNG\x00\x1a").decode()) is None
    assert file_context.decode(base64.b64encode(b"caf\xe9 latte").decode()) is None
    assert file_context.decode(base64.b64encode(b"x" * (file_context.MAX_FILE_BYTES + 1)).decode()) is None
    assert file_context.decode("not base64 at all !!!") is None
    assert file_context.decode("") is None


def test_the_size_gate_still_reads_the_patch_alone():
    """The gate is the old _fits_context, moved and not changed: a file whose
    patch leaves no room simply gets no context, so skip counts cannot move."""
    small = "@@ -1,1 +1,2 @@\n a\n+b\n"
    assert file_context.fits_context(small, _at(16384))
    assert not file_context.fits_context("@@ -1,1 +1,2 @@\n a\n+" + "z" * 40_000 + "\n", _at(16384))


def test_the_overhead_script_still_finds_the_two_constants_where_they_now_live():
    """scripts/prompt_overhead.py reads them out of a file's source text, so a
    move with the regex left pointing at the old module dies on .group of None."""
    source = Path(__file__).resolve().parents[1] / "scripts" / "prompt_overhead.py"
    text = source.read_text(encoding="utf-8")
    assert 'services" / "file_context.py"' in text
    assert "review_runner" not in text, "the script must not read the runner any more"
    import sys
    sys.path.insert(0, str(source.parent))
    import prompt_overhead

    assert prompt_overhead.BYTES_PER_TOKEN == file_context.BYTES_PER_TOKEN
    assert prompt_overhead.PROMPT_OVERHEAD_TOKENS == file_context.PROMPT_OVERHEAD_TOKENS


def test_windows_touching_each_other_are_merged_into_one_span():
    assert file_context.spans([(10, 12), (14, 16)], 100, 1) == [(9, 17)]
    assert file_context.spans([(10, 12), (40, 41)], 100, 2) == [(8, 14), (38, 43)]
    assert file_context.spans([(1, 3)], 2, 5) == [(1, 2)], "a span never runs past the end of the file"
    assert file_context.spans([(500, 501)], 100, 5) == [], "a hunk past the end of the file is not a span"
