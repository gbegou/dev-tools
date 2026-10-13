r"""Export to LaTeX: commands for styles and notations, and the lists, with one of two targets.

``nomencl+acro`` (the default)
    The notations go to a ``nomencl`` nomenclature (``\notationnomenclature`` declares the
    entries, before ``\printnomenclature``), the acronyms and abbreviations to ``acro``
    (``\ac{cfd}``; ``\notationacronyms`` prints their lists)::

        \usepackage{nomencl}
        \makenomenclature
        \usepackage{acro}
        \input{notations}
        ...
        \notationnomenclature \printnomenclature
        \notationacronyms

``glossaries``
    Everything goes to ``glossaries-extra``, with one glossary per group, sorted without an
    external tool (``\makenoidxglossaries``, which the file calls); acronyms are ``\gls{cfd}``
    and ``\notationglossaries`` prints every list::

        \usepackage[nomain]{glossaries-extra}
        \input{notations}
        ...
        \notationglossaries

The list headings use ``\notationtoplevel`` (``section``) for the sections and
``\notationsublevel`` (``subsection``) for the subsections: define them before ``\input`` to
change them (``chapter`` and ``section`` in a book).
"""

import string
from collections.abc import Callable, Iterator
from typing import Literal, final

from anatole.export._common import Context, expand, resolve_language, symbol
from anatole.model import Acronym, Entry, Notation, NotationError, NotationSet, Section, Style
from anatole.typing import Language

__all__ = ["MAX_GROUPS", "NOMENCLATURE_COMMAND", "TARGETS", "Definition", "Target", "to_latex"]

type Definition = Literal["newcommand", "renewcommand", "providecommand", "DeclareRobustCommand"]
"""The LaTeX command that defines each notation and style."""

type Target = Literal["nomencl+acro", "glossaries"]
"""The LaTeX packages the lists go to."""

TARGETS: tuple[Target, ...] = ("nomencl+acro", "glossaries")
"""The LaTeX targets, the default one first."""

NOMENCLATURE_COMMAND = "notationnomenclature"
"""The command that declares the nomencl entries (``nomencl+acro``)."""

MAX_GROUPS = len(string.ascii_uppercase) - 1
"""The most groups with notations that a nomencl nomenclature tells apart.

nomencl tells groups apart by the first letter of the sort prefix, and ``A`` is for the
notations without a group.
"""

_HEADINGS = r"""\providecommand{\notationtoplevel}{section}
\providecommand{\notationsublevel}{subsection}
\providecommand{\notationheading}[2]{\csname #1\endcsname*{#2}}"""


@final
class LatexWriter:
    """The texts of one export: language, fallback, and how references are written."""

    def __init__(
        self,
        notations: NotationSet,
        language: Language,
        acronym_command: str,
        acronym_text: Callable[[Acronym], str] | None = None,
    ) -> None:
        self.notations = notations
        self.language = language
        self.default = notations.default_language
        self.acronym_command = acronym_command
        self.acronym_text = acronym_text

    def text(self, value: str) -> str:
        """Return a text-mode text, references expanded."""
        return self._expand(value, "text")

    def math(self, value: str) -> str:
        """Return a math-mode text, references expanded."""
        return self._expand(value, "math")

    def _expand(self, value: str, context: Context) -> str:
        return expand(
            value,
            "latex",
            self.notations,
            context,
            acronym_command=self.acronym_command,
            acronym_text=self.acronym_text,
        )

    def description(self, entry: Entry | Style) -> str:
        if not len(entry.description):
            return ""
        return self.text(entry.description.resolve(self.language, self.default).latex)

    def title(self, section: Section) -> str:
        if section.group is None:
            return ""
        return self.text(section.group.title.resolve(self.language, self.default).latex)

    def short(self, acronym: Acronym) -> str:
        return self.text(acronym.short.resolve(self.language, self.default).latex)

    def long(self, acronym: Acronym) -> str:
        return self.text(acronym.long.resolve(self.language, self.default).latex)

    def definitions(self, definition: Definition) -> list[str]:
        """Return the commands of the styles and notations, each after the ones it uses."""
        lines: list[str] = []
        for item in self.notations.ordered():
            if isinstance(item, Style):
                body = self.math(item.template.latex)
                lines.append(rf"\{definition}{{\{item.name}}}[1]{{\ensuremath{{{body}}}}}")
            elif isinstance(item, Notation):
                arguments = f"[{item.arguments}]" if item.arguments else ""
                body = symbol(item, "latex", self.notations)
                lines.append(rf"\{definition}{{\{item.name}}}{arguments}{{\ensuremath{{{body}}}}}")
        return lines


def _call(notation: Notation) -> str:
    """Return the command of a notation, its arguments shown as dots."""
    return rf"\{notation.name}" + r"{\cdot}" * notation.arguments


