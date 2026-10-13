r"""Reading and writing notation files (TOML), and conversion from and to plain dicts.

A notation file looks like::

    version = 1
    languages = ["en", "fr"]  # the first one is the default language

    [styles.vect]
    template = { latex = '\boldsymbol{#1}', typst = 'bold(#1)' }

    [groups.symbols]
    title = { en = "Symbols", fr = "Symboles" }

    [groups.symbols.latin]
    title = { en = "Latin letters", fr = "Lettres latines" }

    [notations.velocity]
    group = "symbols.latin"
    style = "vect"
    symbol = 'u'
    description = { en = "Velocity", fr = "Vitesse" }
    units = { latex = '\si{\metre\per\second}', typst = 'm/s' }

    [acronyms.cfd]
    short = "CFD"
    long = { en = "computational fluid dynamics", fr = "mécanique des fluides numérique" }

    [abbreviations.wrt]
    short = "w.r.t."
    long = "with respect to"

The fields written per format (``symbol``, ``units``, ``template``) are a string, the same in
every format, or a table with one string per format (``latex``, ``typst``). The fields written
per language (``description``, ``title``, ``short``, ``long``) are a string or a table with one
string per format, in the default language, or a table with one entry per language, each a
string or a table with one string per format.
"""

import tomllib
from collections.abc import Callable, Mapping
from functools import partial
from pathlib import Path
from typing import cast, final

from anatole.logging import get_logger
from anatole.model import (
    Acronym,
    Entry,
    Group,
    Notation,
    NotationError,
    NotationSet,
    Rendered,
    Style,
    Translated,
)
from anatole.typing import FORMATS, Language

__all__ = ["FORMAT_VERSION", "dumps", "from_dict", "load", "loads", "save", "to_dict"]

FORMAT_VERSION = 1
"""The version of the file format that this package reads and writes."""

_TOP_KEYS = (
    "version",
    "languages",
    "styles",
    "groups",
    "notations",
    "acronyms",
    "abbreviations",
)
_STYLE_KEYS = ("template", "description")
_NOTATION_KEYS = (
    "group",
    "style",
    "arguments",
    "sort",
    "tags",
    "symbol",
    "description",
    "units",
)
_ACRONYM_KEYS = ("group", "sort", "tags", "short", "long", "description")
_DEFAULT_LANGUAGES = ("en",)

_logger = get_logger(__name__)


def _table(
    owner: str, value: object, keys: tuple[str, ...] | None, problems: list[str]
) -> dict[str, object] | None:
    """Return ``value`` as a table, or ``None`` if it is not one.

    ``keys`` are the allowed keys; ``None`` allows any.
    """
    if not isinstance(value, Mapping):
        problems.append(f"{owner}: must be a table")
        return None
    table = {str(k): v for k, v in cast(Mapping[object, object], value).items()}
    unknown = [] if keys is None else [k for k in table if k not in keys]
    if unknown:
        expected = ", ".join(keys or ())
        problems.append(f"{owner}: unknown key(s) {', '.join(unknown)} (expected {expected})")
    return table


def _rendered(owner: str, key: str, value: object, problems: list[str]) -> Rendered:
    if isinstance(value, str):
        return Rendered.both(value)
    if isinstance(value, Mapping):
        table = cast(Mapping[object, object], value)
        unknown = [str(k) for k in table if k not in FORMATS]
        if unknown:
            problems.append(
                f"{owner}: {key} has unknown format(s) {', '.join(unknown)} "
                + f"(expected {', '.join(FORMATS)})"
            )
        texts: dict[str, str] = {}
        for fmt in FORMATS:
            text = table.get(fmt, "")
            if not isinstance(text, str):
                problems.append(f"{owner}: {key}.{fmt} must be a string")
                text = ""
            texts[fmt] = text
        return Rendered(latex=texts["latex"], typst=texts["typst"])
    problems.append(f"{owner}: {key} must be a string or a table with keys latex and typst")
    return Rendered()


