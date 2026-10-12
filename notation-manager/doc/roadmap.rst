Roadmap
=======

Ideas not done yet, roughly by priority.

- A LaTeX preview in the graphical interface (``pdflatex`` and ``dvipng`` or ``pdftocairo``,
  when installed), next to the Typst one.
- An ``add`` command, to create notations from scripts.
- Export options on the command line: the LaTeX definition command (``\providecommand``,
  ``\DeclareRobustCommand``), as :func:`~notation_manager.export.latex.to_latex` already takes.
- Importing the commands of an existing LaTeX file (``\newcommand`` lines) into a notation file.
- A LaTeX nomenclature for ``glossaries`` (symbols list) as well as ``nomencl``.
- Keeping the comments of a notation file when the interface saves it (the TOML is
  rewritten, so comments are lost today).
- GitLab CI, from the ``templates/gitlab-ci`` layout of dev-tools adapted to a pure Python
  package (no build stage).
