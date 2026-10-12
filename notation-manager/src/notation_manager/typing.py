"""Types that clients of notation_manager need."""

from typing import Literal

__all__ = ["FORMATS", "Format", "Language"]

type Format = Literal["latex", "typst"]
"""A target format: symbols and units are written once per format."""

FORMATS: tuple[Format, ...] = ("latex", "typst")
"""The target formats, in the order they are shown and written."""

type Language = str
"""A natural language, as a code (``en``, ``fr``, ``pt-BR``): descriptions and group titles are
written once per language."""