@final
class _Reader:
    """Builds the items of a notation file, collecting every problem."""

    def __init__(self, default: Language) -> None:
        self.default = default
        self.problems: list[str] = []

    def translated(self, owner: str, key: str, value: object) -> Translated:
        if isinstance(value, str):
            return Translated({self.default: value})
        if not isinstance(value, Mapping):
            self.problems.append(
                f"{owner}: {key} must be a string or a table with one entry per language"
            )
            return Translated()
        table = cast(Mapping[object, object], value)
        if table and all(code in FORMATS for code in table):  # the default language, per format
            return Translated({self.default: _rendered(owner, key, table, self.problems)})
        if any(code in FORMATS for code in table):
            self.problems.append(
                f"{owner}: {key} mixes languages and formats: write {key}.<language> = "
                + "{ latex = ..., typst = ... }"
            )
            return Translated()
        return Translated(
            {
                str(code): _rendered(owner, f"{key}.{code}", text, self.problems)
                for code, text in table.items()
            }
        )

    def string(self, owner: str, table: Mapping[str, object], key: str) -> str | None:
        value = table.get(key, "")
        if isinstance(value, str):
            return value
        self.problems.append(f"{owner}: {key} must be a string")
        return None

    def strings(self, owner: str, table: Mapping[str, object], key: str) -> tuple[str, ...] | None:
        value = table.get(key, [])
        if isinstance(value, list) and all(
            isinstance(item, str) for item in cast(list[object], value)
        ):
            return tuple(cast(list[str], value))
        self.problems.append(f"{owner}: {key} must be a list of strings")
        return None

    def build[T](self, before: int, local: list[str], build: Callable[[], T]) -> T | None:
        """Build an item from fields read without problems; collect the problems otherwise.

        ``before`` is the number of problems before its fields were read; ``local`` are the
        problems of its fields that are not collected yet.
        """
        if local or len(self.problems) > before:
            self.problems.extend(local)
            return None
        try:
            return build()
        except NotationError as error:
            self.problems.extend(error.problems)
            return None

    def style(self, name: str, value: object) -> Style | None:
        owner = f"style {name!r}"
        table = _table(owner, value, _STYLE_KEYS, self.problems)
        if table is None:
            return None
        before = len(self.problems)
        local = [f"{owner}: template is missing"] if "template" not in table else []
        template = _rendered(owner, "template", table.get("template", ""), local)
        description = self.translated(owner, "description", table.get("description", {}))
        return self.build(before, local, lambda: Style(name, template, description))

    def notation(self, name: str, value: object) -> Notation | None:
        owner = f"notation {name!r}"
        table = _table(owner, value, _NOTATION_KEYS, self.problems)
        if table is None:
            return None
        local = [
            f"{owner}: {key} is missing" for key in ("symbol", "description") if key not in table
        ]
        before = len(self.problems)
        group, style = self.string(owner, table, "group"), self.string(owner, table, "style")
        sort, tags = self.string(owner, table, "sort"), self.strings(owner, table, "tags")
        arguments = table.get("arguments", 0)
        if not isinstance(arguments, int):
            self.problems.append(f"{owner}: arguments must be an integer")
        symbol = _rendered(owner, "symbol", table.get("symbol", ""), local)
        description = self.translated(owner, "description", table.get("description", ""))
        units = _rendered(owner, "units", table.get("units", ""), local)
        if (
            group is None
            or style is None
            or sort is None
            or tags is None
            or not isinstance(arguments, int)
        ):
            self.problems.extend(local)
            return None
        return self.build(
            before,
            local,
            lambda: Notation(
                name=name,
                symbol=symbol,
                description=description,
                units=units,
                group=group,
                arguments=arguments,
                sort=sort,
                style=style,
                tags=tags,
            ),
        )

    def acronym(self, name: str, value: object, *, abbreviation: bool) -> Acronym | None:
        owner = f"{'abbreviation' if abbreviation else 'acronym'} {name!r}"
        table = _table(owner, value, _ACRONYM_KEYS, self.problems)
        if table is None:
            return None
        local = [f"{owner}: {key} is missing" for key in ("short", "long") if key not in table]
        before = len(self.problems)
        group, sort = self.string(owner, table, "group"), self.string(owner, table, "sort")
        tags = self.strings(owner, table, "tags")
        short = self.translated(owner, "short", table.get("short", {}))
        long = self.translated(owner, "long", table.get("long", {}))
        description = self.translated(owner, "description", table.get("description", {}))
        if group is None or sort is None or tags is None:
            self.problems.extend(local)
            return None
        return self.build(
            before,
            local,
            lambda: Acronym(
                name=name,
                short=short,
                long=long,
                description=description,
                group=group,
                sort=sort,
                tags=tags,
                abbreviation=abbreviation,
            ),
        )

    def groups(self, value: object, parent: str = "") -> list[Group]:
        """Read a table of groups: each has a ``title`` and its subsections as tables."""
        table = _table(f"group {parent!r}" if parent else "groups", value, None, self.problems)
        groups: list[Group] = []
        for key, item in (table or {}).items():
            if parent and key == "title":
                continue
            full = f"{parent}.{key}" if parent else key
            if parent and not isinstance(item, Mapping):
                self.problems.append(
                    f"group {parent!r}: unknown key {key} (expected title, or a table for a "
                    + "subsection)"
                )
                continue
            content = _table(f"group {full!r}", cast(object, item), None, self.problems)
            if content is None:
                continue
            before = len(self.problems)
            local = [] if "title" in content else [f"group {full!r}: title is missing"]
            title = self.translated(f"group {full!r}", "title", content.get("title", {}))
            group = self.build(before, local, partial(Group, full, title))
            if group is not None:
                groups.append(group)
            groups.extend(self.groups(content, full))
        return groups


