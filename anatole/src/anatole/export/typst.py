"""Export to Typst: styles, notations and acronyms as variables or functions, and their lists.

The exported file is imported where the notations are used::

    #import "notations.typ": *
    $velocity = norm(x)$, #cfd then #cfd
    #notation-nomenclature()
    #notation-acronyms()

An acronym prints its long form with its short form at its first use, then its short form; an
abbreviation always prints its short form. The helpers have hyphenated names
(``notation-nomenclature``, ``anatole-acronym``...), which no entry name can take.
"""

import re
from typing import final

from anatole.export._common import expand, resolve_language, symbol
from anatole.model import Acronym, Entry, Notation, NotationSet, Section, Style, Translated
from anatole.typing import Language

__all__ = ["MINIMUM_TYPST_VERSION", "to_typst"]

MINIMUM_TYPST_VERSION = "0.13"
"""The oldest Typst version that compiles the export (it uses the ``std`` module)."""

_PLACEHOLDER = re.compile(r"#(\d)")


def _string(text: str) -> str:
    """Return ``text`` as a Typst string literal."""
    escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def _function(name: str, arguments: int, body: str) -> str:
    parameters = ", ".join(f"arg{index}" for index in range(1, arguments + 1))
    body = _PLACEHOLDER.sub(r"#(arg\1)", body)
    # An anonymous function does not see its own name, so an entry can use the builtin it
    # shadows (``#let norm = (arg1) => $norm(#(arg1))$``) without recursing.
    return f"#let {name} = ({parameters}) => ${body}$"


@final
class _Writer:
    def __init__(self, notations: NotationSet, language: Language) -> None:
        self.notations = notations
        self.language = language
        self.default = notations.default_language

    def text(self, value: str) -> str:
        return expand(value, "typst", self.notations, "text")

    def content(self, value: Translated) -> str:
        if not len(value):
            return "none"
        return f"[{self.text(value.resolve(self.language, self.default).typst)}]"

    def definition(self, item: Style | Entry) -> str:
        match item:
            case Style():
                return _function(
                    item.name, 1, expand(item.template.typst, "typst", self.notations, "math")
                )
            case Notation() if item.arguments:
                return _function(item.name, item.arguments, symbol(item, "typst", self.notations))
            case Notation():
                return f"#let {item.name} = ${symbol(item, 'typst', self.notations)}$"
            case Acronym():
                expand_first = "false" if item.abbreviation else "true"
                return (
                    f"#let {item.name} = anatole-acronym({_string(item.name)}, "
                    + f"{self.content(item.short)}, {self.content(item.long)}, "
                    + f"expand: {expand_first})"
                )

    def entry(self, entry: Entry) -> str:
        if isinstance(entry, Notation):
            call = entry.name
            if entry.arguments:
                call += "(" + ", ".join(["std.sym.dot.c"] * entry.arguments) + ")"
            units = f"[{self.text(entry.units.typst)}]" if entry.units.typst else "none"
            return (
                f"(name: {_string(entry.name)}, symbol: {call}, "
                + f"description: {self.content(entry.description)}, units: {units})"
            )
        return (
            f"(name: {_string(entry.name)}, short: {self.content(entry.short)}, "
            + f"long: {self.content(entry.long)}, "
            + f"description: {self.content(entry.description)}, "
            + f"abbreviation: {'true' if entry.abbreviation else 'false'})"
        )

    def section(self, section: Section, indent: str) -> list[str]:
        group = section.group
        key = "none" if group is None else _string(group.key)
        title = (
            "none"
            if group is None
            else f"[{self.text(group.title.resolve(self.language, self.default).typst)}]"
        )
        lines = [f"{indent}(", f"{indent}  key: {key},", f"{indent}  title: {title},"]
        lines.append(f"{indent}  entries: (")
        lines.extend(f"{indent}    {self.entry(entry)}," for entry in section.entries)
        lines.append(f"{indent}  ),")
        lines.append(f"{indent}  subsections: (")
        for sub in section.subsections:
            lines.extend(self.section(sub, indent + "    "))
        lines.extend([f"{indent}  ),", f"{indent}),"])
        return lines

    def sections(self, name: str, kind: str) -> list[str]:
        lines = [f"#let {name} = ("]
        for section in self.notations.sections("notation" if kind == "notation" else "acronym"):
            lines.extend(self.section(section, "  "))
        lines.append(")")
        return lines


