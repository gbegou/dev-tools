"""Summarize and filter a basedpyright JSON report (``basedpyright --outputjson``).

    basedpyright --outputjson > report.json
    pyright_report.py summary report.json                 # counts by rule, file, package
    pyright_report.py list report.json --package maia     # the errors on code using maia
    pyright_report.py list report.json --rule reportCallIssue --severity all
    pyright_report.py list report.json --file 'src/cases/*' --json > cases.json
    pyright_report.py list report.json --package maia --fail   # CI gate: exit 1 if any
    basedpyright --outputjson | pyright_report.py summary -    # report on standard input

Both commands take the same filters: ``--severity`` (``error``, ``warning``,
``information`` or ``all``; ``list`` keeps the errors by default, ``summary`` counts
everything), ``--rule`` and ``--package`` (repeatable: any of them), ``--file`` (a glob
on the path relative to ``--root``, repeatable). ``list --json`` writes the kept
diagnostics as a report of the same format, so that the commands can be chained.

basedpyright reports an error where the call is, in the calling file: a call into a
library whose API changed shows as ``reportCallIssue`` (``No parameter named "dim"``)
in your code. ``--package`` finds these: a diagnostic uses a package when the statement
it is on uses a name the file bound by importing that package (``maia`` for ``import
maia``, ``PT`` for ``import maia.pytree as PT``, ``compute_elements_center`` for ``from
maia.algo import compute_elements_center``), or imports from it. A statement over
several lines counts as a whole; for ``def``, ``for``, ``if``... only the header line
counts. Relative imports are the file's own code, not a package.

Exit status: 0, or 1 with ``list --fail`` when diagnostics are left; 2 for a report that
cannot be read.
"""

import argparse
import ast
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from fnmatch import fnmatch
from functools import cache
from pathlib import Path
from typing import NoReturn, cast

type Json = dict[str, object]

SEVERITIES = ("error", "warning", "information")
NO_RULE = "(no rule)"
NO_PACKAGE = "(none)"
# statements with a header and a body: only the header is "their" line
BLOCK_STATEMENTS = (
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.If,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.TryStar,
)


@dataclass(frozen=True)
class Diagnostic:
    """One entry of the report (lines and columns 0-based, as in the JSON)."""

    file: str
    severity: str
    rule: str
    message: str
    first_line: int
    last_line: int
    column: int
    entry: Json  # the entry as read, written back by ``list --json``


@dataclass(frozen=True)
class SourceFile:
    """What a file imports, and where, for ``--package``."""

    names_on_line: dict[int, frozenset[str]]  # the names used on each line
    package_of_name: dict[str, str]  # name bound by an import -> top-level package
    imports_on_line: dict[int, frozenset[str]]  # packages imported on each line
    statements: list[tuple[int, int]]  # (first, last) line of each statement


# --------------------------------------------------------------------------- reading


def load_report(source: str) -> Json:
    """The report, from a file or ``-`` (standard input); exit 2 if it is not one."""
    try:
        if source == "-":
            text = sys.stdin.read()
        else:
            text = Path(source).read_text(encoding="utf-8")
        data = cast("object", json.loads(text))
    except (OSError, ValueError) as error:
        fail(f"{source}: cannot read the report ({error})")
    if not isinstance(data, dict) or "generalDiagnostics" not in data:
        fail(
            f"{source}: not a basedpyright --outputjson report (no generalDiagnostics)"
        )
    return cast("Json", data)


def fail(message: str) -> NoReturn:
    """Print the message on standard error and exit with status 2."""
    print(message, file=sys.stderr)
    sys.exit(2)


def position(entry: Json, end: str) -> tuple[int, int]:
    """(line, character) of the start or the end of an entry's range."""
    span = cast("dict[str, dict[str, int]]", entry["range"])
    return span[end]["line"], span[end]["character"]


def diagnostics_of(report: Json) -> list[Diagnostic]:
    """The diagnostics of a report."""
    found: list[Diagnostic] = []
    for entry in cast("list[Json]", report["generalDiagnostics"]):
        first_line, column = position(entry, "start")
        last_line, _ = position(entry, "end")
        found.append(
            Diagnostic(
                file=cast("str", entry["file"]),
                severity=cast("str", entry["severity"]),
                rule=cast("str", entry.get("rule", NO_RULE)),
                message=cast("str", entry["message"]),
                first_line=first_line,
                last_line=last_line,
                column=column,
                entry=entry,
            )
        )
    return found


# --------------------------------------------------------------------------- packages