def _languages(value: object, problems: list[str]) -> tuple[Language, ...]:
    if isinstance(value, list) and all(isinstance(item, str) for item in cast(list[object], value)):
        return tuple(cast(list[str], value))
    problems.append('languages: must be a list of language codes, like ["en", "fr"]')
    return _DEFAULT_LANGUAGES


def from_dict(data: Mapping[str, object]) -> NotationSet:
    """Build a notation set from the dict of a notation file (as :func:`tomllib.loads` gives).

    Raises
    ------
    NotationError
        If the data is invalid; the message lists every problem found.
    """
    problems: list[str] = []
    top = _table("file", data, _TOP_KEYS, problems) or {}
    version = top.get("version", FORMAT_VERSION)
    if version != FORMAT_VERSION:
        raise NotationError(
            f"file: format version {version!r} is not supported (expected {FORMAT_VERSION})"
        )
    languages = _languages(top.get("languages", list(_DEFAULT_LANGUAGES)), problems)
    reader = _Reader(languages[0] if languages else _DEFAULT_LANGUAGES[0])
    reader.problems = problems

    def table(key: str) -> dict[str, object]:
        return _table(key, top.get(key, {}), None, problems) or {}

    styles = [reader.style(name, value) for name, value in table("styles").items()]
    groups = reader.groups(top.get("groups", {}))
    entries: list[Entry | None] = [
        *(reader.notation(name, value) for name, value in table("notations").items()),
        *(
            reader.acronym(name, value, abbreviation=False)
            for name, value in table("acronyms").items()
        ),
        *(
            reader.acronym(name, value, abbreviation=True)
            for name, value in table("abbreviations").items()
        ),
    ]
    try:
        result = NotationSet(
            (entry for entry in entries if entry is not None),
            groups,
            languages,
            (style for style in styles if style is not None),
        )
    except NotationError as error:
        problems.extend(error.problems)
        result = NotationSet()
    if problems:
        raise NotationError(problems)
    return result


def _rendered_value(value: Rendered) -> str | dict[str, str]:
    if value.is_uniform:
        return value.latex
    return {fmt: value.get(fmt) for fmt in FORMATS}


def _translated_value(value: Translated, languages: tuple[Language, ...]) -> object:
    if len(languages) == 1 and value.languages == languages:
        return _rendered_value(value[languages[0]])
    return {language: _rendered_value(text) for language, text in value.items()}


def _entry_dict(entry: Entry, languages: tuple[Language, ...]) -> dict[str, object]:
    data: dict[str, object] = {}
    if entry.group:
        data["group"] = entry.group
    if isinstance(entry, Notation):
        if entry.style:
            data["style"] = entry.style
        if entry.arguments:
            data["arguments"] = entry.arguments
    if entry.sort:
        data["sort"] = entry.sort
    if entry.tags:
        data["tags"] = list(entry.tags)
    if isinstance(entry, Notation):
        data["symbol"] = _rendered_value(entry.symbol)
        data["description"] = _translated_value(entry.description, languages)
        if not entry.units.is_empty:
            data["units"] = _rendered_value(entry.units)
    else:
        data["short"] = _translated_value(entry.short, languages)
        data["long"] = _translated_value(entry.long, languages)
        if len(entry.description):
            data["description"] = _translated_value(entry.description, languages)
    return data