_HELPERS = """\
/// Acronyms: the long form with the short one at the first use (unless `expand` is false),
/// the short form afterwards.
#let anatole-acronyms-used = state("anatole-acronyms-used", ())
#let anatole-acronym(key, short, long, expand: true) = context {
  let first = expand and key not in anatole-acronyms-used.get()
  anatole-acronyms-used.update(used => if key in used { used } else { used + (key,) })
  if first [#long (#short)] else [#short]
}
"""

_LISTS = """\
/// A list of sections: a heading, then a grid with a row per entry and a row per group title.
#let anatole-list(
  sections,
  row,
  title: none,
  columns: (auto, 1fr, auto),
  align: (left, left, right),
  column-gutter: 1em,
  row-gutter: 0.8em,
  section-title: title => std.text(size: 1.1em, std.strong(title)),
  subsection-title: title => std.strong(title),
) = {
  if title != none { std.heading(numbering: none, title) }
  let cells = ()
  let span(content) = std.grid.cell(colspan: columns.len(), content)
  for section in sections {
    if section.title != none { cells.push(span(section-title(section.title))) }
    for entry in section.entries { cells += row(entry) }
    for sub in section.subsections {
      cells.push(span(subsection-title(sub.title)))
      for entry in sub.entries { cells += row(entry) }
    }
  }
  std.grid(
    columns: columns,
    align: align,
    column-gutter: column-gutter,
    row-gutter: row-gutter,
    ..cells,
  )
}

/// The nomenclature: symbol, description and units of each notation, by group.
#let notation-nomenclature(title: [Nomenclature], ..options) = anatole-list(
  notation-groups,
  entry => (entry.symbol, entry.description, entry.units),
  title: title,
  ..options,
)

/// The list of acronyms and abbreviations: short form, long form (and description), by group.
#let notation-acronyms(title: [Acronyms], ..options) = anatole-list(
  acronym-groups,
  entry => (
    entry.short,
    if entry.description == none { entry.long } else [#entry.long: #entry.description],
    none,
  ),
  title: title,
  ..options,
)
"""


def to_typst(
    notations: NotationSet, *, language: Language | None = None, source: str | None = None
) -> str:
    """Return the Typst file of ``notations``.

    Each style becomes a function of one argument (``#let vect = (arg1) => $bold(#(arg1))$``);
    each notation a variable (``#let velocity = $vect(u)$``), or a function of its
    arguments, whose placeholders ``#1``... become the parameters ``arg1``...; each acronym a
    content that expands at its first use. They are defined after the entries they use. The
    references ``@{name}`` become ``#name`` (``name`` for a function in math).

    ``notation-groups`` and ``acronym-groups`` hold the lists as trees of sections (the
    entries without a group first, under a ``none`` title); ``notation-nomenclature()`` and
    ``notation-acronyms()`` print them; the arguments of a function are shown as ``dot.c``.

    Parameters
    ----------
    notations
        The notations.
    language
        The language of the descriptions, titles and acronyms: the default language of
        ``notations`` when ``None``. A missing translation falls back on the default language,
        with a warning in the log.
    source
        The notation file, named in the header comment.

    Raises
    ------
    NotationError
        If ``language`` is not declared.
    """
    language = resolve_language(notations, language)
    writer = _Writer(notations, language)
    origin = f" from {source}" if source else ""
    lines = [
        f"// Generated by anatole{origin}, in {language}: edit the notation file, not this one.",
        f"// Typst {MINIMUM_TYPST_VERSION} or later. Use:",
        '//   #import "<this file>": *',
        "//   $velocity$ in math, #cfd for an acronym, and where the lists go:",
        "//   #notation-nomenclature() and #notation-acronyms().",
        "",
        _HELPERS,
        "// Styles, notations and acronyms",
        *(writer.definition(item) for item in notations.ordered()),
        "",
        "// Lists",
        *writer.sections("notation-groups", "notation"),
        *writer.sections("acronym-groups", "acronym"),
        "",
        _LISTS.rstrip("\n"),
    ]
    return "\n".join(lines) + "\n"
