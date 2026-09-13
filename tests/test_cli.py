import contextlib
import io
import pathlib
import tempfile
import unittest
import unittest.mock

from diffconv.cli import main

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def load(name):
    return (FIXTURES / name).read_text()


class CliTests(unittest.TestCase):
    def _run(self, argv, stdin_text=""):
        stdin = io.StringIO(stdin_text)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), unittest.mock.patch("sys.stdin", stdin):
            status = main(argv)
        return status, stdout.getvalue()

    def test_stdin_to_stdout_default_direction(self):
        status, out = self._run([], stdin_text=load("greeting.diff"))
        self.assertEqual(status, 0)
        self.assertEqual(out, load("greeting.ctx.diff"))

    def test_reverse_direction(self):
        status, out = self._run(
            ["--from", "context", "--to", "unified"], stdin_text=load("greeting.ctx.diff")
        )
        self.assertEqual(status, 0)
        self.assertEqual(out, load("greeting.diff"))

    def test_input_file_argument(self):
        status, out = self._run([str(FIXTURES / "greeting.diff")])
        self.assertEqual(status, 0)
        self.assertEqual(out, load("greeting.ctx.diff"))

    def test_output_file_argument(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = pathlib.Path(tmp) / "result.diff"
            status, out = self._run(
                [str(FIXTURES / "greeting.diff"), "-o", str(out_path)]
            )
            self.assertEqual(status, 0)
            self.assertEqual(out, "")
            self.assertEqual(out_path.read_text(), load("greeting.ctx.diff"))

    def test_empty_input_reports_error_and_nonzero_status(self):
        stdin = io.StringIO("not a diff at all\n")
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr), \
                unittest.mock.patch("sys.stdin", stdin):
            status = main([])
        self.assertEqual(status, 1)
        self.assertIn("no unified diff hunks found", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
