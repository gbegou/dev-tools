r"""What the exports share: the language, references between entries, and styles.

A reference ``@{name}`` becomes, in LaTeX, the command (``{\delta}``, ``\norm`` for a command
with arguments) or the acronym (``\ac{cfd}``, ``\gls{cfd}``); in Typst, the variable
(``#delta``, ended by ``;`` when a letter follows) or, in math, the function (``norm``).
"""

import re
from collections.abc import Callable
from typing import Literal

from anatole.logging import get_logger
from anatole.model import REFERENCE_PATTERN, Acronym, Notation, NotationSet, Style
from anatole.typing import Format, Language

__all__ = ["Context", "expand", "resolve_language", "symbol"]

type Context = Literal["math", "text"]
"""Where a text goes: in math mode (symbols, templates) or text mode (descriptions)."""

_logger = get_logger(__name__)

# Characters after a Typst identifier that would continue it (or its expression).
_TYPST_CONTINUES = re.compile(r"[A-Za-z0-9_.(\[-]")


def resolve_language(notations: NotationSet, language: Language | None) -> Language:
    """Return the language of an export: ``language``, or the default language when ``None``.

    Log a warning for each translation missing in it (the export falls back on the default
    language).

    Raises
    ------
    NotationError
        If ``language`` is not declared.
    """
    if language is None:
        return notations.default_language
    notations.check_language(language)
    for problem in notations.missing_translations([language]):
        _logger.warning(
            "%s: the export uses the default language %s", problem, notations.default_language
        )
    return language


def _takes_arguments(item: Notation | Acronym | Style) -> bool:
    return isinstance(item, Style) or (isinstance(item, Notation) and item.arguments > 0)


def expand(
    text: str,
    fmt: Format,
    notations: NotationSet,
    context: Context,
    *,
    acronym_command: str = "ac",
    acronym_text: Callable[[Acronym], str] | None = None,
) -> str:
    """Return ``text`` with its references ``@{name}`` written in the format ``fmt``.

    Parameters
    ----------
    text
        The text, in the format ``fmt``.
    fmt
        The format.
    notations
        The set the names belong to.
    context
        Whether the text is math (symbols, templates) or text (descriptions).
    acronym_command
        The LaTeX command that prints an acronym (``ac`` for acro, ``gls`` for glossaries).
    acronym_text
        The LaTeX text of an acronym, instead of the command (for a document without
        acronym package).
    """

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        item = notations[name]
        after = text[match.end() : match.end() + 1]
        if fmt == "latex":
            if isinstance(item, Acronym):
                if acronym_text is not None:
                    return acronym_text(item)
                return rf"\{acronym_command}{{{name}}}"
            # Braces keep the spaces after a command; arguments follow a command that takes some.
            return rf"\{name}" if _takes_arguments(item) else rf"{{\{name}}}"
        if context == "math" and _takes_arguments(item):
            return name  # a call in math mode: norm(x)
        return f"#{name}" + (";" if _TYPST_CONTINUES.match(after) else "")

    return REFERENCE_PATTERN.sub(replace, text)


def symbol(notation: Notation, fmt: Format, notations: NotationSet) -> str:
    r"""Return the symbol of ``notation`` in the format ``fmt``.

    The references are expanded and the style applied (``\vect{u}``, ``vect(u)``).
    """
    text = expand(notation.symbol.get(fmt), fmt, notations, "math")
    if not notation.style:
        return text
    return rf"\{notation.style}{{{text}}}" if fmt == "latex" else f"{notation.style}({text})"
