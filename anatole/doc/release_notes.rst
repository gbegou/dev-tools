Release notes
=============

0.1.0 (unreleased)
------------------

First version.

- Notation files (TOML) with three kinds of entries and styles:

  - notations: a command name, a symbol and units written per format (LaTeX, Typst, or once
    for both), a description written per language, a number of arguments, a style;
  - acronyms (expanded at their first use) and abbreviations (never expanded): a short and a
    long form per language, an optional description;
  - styles: templates applied to symbols (vectors in bold, or with an arrow), changed in one
    place for every symbol that uses them.

- Languages declared in the file, the first one the default; the translations in the other
  languages are optional, and listed when missing.
- References between entries, ``@{name}``, checked (existence, no cycle), followed by
  renames, and expanded by the exports (``\redelta`` uses ``\blthickness``).
- A tree of groups (sections and subsections) that heads the lists, and tags that select
  the entries of a document.
- Every problem of a file is reported at once, naming the entry and the field.
- LaTeX export, with two targets for the lists: ``nomencl`` and ``acro`` (the default), or
  ``glossaries-extra`` (one glossary per group, no external tool). Commands for the styles
  and notations, each after the ones it uses.
- Typst export: functions for the styles, variables (or functions) for the notations,
  acronyms that expand at their first use, ``notation-nomenclature()`` and
  ``notation-acronyms()``.
- Word export (``.docx``, with pandoc): the lists, with the symbols as Word equations and the
  siunitx units converted; what cannot be converted is reported by entry.
- Exports in a chosen language, falling back on the default language (with a warning) for
  the translations missing.
- Graphical interface (Tkinter): a searchable tree of styles and entries by group, an editor
  for each kind with a text per language, a language selector, a group editor, a languages
  dialog, a Typst preview with the entries an item uses (with the optional ``typst``
  package), open, save and export.
- Command line: ``gui``, ``check`` (``--strict`` for missing translations), ``list`` and
  ``export`` (``--format``, ``--language``, ``--latex-target``, ``--tag``).
