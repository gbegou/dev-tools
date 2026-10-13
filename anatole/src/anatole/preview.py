"""Preview of an entry or a style, rendered by the Typst compiler (the optional ``typst`` package).

The preview compiles the Typst export of the item and of the items it uses, so that it shows
the symbol, description and units (or the short and long forms of an acronym) exactly as a
document would.
"""

import importlib.util
from dataclasses import replace

from anatole.export._common import expand
from anatole.export.typst import to_typst
from anatole.model import Item, Notation, NotationError, NotationSet, Style
from anatole.typing import Language

__all__ = ["PreviewError", "is_available", "render"]


class PreviewError(RuntimeError):
    """An item that cannot be previewed; the message is the compiler's or the model's."""


def is_available() -> bool:
    """Whether the ``typst`` package is installed (``pip install anatole[preview]``)."""
    return importlib.util.find_spec("typst") is not None


def _alone(item: Item, notations: NotationSet) -> NotationSet:
    """Return a set of ``item`` and the items it uses (from ``notations``), without groups."""
    used = [name for name in item.references() if name in notations and name != item.name]
    names = [*used, *notations.dependencies(used)]
    items = [notations[name] for name in names if name != item.name]
    items.append(item)
    styles = [i for i in items if isinstance(i, Style)]
    entries = [replace(i, group="", tags=()) for i in items if not isinstance(i, Style)]
    return NotationSet(entries, (), notations.languages, styles)


def _body(item: Item, notations: NotationSet, language: Language) -> str:
    """Return the Typst code that shows ``item``, after the export of ``notations``."""
    if isinstance(item, Style):
        description = ""
        if len(item.description):
            text = item.description.resolve(language, notations.default_language).typst
            description = expand(text, "typst", notations, "text")
        return f"${item.name}(x)$ #h(1.5em) {description}"
    row = (
        "(entry.symbol, entry.description, entry.units)"
        if isinstance(item, Notation)
        else "(entry.short, entry.long, entry.description)"
    )
    entries = "(..notation-groups, ..acronym-groups).map(s => s.entries).flatten()"
    return "\n".join(
        [
            f'#let entry = {entries}.filter(e => e.name == "{item.name}").first()',
            f"#std.grid(columns: 3, column-gutter: 1.5em, ..{row})",
        ]
    )


def render(item: Item, notations: NotationSet, language: Language, *, ppi: float = 144.0) -> bytes:
    """Return a PNG image of ``item``, rendered by Typst as it would be listed.

    Parameters
    ----------
    item
        The notation, acronym or style; its group and tags are ignored. It may be a version
        of an item of ``notations`` that is not applied yet.
    notations
        The set whose items ``item`` refers to.
    language
        The language of the texts; the default language for the translations missing.
    ppi
        The resolution, in pixels per inch.

    Raises
    ------
    ModuleNotFoundError
        If the ``typst`` package is not installed (see :func:`is_available`).
    PreviewError
        If the item is not consistent with ``notations`` (an unknown reference...), or Typst
        fails to compile it.
    """
    import typst  # noqa: PLC0415  # optional dependency

    try:
        alone = _alone(item, notations)
        alone.check_language(language)
    except NotationError as error:
        raise PreviewError(str(error)) from error
    body = _body(item, alone, language)
    source = "\n".join(
        [
            to_typst(alone, language=language),
            "#set page(width: auto, height: auto, margin: 6pt, fill: white)",
            "#set text(size: 14pt)",
            body,
        ]
    )
    try:
        # One page (its height is auto), so one image.
        return typst.compile(source.encode(), format="png", ppi=ppi)
    except typst.TypstError as error:
        raise PreviewError(str(error)) from error
