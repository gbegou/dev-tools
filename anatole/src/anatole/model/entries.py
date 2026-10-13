r"""The entries of a notation set (notations, acronyms and abbreviations), styles and groups.

Every object validates itself on construction and raises a ``NotationError`` with a message
that names it and the field. What depends on the rest of the set (groups, references, styles,
languages) is checked by the notation set.
"""

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Literal, Self

from anatole.model.texts import (
    GROUP_KEY_PATTERN,
    NAME_PATTERN,
    SORT_PATTERN,
    TAG_PATTERN,
    NotationError,
    Rendered,
    Translated,
    check_rendered,
    check_translated,
    rename_references,
)

__all__ = [
    "MAX_ARGUMENTS",
    "MAX_GROUP_DEPTH",
    "RESERVED_NAMES",
    "Acronym",
    "Entry",
    "Group",
    "Item",
    "Notation",
    "Style",
]

MAX_ARGUMENTS = 9
"""The most arguments a LaTeX command takes."""

MAX_GROUP_DEPTH = 2
"""The most levels of groups (sections and subsections), as every export renders them."""

RESERVED_NAMES = frozenset(
    {
        # Defined by the exports.
        *("notationnomenclature", "notationacronyms", "notationglossaries"),
        *("notationheading", "notationtoplevel", "notationsublevel", "std"),
        # Typst keywords and constants.
        *("and", "as", "auto", "break", "context", "continue", "else", "false", "for", "if"),
        *("import", "in", "include", "let", "none", "not", "or", "return", "set", "show"),
        *("true", "while"),
    }
)
"""The names that cannot be used, as the exports define them or Typst keywords."""


def _check_name(owner: str, name: str) -> list[str]:
    if not NAME_PATTERN.fullmatch(name):
        return [f"{owner}: the name must be two letters or more (A-Z, a-z)"]
    if name in RESERVED_NAMES:
        return [f"{owner}: the name is reserved (a Typst keyword or an export's)"]
    if name.startswith("end"):
        return [f"{owner}: LaTeX does not define commands whose name starts with 'end'"]
    return []


def _check_placement(owner: str, group: str, sort: str, tags: tuple[str, ...]) -> list[str]:
    problems: list[str] = []
    if group and not all(GROUP_KEY_PATTERN.fullmatch(part) for part in group.split(".")):
        problems.append(
            f"{owner}: the group key must be keys of letters, digits, '_' or '-', joined by '.'"
        )
    if not SORT_PATTERN.fullmatch(sort):
        problems.append(f"{owner}: the sort key must be letters, digits, spaces, '_', '.' or '-'")
    problems.extend(
        f"{owner}: the tag {tag!r} must be letters, digits, '_' or '-'"
        for tag in tags
        if not TAG_PATTERN.fullmatch(tag)
    )
    if len(set(tags)) != len(tags):
        problems.append(f"{owner}: a tag is given twice")
    return problems


def _renamer(old: str, new: str) -> Callable[[str], str]:
    return lambda text: rename_references(text, old, new)


@dataclass(frozen=True, slots=True)
class Style:
    r"""A style: a template of one argument applied to symbols, such as the vector style.

    Styles are exported as commands (``\vect{x}``, ``vect(x)``) but are not listed in the
    nomenclature; a notation names its style, and its symbol is the argument.

    Parameters
    ----------
    name
        The command name (letters only, two or more).
    template
        The template in each format, with ``#1`` for the argument (``\boldsymbol{#1}``,
        ``bold(#1)``).
    description
        What the style is for, in each language; optional.

    Raises
    ------
    NotationError
        If a field is invalid; the message lists every problem.
    """

    name: str
    template: Rendered
    description: Translated = field(default_factory=Translated)

    def __post_init__(self) -> None:
        owner = f"style {self.name!r}"
        problems = _check_name(owner, self.name)
        problems.extend(
            check_rendered(owner, "template", self.template, required=True, arguments=1)
        )
        problems.extend(check_translated(owner, "description", self.description, required=False))
        if problems:
            raise NotationError(problems)

    def references(self) -> list[str]:
        """Return the names of the entries and styles this style uses."""
        return list(dict.fromkeys([*self.template.references(), *self.description.references()]))

    def renamed(self, old: str, new: str) -> Self:
        """Return a copy with the references to ``old`` renamed to ``new``."""
        rename = _renamer(old, new)
        return replace(
            self, template=self.template.map(rename), description=self.description.map(rename)
        )


