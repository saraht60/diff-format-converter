import argparse
import sys

from .convert import parse_context, parse_unified, render_context, render_unified

PARSERS = {"unified": parse_unified, "context": parse_context}
RENDERERS = {"unified": render_unified, "context": render_context}


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="diffconv",
        description="Convert between unified diff (diff -u / git diff) and context diff (diff -c) format.",
    )
    parser.add_argument("input", nargs="?", default="-", help="diff file to read, or - for stdin")
    parser.add_argument("-o", "--output", default="-", help="file to write, or - for stdout")
    parser.add_argument(
        "--from",
        dest="from_format",
        choices=["unified", "context"],
        default="unified",
        help="input format (default: unified)",
    )
    parser.add_argument(
        "--to",
        dest="to_format",
        choices=["unified", "context"],
        default="context",
        help="target format (default: context)",
    )
    args = parser.parse_args(argv)

    if args.input == "-":
        text = sys.stdin.read()
    else:
        with open(args.input, "r", encoding="utf-8") as handle:
            text = handle.read()

    files = PARSERS[args.from_format](text)
    if not files:
        print(f"no {args.from_format} diff hunks found in input", file=sys.stderr)
        return 1

    result = RENDERERS[args.to_format](files)

    if args.output == "-":
        sys.stdout.write(result)
    else:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(result)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