def statement_span(node: ast.stmt) -> tuple[int, int]:
    """0-based (first, last) line of a statement; the header of a compound one."""
    first = node.lineno - 1
    if isinstance(node, ast.Match):  # its body is its cases
        return first, max(first, node.cases[0].pattern.lineno - 2)
    if isinstance(node, BLOCK_STATEMENTS):
        return first, max(first, node.body[0].lineno - 2)
    return first, (node.end_lineno or node.lineno) - 1


@cache
def read_source(path: str) -> SourceFile | None:
    """The imports and statements of a file; None if it cannot be read or parsed."""
    try:
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError, ValueError):
        return None
    names_on_line: defaultdict[int, set[str]] = defaultdict(set)
    imports_on_line: defaultdict[int, set[str]] = defaultdict(set)
    package_of_name: dict[str, str] = {}
    statements: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names_on_line[node.lineno - 1].add(node.id)
        if not isinstance(node, ast.stmt):
            continue
        statements.append(statement_span(node))
        imported: dict[str, str] = {}
        if isinstance(node, ast.Import):
            for alias in node.names:
                package = alias.name.split(".")[0]
                imported[alias.asname or package] = package
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            package = node.module.split(".")[0]
            for alias in node.names:
                imported[alias.asname or alias.name] = package
        package_of_name.update(imported)
        first, last = statement_span(node)
        for line in range(first, last + 1):
            imports_on_line[line].update(imported.values())
    return SourceFile(
        names_on_line={line: frozenset(names) for line, names in names_on_line.items()},
        package_of_name=package_of_name,
        imports_on_line={line: frozenset(p) for line, p in imports_on_line.items()},
        statements=statements,
    )


def packages_of(diagnostic: Diagnostic) -> frozenset[str]:
    """The top-level packages used by the statement a diagnostic is on."""
    source = read_source(diagnostic.file)
    if source is None:
        return frozenset()
    # the innermost statement around the diagnostic, and the diagnostic's own lines
    first, last = diagnostic.first_line, diagnostic.last_line
    around = [s for s in source.statements if s[0] <= first <= s[1]]
    if around:
        inner = min(around, key=lambda span: span[1] - span[0])
        first, last = min(first, inner[0]), max(last, inner[1])
    packages: set[str] = set()
    for line in range(first, last + 1):
        packages.update(source.imports_on_line.get(line, ()))
        for name in source.names_on_line.get(line, ()):
            if name in source.package_of_name:
                packages.add(source.package_of_name[name])
    return frozenset(packages)


# --------------------------------------------------------------------------- filters


@dataclass(frozen=True)
class Filters:
    """What to keep: empty tuples keep everything."""

    severities: tuple[str, ...]
    rules: tuple[str, ...]
    files: tuple[str, ...]
    packages: tuple[str, ...]
    root: Path


def relative(path: str, root: Path) -> str:
    """The path relative to the root if it is below it, else as given."""
    try:
        return Path(path).relative_to(root).as_posix()
    except ValueError:
        return path


def keep(diagnostic: Diagnostic, filters: Filters) -> bool:
    """Whether a diagnostic passes the filters."""
    if filters.severities and diagnostic.severity not in filters.severities:
        return False
    if filters.rules and diagnostic.rule not in filters.rules:
        return False
    if filters.files:
        path = relative(diagnostic.file, filters.root)
        if not any(fnmatch(path, glob) for glob in filters.files):
            return False
    return not filters.packages or bool(packages_of(diagnostic) & set(filters.packages))


# --------------------------------------------------------------------------- commands


def table(title: str, counts: dict[str, Counter[str]], keys: Iterable[str]) -> str:
    """Rows of counts per severity, under a header."""
    keys = list(keys)
    width = max([len(title), *(len(key) for key in keys)])
    lines = [f"{title:<{width}}  " + "  ".join(f"{s:>11}" for s in SEVERITIES)]
    lines += [
        f"{key:<{width}}  " + "  ".join(f"{counts[key][s]:>11}" for s in SEVERITIES)
        for key in keys
    ]
    return "\n".join(lines)


def ranked(counts: dict[str, Counter[str]], top: int) -> list[str]:
    """Keys by decreasing total (errors first), at most ``top`` (0: all)."""
    keys = sorted(
        counts,
        key=lambda k: (-counts[k]["error"], -counts[k].total(), k),
    )
    return keys[:top] if top > 0 else keys