@dataclass(frozen=True, slots=True)
class Notation:
    r"""A notation: a command name with its symbol, units and description.

    Placeholders ``#1`` to ``#9`` stand for the arguments in the symbol, in both formats; the
    texts may refer to other entries with ``@{name}``.

    Parameters
    ----------
    name
        The command name: letters only, two or more (``velocity`` gives ``\velocity`` in
        LaTeX and ``velocity`` in Typst).
    symbol
        The symbol in each format, as math-mode code without delimiters (``\mathbf{u}``,
        ``bold(u)``); with a style, the argument of the style (``u``).
    description
        The description in each language, as text-mode markup.
    units
        The units in each format, as text-mode markup; empty in both when there are none.
    group
        The key of the notation's group (``symbols.latin``); empty when it has none.
    arguments
        The number of arguments, 0 to ``MAX_ARGUMENTS`` (9).
    sort
        The sort key in the nomenclature; empty to sort by name.
    style
        The name of the style applied to the symbol; empty for none.
    tags
        The tags that select the notation for an export.

    Raises
    ------
    NotationError
        If a field is invalid; the message lists every problem.
    """

    name: str
    symbol: Rendered
    description: Translated
    units: Rendered = field(default_factory=Rendered)
    group: str = ""
    arguments: int = 0
    sort: str = ""
    style: str = ""
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        owner = f"notation {self.name!r}"
        problems = _check_name(owner, self.name)
        # bool is an int: reject it explicitly, as the TOML loader may pass one.
        if (
            isinstance(self.arguments, bool)
            or not isinstance(self.arguments, int)  # pyright: ignore[reportUnnecessaryIsInstance]
            or not 0 <= self.arguments <= MAX_ARGUMENTS
        ):
            problems.append(
                f"{owner}: arguments must be an integer from 0 to {MAX_ARGUMENTS}, "
                + f"not {self.arguments!r}"
            )
            arguments = 0
        else:
            arguments = self.arguments
        problems.extend(
            check_rendered(owner, "symbol", self.symbol, required=True, arguments=arguments)
        )
        problems.extend(check_translated(owner, "description", self.description))
        problems.extend(check_rendered(owner, "units", self.units, required=False))
        problems.extend(_check_placement(owner, self.group, self.sort, self.tags))
        if self.style and not NAME_PATTERN.fullmatch(self.style):
            problems.append(f"{owner}: the style must be the name of a style")
        if problems:
            raise NotationError(problems)

    @property
    def sort_key(self) -> tuple[str, str]:
        """The key that orders notations in a nomenclature.

        The sort key (or the name when it is empty), case-insensitively, then the name.
        """
        return ((self.sort or self.name).casefold(), self.name)

    def references(self) -> list[str]:
        """Return the names of the entries and styles this notation uses."""
        names = [
            *([self.style] if self.style else []),
            *self.symbol.references(),
            *self.description.references(),
            *self.units.references(),
        ]
        return list(dict.fromkeys(names))

    def renamed(self, old: str, new: str) -> Self:
        """Return a copy with the references to ``old`` (and its style) renamed to ``new``."""
        rename = _renamer(old, new)
        return replace(
            self,
            symbol=self.symbol.map(rename),
            description=self.description.map(rename),
            units=self.units.map(rename),
            style=new if self.style == old else self.style,
        )


