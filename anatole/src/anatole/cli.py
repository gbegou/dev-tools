"""Command line: ``anatole {gui,check,list,export}``."""

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from anatole import __version__
from anatole.export import OUTPUTS, SUFFIXES, TARGETS, OfficeError, Output, Target, export
from anatole.io import load
from anatole.model import Notation, NotationError
from anatole.typing import FORMATS, Format, Language

__all__ = ["main"]


class _Arguments(argparse.Namespace):
    """The parsed command line; the defaults stand for the options of other commands."""

    verbose: bool = False
    command: str | None = None
    file: Path | None = None
    files: list[Path] = []  # noqa: RUF012  # replaced, not mutated, by argparse
    output: Path | None = None
    format: Output | None = None
    reference_doc: Path | None = None
    language: Language | None = None
    strict: bool = False
    target: Target = "nomencl+acro"
    tags: list[str] | None = None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="anatole",
        description="ANATOLE is a Notations And acronyms manager with Typst Or LaTeX "
        + "Exporters: define notations once, use them in LaTeX and Typst.",
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
    _ = check.add_argument("--strict", action="store_true", help="fail on missing translations too")

    list_ = commands.add_parser("list", help="list the notations of a file")
    _ = list_.add_argument("file", type=Path)
    _ = list_.add_argument(
        "--tag",
        action="append",
        dest="tags",
        metavar="TAG",
        help="list the entries selected by this tag (repeat for several)",
    )
    _ = list_.add_argument(
        "-f", "--format", choices=FORMATS, help="the format of the symbols (default: latex)"
    )
    _ = list_.add_argument(
        "-l", "--language", help="the language of the descriptions (default: the file's default)"
    )

    export_ = commands.add_parser(
        "export",
        help="export a notation file to LaTeX, Typst or Word",
        description="Export a notation file. The output follows its suffix ("
        + ", ".join(f"{suffix}: {fmt}" for suffix, fmt in SUFFIXES.items())
        + ") unless --format is given. The descriptions are in the default language of the "
        + "file unless --language is given; a missing translation falls back on the default "
        + "language, with a warning.",
    )
    _ = export_.add_argument("file", type=Path, help="the notation file")
    _ = export_.add_argument("output", type=Path, help="the file to write")
    _ = export_.add_argument("-f", "--format", choices=OUTPUTS, help="the output")
    _ = export_.add_argument("-l", "--language", help="the language of the descriptions")
    _ = export_.add_argument(
        "-t",
        "--latex-target",
        dest="target",
        choices=TARGETS,
        default=TARGETS[0],
        help="the LaTeX packages of the lists (default: %(default)s)",
    )
    _ = export_.add_argument(
        "--tag",
        action="append",
        dest="tags",
        metavar="TAG",
        help="export the entries selected by this tag (repeat for several): those with the "
        + "tag, those without tags, and the entries they use",
    )
    _ = export_.add_argument(
        "--reference-doc",
        type=Path,
        metavar="DOCX",
        help="a Word document whose styles the Word export takes",
    )
    return parser


def _check(files: Sequence[Path], *, strict: bool) -> int:
    status = 0
    for file in files:
        try:
            notations = load(file)
        except (OSError, NotationError) as error:
            print(error, file=sys.stderr)
            status = 1
            continue
        missing = notations.missing_translations()
        print(
            f"{file}: {len(notations.notations)} notations, {len(notations.acronyms)} acronyms "
            + f"and abbreviations, {len(notations.styles)} styles, {len(notations.groups)} "
            + f"groups, languages {', '.join(notations.languages)}, valid"
            + (f", {len(missing)} missing translations" if missing else "")
        )
        for problem in missing:
            print(f"{file}: {problem}", file=sys.stderr if strict else sys.stdout)
        if strict and missing:
            status = 1
    return status


def _list(file: Path, fmt: Format, language: Language | None, tags: list[str] | None) -> int:
    notations = load(file)
    language = language or notations.default_language
    notations.check_language(language)
    if tags is not None:
        notations = notations.subset(tags)
    default = notations.default_language
    rows = [("kind", "name", "group", "symbol", "description")]
    for style in notations.styles:
        rows.append(("style", style.name, "", style.template.get(fmt), ""))
    for entry in notations:
        if isinstance(entry, Notation):
            text = entry.description.resolve(language, default).get(fmt)
            rows.append(("notation", entry.name, entry.group, entry.symbol.get(fmt), text))
        else:
            short = entry.short.resolve(language, default).get(fmt)
            long = entry.long.resolve(language, default).get(fmt)
            rows.append((entry.kind, entry.name, entry.group, short, long))
    widths = [max(len(row[column]) for row in rows) for column in range(4)]
    for row in rows:
        cells = (cell.ljust(width) for cell, width in zip(row, widths, strict=False))
        print("  ".join([*cells, row[4]]).rstrip())
    return 0


def _export(
    file: Path,
    output: Path,
    fmt: Output | None,
    language: Language | None,
    *,
    target: Target,
    tags: list[str] | None,
    reference_doc: Path | None,
) -> int:
    problems = export(
        load(file),
        output,
        fmt,
        language=language,
        target=target,
        tags=tags,
        source=file.name,
        reference_doc=reference_doc,
    )
    print(f"{output}: written" + (f", {len(problems)} problems (see above)" if problems else ""))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line with ``argv`` (``sys.argv[1:]`` by default); return the exit code.

    Exit codes: 0 on success, 1 when a file cannot be read, is invalid or cannot be exported
    (or, with ``check --strict``, misses translations), 2 on a usage error.
    """
    arguments = _parser().parse_args(argv, namespace=_Arguments())
    logging.basicConfig(
        level=logging.INFO if arguments.verbose else logging.WARNING, format="%(message)s"
    )
    file, output = arguments.file, arguments.output
    try:
        match arguments.command:
            case "check":
                return _check(arguments.files, strict=arguments.strict)
            case "list" if file is not None:
                fmt: Format = "typst" if arguments.format == "typst" else "latex"
                return _list(file, fmt, arguments.language, arguments.tags)
            case "export" if file is not None and output is not None:
                return _export(
                    file,
                    output,
                    arguments.format,
                    arguments.language,
                    target=arguments.target,
                    tags=arguments.tags,
                    reference_doc=arguments.reference_doc,
                )
            case _:
                from anatole.gui import run  # noqa: PLC0415  # tkinter only when needed

                return run(file)
    except (OSError, ValueError, OfficeError) as error:  # NotationError is a ValueError
        print(error, file=sys.stderr)
        return 1
