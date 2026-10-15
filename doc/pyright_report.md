# Working through a basedpyright report

basedpyright on a project that uses untyped libraries (maia, ParaDiGM, scipy...) prints
thousands of diagnostics, mostly warnings about types it cannot know. The few that matter
get lost, for instance the call into a library whose API changed. basedpyright reports
that one where the call is, in your file, as `reportCallIssue: No parameter named "dim"`.

`tools/pyright_report.py` reads basedpyright's JSON report and answers two questions:

- `summary`: how many errors and warnings, of which rules, in which files, on statements
  using which packages?
- `list`: which ones exactly? One line per diagnostic, `path:line:column: severity: message
  (rule)`, which editors and terminals open at the right place. With `--fail`, it can fail
  a CI job.

Both commands take the same filters: `--severity`, `--rule`, `--file` and `--package`.
`--help` on the tool and on each command gives every option, with examples.

## Getting a report

```bash
basedpyright --outputjson > report.json
```

basedpyright exits with status 1 when it finds errors, but the report is written anyway.
The report can also be piped: the tool reads it from standard input when its name is `-`.

Check that basedpyright sees the packages your code imports, **the same versions your
tests use**. It finds them through the Python it runs (its `--pythonpath`), whose module
search path includes `PYTHONPATH`. For a project built with CMake and project_utils,
source the build environment first (`source build/source.sh`), otherwise:

- a package that is not found gives one `reportMissingImports` error, and every call
  into it goes unchecked;
- another installed version is checked instead of the one the tests import, and its
  differences go unseen.

## A worked example

A module `pkg/user.py` uses a package `lib` in several ways, a standard module and a
module of its own package:

```python
import lib.sub as ls
from lib import helper
from os import path

from . import local

ls.call(1)
helper(
    2,
    dim=3,
)
path.join("a")
local.thing()
for item in helper(4):
    print(item)
```

The overview of its report (`pyright_report.py summary report.json`):

```text
3 errors, 3 warnings, 1 information (7 of the 7 diagnostics of the report)

by rule                           error      warning  information
reportCallIssue                       2            0            0
reportAttributeAccessIssue            1            0            0
reportMissingModuleSource             0            1            0
reportUnknownArgumentType             0            0            1
reportUnknownVariableType             0            1            0
reportUnusedCallResult                0            1            0

by file (all)        error      warning  information
pkg/user.py              3            3            1

by package used        error      warning  information
lib                        2            2            0
(none)                     1            0            1
os                         0            1            0
```

The tables are sorted by errors, then by total. A statement that uses several packages
counts in each of their rows; `(none)` counts the statements that use no package. Files are
limited to the 10 with the most errors; `--top 0` lists them all.

The errors (`pyright_report.py list report.json`):

```text
pkg/user.py:7:5: error: Expected 0 positional arguments (reportCallIssue)
pkg/user.py:10:5: error: No parameter named "dim" (reportCallIssue)
pkg/user.py:13:5: error: "thing" is not a known attribute of module ".local" (reportAttributeAccessIssue)
```

Everything on statements using `lib`, warnings included
(`pyright_report.py list report.json --package lib --severity all`):

```text
pkg/user.py:1:5: warning: Import "lib.sub" could not be resolved from source (reportMissingModuleSource)
pkg/user.py:7:5: error: Expected 0 positional arguments (reportCallIssue)
pkg/user.py:10:5: error: No parameter named "dim" (reportCallIssue)
pkg/user.py:14:5: warning: Type of "item" is partially unknown (reportUnknownVariableType)
```

Line 1 is an import of `lib`. Line 7 uses `ls`, bound to `lib` by `import lib.sub as ls`.
Line 10 is inside the call `helper(...)` of lines 8-11, and `helper` comes from
`from lib import helper`. Line 14 is the header of a `for` over `helper(4)`. Line 13 is not
there: `local` comes from a relative import, which is the package's own code. Neither is
line 15: `print(item)` uses no package.

## The filters

| Option | Keeps | Repeatable |
| --- | --- | --- |
| `--severity error\|warning\|information\|all` | that severity (`list`: `error` by default; `summary`: `all`) | no |
| `--rule RULE` | that basedpyright rule, e.g. `reportCallIssue` | yes: any of them |
| `--file GLOB` | the files whose path relative to `--root` matches, e.g. `'src/*'` (`*` also matches `/`) | yes: any of them |
| `--package NAME` | the statements that use that top-level package (below) | yes: any of them |

Different options combine: a diagnostic must pass all of them. `--root DIR` (default: the
current directory) is the directory the paths are shown, and `--file` globs matched,
relative to.

### What "a statement uses a package" means

The tool reads each file of the report (they must still be where the report says, and
unchanged since) and finds:

- the names its imports bind, anywhere in the file: `import maia` binds `maia`,
  `import maia.pytree as PT` binds `PT`, `from maia.algo import compute_elements_center`
  binds `compute_elements_center`, all to the package `maia`;
- the statement each diagnostic is on: a statement over several lines (a call with its
  arguments on several lines) counts as a whole, while a `def`, `class`, `for`, `while`,
  `if`, `with`, `try` or `match` only counts by its header, not its body.

The statement uses a package if it uses one of the names bound to it, or if it is an import
from it. Relative imports (`from . import local`) are the project's own code.

Limits: a name assigned from a package (`algo = maia.algo`, then `algo.f()`) is not
followed, and neither are the names of `from maia import *`. A local variable named like an
imported one counts as the import.

## Recipes

**A library changed its API.** The calls that no longer match it are `reportCallIssue`
(an unknown keyword, a missing argument), its missing names are `reportAttributeAccessIssue`:

```bash
pyright_report.py list report.json --package maia --rule reportCallIssue --rule reportAttributeAccessIssue
```

**Triaging a large report.** Start from `summary`, then narrow down by rule or file:

```bash
pyright_report.py summary report.json --severity error
pyright_report.py list report.json --rule reportArgumentType
pyright_report.py list report.json --file 'src/solver/*' --severity all --full
```

`--full` prints multi-line messages in full: basedpyright explains a type mismatch on the
following lines.

**Saving a selection.** `list --json` writes the kept diagnostics as a report of the same
format, with its counts updated, to keep or to read again:

```bash
pyright_report.py list report.json --package maia --severity all --json > maia.json
pyright_report.py summary maia.json
```

**A CI gate.** `list --fail` exits with status 1 when a diagnostic is left. For instance
in a GitLab lint job, after the build environment is sourced:

```bash
basedpyright --outputjson > report.json || true   # status 1 when there are errors
python tools/pyright_report.py list report.json --package maia --rule reportCallIssue --fail
```

## Exit status

| Status | When |
| --- | --- |
| 0 | the command ran |
| 1 | `list --fail`, and some diagnostics are left |
| 2 | the report cannot be read, or is not a basedpyright report (no `generalDiagnostics`) |
| 141 | the output was closed before the end (piped into `head`, for instance), as for other commands |
