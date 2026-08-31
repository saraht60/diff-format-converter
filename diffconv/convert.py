"""Convert between unified diffs and POSIX context diffs.

Unified diff (what `git diff` and `diff -u` produce) and context diff
(`diff -c`) describe the same edits, just laid out differently: unified
interleaves added/removed lines in one block per hunk, context splits each
hunk into a "before" block and an "after" block and marks lines that were
replaced (rather than purely added or removed) with `!`.
"""

from dataclasses import dataclass, field
import re

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
DIFF_GIT_RE = re.compile(r"^diff --git a/(.*) b/(.*)$")
NO_NEWLINE_MARKER = "\\ No newline at end of file"


@dataclass
class Hunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    # each entry is (kind, text, has_newline) where kind is ' ' (context),
    # '-' (removed) or '+' (added), in the order they appear in the unified
    # hunk body. has_newline is False for a line immediately followed by
    # "\ No newline at end of file" in the source diff.
    lines: list = field(default_factory=list)


@dataclass
class FileDiff:
    old_path: str
    old_label: str
    new_path: str
    new_label: str
    hunks: list = field(default_factory=list)
    # raw lines from a git "diff --git" extended header block (renames,
    # mode changes, index lines, binary file notices) that preceded the
    # file's "---"/"+++" or "***"/"---" header in the source diff.
    extended: list = field(default_factory=list)
    # False for a git extended-header entry with no "---"/"+++" section at
    # all - a pure rename, mode change, or binary file notice. render_unified
    # uses this to skip re-adding a header git never wrote in the first place.
    has_content: bool = True


def _split_header(rest):
    # unified headers look like "a/file.py" or "a/file.py\t<timestamp>".
    # keep the tab so we can put the label back exactly as it was.
    if "\t" in rest:
        path, label = rest.split("\t", 1)
        return path, "\t" + label
    return rest, ""


def _parse_unified_hunks(lines, i, n):
    """Parse consecutive "@@ ... @@" hunks starting at lines[i]."""
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
                # "\ No newline at end of file" applies to the line
                # that was just appended, not a content line itself.
                if body and raw == NO_NEWLINE_MARKER:
                    kind, text_, _ = body[-1]
                    body[-1] = (kind, text_, False)
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
            body.append((kind, text_, True))
            i += 1

        hunks.append(Hunk(old_start, old_count, new_start, new_count, body))
    return hunks, i


def parse_unified(text):
    """Parse unified diff text into a list of FileDiff objects."""
    lines = text.splitlines()
    n = len(lines)
    files = []
    i = 0
    while i < n:
        line = lines[i]
        git_match = DIFF_GIT_RE.match(line)
        if git_match:
            extended = [line]
            i += 1
            while i < n and not lines[i].startswith("--- ") and not DIFF_GIT_RE.match(lines[i]):
                extended.append(lines[i])
                i += 1
            if i < n and lines[i].startswith("--- ") and i + 1 < n and lines[i + 1].startswith("+++ "):
                old_path, old_label = _split_header(lines[i][4:])
                new_path, new_label = _split_header(lines[i + 1][4:])
                i += 2
                hunks, i = _parse_unified_hunks(lines, i, n)
                files.append(FileDiff(old_path, old_label, new_path, new_label, hunks, extended, True))
            else:
                # extended-header-only entry: a rename, mode change, or
                # binary file notice with no "---"/"+++" section at all.
                old_git, new_git = git_match.group(1), git_match.group(2)
                files.append(FileDiff(f"a/{old_git}", "", f"b/{new_git}", "", [], extended, False))
        elif line.startswith("--- ") and i + 1 < n and lines[i + 1].startswith("+++ "):
            old_path, old_label = _split_header(line[4:])
            new_path, new_label = _split_header(lines[i + 1][4:])
            i += 2
            hunks, i = _parse_unified_hunks(lines, i, n)
            files.append(FileDiff(old_path, old_label, new_path, new_label, hunks))
        else:
            i += 1
    return files


def _tag_changes(lines):
    """Mark contiguous remove-then-add runs as '!' (a replacement).

    Context diff shows a block of lines that were swapped for other lines
    with '!' on both sides, rather than as an unpaired delete plus insert.
    """
    tags = [kind if kind in ("-", "+") else " " for kind, _, _ in lines]
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
        out.extend(file_diff.extended)
        out.append(f"*** {file_diff.old_path}{file_diff.old_label}")
        out.append(f"--- {file_diff.new_path}{file_diff.new_label}")
        for hunk in file_diff.hunks:
            out.append("***************")
            tags = _tag_changes(hunk.lines)

            out.append(f"*** {_format_range(hunk.old_start, hunk.old_count)} ****")
            for (kind, text_, newline), tag in zip(hunk.lines, tags):
                if kind in (" ", "-"):
                    prefix = "  " if tag == " " else ("! " if tag == "!" else "- ")
                    out.append(prefix + text_)
                    if not newline:
                        out.append(NO_NEWLINE_MARKER)

            out.append(f"--- {_format_range(hunk.new_start, hunk.new_count)} ----")
            for (kind, text_, newline), tag in zip(hunk.lines, tags):
                if kind in (" ", "+"):
                    prefix = "  " if tag == " " else ("! " if tag == "!" else "+ ")
                    out.append(prefix + text_)
                    if not newline:
                        out.append(NO_NEWLINE_MARKER)
    return "\n".join(out) + "\n"


