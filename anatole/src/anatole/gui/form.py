"""The logic of the graphical interface that needs no display: the editor forms and the search.

The forms hold the editor fields as text, by field name. A field written per format has a
LaTeX and a Typst entry; an empty Typst entry means the same text as the LaTeX one (and the
other way round), so that a text common to both formats is typed once. A field written per
language has such a pair per language; a language left empty has no translation.
"""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Literal

from anatole.model import (
    Acronym,
    Group,
    Item,
    Notation,
    NotationError,
    Rendered,
    Style,
    Translated,
)
from anatole.typing import FORMATS, Language

__all__ = [
    "KINDS",
    "GroupForm",
    "ItemForm",
    "Kind",
    "Pair",
    "kind_of",
    "language_key",
    "matches",
]

type Pair = tuple[str, str]
"""A text in LaTeX and in Typst, as typed in the editor."""

type Kind = Literal["notation", "acronym", "abbreviation", "style"]
"""The kinds of items the editor makes."""

KINDS: tuple[Kind, ...] = ("notation", "acronym", "abbreviation", "style")
"""The kinds of items, in the order the editor offers them."""

LANGUAGE_FIELDS = ("description", "short", "long", "title")
"""The fields written per language."""


def kind_of(item: Item) -> Kind:
    """Return the kind of ``item``."""
    match item:
        case Style():
            return "style"
        case Notation():
            return "notation"
        case Acronym():
            return item.kind


def language_key(name: str, language: Language, fmt: str) -> str:
    """Return the field name of the field ``name`` in ``language`` and the format ``fmt``."""
    return f"{name}:{language}:{fmt}"


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


def _pairs(value: Translated) -> dict[Language, Pair]:
    return {language: _pair(text) for language, text in value.items()}


def _language_pairs(values: Mapping[str, str], name: str) -> dict[Language, Pair]:
    pairs: dict[Language, Pair] = {}
    for key in values:
        prefix, _, rest = key.partition(":")
        language, _, fmt = rest.rpartition(":")
        if prefix == name and fmt == "latex":
            pair = (values[key], values.get(language_key(name, language, "typst"), ""))
            if any(pair):  # an empty language has no translation
                pairs[language] = pair
    return pairs


def _language_values(
    name: str, pairs: Mapping[Language, Pair], languages: Iterable[Language]
) -> dict[str, str]:
    values: dict[str, str] = {}
    for language in languages:
        for fmt, text in zip(FORMATS, pairs.get(language, ("", "")), strict=True):
            values[language_key(name, language, fmt)] = text
    return values


