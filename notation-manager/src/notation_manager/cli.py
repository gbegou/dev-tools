"""Command line: ``notation-manager {gui,check,list,export}``."""

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from notation_manager import __version__
from notation_manager.export import SUFFIXES, export
from notation_manager.io import load
from notation_manager.model import NotationError
from notation_manager.typing import LANGUAGES, Language

__all__ = ["main"]


class _Arguments(argparse.Namespace):
    """The parsed command line; the defaults stand for the options of other commands."""

    verbose: bool = False
    command: str | None = None
    file: Path | None = None
    files: list[Path] = []  # noqa: RUF012  # replaced, not mutated, by argparse
    output: Path | None = None
    language: Language | None = None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="notation-manager",
        description="Manage notations once, use them in LaTeX and Typst.",
    )
    _ = parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    _ = parser.add_argument(
        "-v", "--verbose", action="store_true", help="log what is read and written"
    )
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")

    gui = commands.add_parser("gui", help="open the graphical interface (the default command)")
    _ = gui.add_argument("file", nargs="?", type=Path, help="the notation file to open")

    check = commands.add_parser("check", help="check notation files, report every problem")
    _ = check.add_argument("files", nargs="+", type=Path, metavar="file")

    list_ = commands.add_parser("list", help="list the notations of a file")
    _ = list_.add_argument("file", type=Path)
    _ = list_.add_argument(
        "-l", "--language", choices=LANGUAGES, help="the rendering shown (default: latex)"
    )

    export_ = commands.add_parser(
        "export",
        help="export a notation file to LaTeX or Typst",
        description="Export a notation file. The language follows the output suffix ("
        + ", ".join(f"{suffix}: {language}" for suffix, language in SUFFIXES.items())
        + ") unless --language is given.",
    )
    _ = export_.add_argument("file", type=Path, help="the notation file")
    _ = export_.add_argument("output", type=Path, help="the file to write")
    _ = export_.add_argument("-l", "--language", choices=LANGUAGES, help="the target language")
    return parser


def _check(files: Sequence[Path]) -> int:
    status = 0
    for file in files:
        try:
            notations = load(file)
        except (OSError, NotationError) as error:
            print(error, file=sys.stderr)
            status = 1
        else:
            print(f"{file}: {len(notations)} notations, {len(notations.groups)} groups, valid")
    return status


def _list(file: Path, language: Language) -> int:
    notations = load(file)
    rows = [("name", "group", "symbol", "description")]
    rows.extend(
        (n.name, n.group, n.symbol.get(language), n.description.get(language)) for n in notations
    )
    widths = [max(len(row[column]) for row in rows) for column in range(3)]
    for row in rows:
        print(
            "  ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=False)), row[3]
        )
    return 0


def _export(file: Path, output: Path, language: Language | None) -> int:
    export(load(file), output, language, source=file.name)
    print(f"{output}: written")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line with ``argv`` (``sys.argv[1:]`` by default); return the exit code.

    Exit codes: 0 on success, 1 when a file cannot be read, is invalid or cannot be exported,
    2 on a usage error.
    """
    arguments = _parser().parse_args(argv, namespace=_Arguments())
    logging.basicConfig(
        level=logging.INFO if arguments.verbose else logging.WARNING, format="%(message)s"
    )
    file, output = arguments.file, arguments.output
    try:
        match arguments.command:
            case "check":
                return _check(arguments.files)
            case "list" if file is not None:
                return _list(file, arguments.language or "latex")
            case "export" if file is not None and output is not None:
                return _export(file, output, arguments.language)
            case _:
                from notation_manager.gui import run  # noqa: PLC0415  # tkinter only when needed

                return run(file)
    except (OSError, ValueError) as error:  # NotationError is a ValueError
        print(error, file=sys.stderr)
        return 1
