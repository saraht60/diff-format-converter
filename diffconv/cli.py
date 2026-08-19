import argparse
import sys

from .convert import parse_unified, render_context


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="diffconv",
        description="Convert a unified diff (diff -u / git diff) into context diff (diff -c) format.",
    )
    parser.add_argument("input", nargs="?", default="-", help="unified diff file to read, or - for stdin")
    parser.add_argument("-o", "--output", default="-", help="file to write, or - for stdout")
    parser.add_argument(
        "--to",
        choices=["context"],
        default="context",
        help="target format (only 'context' is implemented so far)",
    )
    args = parser.parse_args(argv)

    if args.input == "-":
        text = sys.stdin.read()
    else:
        with open(args.input, "r", encoding="utf-8") as handle:
            text = handle.read()

    files = parse_unified(text)
    if not files:
        print("no unified diff hunks found in input", file=sys.stderr)
        return 1

    result = render_context(files)

    if args.output == "-":
        sys.stdout.write(result)
    else:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(result)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