@dataclass(slots=True)
class ItemForm:
    """The text fields of the item editor, for every kind of item.

    The fields that a kind does not have are ignored: ``symbol`` is the template of a style;
    ``tags`` are separated by commas or spaces.
    """

    kind: Kind = "notation"
    name: str = ""
    group: str = ""
    sort: str = ""
    tags: str = ""
    arguments: str = "0"
    style: str = ""
    symbol: Pair = ("", "")
    units: Pair = ("", "")
    descriptions: dict[Language, Pair] = field(default_factory=dict[Language, Pair])
    shorts: dict[Language, Pair] = field(default_factory=dict[Language, Pair])
    longs: dict[Language, Pair] = field(default_factory=dict[Language, Pair])

    @classmethod
    def from_item(cls, item: Item) -> "ItemForm":
        """Return the form that shows ``item``."""
        form = cls(kind=kind_of(item), name=item.name, descriptions=_pairs(item.description))
        match item:
            case Style():
                form.symbol = _pair(item.template)
            case Notation():
                form.group, form.sort, form.tags = item.group, item.sort, " ".join(item.tags)
                form.arguments, form.style = str(item.arguments), item.style
                form.symbol, form.units = _pair(item.symbol), _pair(item.units)
            case Acronym():
                form.group, form.sort, form.tags = item.group, item.sort, " ".join(item.tags)
                form.shorts, form.longs = _pairs(item.short), _pairs(item.long)
        return form

    def values(self, languages: Iterable[Language]) -> dict[str, str]:
        """Return the fields by name, with the texts in ``languages`` (empty when missing)."""
        languages = tuple(languages)
        return {
            "kind": self.kind,
            "name": self.name,
            "group": self.group,
            "sort": self.sort,
            "tags": self.tags,
            "arguments": self.arguments,
            "style": self.style,
            "symbol:latex": self.symbol[0],
            "symbol:typst": self.symbol[1],
            "units:latex": self.units[0],
            "units:typst": self.units[1],
            **_language_values("description", self.descriptions, languages),
            **_language_values("short", self.shorts, languages),
            **_language_values("long", self.longs, languages),
        }

    @classmethod
    def from_values(cls, values: Mapping[str, str]) -> "ItemForm":
        """Return the form of fields by name (the inverse of :meth:`values`)."""
        kind = values.get("kind", "notation")
        return cls(
            kind=kind if kind in KINDS else "notation",
            name=values.get("name", ""),
            group=values.get("group", ""),
            sort=values.get("sort", ""),
            tags=values.get("tags", ""),
            arguments=values.get("arguments", "0"),
            style=values.get("style", ""),
            symbol=(values.get("symbol:latex", ""), values.get("symbol:typst", "")),
            units=(values.get("units:latex", ""), values.get("units:typst", "")),
            descriptions=_language_pairs(values, "description"),
            shorts=_language_pairs(values, "short"),
            longs=_language_pairs(values, "long"),
        )

    def to_item(self) -> Item:
        """Return the item that the form describes.

        Surrounding whitespace is stripped; an empty Typst text is the LaTeX one (and the
        other way round); a language whose text is empty has no translation.

        Raises
        ------
        NotationError
            If a field is invalid; the message lists every problem.
        """
        name = self.name.strip()
        tags = tuple(tag for tag in re.split(r"[\s,]+", self.tags) if tag)
        description = _translations(self.descriptions)
        match self.kind:
            case "style":
                return Style(name, _rendered(self.symbol), description)
            case "notation":
                try:
                    arguments = int(self.arguments.strip() or "0")
                except ValueError:
                    raise NotationError(
                        f"notation {name!r}: arguments must be an integer, not {self.arguments!r}"
                    ) from None
                return Notation(
                    name=name,
                    symbol=_rendered(self.symbol),
                    description=description,
                    units=_rendered(self.units),
                    group=self.group.strip(),
                    arguments=arguments,
                    sort=self.sort.strip(),
                    style=self.style.strip(),
                    tags=tags,
                )
            case _:
                return Acronym(
                    name=name,
                    short=_translations(self.shorts),
                    long=_translations(self.longs),
                    description=description,
                    group=self.group.strip(),
                    sort=self.sort.strip(),
                    tags=tags,
                    abbreviation=self.kind == "abbreviation",
                )


@dataclass(slots=True)
class GroupForm:
    """The text fields of the group editor: the key (``symbols.latin``) and the titles."""

    key: str = ""
    titles: dict[Language, Pair] = field(default_factory=dict[Language, Pair])

    @classmethod
    def from_group(cls, group: Group) -> "GroupForm":
        """Return the form that shows ``group``."""
        return cls(key=group.key, titles=_pairs(group.title))

    def values(self, languages: Iterable[Language]) -> dict[str, str]:
        """Return the fields by name, with the titles in ``languages``."""
        return {"key": self.key, **_language_values("title", self.titles, languages)}

    @classmethod
    def from_values(cls, values: Mapping[str, str]) -> "GroupForm":
        """Return the form of fields by name (the inverse of :meth:`values`)."""
        return cls(key=values.get("key", ""), titles=_language_pairs(values, "title"))

    def to_group(self) -> Group:
        """Return the group that the form describes (see :meth:`ItemForm.to_item`).

        Raises
        ------
        NotationError
            If a field is invalid.
        """
        return Group(key=self.key.strip(), title=_translations(self.titles))


def matches(item: Item, query: str) -> bool:
    """Return whether ``item`` matches a search.

    Every word of ``query`` must appear, regardless of case, in the name, the kind, the group,
    the sort key, the tags, or a text of the item (in any language and format).
    """
    texts: list[Rendered] = [text for _, text in item.description.items()]
    words = [item.name, kind_of(item)]
    match item:
        case Style():
            texts.append(item.template)
        case Notation():
            texts.extend([item.symbol, item.units])
            words.extend([item.group, item.sort, item.style, *item.tags])
        case Acronym():
            texts.extend(text for value in (item.short, item.long) for _, text in value.items())
            words.extend([item.group, item.sort, *item.tags])
    haystack = " ".join([*words, *(t.get(f) for t in texts for f in FORMATS)]).casefold()
    return all(word in haystack for word in query.casefold().split())
