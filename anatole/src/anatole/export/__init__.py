"""Exports of a notation set to the target formats."""

from collections.abc import Iterable
from pathlib import Path

from anatole.export.latex import TARGETS, Target, to_latex
from anatole.export.typst import to_typst
from anatole.logging import get_logger
from anatole.model import NotationSet
from anatole.typing import Format, Language

__all__ = [
    "SUFFIXES",
    "TARGETS",
    "Target",
    "export",
    "format_of",
    "to_latex",
    "to_text",
    "to_typst",
]

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
    target: Target = "nomencl+acro",
    tags: Iterable[str] | None = None,
    source: str | None = None,
) -> str:
    """Return the export of ``notations`` in the format ``fmt``.

    With ``tags``, only the entries selected by them are exported (see
    :meth:`~anatole.model.NotationSet.subset`). See :func:`to_latex` (which takes ``target``)
    and :func:`to_typst`.
    """
    if tags is not None:
        notations = notations.subset(tags)
    if fmt == "latex":
        return to_latex(notations, language=language, target=target, source=source)
    return to_typst(notations, language=language, source=source)


def export(
    notations: NotationSet,
    path: str | Path,
    fmt: Format | None = None,
    *,
    language: Language | None = None,
    target: Target = "nomencl+acro",
    tags: Iterable[str] | None = None,
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
    target
        The LaTeX packages of the lists: ``nomencl+acro`` or ``glossaries``.
    tags
        Export only the entries selected by these tags (and the entries they use); all the
        entries when ``None``.
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
    text = to_text(notations, fmt, language=language, target=target, tags=tags, source=source)
    _ = path.write_text(text, encoding="utf-8")
    _logger.info("exported %d notations to %s (%s)", len(notations), path, fmt)
