"""The logic of the graphical interface that needs no display: the editor forms and the search.

The forms hold the editor fields as text. A field written per format has a LaTeX and a Typst
entry; an empty Typst entry means the same text as the LaTeX one (and the other way round), so
that a text common to both formats is typed once.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from anatole.model import Group, Notation, NotationError, Rendered, Translated
from anatole.typing import FORMATS, Language

__all__ = ["GroupForm", "NotationForm", "Pair", "description_key", "matches", "title_key"]

type Pair = tuple[str, str]
"""A text in LaTeX and in Typst, as typed in the editor."""


def description_key(language: Language, fmt: str) -> str:
    """Return the field name of the description in ``language`` and the format ``fmt``."""
    return f"description:{language}:{fmt}"


def title_key(language: Language, fmt: str) -> str:
    """Return the field name of the group title in ``language`` and the format ``fmt``."""
    return f"title:{language}:{fmt}"


def _pair(value: Rendered) -> Pair:
    """Return the editor texts of ``value``: the Typst one is empty when it is the same."""
    return (value.latex, "" if value.is_uniform else value.typst)


def _rendered(pair: Pair) -> Rendered:
    """Return the text of an editor pair: an empty side takes the other side's text."""
    latex, typst = (text.strip() for text in pair)
    return Rendered(latex or typst, typst or latex)


def _translations(pairs: Mapping[Language, Pair]) -> Translated:
    """Return the translations of editor pairs, without the languages left empty."""
    return Translated(
        {language: _rendered(pair) for language, pair in pairs.items() if any(map(str.strip, pair))}
    )


def _language_pairs(values: Mapping[str, str], prefix: str) -> dict[Language, Pair]:
    pairs: dict[Language, Pair] = {}
    for key in values:
        kind, _, rest = key.partition(":")
        language, _, fmt = rest.rpartition(":")
        if kind == prefix and fmt == "latex":
            pair = (values[key], values.get(f"{prefix}:{language}:typst", ""))
            if any(pair):  # an empty language has no translation
                pairs[language] = pair
    return pairs


@dataclass(slots=True)
class NotationForm:
    """The text fields of the notation editor."""

    name: str = ""
    group: str = ""
    arguments: str = "0"
    sort: str = ""
    symbol: Pair = ("", "")
    units: Pair = ("", "")
    descriptions: dict[Language, Pair] = field(default_factory=dict[Language, Pair])

    @classmethod
    def from_notation(cls, notation: Notation) -> "NotationForm":
        """Return the form that shows ``notation``."""
        return cls(
            name=notation.name,
            group=notation.group,
            arguments=str(notation.arguments),
            sort=notation.sort,
            symbol=_pair(notation.symbol),
            units=_pair(notation.units),
            descriptions={language: _pair(text) for language, text in notation.description.items()},
        )

    def values(self, languages: Iterable[Language]) -> dict[str, str]:
        """Return the fields by name, with the descriptions in ``languages``.

        A description the form does not have is empty.
        """
        values = {
            "name": self.name,
            "group": self.group,
            "arguments": self.arguments,
            "sort": self.sort,
            "symbol:latex": self.symbol[0],
            "symbol:typst": self.symbol[1],
            "units:latex": self.units[0],
            "units:typst": self.units[1],
        }
        for language in languages:
            pair = self.descriptions.get(language, ("", ""))
            for fmt, text in zip(FORMATS, pair, strict=True):
                values[description_key(language, fmt)] = text
        return values

    @classmethod
    def from_values(cls, values: Mapping[str, str]) -> "NotationForm":
        """Return the form of fields by name (the inverse of :meth:`values`)."""
        return cls(
            name=values.get("name", ""),
            group=values.get("group", ""),
            arguments=values.get("arguments", "0"),
            sort=values.get("sort", ""),
            symbol=(values.get("symbol:latex", ""), values.get("symbol:typst", "")),
            units=(values.get("units:latex", ""), values.get("units:typst", "")),
            descriptions=_language_pairs(values, "description"),
        )

    def to_notation(self) -> Notation:
        """Return the notation that the form describes.

        Surrounding whitespace is stripped; an empty Typst text is the LaTeX one (and the
        other way round); a language whose description is empty has no translation.

        Raises
        ------
        NotationError
            If a field is invalid; the message lists every problem.
        """
        try:
            arguments = int(self.arguments.strip() or "0")
        except ValueError:
            raise NotationError(
                f"notation {self.name.strip()!r}: arguments must be an integer, "
                + f"not {self.arguments!r}"
            ) from None
        return Notation(
            name=self.name.strip(),
            symbol=_rendered(self.symbol),
            description=_translations(self.descriptions),
            units=_rendered(self.units),
            group=self.group.strip(),
            arguments=arguments,
            sort=self.sort.strip(),
        )


@dataclass(slots=True)
class GroupForm:
    """The text fields of the group editor."""

    key: str = ""
    titles: dict[Language, Pair] = field(default_factory=dict[Language, Pair])

    @classmethod
    def from_group(cls, group: Group) -> "GroupForm":
        """Return the form that shows ``group``."""
        return cls(
            key=group.key,
            titles={language: _pair(text) for language, text in group.title.items()},
        )

    def values(self, languages: Iterable[Language]) -> dict[str, str]:
        """Return the fields by name, with the titles in ``languages``."""
        values = {"key": self.key}
        for language in languages:
            pair = self.titles.get(language, ("", ""))
            for fmt, text in zip(FORMATS, pair, strict=True):
                values[title_key(language, fmt)] = text
        return values

    @classmethod
    def from_values(cls, values: Mapping[str, str]) -> "GroupForm":
        """Return the form of fields by name (the inverse of :meth:`values`)."""
        return cls(key=values.get("key", ""), titles=_language_pairs(values, "title"))

    def to_group(self) -> Group:
        """Return the group that the form describes (see :meth:`NotationForm.to_notation`).

        Raises
        ------
        NotationError
            If a field is invalid.
        """
        return Group(key=self.key.strip(), title=_translations(self.titles))


def matches(notation: Notation, query: str) -> bool:
    """Return whether ``notation`` matches a search.

    Every word of ``query`` must appear, regardless of case, in the name, the group, the sort
    key, or a text of the symbol, units or description (in any language).
    """
    texts = [notation.symbol, notation.units, *(text for _, text in notation.description.items())]
    haystack = " ".join(
        [notation.name, notation.group, notation.sort, *(t.get(f) for t in texts for f in FORMATS)]
    ).casefold()
    return all(word in haystack for word in query.casefold().split())
