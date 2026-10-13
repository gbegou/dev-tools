"""Exports of a notation set to the target formats."""

from pathlib import Path

from notation_manager.export.latex import to_latex
from notation_manager.export.typst import to_typst
from notation_manager.logging import get_logger
from notation_manager.model import NotationSet
from notation_manager.typing import Format, Language

__all__ = ["SUFFIXES", "export", "format_of", "to_latex", "to_text", "to_typst"]

SUFFIXES: dict[str, Format] = {".tex": "latex", ".sty": "latex", ".typ": "typst"}
"""The file suffixes whose format :func:`format_of` recognizes."""

_logger = get_logger(__name__)


def format_of(path: str | Path) -> Format:
    """Return the format of an export file, from its suffix (see :data:`SUFFIXES`).

    Raises
    ------
    ValueError
        If the suffix is not recognized.
    """
    suffix = Path(path).suffix.lower()
    try:
        return SUFFIXES[suffix]
    except KeyError:
        known = ", ".join(SUFFIXES)
        raise ValueError(
            f"{path}: cannot tell the format from the suffix {suffix!r} (known: {known})"
        ) from None


def to_text(
    notations: NotationSet,
    fmt: Format,
    *,
    language: Language | None = None,
    source: str | None = None,
) -> str:
    """Return the export of ``notations`` in the format ``fmt``.

    See :func:`to_latex` and :func:`to_typst`.
    """
    if fmt == "latex":
        return to_latex(notations, language=language, source=source)
    return to_typst(notations, language=language, source=source)


def export(
    notations: NotationSet,
    path: str | Path,
    fmt: Format | None = None,
    *,
    language: Language | None = None,
    source: str | None = None,
) -> None:
    """Write the export of ``notations`` to ``path``.

    Parameters
    ----------
    notations
        The notations.
    path
        The file to write.
    fmt
        The format; ``None`` to tell it from the suffix of ``path``.
    language
        The language of the descriptions and group titles; the default language when ``None``.
    source
        The notation file, named in the header comment.

    Raises
    ------
    ValueError
        If ``fmt`` is ``None`` and the suffix of ``path`` is not recognized.
    NotationError
        If the notations cannot be exported (see :func:`to_latex`), or ``language`` is not
        declared.
    OSError
        If the file cannot be written.
    """
    path = Path(path)
    fmt = fmt or format_of(path)
    text = to_text(notations, fmt, language=language, source=source)
    _ = path.write_text(text, encoding="utf-8")
    _logger.info("exported %d notations to %s (%s)", len(notations), path, fmt)
