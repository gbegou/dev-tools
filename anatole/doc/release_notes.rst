Release notes
=============

0.1.0 (unreleased)
------------------

First version.

- Notation files (TOML): notations with a command name, a symbol and units written per
  format (LaTeX, Typst, or once for both), a description written per language (English,
  French...: the languages are declared in the file, the first one is the default), a
  group, a number of arguments and a sort key; groups with a title per language. Every
  problem of a file is reported at once, naming the notation and the field; the
  translations missing are listed.
- Exports in a chosen language, falling back on the default language (with a warning) for
  the translations missing.
- LaTeX export: one command per notation (``\newcommand``, with ``\ensuremath``), and
  ``\notationnomenclature`` that declares the ``nomencl`` entries, sorted by group then sort
  key, with group titles and units (``\nomunit``).
- Typst export: one variable per notation, or an anonymous function of its arguments, and
  ``notation-nomenclature()``.
- Graphical interface (Tkinter): a searchable tree by group, an editor with a description
  per language, a language selector, a group editor, a languages dialog, a Typst preview
  (with the optional ``typst`` package), open, save and export.
- Command line: ``gui``, ``check`` (``--strict`` for missing translations), ``list`` and
  ``export`` (``--format``, ``--language``).
