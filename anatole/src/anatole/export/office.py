r"""Export to Word: the nomenclature and the acronyms as a ``.docx`` document.

Word has no commands like ``\velocity``: the export is the lists, with each symbol as a Word
equation (editable, in the equation font), written by pandoc (the optional ``pypandoc-binary``
package, ``pip install anatole[office]``) from a LaTeX source. Units written with siunitx
(``\si{\metre\per\second}``) are converted when pandoc knows them; what it cannot convert (an
unknown unit, an unknown command) is reported, by entry, and left out or kept as TeX.
"""

import importlib.util
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import final

from anatole.export._common import resolve_language, symbol
from anatole.export.latex import LatexWriter
from anatole.logging import get_logger
from anatole.model import Acronym, Entry, Notation, NotationSet, Section
from anatole.typing import Language

__all__ = ["OfficeError", "is_available", "to_docx"]

_logger = get_logger(__name__)

_SKIPPED = re.compile(r"\[INFO\] Skipped '(.+?)' at .*? line (\d+)")
_ENSUREMATH = re.compile(r"\\ensuremath\{(.*)\}")
_UNCONVERTED = re.compile(r"\[WARNING\] Could not convert TeX math (.+?), rendering as TeX")


class OfficeError(RuntimeError):
    """The Word export cannot run (pandoc missing or failing)."""


def is_available() -> bool:
    """Whether pandoc is available through ``pypandoc`` (``pip install anatole[office]``)."""
    return importlib.util.find_spec("pypandoc") is not None


def _pandoc() -> str:
    try:
        # An optional dependency, without type stubs.
        import pypandoc  # noqa: PLC0415  # pyright: ignore[reportMissingTypeStubs]

        path: object = pypandoc.get_pandoc_path()
        return str(path)
    except (ImportError, OSError) as error:
        raise OfficeError("the Word export needs pandoc: pip install 'anatole[office]'") from error


@dataclass(frozen=True, slots=True)
class _Source:
    """The LaTeX source given to pandoc, and the entry on each line of it."""

    text: str
    entries: dict[int, Entry]


@final
class _Builder:
    def __init__(self, notations: NotationSet, language: Language) -> None:
        self.notations = notations
        self.language = language
        default = notations.default_language
        # Word has no acronym package: a reference to an acronym prints its short form.
        self.writer = LatexWriter(
            notations,
            language,
            "ac",
            acronym_text=lambda acronym: acronym.short.resolve(language, default).latex,
        )
        self.lines: list[str] = []
        self.entries: dict[int, Entry] = {}

    def heading(self, level: int, title: str) -> None:
        command = ("section", "subsection", "subsubsection")[level]
        self.lines.append(rf"\{command}*{{{title}}}")

    def table(self, entries: tuple[Entry, ...]) -> None:
        # Symbol, description and units; short and long forms for acronyms.
        notations = any(isinstance(entry, Notation) for entry in entries)
        # Relative widths: pandoc gives the Word table the same proportions.
        columns = (
            r"p{0.15\linewidth}p{0.65\linewidth}p{0.2\linewidth}"
            if notations
            else r"p{0.2\linewidth}p{0.8\linewidth}"
        )
        self.lines.append(rf"\begin{{tabular}}{{{columns}}}")
        for entry in entries:
            self.entries[len(self.lines) + 1] = entry
            row = self.row(entry)
            self.lines.append(" & ".join(row if notations else row[:2]) + r" \\")
        self.lines.append(r"\end{tabular}")

    def row(self, entry: Entry) -> tuple[str, str, str]:
        description = self.writer.description(entry)
        if isinstance(entry, Notation):
            call = rf"\{entry.name}" + r"{\cdot}" * entry.arguments
            return f"${call}$", description, self.writer.text(entry.units.latex)
        long = self.writer.long(entry)
        return self.writer.short(entry), f"{long}: {description}" if description else long, ""

    def sections(self, title: str, sections: tuple[Section, ...]) -> None:
        if not sections:
            return
        self.heading(0, title)
        for section in sections:
            if section.group is not None:
                self.heading(1, self.writer.title(section))
            if section.entries:
                self.table(section.entries)
            for sub in section.subsections:
                self.heading(2, self.writer.title(sub))
                self.table(sub.entries)

    def source(self, nomenclature: str, acronyms: str) -> _Source:
        self.lines = self.writer.definitions("newcommand")
        self.sections(nomenclature, self.notations.sections("notation"))
        self.sections(acronyms, self.notations.sections("acronym"))
        return _Source("\n".join(self.lines) + "\n", self.entries)


