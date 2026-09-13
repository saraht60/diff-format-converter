# diffconv

`git diff` and most modern tools only speak unified diff format:

```diff
--- a/greeting.py
+++ b/greeting.py
@@ -1,2 +1,2 @@
 def greet(name):
-    print("Hello " + name)
+    print(f"Hello, {name}!")
```

Every so often something older wants context diff format instead - the
`diff -c` style with a separate "before" and "after" block per hunk, and
`!` marking lines that were replaced rather than plainly added or removed.
I keep running into this with an old patch-review script that only reads
context diffs, and I got tired of hand-converting, so: this.

Given the diff above, it produces:

```
*** a/greeting.py
--- b/greeting.py
***************
*** 1,2 ****
  def greet(name):
!     print("Hello " + name)
--- 1,2 ----
  def greet(name):
!     print(f"Hello, {name}!")
```

## Usage

No install needed, it's pure standard library:

```
python -m diffconv path/to/change.patch
```

Reads from stdin and writes to stdout by default, so it drops straight
into a pipeline:

```
git diff | python -m diffconv > change.ctx.diff
```

Write to a file instead of stdout with `-o`:

```
python -m diffconv change.patch -o change.ctx.diff
```

It goes the other way too, with `--from context --to unified`:

```
python -m diffconv old.ctx.diff --from context --to unified
```

If you install the package (`pip install -e .`), the same thing is
available as the `diffconv` command instead of `python -m diffconv`.

## As a library

```python
from diffconv import parse_unified, render_context

files = parse_unified(open("change.patch").read())
print(render_context(files))
```

`parse_unified` and `parse_context` both return a list of `FileDiff`
objects (one per file touched by the patch, each holding a list of `Hunk`
objects), so you can inspect or filter the diff before rendering it with
`render_context` or `render_unified`.

## Limitations

This is a first pass. It handles the common case - plain unified diffs with
standard `@@ -l,s +l,s @@` headers, including files with no trailing newline
- but not everything a real diff can contain yet.

It understands git's `diff --git` extended headers well enough to carry them
through unchanged: renames, mode changes, and binary file notices all
round-trip, even the ones with no `---`/`+++` section of their own (a pure
rename or mode change has nothing else to show). It doesn't try to interpret
those headers, though - a rename shows up as the same opaque `rename
from`/`rename to` lines on both sides rather than as a change to `old_path`
or `new_path` you could inspect programmatically, and quoted paths (a
filename containing a space or a non-ASCII character) aren't unescaped.

It also assumes the input format rather than detecting it - you have to pass
`--from context` yourself if you're not starting from unified diff.

## Tests

```
python -m unittest discover
```

`tests/fixtures/` holds paired `.diff`/`.ctx.diff` files used for exact
output checks and round-trip checks (unified -> context -> unified should
reproduce the original).
