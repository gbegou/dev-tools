r"""Texts per format and per language, references between entries, and their checks.

A text written once per target format is a :class:`Rendered`; a text written once per natural
language, each translation once per format, is a :class:`Translated`. A text refers to another
entry with ``@{name}``: ``\mathit{Re}_{@{blthickness}}`` uses the symbol of ``blthickness``.
"""

import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import ClassVar, override

from anatole.typing import FORMATS, Format, Language

__all__ = [
    "GROUP_KEY_PATTERN",
    "LANGUAGE_PATTERN",
    "NAME_PATTERN",
    "REFERENCE_PATTERN",
    "SORT_PATTERN",
    "TAG_PATTERN",
    "NotationError",
    "Rendered",
    "Translated",
    "references",
    "rename_references",
]

NAME_PATTERN = re.compile(r"[A-Za-z]{2,}")
"""The pattern of an entry name.

Two letters or more: a LaTeX control word, and a Typst identifier that math mode does not read
as a single letter.
"""

GROUP_KEY_PATTERN = re.compile(r"[A-Za-z0-9_-]+")
"""The pattern of one level of a group key (a bare TOML key)."""

TAG_PATTERN = re.compile(r"[A-Za-z0-9_-]+")
"""The pattern of a tag."""

LANGUAGE_PATTERN = re.compile(r"[a-z]{2,3}(-[A-Za-z0-9]{2,8})*")
"""The pattern of a language code, such as ``en``, ``fr`` or ``pt-BR`` (a BCP 47 tag, as Typst
uses)."""

SORT_PATTERN = re.compile(r"[A-Za-z0-9 _.-]*")
"""The pattern of a sort key, made of characters that makeindex sorts without quoting."""

REFERENCE_PATTERN = re.compile(r"@\{([A-Za-z]+)\}")
"""The pattern of a reference to another entry, ``@{name}``."""

_PLACEHOLDER = re.compile(r"#(\d)")


class NotationError(ValueError):
    """An invalid entry, group or notation file.

    Attributes
    ----------
    problems
        One message per problem found, each naming the entry (or group) and the field.
    """

    problems: tuple[str, ...]

    def __init__(self, problems: str | Iterable[str]) -> None:
        self.problems = (problems,) if isinstance(problems, str) else tuple(problems)
        super().__init__("\n".join(self.problems))


def references(text: str) -> list[str]:
    """Return the names that ``text`` refers to with ``@{name}``, in order, without repeats."""
    return list(dict.fromkeys(REFERENCE_PATTERN.findall(text)))


def rename_references(text: str, old: str, new: str) -> str:
    """Return ``text`` with the references to ``old`` turned into references to ``new``."""
    return text.replace(f"@{{{old}}}", f"@{{{new}}}")


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

    def map(self, function: Callable[[str], str]) -> "Rendered":
        """Return a copy with ``function`` applied to the text in every format."""
        return Rendered(latex=function(self.latex), typst=function(self.typst))

    def references(self) -> list[str]:
        """Return the names this text refers to, in every format."""
        return list(dict.fromkeys([*references(self.latex), *references(self.typst)]))

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

    def map(self, function: Callable[[str], str]) -> "Translated":
        """Return a copy with ``function`` applied to every text."""
        return Translated({language: text.map(function) for language, text in self._texts})

    def references(self) -> list[str]:
        """Return the names these texts refer to, in every language and format."""
        return list(dict.fromkeys(name for _, text in self._texts for name in text.references()))

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


def check_rendered(
    owner: str, field_name: str, value: Rendered, *, required: bool, arguments: int = 0
) -> list[str]:
    """Return the problems of one field written per format (an empty list when it is valid).

    The field needs both formats (or, when not ``required``, both or none), balanced LaTeX
    braces, placeholders ``#1`` to ``#arguments`` only, and well-formed references.
    """
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
        text = value.get(fmt)
        for match in _PLACEHOLDER.finditer(text):
            index = int(match.group(1))
            if not 1 <= index <= arguments:
                expected = f"#1 to #{arguments}" if arguments else "no placeholder"
                problems.append(
                    f"{owner}: {field_name} uses {match.group(0)} in {fmt}, "
                    + f"but takes {arguments} argument(s) ({expected})"
                )
        if text.count("@{") != len(REFERENCE_PATTERN.findall(text)):
            problems.append(
                f"{owner}: {field_name} has a malformed reference in {fmt} "
                + "(expected @{name}, a name of letters only)"
            )
    return problems


def check_translated(
    owner: str, field_name: str, value: Translated, *, required: bool = True
) -> list[str]:
    """Return the problems of one field written per language.

    A required field needs at least one translation; every translation needs valid language
    codes and both formats (see :func:`check_rendered`).
    """
    if required and not len(value):
        return [f"{owner}: {field_name} has no translation"]
    problems: list[str] = []
    for language, text in value.items():
        if not LANGUAGE_PATTERN.fullmatch(language):
            problems.append(
                f"{owner}: {field_name} has an invalid language code {language!r} "
                + "(expected a code like en, fr or pt-BR)"
            )
        problems.extend(check_rendered(owner, f"{field_name} ({language})", text, required=True))
    return problems