def to_dict(notations: NotationSet) -> dict[str, object]:
    """Return the dict of the notation file of ``notations`` (the inverse of :func:`from_dict`).

    Texts that are the same in every format are single strings, and so are the texts written
    per language when the set has one language; default values (no group, no units, no
    arguments...) are left out. Subsections are tables inside their section's table.
    """
    languages = notations.languages
    styles: dict[str, object] = {}
    for style in notations.styles:
        style_data: dict[str, object] = {"template": _rendered_value(style.template)}
        if len(style.description):
            style_data["description"] = _translated_value(style.description, languages)
        styles[style.name] = style_data
    groups: dict[str, dict[str, object]] = {}
    for group in notations.groups:
        content: dict[str, object] = {"title": _translated_value(group.title, languages)}
        if group.parent:
            groups[group.parent][group.key.rpartition(".")[2]] = content
        groups[group.key] = content
    return {
        "version": FORMAT_VERSION,
        "languages": list(languages),
        "styles": styles,
        "groups": {g.key: groups[g.key] for g in notations.groups if not g.parent},
        "notations": {n.name: _entry_dict(n, languages) for n in notations.notations},
        "acronyms": {
            a.name: _entry_dict(a, languages) for a in notations.acronyms if not a.abbreviation
        },
        "abbreviations": {
            a.name: _entry_dict(a, languages) for a in notations.acronyms if a.abbreviation
        },
    }


def loads(text: str) -> NotationSet:
    """Read a notation set from the text of a notation file.

    Raises
    ------
    NotationError
        If the text is not valid TOML or the notations are invalid.
    """
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise NotationError(f"file: invalid TOML: {error}") from error
    return from_dict(data)


def load(path: str | Path) -> NotationSet:
    """Read a notation set from a notation file.

    Raises
    ------
    OSError
        If the file cannot be read.
    NotationError
        If the file is not valid TOML or the notations are invalid; each message is prefixed by
        the path.
    """
    path = Path(path)
    try:
        notations = loads(path.read_text(encoding="utf-8"))
    except NotationError as error:
        raise NotationError(f"{path}: {problem}" for problem in error.problems) from error
    _logger.info("read %r from %s", notations, path)
    return notations


def _toml_string(text: str) -> str:
    """Return ``text`` as a TOML string.

    A literal string (no escapes, so that LaTeX backslashes stay readable) when it can be one,
    a basic string otherwise.
    """
    if "'" not in text and not any(ord(char) < 0x20 or char == "\x7f" for char in text):
        return f"'{text}'"
    escaped: list[str] = []
    for char in text:
        if char == "\\":
            escaped.append("\\\\")
        elif char == '"':
            escaped.append('\\"')
        elif char == "\n":
            escaped.append("\\n")
        elif char == "\t":
            escaped.append("\\t")
        elif ord(char) < 0x20 or char == "\x7f":
            escaped.append(f"\\u{ord(char):04x}")
        else:
            escaped.append(char)
    return '"' + "".join(escaped) + '"'


def _toml_value(value: object) -> str:
    if isinstance(value, str):
        return _toml_string(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in cast(list[object], value)) + "]"
    if isinstance(value, Mapping):
        table = cast(Mapping[str, object], value)
        items = ", ".join(f"{key} = {_toml_value(item)}" for key, item in table.items())
        return f"{{ {items} }}"
    raise TypeError(f"cannot write {type(value).__name__} to TOML")


def dumps(notations: NotationSet) -> str:
    r"""Return the text of the notation file of ``notations``.

    Strings are written as TOML literal strings when they can be (``'\mathbf{u}'``), so that
    the file stays readable and editable by hand.
    """
    data = to_dict(notations)
    languages = notations.languages
    lines = [f"version = {FORMAT_VERSION}", f"languages = {_toml_value(data['languages'])}"]

    def table(header: str, content: Mapping[str, object]) -> None:
        lines.extend(["", f"[{header}]"])
        lines.extend(f"{key} = {_toml_value(value)}" for key, value in content.items())

    for name, content in cast(dict[str, dict[str, object]], data["styles"]).items():
        table(f"styles.{name}", content)
    for group in notations.groups:
        table(f"groups.{group.key}", {"title": _translated_value(group.title, languages)})
    for section in ("notations", "acronyms", "abbreviations"):
        for name, content in cast(dict[str, dict[str, object]], data[section]).items():
            table(f"{section}.{name}", content)
    return "\n".join(lines) + "\n"


def save(notations: NotationSet, path: str | Path) -> None:
    """Write ``notations`` to a notation file (see :func:`dumps`).

    Raises
    ------
    OSError
        If the file cannot be written.
    """
    path = Path(path)
    _ = path.write_text(dumps(notations), encoding="utf-8")
    _logger.info("wrote %r to %s", notations, path)
