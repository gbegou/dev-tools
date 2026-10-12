"""Notations defined once, rendered in LaTeX and Typst.

A notation file (TOML) holds notations: a command name, a symbol, a description and units,
each rendered once per language. The package reads and writes these files, exports them to a
LaTeX file (commands and a nomencl nomenclature) and a Typst file (variables and a
nomenclature), and has a graphical interface to browse and edit them.
"""

from notation_manager.export import export, to_latex, to_typst
from notation_manager.io import dumps, from_dict, load, loads, save, to_dict
from notation_manager.model import Group, Notation, NotationError, NotationSet, Rendered

__all__ = [
    "Group",
    "Notation",
    "NotationError",
    "NotationSet",
    "Rendered",
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