@dataclass(frozen=True, slots=True)
class Acronym:
    r"""An acronym (expanded at first use) or an abbreviation (never expanded).

    Parameters
    ----------
    name
        The key (letters only, two or more): ``\ac{cfd}``, ``\gls{cfd}``, ``#cfd``.
    short
        The short form in each language (``CFD``, ``MFN``).
    long
        The long form in each language (``computational fluid dynamics``).
    description
        A description in each language; optional.
    group
        The key of the acronym's group; empty when it has none.
    sort
        The sort key in the lists; empty to sort by name.
    tags
        The tags that select the acronym for an export.
    abbreviation
        Whether it is an abbreviation (``w.r.t.``): shown short, never expanded.

    Raises
    ------
    NotationError
        If a field is invalid; the message lists every problem.
    """

    name: str
    short: Translated
    long: Translated
    description: Translated = field(default_factory=Translated)
    group: str = ""
    sort: str = ""
    tags: tuple[str, ...] = ()
    abbreviation: bool = False

    def __post_init__(self) -> None:
        kind = "abbreviation" if self.abbreviation else "acronym"
        owner = f"{kind} {self.name!r}"
        problems = _check_name(owner, self.name)
        problems.extend(check_translated(owner, "short", self.short))
        problems.extend(check_translated(owner, "long", self.long))
        problems.extend(check_translated(owner, "description", self.description, required=False))
        problems.extend(_check_placement(owner, self.group, self.sort, self.tags))
        if problems:
            raise NotationError(problems)

    @property
    def kind(self) -> Literal["acronym", "abbreviation"]:
        """``acronym`` or ``abbreviation``."""
        return "abbreviation" if self.abbreviation else "acronym"

    @property
    def sort_key(self) -> tuple[str, str]:
        """The key that orders acronyms in a list.

        The sort key (or the name when it is empty), case-insensitively, then the name.
        """
        return ((self.sort or self.name).casefold(), self.name)

    def references(self) -> list[str]:
        """Return the names of the entries this acronym uses."""
        names = [*self.short.references(), *self.long.references()]
        return list(dict.fromkeys([*names, *self.description.references()]))

    def renamed(self, old: str, new: str) -> Self:
        """Return a copy with the references to ``old`` renamed to ``new``."""
        rename = _renamer(old, new)
        return replace(
            self,
            short=self.short.map(rename),
            long=self.long.map(rename),
            description=self.description.map(rename),
        )


type Entry = Notation | Acronym
"""An entry of the lists: a notation, an acronym or an abbreviation."""

type Item = Entry | Style
"""Anything with a name in a notation set: an entry or a style."""


@dataclass(frozen=True, slots=True)
class Group:
    """A group of entries, shown under its title in the lists.

    Groups form a tree of ``MAX_GROUP_DEPTH`` (2) levels: ``symbols`` is a section,
    ``symbols.latin`` a subsection of it.

    Parameters
    ----------
    key
        The key that entries refer to: keys of letters, digits, ``_`` and ``-``, joined by
        ``.`` from the section down.
    title
        The title, in each language.

    Raises
    ------
    NotationError
        If the key or the title is invalid.
    """

    key: str
    title: Translated

    def __post_init__(self) -> None:
        owner = f"group {self.key!r}"
        problems: list[str] = []
        parts = self.key.split(".")
        if not all(GROUP_KEY_PATTERN.fullmatch(part) for part in parts):
            problems.append(
                f"{owner}: the key must be keys of letters, digits, '_' or '-', joined by '.'"
            )
        elif len(parts) > MAX_GROUP_DEPTH:
            problems.append(
                f"{owner}: groups have at most {MAX_GROUP_DEPTH} levels (a section and its "
                + "subsections)"
            )
        problems.extend(check_translated(owner, "title", self.title))
        if problems:
            raise NotationError(problems)

    @property
    def parent(self) -> str:
        """The key of the parent group; empty for a section."""
        return self.key.rpartition(".")[0]

    @property
    def depth(self) -> int:
        """1 for a section, 2 for a subsection."""
        return self.key.count(".") + 1
