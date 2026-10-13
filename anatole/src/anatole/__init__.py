"""ANATOLE is a Notations And acronyms manager with Typst Or LaTeX Exporters.

Notations defined once, rendered in LaTeX and Typst.

A notation file (TOML) holds notations: a command name, a symbol and units written once per
format (LaTeX, Typst), and a description written once per language (English, French...). The
package reads and writes these files, exports them to a LaTeX file (commands and a nomencl
nomenclature) and a Typst file (variables and a nomenclature), in a chosen language, and has
a graphical interface to browse and edit them.
"""

from anatole.export import export, to_latex, to_typst
from anatole.io import dumps, from_dict, load, loads, save, to_dict
from anatole.model import (
    Group,
    Notation,
    NotationError,
    NotationSet,
    Rendered,
    Translated,
)

__all__ = [
    "Group",
    "Notation",
    "NotationError",
    "NotationSet",
    "Rendered",
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
