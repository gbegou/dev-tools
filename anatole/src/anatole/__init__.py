"""ANATOLE is a Notations And acronyms manager with Typst Or LaTeX Exporters.

Notations defined once, rendered in LaTeX and Typst.

A notation file (TOML) holds notations (a command name, a symbol and units written once per
format, LaTeX and Typst, and a description written once per language, English, French...),
acronyms and abbreviations, styles applied to symbols (vectors in bold or with an arrow), and
a tree of groups. Texts refer to other entries with ``@{name}``. The package reads and writes
these files, exports them to LaTeX (nomencl and acro, or glossaries-extra) and Typst, in a
chosen language, and has a graphical interface to browse and edit them.
"""

from anatole.export import export, to_latex, to_typst
from anatole.io import dumps, from_dict, load, loads, save, to_dict
from anatole.model import (
    Acronym,
    Group,
    Notation,
    NotationError,
    NotationSet,
    Rendered,
    Style,
    Translated,
)

__all__ = [
    "Acronym",
    "Group",
    "Notation",
    "NotationError",
    "NotationSet",
    "Rendered",
    "Style",
    "Translated",
    "__version__",
    "dumps",
    "export",
    "from_dict",
    "load",
    "loads",
    "save",
    "to_dict",
    "to_latex",
    "to_typst",
]

__version__ = "0.1.0"
