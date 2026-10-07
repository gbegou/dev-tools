"""Merge GitLab Code Quality reports into a single file.

GitLab accepts a single ``codequality`` report file per job, while each tool
(ruff, basedpyright) writes its own. This script concatenates the reports and
makes every issue path relative to the repository root, so that GitLab links
the findings to the right files and lines.

Usage::

    python .gitlab/ci/merge_codequality.py OUTPUT INPUT [INPUT ...]

Missing input files are skipped (a tool may not have run), so the job still
uploads whatever reports exist.
"""

import argparse
import json
from pathlib import Path
from typing import cast

type Issue = dict[str, object]


def read_issues(path: Path) -> list[Issue]:
    """Read the issues of one Code Quality report (a JSON array of objects)."""
    data = cast("object", json.loads(path.read_text(encoding="utf-8")))
    if not isinstance(data, list):
        msg = f"{path}: expected a JSON array, got {type(data).__name__}"
        raise TypeError(msg)
    items = cast("list[object]", data)
    return [cast("Issue", item) for item in items if isinstance(item, dict)]


def relative_to_root(issue: Issue, root: Path) -> None:
    """Make the issue path relative to the repository root, in place."""
    location = issue.get("location")
    if not isinstance(location, dict):
        return
    location = cast("dict[str, object]", location)
    path = location.get("path")
    if isinstance(path, str) and Path(path).is_absolute():
        location["path"] = Path(path).relative_to(root, walk_up=True).as_posix()


def main() -> None:
    """Merge the reports given on the command line."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    _ = parser.add_argument("output", type=Path, help="merged report to write")
    _ = parser.add_argument("inputs", type=Path, nargs="+", help="reports to merge")
    _ = parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="repository root for relative paths (default: current directory)",
    )
    args = parser.parse_args()
    output = cast("Path", args.output)
    inputs = cast("list[Path]", args.inputs)
    root = cast("Path", args.root).resolve()

    issues: list[Issue] = []
    for path in inputs:
        if not path.exists():
            print(f"{path}: not found, skipped")
            continue
        report = read_issues(path)
        print(f"{path}: {len(report)} issues")
        issues.extend(report)
    for issue in issues:
        relative_to_root(issue, root)

    _ = output.write_text(json.dumps(issues, indent=2), encoding="utf-8")
    print(f"{output}: {len(issues)} issues written")


if __name__ == "__main__":
    main()