def _owner(entry: Entry) -> str:
    kind = entry.kind if isinstance(entry, Acronym) else "notation"
    return f"{kind} {entry.name!r}"


def _problems(log: str, source: _Source, notations: NotationSet) -> list[str]:
    """Return the problems pandoc reports, each naming its entry when it can be found."""
    problems: list[str] = []
    skipped = dict.fromkeys((m.group(1), int(m.group(2))) for m in _SKIPPED.finditer(log))
    for command, line in skipped:
        entry = source.entries.get(line)
        owner = _owner(entry) if entry is not None else "word"
        problems.append(f"{owner}: Word: {command} is not converted (left out)")
    for found in dict.fromkeys(m.group(1) for m in _UNCONVERTED.finditer(log)):
        # The commands of the notations are expanded, in \ensuremath.
        wrapped = _ENSUREMATH.fullmatch(found.strip())
        math = wrapped.group(1) if wrapped else found.strip()
        culprits = [
            _owner(n) for n in notations.notations if math and math in symbol(n, "latex", notations)
        ]
        owner = ", ".join(culprits) or "word"
        problems.append(f"{owner}: Word: the math {math} is not converted (kept as TeX)")
    return problems


def to_docx(
    notations: NotationSet,
    path: str | Path,
    *,
    language: Language | None = None,
    reference_doc: str | Path | None = None,
    nomenclature_title: str = "Nomenclature",
    acronyms_title: str = "Acronyms",
) -> list[str]:
    r"""Write the lists of ``notations`` to the Word document ``path``.

    The notations are a table of symbols (Word equations), descriptions and units; the
    acronyms and abbreviations a table of short and long forms; both by section and
    subsection, under the headings ``nomenclature_title`` and ``acronyms_title``. Styles and
    references are expanded; a reference to an acronym prints its short form.

    Parameters
    ----------
    notations
        The notations.
    path
        The ``.docx`` file to write.
    language
        The language of the texts; the default language when ``None`` (with the fallback of
        :func:`~anatole.export.latex.to_latex`).
    reference_doc
        A Word document whose styles (fonts, headings, tables) the export takes, as pandoc's
        ``--reference-doc``.
    nomenclature_title, acronyms_title
        The headings of the two lists.

    Returns
    -------
    list[str]
        The problems of the conversion, by entry (``notation 'x': Word: \furlong is not
        converted (left out)``), also logged as warnings; the document is written anyway.

    Raises
    ------
    OfficeError
        If pandoc is not available or fails.
    NotationError
        If ``language`` is not declared.
    """
    language = resolve_language(notations, language)
    source = _Builder(notations, language).source(nomenclature_title, acronyms_title)
    command = [_pandoc(), "--from=latex", "--to=docx", "--verbose", f"--output={path}"]
    if reference_doc is not None:
        command.append(f"--reference-doc={reference_doc}")
    with tempfile.TemporaryDirectory() as directory:
        input_path = Path(directory) / "notations.tex"
        _ = input_path.write_text(source.text, encoding="utf-8")
        result = subprocess.run(
            [*command, str(input_path)], capture_output=True, text=True, check=False
        )
    if result.returncode != 0:
        raise OfficeError(f"pandoc failed: {result.stderr.strip()}")
    problems = _problems(result.stderr, source, notations)
    for problem in problems:
        _logger.warning("%s", problem)
    _logger.info("exported %d entries to %s (docx, %s)", len(notations), path, language)
    return problems
