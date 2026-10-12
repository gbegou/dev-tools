r"""Reading and writing notation files (TOML), and conversion from and to plain dicts.

A notation file looks like::

    version = 1

    [groups.latin]
    title = "Latin symbols"

    [notations.velocity]
    group = "latin"
    symbol = { latex = '\mathbf{u}', typst = 'bold(u)' }
    description = "Velocity"
    units = { latex = '\si{\metre\per\second}', typst = 'm/s' }

A rendered field (``symbol``, ``description``, ``units``, ``title``) is either a string, the same
in every language, or a table with one string per language.
"""

import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from notation_manager.logging import get_logger
from notation_manager.model import Group, Notation, NotationError, NotationSet, Rendered
from notation_manager.typing import LANGUAGES

__all__ = ["FORMAT_VERSION", "dumps", "from_dict", "load", "loads", "save", "to_dict"]

FORMAT_VERSION = 1
"""The version of the file format that this package reads and writes."""

_NOTATION_KEYS = ("group", "arguments", "sort", "symbol", "description", "units")
_GROUP_KEYS = ("title",)
_TOP_KEYS = ("version", "groups", "notations")

_logger = get_logger(__name__)


def _rendered(owner: str, key: str, value: object, problems: list[str]) -> Rendered:
    if isinstance(value, str):
        return Rendered.both(value)
    if isinstance(value, Mapping):
        table = cast(Mapping[object, object], value)
        unknown = [str(k) for k in table if k not in LANGUAGES]
        if unknown:
            problems.append(
                f"{owner}: {key} has unknown language(s) {', '.join(unknown)} "
                + f"(expected {', '.join(LANGUAGES)})"
            )
        texts: dict[str, str] = {}
        for language in LANGUAGES:
            text = table.get(language, "")
            if not isinstance(text, str):
                problems.append(f"{owner}: {key}.{language} must be a string")
                text = ""
            texts[language] = text
        return Rendered(latex=texts["latex"], typst=texts["typst"])
    problems.append(f"{owner}: {key} must be a string or a table with keys latex and typst")
    return Rendered()


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


def _group(key: str, value: object, problems: list[str]) -> Group | None:
    owner = f"group {key!r}"
    table = _table(owner, value, _GROUP_KEYS, problems)
    if table is None:
        return None
    if "title" not in table:
        problems.append(f"{owner}: title is missing")
        return None
    local: list[str] = []
    title = _rendered(owner, "title", table["title"], local)
    if local:
        problems.extend(local)
        return None
    try:
        return Group(key=key, title=title)
    except NotationError as error:
        problems.extend(error.problems)
        return None


def _notation(name: str, value: object, problems: list[str]) -> Notation | None:
    owner = f"notation {name!r}"
    table = _table(owner, value, _NOTATION_KEYS, problems)
    if table is None:
        return None
    local = [f"{owner}: {key} is missing" for key in ("symbol", "description") if key not in table]
    group = table.get("group", "")
    sort = table.get("sort", "")
    arguments = table.get("arguments", 0)
    if not isinstance(group, str):
        local.append(f"{owner}: group must be a string")
    if not isinstance(sort, str):
        local.append(f"{owner}: sort must be a string")
    if not isinstance(arguments, int):
        local.append(f"{owner}: arguments must be an integer")
    symbol = _rendered(owner, "symbol", table.get("symbol", ""), local)
    description = _rendered(owner, "description", table.get("description", ""), local)
    units = _rendered(owner, "units", table.get("units", ""), local)
    if local or not (
        isinstance(group, str) and isinstance(sort, str) and isinstance(arguments, int)
    ):
        problems.extend(local)
        return None
    try:
        return Notation(
            name=name,
            symbol=symbol,
            description=description,
            units=units,
            group=group,
            arguments=arguments,
            sort=sort,
        )
    except NotationError as error:
        problems.extend(error.problems)
        return None


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
    groups = [
        _group(key, value, problems)
        for key, value in (_table("groups", top.get("groups", {}), None, problems) or {}).items()
    ]
    notations = [
        _notation(name, value, problems)
        for name, value in (
            _table("notations", top.get("notations", {}), None, problems) or {}
        ).items()
    ]
    try:
        result = NotationSet(
            (notation for notation in notations if notation is not None),
            (group for group in groups if group is not None),
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
    return {language: value.get(language) for language in LANGUAGES}


def to_dict(notations: NotationSet) -> dict[str, object]:
    """Return the dict of the notation file of ``notations`` (the inverse of :func:`from_dict`).

    Rendered fields that are the same in every language are single strings; default values
    (no group, no units, no arguments, no sort key) are left out.
    """
    groups = {group.key: {"title": _rendered_value(group.title)} for group in notations.groups}
    entries: dict[str, object] = {}
    for notation in notations:
        entry: dict[str, object] = {}
        if notation.group:
            entry["group"] = notation.group
        if notation.arguments:
            entry["arguments"] = notation.arguments
        if notation.sort:
            entry["sort"] = notation.sort
        entry["symbol"] = _rendered_value(notation.symbol)
        entry["description"] = _rendered_value(notation.description)
        if not notation.units.is_empty:
            entry["units"] = _rendered_value(notation.units)
        entries[notation.name] = entry
    return {"version": FORMAT_VERSION, "groups": groups, "notations": entries}


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
    _logger.info(
        "read %d notations and %d groups from %s", len(notations), len(notations.groups), path
    )
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
    lines = [f"version = {FORMAT_VERSION}"]
    for section in ("groups", "notations"):
        for key, table in cast(dict[str, dict[str, object]], data[section]).items():
            lines.append("")
            lines.append(f"[{section}.{key}]")
            lines.extend(f"{field} = {_toml_value(value)}" for field, value in table.items())
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
    _logger.info(
        "wrote %d notations and %d groups to %s", len(notations), len(notations.groups), path
    )
