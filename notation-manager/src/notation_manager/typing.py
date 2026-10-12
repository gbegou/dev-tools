"""Types that clients of notation_manager need."""

from typing import Literal

__all__ = ["LANGUAGES", "Language"]

type Language = Literal["latex", "typst"]
"""A target language: every rendering has one text per language."""

LANGUAGES: tuple[Language, ...] = ("latex", "typst")
"""The target languages, in the order they are shown and written."""
