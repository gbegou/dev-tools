"""Exports of a notation set to the target languages."""

from pathlib import Path

from notation_manager.export.latex import to_latex
from notation_manager.export.typst import to_typst
from notation_manager.logging import get_logger
from notation_manager.model import NotationSet
from notation_manager.typing import Language

__all__ = ["SUFFIXES", "export", "language_of", "to_latex", "to_text", "to_typst"]

SUFFIXES: dict[str, Language] = {".tex": "latex", ".sty": "latex", ".typ": "typst"}
"""The file suffixes whose language :func:`language_of` recognizes."""

_logger = get_logger(__name__)


def language_of(path: str | Path) -> Language:
    """Return the language of an export file, from its suffix (see :data:`SUFFIXES`).

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
            f"{path}: cannot tell the language from the suffix {suffix!r} (known: {known})"
        ) from None


def to_text(notations: NotationSet, language: Language, *, source: str | None = None) -> str:
    """Return the export of ``notations`` in ``language``.

    See :func:`to_latex` and :func:`to_typst`.
    """
    if language == "latex":
        return to_latex(notations, source=source)
    return to_typst(notations, source=source)


def export(
    notations: NotationSet,
    path: str | Path,
    language: Language | None = None,
    *,
    source: str | None = None,
) -> None:
    """Write the export of ``notations`` to ``path``.

    Parameters
    ----------
    notations
        The notations.
    path
        The file to write.
    language
        The language; ``None`` to tell it from the suffix of ``path``.
    source
        The notation file, named in the header comment.

    Raises
    ------
    ValueError
        If ``language`` is ``None`` and the suffix of ``path`` is not recognized.
    NotationError
        If the notations cannot be exported (see :func:`to_latex`).
    OSError
        If the file cannot be written.
    """
    path = Path(path)
    language = language or language_of(path)
    _ = path.write_text(to_text(notations, language, source=source), encoding="utf-8")
    _logger.info("exported %d notations to %s (%s)", len(notations), path, language)