def _flatten(sections: tuple[Section, ...]) -> Iterator[tuple[Section, int, bool]]:
    """Yield (section, depth, first-in-its-section) for every section that has entries."""
    for section in sections:
        if section.entries:
            yield section, 1, True
        for index, sub in enumerate(section.subsections):
            yield sub, 2, index == 0 and not section.entries


# nomencl + acro


def _nomencl(writer: LatexWriter) -> list[str]:
    sections = writer.notations.sections("notation")
    leaves = list(_flatten(sections))
    grouped = [leaf for leaf in leaves if leaf[0].group is not None]
    if len(grouped) > MAX_GROUPS:
        raise NotationError(
            f"latex: {len(grouped)} groups have notations, nomencl tells at most {MAX_GROUPS} apart"
        )
    parents = {s.group.key: s for s in sections if s.group is not None}
    lines = [
        "% Nomenclature (nomencl)",
        r"\providecommand{\nomunit}[1]{\renewcommand{\nomentryend}{\hspace*{\fill}#1}}",
    ]
    letters = iter(string.ascii_uppercase[1:])
    entries: list[str] = []
    headings: list[str] = []
    for section, depth, first in leaves:
        group = section.group
        letter = ("A" if group is None else next(letters)) if grouped else ""
        if group is not None:
            items: list[str] = []
            if depth == 2 and first:
                items.append(rf"\item[\large\bfseries {writer.title(parents[group.parent])}]")
            weight = r"\large\bfseries" if depth == 1 else r"\bfseries"
            items.append(rf"\item[{weight} {writer.title(section)}]")
            headings.append(rf"\@namedef{{notation@group@{letter}}}{{{''.join(items)}}}")
        for notation in section.entries:
            assert isinstance(notation, Notation)
            description = writer.description(notation)
            if notation.units.latex:
                description += rf"\nomunit{{{writer.text(notation.units.latex)}}}"
            prefix = letter + notation.sort_key[0]
            entries.append(rf"  \nomenclature[{prefix}]{{${_call(notation)}$}}{{{description}}}%")
    if headings:
        lines.extend(
            [
                r"\makeatletter",
                *headings,
                r"\renewcommand{\nomgroup}[1]{\@ifundefined{notation@group@#1}{}{%",
                r"  \@nameuse{notation@group@#1}}}",
                r"\makeatother",
            ]
        )
    lines.extend([rf"\newcommand{{\{NOMENCLATURE_COMMAND}}}{{%", *entries, "}"])
    return lines


def _acro_short(text: str) -> str:
    # acro adds the period at the end of a sentence itself: \acdot avoids a doubled period.
    return text[:-1] + r"\acdot" if text.endswith(".") else text


def _acro(writer: LatexWriter) -> list[str]:
    sections = writer.notations.sections("acronym")
    lines = ["% Acronyms and abbreviations (acro)"]
    for acronym in writer.notations.acronyms:
        properties = [
            f"short = {{{_acro_short(writer.short(acronym))}}}",
            f"long = {{{writer.long(acronym)}}}",
            f"tag = {{anatole-{acronym.group or 'none'}}}",
        ]
        if acronym.sort:
            properties.append(f"sort = {{{acronym.sort}}}")
        if acronym.abbreviation:
            properties.append("first-style = short")
        if description := writer.description(acronym):
            properties.append(f"extra = {{{description}}}")
        lines.append(rf"\DeclareAcronym{{{acronym.name}}}{{{', '.join(properties)}}}")
    lines.append(r"\newcommand{\notationacronyms}{%")
    for section, depth, first in _flatten(sections):
        if section.group is not None:
            if depth == 2 and first:
                parent = next(
                    s for s in sections if s.group and s.group.key == section.group.parent
                )
                lines.append(rf"  \notationheading{{\notationtoplevel}}{{{writer.title(parent)}}}%")
            level = r"\notationtoplevel" if depth == 1 else r"\notationsublevel"
            lines.append(rf"  \notationheading{{{level}}}{{{writer.title(section)}}}%")
        tag = f"anatole-{section.group.key if section.group else 'none'}"
        lines.append(rf"  \printacronyms[include={tag}, heading=none, display=all]%")
    lines.append("}")
    return lines


# glossaries


def _glossary_name(section: Section) -> str:
    return f"anatole-{section.group.key if section.group else 'none'}"


