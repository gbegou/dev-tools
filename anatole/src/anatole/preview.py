"""Preview of a notation, rendered by the Typst compiler (the optional ``typst`` package).

The preview compiles the Typst export of the notation alone, so that it shows the symbol,
description and units exactly as a document would.
"""

import importlib.util
from dataclasses import replace

from anatole.export.typst import to_typst
from anatole.model import Notation, NotationSet
from anatole.typing import Language

__all__ = ["PreviewError", "is_available", "render"]


class PreviewError(RuntimeError):
    """A notation that the Typst compiler rejects; the message is the compiler's."""


def is_available() -> bool:
    """Whether the ``typst`` package is installed (``pip install anatole[preview]``)."""
    return importlib.util.find_spec("typst") is not None


def render(notation: Notation, language: Language, *, ppi: float = 144.0) -> bytes:
    """Return a PNG image of the nomenclature entry of ``notation``, rendered by Typst.

    Parameters
    ----------
    notation
        The notation; its group is ignored.
    language
        The language of the description; the first translation when it has none in it.
    ppi
        The resolution, in pixels per inch.

    Raises
    ------
    ModuleNotFoundError
        If the ``typst`` package is not installed (see :func:`is_available`).
    PreviewError
        If Typst fails to compile the notation.
    """
    import typst  # noqa: PLC0415  # optional dependency

    alone = replace(notation, group="")
    languages = (*notation.description.languages,)
    if language in languages:
        languages = (language, *(code for code in languages if code != language))
    source = "\n".join(
        [
            to_typst(NotationSet([alone], languages=languages)),
            "#set page(width: auto, height: auto, margin: 6pt, fill: white)",
            "#set text(size: 14pt)",
            "#notation-nomenclature(",
            "  title: none, columns: (auto, auto, auto), column-gutter: 1.5em,",
            ")",
        ]
    )
    try:
        # One page (its height is auto), so one image.
        return typst.compile(source.encode(), format="png", ppi=ppi)
    except typst.TypstError as error:
        raise PreviewError(str(error)) from error
