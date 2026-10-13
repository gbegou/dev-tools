r"""Notations, groups and the set that holds them.

A notation has a command name (``\velocity`` in LaTeX, ``#velocity`` in Typst), a symbol and
optional units, written once per target format (:class:`Rendered`), and a description, written
once per natural language (:class:`Translated`), each translation once per format. Every object
validates itself on construction and raises :class:`NotationError` with a message that names
the notation and the field.
"""

import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field, replace
from typing import ClassVar, override

from notation_manager.typing import FORMATS, Format, Language

__all__ = [
    "GROUP_KEY_PATTERN",
    "LANGUAGE_PATTERN",
    "MAX_ARGUMENTS",
    "NAME_PATTERN",
    "RESERVED_NAMES",
    "SORT_PATTERN",
    "Group",
    "Notation",
    "NotationError",
    "NotationSet",
    "Rendered",
    "Translated",
]

NAME_PATTERN = re.compile(r"[A-Za-z]{2,}")
"""The pattern of a command name.

Two letters or more: a LaTeX control word, and a Typst identifier that math mode does not read
as a single letter.
"""

GROUP_KEY_PATTERN = re.compile(r"[A-Za-z0-9_-]+")
"""The pattern of a group key (a bare TOML key)."""

LANGUAGE_PATTERN = re.compile(r"[a-z]{2,3}(-[A-Za-z0-9]{2,8})*")
"""The pattern of a language code, such as ``en``, ``fr`` or ``pt-BR`` (a BCP 47 tag, as Typst
uses)."""

SORT_PATTERN = re.compile(r"[A-Za-z0-9 _.-]*")
"""The pattern of a sort key, made of characters that makeindex sorts without quoting."""

MAX_ARGUMENTS = 9
"""The most arguments a LaTeX command takes."""

RESERVED_NAMES = frozenset(
    {
        # Defined by the exports.
        "notationnomenclature",
        "std",
        # Typst keywords and constants.
        *("and", "as", "auto", "break", "context", "continue", "else", "false", "for", "if"),
        *("import", "in", "include", "let", "none", "not", "or", "return", "set", "show"),
        *("true", "while"),
    }
)
"""The command names that cannot be used, as the exports define them or Typst keywords."""

_PLACEHOLDER = re.compile(r"#(\d)")


class NotationError(ValueError):
    """An invalid notation, group or notation file.

    Attributes
    ----------
    problems
        One message per problem found, each naming the notation (or group) and the field.
    """

    problems: tuple[str, ...]

    def __init__(self, problems: str | Iterable[str]) -> None:
        self.problems = (problems,) if isinstance(problems, str) else tuple(problems)
        super().__init__("\n".join(self.problems))


@dataclass(frozen=True, slots=True)
class Rendered:
    r"""A text written once per target format.

    Parameters
    ----------
    latex
        The LaTeX text.
    typst
        The Typst text.
    """

    latex: str = ""
    typst: str = ""

    @classmethod
    def both(cls, text: str) -> "Rendered":
        """Return a rendering that is the same text in every format."""
        return cls(latex=text, typst=text)

    def get(self, fmt: Format) -> str:
        """Return the text in the format ``fmt``."""
        return self.latex if fmt == "latex" else self.typst

    def with_text(self, fmt: Format, text: str) -> "Rendered":
        """Return a copy with the text in the format ``fmt`` replaced by ``text``."""
        if fmt == "latex":
            return Rendered(latex=text, typst=self.typst)
        return Rendered(latex=self.latex, typst=text)

    @property
    def is_empty(self) -> bool:
        """Whether the text is empty in every format."""
        return not self.latex and not self.typst

    @property
    def is_uniform(self) -> bool:
        """Whether the text is the same in every format."""
        return self.latex == self.typst


