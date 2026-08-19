"""Parse unified diffs and render them as POSIX context diffs.

Unified diff (what `git diff` and `diff -u` produce) and context diff
(`diff -c`) describe the same edits, just laid out differently: unified
interleaves added/removed lines in one block per hunk, context splits each
hunk into a "before" block and an "after" block and marks lines that were
replaced (rather than purely added or removed) with `!`.
"""

from dataclasses import dataclass, field
import re

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


@dataclass
class Hunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    # each entry is (kind, text) where kind is ' ' (context), '-' (removed)
    # or '+' (added), in the order they appear in the unified hunk body.
    lines: list = field(default_factory=list)


@dataclass
class FileDiff:
    old_path: str
    old_label: str
    new_path: str
    new_label: str
    hunks: list = field(default_factory=list)


def _split_header(rest):
    # unified headers look like "a/file.py" or "a/file.py\t<timestamp>".
    # keep the tab so we can put the label back exactly as it was.
    if "\t" in rest:
        path, label = rest.split("\t", 1)
        return path, "\t" + label
    return rest, ""


def parse_unified(text):
    """Parse unified diff text into a list of FileDiff objects."""
    lines = text.splitlines()
    n = len(lines)
    files = []
    i = 0
    while i < n:
        line = lines[i]
        if line.startswith("--- ") and i + 1 < n and lines[i + 1].startswith("+++ "):
            old_path, old_label = _split_header(line[4:])
            new_path, new_label = _split_header(lines[i + 1][4:])
            i += 2
            hunks = []
            while i < n and lines[i].startswith("@@ "):
                match = HUNK_RE.match(lines[i])
                if not match:
                    raise ValueError(f"malformed hunk header: {lines[i]!r}")
                old_start = int(match.group(1))
                old_count = int(match.group(2)) if match.group(2) is not None else 1
                new_start = int(match.group(3))
                new_count = int(match.group(4)) if match.group(4) is not None else 1
                i += 1

                body = []
                remaining_old, remaining_new = old_count, new_count
                # read by counting consumed old/new lines rather than by
                # sniffing prefixes, since a removed line can itself start
                # with "--- " and would otherwise look like a file header.
                while remaining_old > 0 or remaining_new > 0:
                    if i >= n:
                        raise ValueError("unified diff hunk ended before its line counts were satisfied")
                    raw = lines[i]
                    if raw.startswith("\\"):
                        # "\ No newline at end of file" - not a content line
                        i += 1
                        continue
                    kind = raw[0] if raw else " "
                    text_ = raw[1:] if raw else ""
                    if kind == " ":
                        remaining_old -= 1
                        remaining_new -= 1
                    elif kind == "-":
                        remaining_old -= 1
                    elif kind == "+":
                        remaining_new -= 1
                    else:
                        raise ValueError(f"unexpected line in hunk body: {raw!r}")
                    body.append((kind, text_))
                    i += 1

                hunks.append(Hunk(old_start, old_count, new_start, new_count, body))
            files.append(FileDiff(old_path, old_label, new_path, new_label, hunks))
        else:
            i += 1
    return files


def _tag_changes(lines):
    """Mark contiguous remove-then-add runs as '!' (a replacement).

    Context diff shows a block of lines that were swapped for other lines
    with '!' on both sides, rather than as an unpaired delete plus insert.
    """
    tags = [kind if kind in ("-", "+") else " " for kind, _ in lines]
    i, n = 0, len(lines)
    while i < n:
        if lines[i][0] == "-":
            j = i
            while j < n and lines[j][0] == "-":
                j += 1
            k = j
            while k < n and lines[k][0] == "+":
                k += 1
            if k > j:
                for idx in range(i, k):
                    tags[idx] = "!"
            i = k
        else:
            i += 1
    return tags


def _format_range(start, count):
    if count == 0:
        # an empty range is shown straddling the insertion point
        return f"{start},{start - 1}"
    if count == 1:
        return str(start)
    return f"{start},{start + count - 1}"


def render_context(files):
    """Render FileDiff objects as context diff text."""
    out = []
    for file_diff in files:
        out.append(f"*** {file_diff.old_path}{file_diff.old_label}")
        out.append(f"--- {file_diff.new_path}{file_diff.new_label}")
        for hunk in file_diff.hunks:
            out.append("***************")
            tags = _tag_changes(hunk.lines)

            out.append(f"*** {_format_range(hunk.old_start, hunk.old_count)} ****")
            for (kind, text_), tag in zip(hunk.lines, tags):
                if kind in (" ", "-"):
                    prefix = "  " if tag == " " else ("! " if tag == "!" else "- ")
                    out.append(prefix + text_)

            out.append(f"--- {_format_range(hunk.new_start, hunk.new_count)} ----")
            for (kind, text_), tag in zip(hunk.lines, tags):
                if kind in (" ", "+"):
                    prefix = "  " if tag == " " else ("! " if tag == "!" else "+ ")
                    out.append(prefix + text_)
    return "\n".join(out) + "\n"
