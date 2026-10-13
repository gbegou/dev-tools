r"""The model: entries (notations, acronyms, abbreviations), styles, groups, and their set.

A notation has a command name (``\velocity`` in LaTeX, ``velocity`` in Typst), a symbol and
optional units written once per target format (:class:`Rendered`), and a description written
once per natural language (:class:`Translated`). An acronym has a short and a long form per
language. A style is a template applied to symbols (vectors in bold, or with an arrow). Texts
refer to other entries with ``@{name}``. Groups form a tree of sections and subsections.
"""

from anatole.model.entries import (
    MAX_ARGUMENTS,
    MAX_GROUP_DEPTH,
    RESERVED_NAMES,
    Acronym,
    Entry,
    Group,
    Item,
    Notation,
    Style,
)
from anatole.model.notations import Kind, NotationSet, Section
from anatole.model.texts import (
    GROUP_KEY_PATTERN,
    LANGUAGE_PATTERN,
    NAME_PATTERN,
    REFERENCE_PATTERN,
    SORT_PATTERN,
    TAG_PATTERN,
    NotationError,
    Rendered,
    Translated,
    references,
    rename_references,
)

__all__ = [
    "GROUP_KEY_PATTERN",
    "LANGUAGE_PATTERN",
    "MAX_ARGUMENTS",
    "MAX_GROUP_DEPTH",
    "NAME_PATTERN",
    "REFERENCE_PATTERN",
    "RESERVED_NAMES",
    "SORT_PATTERN",
    "TAG_PATTERN",
    "Acronym",
    "Entry",
    "Group",
    "Item",
    "Kind",
    "Notation",
    "NotationError",
    "NotationSet",
    "Rendered",
    "Section",
    "Style",
    "Translated",
    "references",
    "rename_references",
]