class Translated:
    """A text written once per natural language, each translation once per format.

    Parameters
    ----------
    texts
        The translations by language code; a string is the same text in every format.
        ``Translated({"en": "Velocity", "fr": "Vitesse"})``.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_texts",)

    _texts: tuple[tuple[Language, Rendered], ...]

    def __init__(self, texts: Mapping[Language, str | Rendered] | None = None) -> None:
        self._texts = tuple(
            (language, Rendered.both(text) if isinstance(text, str) else text)
            for language, text in (texts or {}).items()
        )

    @property
    def languages(self) -> tuple[Language, ...]:
        """The languages of the translations, in order."""
        return tuple(language for language, _ in self._texts)

    def items(self) -> tuple[tuple[Language, Rendered], ...]:
        """Return the translations, as (language, text) pairs."""
        return self._texts

    def get(self, language: Language) -> Rendered | None:
        """Return the translation in ``language``, ``None`` if there is none."""
        return next((text for code, text in self._texts if code == language), None)

    def __getitem__(self, language: Language) -> Rendered:
        text = self.get(language)
        if text is None:
            raise KeyError(f"no translation in {language!r}")
        return text

    def __contains__(self, language: object) -> bool:
        return language in self.languages

    def __len__(self) -> int:
        return len(self._texts)

    def resolve(self, language: Language, fallback: Language) -> Rendered:
        """Return the translation in ``language``, or in ``fallback`` when there is none.

        Raises
        ------
        KeyError
            If there is a translation in neither.
        """
        text = self.get(language)
        return text if text is not None else self[fallback]

    def with_text(self, language: Language, text: str | Rendered) -> "Translated":
        """Return a copy with the translation in ``language`` set to ``text``.

        A new language is added last.
        """
        texts = dict(self._texts)
        texts[language] = Rendered.both(text) if isinstance(text, str) else text
        return Translated(texts)

    def only(self, languages: Iterable[Language]) -> "Translated":
        """Return a copy with the translations in ``languages`` only, in that order."""
        texts = dict(self._texts)
        return Translated(
            {language: texts[language] for language in languages if language in texts}
        )

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Translated):
            return NotImplemented
        return self._texts == other._texts

    @override
    def __hash__(self) -> int:
        return hash(self._texts)

    @override
    def __repr__(self) -> str:
        return f"Translated({dict(self._texts)!r})"


def _unbalanced_braces(text: str) -> bool:
    r"""Whether the braces of a LaTeX text do not balance (``\{`` and ``\}`` are skipped)."""
    depth = 0
    escaped = False
    for char in text:
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth < 0:
                return True
    return depth != 0


def _check_rendered(
    owner: str, field_name: str, value: Rendered, *, required: bool, arguments: int = 0
) -> list[str]:
    """Return the problems of one rendered field (an empty list when it is valid)."""
    problems: list[str] = []
    missing = [fmt for fmt in FORMATS if not value.get(fmt).strip()]
    if required and missing:
        problems.extend(f"{owner}: {field_name} is empty in {fmt}" for fmt in missing)
    elif not required and len(missing) == 1:
        present = next(fmt for fmt in FORMATS if fmt not in missing)
        problems.append(f"{owner}: {field_name} is given in {present} but empty in {missing[0]}")
    if _unbalanced_braces(value.latex):
        problems.append(f"{owner}: {field_name} has unbalanced braces in latex: {value.latex}")
    for fmt in FORMATS:
        for match in _PLACEHOLDER.finditer(value.get(fmt)):
            index = int(match.group(1))
            if not 1 <= index <= arguments:
                expected = f"#1 to #{arguments}" if arguments else "no placeholder"
                problems.append(
                    f"{owner}: {field_name} uses {match.group(0)} in {fmt}, "
                    + f"but the notation takes {arguments} argument(s) ({expected})"
                )
    return problems


def _check_translated(owner: str, field_name: str, value: Translated) -> list[str]:
    """Return the problems of one translated field.

    It needs at least one translation, valid language codes, and each translation given in
    every format.
    """
    if not len(value):
        return [f"{owner}: {field_name} has no translation"]
    problems: list[str] = []
    for language, text in value.items():
        if not LANGUAGE_PATTERN.fullmatch(language):
            problems.append(
                f"{owner}: {field_name} has an invalid language code {language!r} "
                + "(expected a code like en, fr or pt-BR)"
            )
        problems.extend(_check_rendered(owner, f"{field_name} ({language})", text, required=True))
    return problems


@dataclass(frozen=True, slots=True)
class Group:
    """A group of notations, shown under its title in the nomenclature.

    Parameters
    ----------
    key
        The key that notations refer to (letters, digits, ``_`` and ``-``).
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
        if not GROUP_KEY_PATTERN.fullmatch(self.key):
            problems.append(f"{owner}: the key must be letters, digits, '_' or '-'")
        problems.extend(_check_translated(owner, "title", self.title))
        if problems:
            raise NotationError(problems)