def _parse_hunk_range(line, prefix, suffix):
    body = line[len(prefix):len(line) - len(suffix)]
    try:
        if "," in body:
            start_s, end_s = body.split(",", 1)
            start, end = int(start_s), int(end_s)
        else:
            start = end = int(body)
    except ValueError:
        raise ValueError(f"malformed context hunk range: {line!r}") from None
    # end < start (e.g. "3,2") is how render_context marks a pure insertion
    # or deletion point - see _format_range - so the count comes out as 0.
    return start, end - start + 1


def _read_marked_lines(lines, i, n, tags):
    # a context diff line is a one-character tag plus a space, then content;
    # matching on that fixed prefix is what lets us stop at the first line
    # that belongs to the next section rather than to this block.
    prefixes = tuple(tag + " " for tag in tags)
    result = []
    while i < n and lines[i].startswith(prefixes):
        result.append([lines[i][0], lines[i][2:], True])
        i += 1
        if i < n and lines[i] == NO_NEWLINE_MARKER:
            result[-1][2] = False
            i += 1
    return [tuple(entry) for entry in result], i


def _merge_context_lines(before_lines, after_lines):
    """Interleave a context hunk's before/after blocks into unified order.

    Context diff lists the old file's lines (tagged ' ', '-', '!') and the
    new file's lines (tagged ' ', '+', '!') as two separate blocks. Unified
    diff wants them as one stream, so we walk both blocks together: shared
    context lines advance both pointers in lock step, and each run of
    changed lines contributes its removals before its additions, mirroring
    how _tag_changes builds '!' runs from a '-' run followed by a '+' run.
    """
    body = []
    bi, ai = 0, 0
    bn, an = len(before_lines), len(after_lines)
    while bi < bn or ai < an:
        before_tag = before_lines[bi][0] if bi < bn else None
        after_tag = after_lines[ai][0] if ai < an else None
        if before_tag == " " or after_tag == " ":
            if before_tag != " " or after_tag != " " or before_lines[bi][1] != after_lines[ai][1]:
                raise ValueError("context lines do not align between before and after blocks")
            body.append((" ", before_lines[bi][1], before_lines[bi][2]))
            bi += 1
            ai += 1
            continue
        advanced = False
        while bi < bn and before_lines[bi][0] in ("-", "!"):
            body.append(("-", before_lines[bi][1], before_lines[bi][2]))
            bi += 1
            advanced = True
        while ai < an and after_lines[ai][0] in ("+", "!"):
            body.append(("+", after_lines[ai][1], after_lines[ai][2]))
            ai += 1
            advanced = True
        if not advanced:
            raise ValueError("malformed context diff hunk: could not align before/after blocks")
    return body


def parse_context(text):
    """Parse context diff text into a list of FileDiff objects."""
    lines = text.splitlines()
    n = len(lines)
    files = []
    i = 0
    while i < n:
        git_match = DIFF_GIT_RE.match(lines[i])
        if git_match:
            extended = [lines[i]]
            i += 1
            while i < n and not lines[i].startswith("*** "):
                extended.append(lines[i])
                i += 1
        else:
            extended = []

        if i < n and lines[i].startswith("*** ") and i + 1 < n and lines[i + 1].startswith("--- "):
            old_path, old_label = _split_header(lines[i][4:])
            new_path, new_label = _split_header(lines[i + 1][4:])
            i += 2
            hunks = []
            while i < n and lines[i].startswith("***************"):
                i += 1
                if i >= n or not (lines[i].startswith("*** ") and lines[i].endswith(" ****")):
                    raise ValueError(f"expected old-range header, got: {lines[i] if i < n else ''!r}")
                old_start, old_count = _parse_hunk_range(lines[i], "*** ", " ****")
                i += 1
                before_lines, i = _read_marked_lines(lines, i, n, (" ", "-", "!"))

                if i >= n or not (lines[i].startswith("--- ") and lines[i].endswith(" ----")):
                    raise ValueError(f"expected new-range header, got: {lines[i] if i < n else ''!r}")
                new_start, new_count = _parse_hunk_range(lines[i], "--- ", " ----")
                i += 1
                after_lines, i = _read_marked_lines(lines, i, n, (" ", "+", "!"))

                body = _merge_context_lines(before_lines, after_lines)
                hunks.append(Hunk(old_start, old_count, new_start, new_count, body))
            # an extended header with no hunks means the source unified diff
            # had no "---"/"+++" section either (a pure rename, mode change,
            # or binary file notice) - see parse_unified.
            has_content = bool(hunks) or not extended
            files.append(FileDiff(old_path, old_label, new_path, new_label, hunks, extended, has_content))
        else:
            i += 1
    return files


def _format_unified_range(start, count):
    if count == 1:
        return str(start)
    return f"{start},{count}"


def render_unified(files):
    """Render FileDiff objects as unified diff text."""
    out = []
    for file_diff in files:
        out.extend(file_diff.extended)
        if file_diff.has_content:
            out.append(f"--- {file_diff.old_path}{file_diff.old_label}")
            out.append(f"+++ {file_diff.new_path}{file_diff.new_label}")
            for hunk in file_diff.hunks:
                old_range = _format_unified_range(hunk.old_start, hunk.old_count)
                new_range = _format_unified_range(hunk.new_start, hunk.new_count)
                out.append(f"@@ -{old_range} +{new_range} @@")
                for kind, text_, newline in hunk.lines:
                    out.append(kind + text_)
                    if not newline:
                        out.append(NO_NEWLINE_MARKER)
    return "\n".join(out) + "\n"
