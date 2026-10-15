"""Tests of tools/pyright_report.py, through its command line.

A small project in a temporary directory: a module using a package ``lib`` (imported in
several ways), a report about it written by hand with basedpyright's messages, and, when
basedpyright is installed, its real report about a wrong call into ``lib``. The worked
example of doc/pyright_report.md is this project: its outputs are checked here.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

TOOL = Path(__file__).resolve().parents[1] / "pyright_report.py"
DOC = Path(__file__).resolve().parents[2] / "doc" / "pyright_report.md"

# the lines of USER (1-based) that the hand-made report points at
USER = """\
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
"""


def run(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    """Run the tool; its output and exit status."""
    return subprocess.run(
        [sys.executable, str(TOOL), *args],
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


def entry(
    path: Path, line: int, severity: str, rule: str, message: str
) -> dict[str, object]:
    """A report entry on a 1-based line, as basedpyright writes it (0-based)."""
    position = {"line": line - 1, "character": 4}
    return {
        "file": str(path),
        "severity": severity,
        "message": message,
        "range": {"start": position, "end": position},
        "rule": rule,
    }


def make_project(tmp_path: Path) -> tuple[Path, Path]:
    """(root, report): a project with one module and a hand-made report about it."""
    user = tmp_path / "pkg" / "user.py"
    user.parent.mkdir()
    _ = user.write_text(USER)
    unused = (
        'Result of call expression is of type "str" and is not used; assign to '
        'variable "_" if this is intentional'
    )
    entries = [
        entry(user, 7, "error", "reportCallIssue", "Expected 0 positional arguments"),
        entry(user, 10, "error", "reportCallIssue", 'No parameter named "dim"'),
        entry(user, 12, "warning", "reportUnusedCallResult", unused),
        entry(
            user,
            13,
            "error",
            "reportAttributeAccessIssue",
            '"thing" is not a known attribute of module ".local"',
        ),
        entry(
            user,
            14,
            "warning",
            "reportUnknownVariableType",
            'Type of "item" is partially unknown\n  Type of "item" is "int | Unknown"',
        ),
        entry(
            user,
            15,
            "information",
            "reportUnknownArgumentType",
            "Argument type is partially unknown",
        ),
        entry(
            user,
            1,
            "warning",
            "reportMissingModuleSource",
            'Import "lib.sub" could not be resolved from source',
        ),
    ]
    report = tmp_path / "report.json"
    summary = {"filesAnalyzed": 1, "errorCount": 3, "warningCount": 3}
    _ = report.write_text(
        json.dumps({"generalDiagnostics": entries, "summary": summary})
    )
    return tmp_path, report


@pytest.fixture
def project(tmp_path: Path) -> tuple[Path, Path]:
    """The example project (doc/pyright_report.md), in a temporary directory."""
    return make_project(tmp_path)


def listed(root: Path, report: Path, *args: str) -> list[str]:
    """The lines of ``list``."""
    result = run("list", str(report), "--root", str(root), *args)
    assert result.returncode == 0, result.stderr
    return result.stdout.splitlines()


def test_list_keeps_the_errors_by_default(project: tuple[Path, Path]) -> None:
    root, report = project
    lines = listed(root, report)
    assert len(lines) == 3
    assert lines[1] == (
        'pkg/user.py:10:5: error: No parameter named "dim" (reportCallIssue)'
    )


def test_package_of_each_statement(project: tuple[Path, Path]) -> None:
    root, report = project
    # lib: "import lib.sub as ls", a call over several lines of a name from "from lib
    # import" (the error is on its third line), a for header, and the import itself
    lib = listed(root, report, "--package", "lib", "--severity", "all")
    assert [line.split(":")[1] for line in lib] == ["1", "7", "10", "14"]
    os_lines = listed(root, report, "--package", "os", "--severity", "all")
    assert [line.split(":")[1] for line in os_lines] == ["12"]
    # a relative import is the file's own code; the loop body uses no package
    assert listed(root, report, "--package", "local", "--severity", "all") == []


def test_filters_combine(project: tuple[Path, Path]) -> None:
    root, report = project
    calls = listed(root, report, "--rule", "reportCallIssue", "--package", "lib")
    assert len(calls) == 2
    assert listed(root, report, "--file", "other/*") == []
    assert len(listed(root, report, "--file", "pkg/*", "--severity", "warning")) == 3


def test_full_messages(project: tuple[Path, Path]) -> None:
    root, report = project
    args = ("--rule", "reportUnknownVariableType", "--severity", "all")
    assert listed(root, report, *args) == [
        (
            'pkg/user.py:14:5: warning: Type of "item" is partially unknown '
            "(reportUnknownVariableType)"
        )
    ]
    assert listed(root, report, *args, "--full") == [
        'pkg/user.py:14:5: warning: Type of "item" is partially unknown',
        '      Type of "item" is "int | Unknown" (reportUnknownVariableType)',
    ]


def test_summary(project: tuple[Path, Path]) -> None:
    root, report = project
    result = run("summary", str(report), "--root", str(root))
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert out.startswith("3 errors, 3 warnings, 1 information (7 of the 7 diagnostics")
    rows = {line.split()[0]: line.split()[1:] for line in out.splitlines() if line}
    assert rows["reportCallIssue"] == ["2", "0", "0"]
    assert rows["lib"] == ["2", "2", "0"]
    assert rows["os"] == ["0", "1", "0"]
    assert rows["(none)"] == ["1", "0", "1"]


def test_json_round_trip(project: tuple[Path, Path]) -> None:
    root, report = project
    result = run("list", str(report), "--root", str(root), "--package", "lib", "--json")
    assert result.returncode == 0, result.stderr
    kept = cast("dict[str, object]", json.loads(result.stdout))
    assert len(cast("list[object]", kept["generalDiagnostics"])) == 2
    assert kept["summary"] == {
        "filesAnalyzed": 1,
        "errorCount": 2,
        "warningCount": 0,
        "informationCount": 0,
    }
    # the output is a report too: read back from standard input
    again = run("list", "-", "--root", str(root), stdin=result.stdout)
    assert again.returncode == 0, again.stderr
    assert len(again.stdout.splitlines()) == 2


def test_fail_exit_status(project: tuple[Path, Path]) -> None:
    root, report = project
    found = run("list", str(report), "--root", str(root), "--package", "lib", "--fail")
    assert found.returncode == 1
    clean = run(
        "list", str(report), "--root", str(root), "--package", "numpy", "--fail"
    )
    assert clean.returncode == 0
    assert clean.stdout == ""


def test_unreadable_reports(tmp_path: Path) -> None:
    missing = run("summary", str(tmp_path / "missing.json"))
    assert missing.returncode == 2
    assert "cannot read the report" in missing.stderr
    other = tmp_path / "other.json"
    _ = other.write_text("[]")
    assert run("summary", str(other)).returncode == 2
    assert run("summary", "-", stdin="not json").returncode == 2


@pytest.mark.skipif(shutil.which("basedpyright") is None, reason="basedpyright missing")
def test_a_real_report(tmp_path: Path) -> None:
    """basedpyright's own report: a call with a keyword the library does not have"""
    _ = (tmp_path / "lib.py").write_text(
        "def center(zone: int, dim: int) -> int:\n    return zone + dim\n"
    )
    _ = (tmp_path / "user.py").write_text(
        "import lib\n\nvalue = lib.center(1, dimension=2)\n"
    )
    pyright = subprocess.run(
        ["basedpyright", "--pythonpath", sys.executable, "--outputjson", "user.py"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    lines = run(
        "list",
        "-",
        "--root",
        str(tmp_path),
        "--package",
        "lib",
        "--rule",
        "reportCallIssue",
        stdin=pyright.stdout,
    ).stdout.splitlines()
    assert lines
    assert all(line.startswith("user.py:3:") for line in lines)
    assert any('"dimension"' in line for line in lines)


@pytest.mark.parametrize("command", [[], ["summary"], ["list"]])
def test_help(command: list[str]) -> None:
    result = run(*command, "--help")
    assert result.returncode == 0, result.stderr
    assert "examples:" in result.stdout


def test_documented_example(project: tuple[Path, Path]) -> None:
    """The outputs shown in doc/pyright_report.md are the tool's on this project"""
    root, report = project
    blocks = DOC.read_text().split("```")[1::2]  # the contents of the code blocks
    shown = {block.split("\n", 1)[1].rstrip() for block in blocks if "\n" in block}
    assert (root / "pkg" / "user.py").read_text().rstrip() in shown
    for args in (
        ["summary"],
        ["list"],
        ["list", "--package", "lib", "--severity", "all"],
    ):
        result = run(*args[:1], str(report), "--root", str(root), *args[1:])
        assert result.stdout.rstrip() in shown, " ".join(args)