@dataclass(frozen=True, slots=True)
class Notation:
    r"""A notation: a command name with its symbol, units and description.

    Placeholders ``#1`` to ``#9`` stand for the arguments in the symbol, in both formats.

    Parameters
    ----------
    name
        The command name: letters only, two or more (``velocity`` gives ``\velocity`` in
        LaTeX and ``velocity`` in Typst).
    symbol
        The symbol in each format, as math-mode code without delimiters (``\mathbf{u}``,
        ``bold(u)``).
    description
        The description in each language, as text-mode markup.
    units
        The units in each format, as text-mode markup; empty in both when there are none.
    group
        The key of the notation's group; empty when it has none.
    arguments
        The number of arguments, 0 to :data:`MAX_ARGUMENTS`.
    sort
        The sort key in the nomenclature; empty to sort by name.

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

    def __post_init__(self) -> None:
        owner = f"notation {self.name!r}"
        problems: list[str] = []
        if not NAME_PATTERN.fullmatch(self.name):
            problems.append(f"{owner}: the name must be two letters or more (A-Z, a-z)")
        elif self.name in RESERVED_NAMES:
            problems.append(f"{owner}: the name is reserved (a Typst keyword or an export's)")
        elif self.name.startswith("end"):
            problems.append(f"{owner}: LaTeX does not define commands whose name starts with 'end'")
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
            _check_rendered(owner, "symbol", self.symbol, required=True, arguments=arguments)
        )
        problems.extend(_check_translated(owner, "description", self.description))
        problems.extend(_check_rendered(owner, "units", self.units, required=False))
        if self.group and not GROUP_KEY_PATTERN.fullmatch(self.group):
            problems.append(f"{owner}: the group key must be letters, digits, '_' or '-'")
        if not SORT_PATTERN.fullmatch(self.sort):
            problems.append(
                f"{owner}: the sort key must be letters, digits, spaces, '_', '.' or '-'"
            )
        if problems:
            raise NotationError(problems)

    @property
    def sort_key(self) -> tuple[str, str]:
        """The key that orders notations in a nomenclature.

        The sort key (or the name when it is empty), case-insensitively, then the name.
        """
        return ((self.sort or self.name).casefold(), self.name)


def _check_languages(languages: tuple[Language, ...]) -> list[str]:
    problems: list[str] = []
    if not languages:
        problems.append("languages: at least one language is needed")
    for language in languages:
        if not LANGUAGE_PATTERN.fullmatch(language):
            problems.append(
                f"languages: invalid language code {language!r} (expected a code like en, fr or "
                + "pt-BR)"
            )
        if languages.count(language) > 1:
            problems.append(f"languages: {language!r} is declared twice")
    return list(dict.fromkeys(problems))


class NotationSet:
    r"""An ordered collection of notations, by name, with their groups and languages.

    Parameters
    ----------
    notations
        The notations, in the order they are kept (and saved).
    groups
        The groups, in the order of the nomenclature.
    languages
        The languages of the descriptions and group titles; the first one is the default
        language, in which every description and title is required. The other translations
        are optional: the exports fall back on the default language.

    Raises
    ------
    NotationError
        If two notations or two groups share a name, a notation refers to an unknown group,
        a language is invalid, or a translation is missing in the default language or is in a
        language not declared; the message lists every problem.
    """

    def __init__(
        self,
        notations: Iterable[Notation] = (),
        groups: Iterable[Group] = (),
        languages: Iterable[Language] = ("en",),
    ) -> None:
        self._languages: tuple[Language, ...] = tuple(languages)
        self._groups: dict[str, Group] = {}
        self._notations: dict[str, Notation] = {}
        problems = _check_languages(self._languages)
        if problems:
            raise NotationError(problems)
        for group in groups:
            if group.key in self._groups:
                problems.append(f"group {group.key!r}: defined twice")
            problems.extend(
                self._translation_problems(f"group {group.key!r}", "title", group.title)
            )
            self._groups[group.key] = group
        for notation in notations:
            if notation.name in self._notations:
                problems.append(f"notation {notation.name!r}: defined twice")
            else:
                problems.extend(self._notation_problems(notation))
            self._notations[notation.name] = notation
        if problems:
            raise NotationError(problems)

    def _translation_problems(self, owner: str, field_name: str, value: Translated) -> list[str]:
        problems: list[str] = []
        if self.default_language not in value:
            problems.append(
                f"{owner}: {field_name} is missing in the default language {self.default_language}"
            )
        problems.extend(
            f"{owner}: {field_name} is in {language}, which is not a declared language "
            + f"({', '.join(self._languages)})"
            for language in value.languages
            if language not in self._languages
        )
        return problems

    def _notation_problems(self, notation: Notation) -> list[str]:
        owner = f"notation {notation.name!r}"
        problems = self._translation_problems(owner, "description", notation.description)
        if notation.group and notation.group not in self._groups:
            problems.append(f"{owner}: unknown group {notation.group!r}")
        return problems

    # Languages

    @property
    def languages(self) -> tuple[Language, ...]:
        """The languages, the default one first."""
        return self._languages

    @property
    def default_language(self) -> Language:
        """The default language, in which every description and title has a translation."""
        return self._languages[0]

    def set_languages(self, languages: Iterable[Language]) -> None:
        """Change the languages; the first one becomes the default language.

        The translations in the languages removed are dropped.

        Raises
        ------
        NotationError
            If a language is invalid, or a description or title has no translation in the new
            default language; nothing is changed then.
        """
        languages = tuple(languages)
        problems = _check_languages(languages)
        if problems:
            raise NotationError(problems)
        default = languages[0]
        problems.extend(
            f"group {group.key!r}: title is missing in the new default language {default}"
            for group in self._groups.values()
            if default not in group.title
        )
        problems.extend(
            f"notation {notation.name!r}: description is missing in the new default language "
            + default
            for notation in self
            if default not in notation.description
        )
        if problems:
            raise NotationError(problems)
        self._languages = languages
        self._groups = {
            key: replace(group, title=group.title.only(languages))
            for key, group in self._groups.items()
        }
        self._notations = {
            name: replace(notation, description=notation.description.only(languages))
            for name, notation in self._notations.items()
        }

    def missing_translations(self, languages: Iterable[Language] | None = None) -> list[str]:
        """Return the translations missing in ``languages`` (by default, every language).

        One message each: ``notation 'velocity': description is missing in fr``.
        """
        missing: list[str] = []
        for language in self._languages if languages is None else languages:
            missing.extend(
                f"group {group.key!r}: title is missing in {language}"
                for group in self._groups.values()
                if language not in group.title
            )
            missing.extend(
                f"notation {notation.name!r}: description is missing in {language}"
                for notation in self
                if language not in notation.description
            )
        return missing

    def check_language(self, language: Language) -> None:
        """Check that ``language`` is declared.

        Raises
        ------
        NotationError
            If it is not.
        """
        if language not in self._languages:
            raise NotationError(
                f"language {language!r} is not declared ({', '.join(self._languages)})"
            )

    # Notations

    def __len__(self) -> int:
        return len(self._notations)

    def __iter__(self) -> Iterator[Notation]:
        return iter(self._notations.values())

    def __contains__(self, name: object) -> bool:
        return name in self._notations

    def __getitem__(self, name: str) -> Notation:
        try:
            return self._notations[name]
        except KeyError:
            raise KeyError(f"no notation named {name!r}") from None

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, NotationSet):
            return NotImplemented
        return (
            self._languages == other._languages
            and list(self._notations.items()) == list(other._notations.items())
            and list(self._groups.items()) == list(other._groups.items())
        )

    __hash__: ClassVar[None] = None  # pyright: ignore[reportIncompatibleMethodOverride]  # mutable

    @override
    def __repr__(self) -> str:
        return (
            f"NotationSet({len(self._notations)} notations, {len(self._groups)} groups, "
            + f"languages {', '.join(self._languages)})"
        )

    def add(self, notation: Notation) -> None:
        """Add a notation at the end.

        Raises
        ------
        NotationError
            If the name is taken, the group is unknown, or the description is not in the
            default language or is in a language not declared.
        """
        if notation.name in self._notations:
            raise NotationError(f"notation {notation.name!r}: the name is already taken")
        if problems := self._notation_problems(notation):
            raise NotationError(problems)
        self._notations[notation.name] = notation

    def replace(self, name: str, notation: Notation) -> None:
        """Replace the notation ``name`` by ``notation``, at the same position.

        The new notation may have another name (a rename).

        Raises
        ------
        KeyError
            If there is no notation ``name``.
        NotationError
            If the new name is taken by another notation, the group is unknown, or the
            description is not in the default language or is in a language not declared.
        """
        if name not in self._notations:
            raise KeyError(f"no notation named {name!r}")
        if notation.name != name and notation.name in self._notations:
            raise NotationError(f"notation {notation.name!r}: the name is already taken")
        if problems := self._notation_problems(notation):
            raise NotationError(problems)
        self._notations = {
            (notation.name if key == name else key): (notation if key == name else value)
            for key, value in self._notations.items()
        }

    def remove(self, name: str) -> Notation:
        """Remove the notation ``name`` and return it.

        Raises
        ------
        KeyError
            If there is no notation ``name``.
        """
        try:
            return self._notations.pop(name)
        except KeyError:
            raise KeyError(f"no notation named {name!r}") from None

    # Groups

    @property
    def groups(self) -> tuple[Group, ...]:
        """The groups, in the order of the nomenclature."""
        return tuple(self._groups.values())

    def group(self, key: str) -> Group:
        """Return the group ``key``.

        Raises
        ------
        KeyError
            If there is no group ``key``.
        """
        try:
            return self._groups[key]
        except KeyError:
            raise KeyError(f"no group with key {key!r}") from None

    def add_group(self, group: Group) -> None:
        """Add a group at the end.

        Raises
        ------
        NotationError
            If the key is taken, or the title is not in the default language or is in a
            language not declared.
        """
        if group.key in self._groups:
            raise NotationError(f"group {group.key!r}: the key is already taken")
        if problems := self._translation_problems(f"group {group.key!r}", "title", group.title):
            raise NotationError(problems)
        self._groups[group.key] = group

    def replace_group(self, key: str, group: Group) -> None:
        """Replace the group ``key`` by ``group``, at the same position.

        When the key changes, the notations of the group follow it.

        Raises
        ------
        KeyError
            If there is no group ``key``.
        NotationError
            If the new key is taken by another group, or the title is not in the default
            language or is in a language not declared.
        """
        if key not in self._groups:
            raise KeyError(f"no group with key {key!r}")
        if group.key != key and group.key in self._groups:
            raise NotationError(f"group {group.key!r}: the key is already taken")
        if problems := self._translation_problems(f"group {group.key!r}", "title", group.title):
            raise NotationError(problems)
        self._groups = {
            (group.key if old == key else old): (group if old == key else value)
            for old, value in self._groups.items()
        }
        if group.key != key:
            for name, notation in self._notations.items():
                if notation.group == key:
                    self._notations[name] = replace(notation, group=group.key)

    def remove_group(self, key: str) -> Group:
        """Remove the group ``key`` and return it.

        Raises
        ------
        KeyError
            If there is no group ``key``.
        NotationError
            If notations still belong to the group.
        """
        if key not in self._groups:
            raise KeyError(f"no group with key {key!r}")
        members = [notation.name for notation in self if notation.group == key]
        if members:
            raise NotationError(
                f"group {key!r}: still used by {', '.join(repr(name) for name in members)}"
            )
        return self._groups.pop(key)

    def move_group(self, key: str, offset: int) -> None:
        """Move the group ``key`` by ``offset`` positions (clamped to the ends).

        Raises
        ------
        KeyError
            If there is no group ``key``.
        """
        keys = list(self._groups)
        try:
            index = keys.index(key)
        except ValueError:
            raise KeyError(f"no group with key {key!r}") from None
        keys.insert(max(0, min(len(keys) - 1, index + offset)), keys.pop(index))
        self._groups = {k: self._groups[k] for k in keys}

    def nomenclature(self) -> list[tuple[Group | None, list[Notation]]]:
        """Return the notations in nomenclature order.

        The notations without a group come first (under ``None``), then each group in order;
        within each, notations are sorted by :attr:`Notation.sort_key`. Empty groups are left
        out.
        """
        sections: list[tuple[Group | None, list[Notation]]] = []
        for group in (None, *self._groups.values()):
            key = "" if group is None else group.key
            members = sorted(
                (notation for notation in self if notation.group == key),
                key=lambda notation: notation.sort_key,
            )
            if members:
                sections.append((group, members))
        return sections
