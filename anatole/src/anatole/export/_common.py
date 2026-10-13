"""What the exports share: the choice of the language."""

from anatole.logging import get_logger
from anatole.model import NotationSet
from anatole.typing import Language

_logger = get_logger(__name__)


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
