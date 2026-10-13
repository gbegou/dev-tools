"""Exports of a notation set: LaTeX and Typst files, and Word documents."""

from collections.abc import Iterable
from pathlib import Path
from typing import Literal

from anatole.export.latex import TARGETS, Target, to_latex
from anatole.export.office import OfficeError, to_docx
from anatole.export.typst import to_typst
from anatole.logging import get_logger
from anatole.model import NotationSet
from anatole.typing import Format, Language

__all__ = [
    "OUTPUTS",
    "SUFFIXES",
    "TARGETS",
    "OfficeError",
    "Output",
    "Target",
    "export",
    "format_of",
    "to_docx",
    "to_latex",
    "to_text",
    "to_typst",
]

type Output = Format | Literal["docx"]
"""What an export writes: a LaTeX or Typst file, or a Word document."""

OUTPUTS: tuple[Output, ...] = ("latex", "typst", "docx")
"""The outputs of :func:`export`."""

SUFFIXES: dict[str, Output] = {
    ".tex": "latex",
    ".sty": "latex",
    ".typ": "typst",
    ".docx": "docx",
}
"""The file suffixes whose output :func:`format_of` recognizes."""

_logger = get_logger(__name__)


def format_of(path: str | Path) -> Output:
    """Return the output of an export file, from its suffix (see :data:`SUFFIXES`).

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
    fmt: Output | None = None,
    *,
    language: Language | None = None,
    target: Target = "nomencl+acro",
    tags: Iterable[str] | None = None,
    source: str | None = None,
    reference_doc: str | Path | None = None,
) -> list[str]:
    """Write the export of ``notations`` to ``path``.

    Parameters
    ----------
    notations
        The notations.
    path
        The file to write.
    fmt
        The output (``latex``, ``typst`` or ``docx``); ``None`` to tell it from the suffix of
        ``path``.
    language
        The language of the descriptions and group titles; the default language when ``None``.
    target
        The LaTeX packages of the lists: ``nomencl+acro`` or ``glossaries``.
    tags
        Export only the entries selected by these tags (and the entries they use); all the
        entries when ``None``.
    source
        The notation file, named in the header comment.
    reference_doc
        For a Word document, a document whose styles it takes (see :func:`to_docx`).

    Returns
    -------
    list[str]
        The problems of a Word export (see :func:`to_docx`); empty for the other outputs.

    Raises
    ------
    ValueError
        If ``fmt`` is ``None`` and the suffix of ``path`` is not recognized.
    NotationError
        If the notations cannot be exported (see :func:`to_latex`), or ``language`` is not
        declared.
    OfficeError
        If a Word document cannot be written (pandoc missing or failing).
    OSError
        If the file cannot be written.
    """
    path = Path(path)
    fmt = fmt or format_of(path)
    if fmt == "docx":
        selected = notations if tags is None else notations.subset(tags)
        return to_docx(selected, path, language=language, reference_doc=reference_doc)
    text = to_text(notations, fmt, language=language, target=target, tags=tags, source=source)
    _ = path.write_text(text, encoding="utf-8")
    _logger.info("exported %d notations to %s (%s)", len(notations), path, fmt)
    return []
