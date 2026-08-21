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
standard `@@ -l,s +l,s @@` headers - but not everything a real diff can
contain yet. See the roadmap for what's missing.