def _glossaries(writer: LatexWriter) -> list[str]:
    sections = writer.notations.sections()
    leaves = list(_flatten(sections))
    lines = [
        "% Glossaries (glossaries-extra), one per group, sorted in their order of definition",
        r"\makenoidxglossaries",
        r"\setabbreviationstyle[acronym]{long-short}",
        r"\setabbreviationstyle[abbreviation]{short-nolong}",
        r"\glssetcategoryattribute{abbreviation}{discardperiod}{true}",
    ]
    for section, _, _ in leaves:
        lines.append(rf"\newglossary*{{{_glossary_name(section)}}}{{{writer.title(section)}}}")
    for section, _, _ in leaves:
        glossary = _glossary_name(section)
        for entry in section.entries:
            if isinstance(entry, Notation):
                fields = [
                    f"type={glossary}",
                    rf"name={{${_call(entry)}$}}",
                    f"description={{{writer.description(entry)}}}",
                    f"sort={{{entry.sort_key[0]}}}",
                ]
                if entry.units.latex:
                    fields.append(f"symbol={{{writer.text(entry.units.latex)}}}")
                lines.append(rf"\newglossaryentry{{{entry.name}}}{{{', '.join(fields)}}}")
            else:
                command = "newabbreviation" if entry.abbreviation else "newacronym"
                options = [f"type={glossary}", f"sort={{{entry.sort_key[0]}}}"]
                if entry.abbreviation:
                    options.append("category=abbreviation")
                if description := writer.description(entry):
                    options.append(f"description={{{description}}}")
                lines.append(
                    rf"\{command}[{', '.join(options)}]{{{entry.name}}}"
                    + f"{{{writer.short(entry)}}}{{{writer.long(entry)}}}"
                )
    lines.extend([r"\newcommand{\notationglossaries}{%", r"  \glsaddallunused"])
    parents = {s.group.key: s for s in sections if s.group is not None}
    for section, depth, first in leaves:
        if section.group is not None:
            if depth == 2 and first:
                title = writer.title(parents[section.group.parent])
                lines.append(rf"  \notationheading{{\notationtoplevel}}{{{title}}}%")
            level = r"\notationtoplevel" if depth == 1 else r"\notationsublevel"
            lines.append(rf"  \notationheading{{{level}}}{{{writer.title(section)}}}%")
        style = "long4col" if any(isinstance(e, Notation) for e in section.entries) else "long"
        lines.append(
            r"  {\renewcommand*{\glossarysection}[2][]{}"
            + rf"\printnoidxglossary[type={_glossary_name(section)}, sort=def, "
            + f"style={style}, nonumberlist]}}%"
        )
    lines.append("}")
    return lines


def to_latex(
    notations: NotationSet,
    *,
    language: Language | None = None,
    target: Target = "nomencl+acro",
    source: str | None = None,
    definition: Definition = "newcommand",
) -> str:
    r"""Return the LaTeX file of ``notations``.

    Each style becomes a command of one argument (``\vect{x}``), each notation a command
    usable in text and math (``\newcommand{\velocity}{\ensuremath{\vect{u}}}``); the
    references ``@{name}`` become commands, or ``\ac{cfd}`` (acro) and ``\gls{cfd}``
    (glossaries) for acronyms. The lists follow the tree of groups, with section and subsection
    titles; the units go to ``\nomunit`` (nomencl, defined when nomencl does not define it) or
    the symbol column (glossaries); the arguments of a command are shown as ``\cdot``.

    Parameters
    ----------
    notations
        The notations.
    language
        The language of the descriptions, titles and acronyms: the default language of
        ``notations`` when ``None``. A missing translation falls back on the default language,
        with a warning in the log.
    target
        The packages the lists go to: ``nomencl+acro`` or ``glossaries``.
    source
        The notation file, named in the header comment.
    definition
        The command that defines each notation and style: ``newcommand`` (the default) fails
        on a name that LaTeX or a package already defines.

    Raises
    ------
    NotationError
        If more than :data:`~anatole.export.latex.MAX_GROUPS` groups have notations
        (nomencl), or ``language`` is not declared.
    """
    language = resolve_language(notations, language)
    writer = LatexWriter(notations, language, "ac" if target == "nomencl+acro" else "gls")
    origin = f" from {source}" if source else ""
    lines = [
        f"% Generated by anatole{origin}, in {language}, for {target}: edit the notation "
        + "file, not this one.",
    ]
    if target == "nomencl+acro":
        lines.extend(
            [
                r"% In the preamble, after \usepackage{nomencl}, \makenomenclature and",
                r"% \usepackage{acro}: \input{<this file>}. In the document: \velocity,",
                r"% \ac{cfd}, and where the lists go: \notationnomenclature\printnomenclature",
                r"% and \notationacronyms.",
            ]
        )
    else:
        lines.extend(
            [
                r"% In the preamble, after \usepackage[nomain]{glossaries-extra}:",
                r"% \input{<this file>}. In the document: \velocity, \gls{cfd}, and where the",
                r"% lists go: \notationglossaries.",
            ]
        )
    lines.extend(["", "% Styles and notations", *writer.definitions(definition), "", _HEADINGS, ""])
    if target == "nomencl+acro":
        lines.extend([*_nomencl(writer), "", *_acro(writer)])
    else:
        lines.extend(_glossaries(writer))
    return "\n".join(lines) + "\n"
