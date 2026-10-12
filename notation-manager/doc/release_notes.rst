Release notes
=============

0.1.0 (unreleased)
------------------

First version.

- Notation files (TOML): notations with a command name, a symbol, a description, units, a
  group, a number of arguments and a sort key, each rendered text written once per language
  (or once for both); groups with a title. Every problem of a file is reported at once,
  naming the notation and the field.
- LaTeX export: one command per notation (``\newcommand``, with ``\ensuremath``), and
  ``\notationnomenclature`` that declares the ``nomencl`` entries, sorted by group then sort
  key, with group titles and units (``\nomunit``).
- Typst export: one variable per notation, or an anonymous function of its arguments, and
  ``notation-nomenclature()``.
- Graphical interface (Tkinter): a searchable tree by group, an editor, a group editor, a
  Typst preview (with the optional ``typst`` package), open, save and export.
- Command line: ``gui``, ``check``, ``list``, ``export``.
