import pathlib
import unittest

from diffconv.convert import (
    Hunk,
    parse_context,
    parse_unified,
    render_context,
    render_unified,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def load(name):
    return (FIXTURES / name).read_text()


class ParseUnifiedTests(unittest.TestCase):
    def test_basic_fields(self):
        files = parse_unified(load("greeting.diff"))
        self.assertEqual(len(files), 1)
        file_diff = files[0]
        self.assertEqual(file_diff.old_path, "a/greeting.py")
        self.assertEqual(file_diff.new_path, "b/greeting.py")
        self.assertEqual(len(file_diff.hunks), 1)
        hunk = file_diff.hunks[0]
        self.assertEqual((hunk.old_start, hunk.old_count), (1, 2))
        self.assertEqual((hunk.new_start, hunk.new_count), (1, 2))
        self.assertEqual(
            hunk.lines,
            [
                (" ", "def greet(name):", True),
                ("-", '    print("Hello " + name)', True),
                ("+", '    print(f"Hello, {name}!")', True),
            ],
        )

    def test_no_newline_marker_clears_newline_flag(self):
        files = parse_unified(load("no_newline.diff"))
        hunk = files[0].hunks[0]
        self.assertEqual(hunk.lines[1], ("-", "old last line", False))
        self.assertEqual(hunk.lines[2], ("+", "new last line", False))

    def test_rename_only_has_no_content(self):
        files = parse_unified(load("rename_only.diff"))
        self.assertEqual(len(files), 1)
        file_diff = files[0]
        self.assertFalse(file_diff.has_content)
        self.assertEqual(file_diff.hunks, [])
        self.assertEqual(
            file_diff.extended,
            [
                "diff --git a/old_name.py b/new_name.py",
                "similarity index 100%",
                "rename from old_name.py",
                "rename to new_name.py",
            ],
        )

    def test_malformed_hunk_header_raises(self):
        with self.assertRaises(ValueError):
            parse_unified("--- a/f\n+++ b/f\n@@ garbage @@\n")

    def test_truncated_hunk_raises(self):
        with self.assertRaises(ValueError):
            parse_unified("--- a/f\n+++ b/f\n@@ -1,2 +1,2 @@\n line\n")


class RenderContextTests(unittest.TestCase):
    def test_matches_fixture(self):
        files = parse_unified(load("greeting.diff"))
        self.assertEqual(render_context(files), load("greeting.ctx.diff"))

    def test_no_newline_matches_fixture(self):
        files = parse_unified(load("no_newline.diff"))
        self.assertEqual(render_context(files), load("no_newline.ctx.diff"))

    def test_pure_insertion_matches_fixture(self):
        files = parse_unified(load("insertion.diff"))
        self.assertEqual(render_context(files), load("insertion.ctx.diff"))

    def test_pure_deletion_matches_fixture(self):
        files = parse_unified(load("deletion.diff"))
        self.assertEqual(render_context(files), load("deletion.ctx.diff"))


class RenderUnifiedTests(unittest.TestCase):
    def test_matches_fixture(self):
        files = parse_context(load("greeting.ctx.diff"))
        self.assertEqual(render_unified(files), load("greeting.diff"))

    def test_no_newline_matches_fixture(self):
        files = parse_context(load("no_newline.ctx.diff"))
        self.assertEqual(render_unified(files), load("no_newline.diff"))

    def test_pure_insertion_matches_fixture(self):
        files = parse_context(load("insertion.ctx.diff"))
        self.assertEqual(render_unified(files), load("insertion.diff"))

    def test_pure_deletion_matches_fixture(self):
        files = parse_context(load("deletion.ctx.diff"))
        self.assertEqual(render_unified(files), load("deletion.diff"))

    def test_context_lines_out_of_alignment_raises(self):
        broken = (
            "*** a/f\n"
            "--- b/f\n"
            "***************\n"
            "*** 1,2 ****\n"
            "  same\n"
            "--- 1,2 ----\n"
            "  different\n"
        )
        with self.assertRaises(ValueError):
            parse_context(broken)


class RoundTripTests(unittest.TestCase):
    """unified -> context -> unified should reproduce the original text,
    since both formats describe the same edits."""

    def _assert_round_trips(self, fixture_name):
        original = load(fixture_name)
        as_context = render_context(parse_unified(original))
        back_to_unified = render_unified(parse_context(as_context))
        self.assertEqual(back_to_unified, original)

    def test_greeting(self):
        self._assert_round_trips("greeting.diff")

    def test_no_newline(self):
        self._assert_round_trips("no_newline.diff")

    def test_insertion(self):
        self._assert_round_trips("insertion.diff")

    def test_deletion(self):
        self._assert_round_trips("deletion.diff")

    def test_rename_only(self):
        self._assert_round_trips("rename_only.diff")

    def test_multi_file_multi_hunk(self):
        self._assert_round_trips("multi.diff")


class TagChangesTests(unittest.TestCase):
    def test_unequal_length_change_runs_are_all_tagged(self):
        # a two-line replacement by a single line should tag every line
        # in the run '!', not just the ones that have a counterpart.
        files = parse_unified(
            "--- a/f\n+++ b/f\n@@ -1,2 +1,1 @@\n-one\n-two\n+only\n"
        )
        rendered = render_context(files)
        self.assertIn("! one", rendered)
        self.assertIn("! two", rendered)
        self.assertIn("! only", rendered)


class FileDiffDefaultsTests(unittest.TestCase):
    def test_hunk_and_file_diff_default_lists_are_independent(self):
        # dataclass field(default_factory=list) should give each instance
        # its own list rather than sharing one across instances.
        hunk_a = Hunk(1, 1, 1, 1)
        hunk_b = Hunk(2, 1, 2, 1)
        hunk_a.lines.append((" ", "x", True))
        self.assertEqual(hunk_b.lines, [])


if __name__ == "__main__":
    unittest.main()
