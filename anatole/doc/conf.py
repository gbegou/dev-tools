"""Sphinx configuration."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from notation_manager import __version__  # noqa: E402

project = "notation-manager"
author = "Guillaume Begou"
copyright = "2026, Guillaume Begou"
release = __version__
version = __version__

extensions = ["sphinx.ext.autodoc", "sphinx.ext.napoleon"]
autodoc_member_order = "bysource"
autodoc_typehints = "description"
autodoc_default_options = {"members": True, "show-inheritance": True}
napoleon_google_docstring = False
napoleon_numpy_docstring = True
nitpicky = True
nitpick_ignore_regex = [
    # The standard library: no intersphinx, so that the build needs no network.
    ("py:.*", r"(collections|logging|pathlib|tkinter|tomllib|typing)(\..*)?"),
]

html_theme = "furo"
html_title = f"notation-manager {release}"
exclude_patterns = ["_build"]