def summary(kept: list[Diagnostic], total: int, root: Path, top: int) -> str:
    """Counts by severity, rule, file and package."""
    by_rule: defaultdict[str, Counter[str]] = defaultdict(Counter)
    by_file: defaultdict[str, Counter[str]] = defaultdict(Counter)
    by_package: defaultdict[str, Counter[str]] = defaultdict(Counter)
    overall: Counter[str] = Counter()
    for d in kept:
        overall[d.severity] += 1
        by_rule[d.rule][d.severity] += 1
        by_file[relative(d.file, root)][d.severity] += 1
        for package in packages_of(d) or {NO_PACKAGE}:
            by_package[package][d.severity] += 1
    head = ", ".join(
        f"{overall[s]} {s}{'' if s == 'information' or overall[s] == 1 else 's'}"
        for s in SEVERITIES
    )
    files = ranked(by_file, top)
    shown = f"{len(files)} of {len(by_file)}" if len(files) < len(by_file) else "all"
    return "\n\n".join(
        [
            f"{head} ({len(kept)} of the {total} diagnostics of the report)",
            table("by rule", by_rule, ranked(by_rule, 0)),
            table(f"by file ({shown})", by_file, files),
            table(
                "by package used (a statement may use several)",
                by_package,
                ranked(by_package, 0),
            ),
        ]
    )


def line_of(diagnostic: Diagnostic, root: Path, full: bool) -> str:
    """``path:line:column: severity: message (rule)``, 1-based like the compilers."""
    lines = diagnostic.message.splitlines() or [""]
    message = "\n    ".join(lines) if full else lines[0]
    path = relative(diagnostic.file, root)
    where = f"{path}:{diagnostic.first_line + 1}:{diagnostic.column + 1}"
    return f"{where}: {diagnostic.severity}: {message} ({diagnostic.rule})"


def as_report(report: Json, kept: list[Diagnostic]) -> Json:
    """The report with only the kept diagnostics, and its counts updated."""
    counts = Counter(d.severity for d in kept)
    totals = dict(cast("Json", report.get("summary", {})))
    totals.update(
        errorCount=counts["error"],
        warningCount=counts["warning"],
        informationCount=counts["information"],
    )
    return {**report, "generalDiagnostics": [d.entry for d in kept], "summary": totals}


# --------------------------------------------------------------------------- command line


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    """The command line."""
    parser = argparse.ArgumentParser(
        description=(__doc__ or "").splitlines()[0],
        epilog="See the module docstring (the top of this file) for the details.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name, text in (
        ("summary", "counts by severity, rule, file and package"),
        ("list", "the diagnostics, one per line (path:line:column)"),
    ):
        command = commands.add_parser(name, help=text, description=text)
        _ = command.add_argument("report", help="basedpyright --outputjson file, or -")
        _ = command.add_argument(
            "--severity",
            choices=(*SEVERITIES, "all"),
            default="error" if name == "list" else "all",
            help="keep this severity (default: %(default)s)",
        )
        _ = command.add_argument(
            "--rule", action="append", default=[], help="keep this rule (repeatable)"
        )
        _ = command.add_argument(
            "--file",
            action="append",
            default=[],
            help="keep the paths matching this glob (repeatable)",
        )
        _ = command.add_argument(
            "--package",
            action="append",
            default=[],
            help="keep the code using this package (repeatable)",
        )
        _ = command.add_argument(
            "--root",
            type=Path,
            default=Path.cwd(),
            help="paths are shown relative to it (default: .)",
        )
        if name == "summary":
            _ = command.add_argument(
                "--top",
                type=int,
                default=10,
                help="files shown, most errors first (0: all)",
            )
        else:
            _ = command.add_argument(
                "--full", action="store_true", help="multi-line messages in full"
            )
            _ = command.add_argument(
                "--json",
                action="store_true",
                help="write the kept diagnostics as a report",
            )
            _ = command.add_argument(
                "--fail", action="store_true", help="exit 1 if any diagnostic is kept"
            )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run a command; return the exit status."""
    args = parse_args(argv)
    severity = cast("str", args.severity)
    root = cast("Path", args.root).resolve()
    filters = Filters(
        severities=() if severity == "all" else (severity,),
        rules=tuple(cast("list[str]", args.rule)),
        files=tuple(cast("list[str]", args.file)),
        packages=tuple(cast("list[str]", args.package)),
        root=root,
    )
    report = load_report(cast("str", args.report))
    diagnostics = diagnostics_of(report)
    kept = [d for d in diagnostics if keep(d, filters)]
    if cast("str", args.command) == "summary":
        print(summary(kept, len(diagnostics), root, cast("int", args.top)))
        return 0
    if cast("bool", args.json):
        print(json.dumps(as_report(report, kept), indent=2))
    else:
        for d in kept:
            print(line_of(d, root, cast("bool", args.full)))
    return 1 if cast("bool", args.fail) and kept else 0


if __name__ == "__main__":
    sys.exit(main())
