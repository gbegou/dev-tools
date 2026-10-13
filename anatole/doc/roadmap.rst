Roadmap
=======

Ideas not done yet, roughly by priority.

- A LaTeX preview in the graphical interface (``pdflatex`` and ``dvipng`` or ``pdftocairo``,
  when installed), next to the Typst one.
- An ``add`` command, to create notations from scripts.
- Word: an equation gallery (a ``.dotx`` template with a building block per notation:
  ``velocity`` then F3 inserts its equation).
- PowerPoint: the lists on slides, and an SVG image of each symbol (rendered by Typst).
- Plural forms of acronyms (``acro``'s ``short-plural``, ``glossaries``' ``shortplural``).
- Tags chosen in the interface for its exports (the command line has ``--tag``).
- A multilingual export, whose descriptions follow the language of the document
  (``text.lang`` in Typst, ``\languagename`` with babel in LaTeX), for documents that
  switch languages.
- Export options on the command line: the LaTeX definition command (``\providecommand``,
  ``\DeclareRobustCommand``), as :func:`~anatole.export.latex.to_latex` already
  takes.
- Importing the commands of an existing LaTeX file (``\newcommand`` lines) into a notation file.
- Keeping the comments of a notation file when the interface saves it (the TOML is
  rewritten, so comments are lost today).
- GitLab CI, from the ``templates/gitlab-ci`` layout of dev-tools adapted to a pure Python
  package (no build stage).
