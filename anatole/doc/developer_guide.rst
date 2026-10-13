Developer guide
===============

Layout
------

.. code-block:: text

   src/anatole/
       model/            texts.py (Rendered, Translated, references, checks), entries.py
                         (Notation, Acronym, Style, Group), notations.py (NotationSet:
                         consistency, renames, group tree, sections, tags)
       io.py             notation files (TOML): read, write, to and from dicts
       export/_common.py what the exports share: language, references, styles
       export/latex.py   LaTeX export (commands; nomencl and acro, or glossaries-extra)
       export/typst.py   Typst export (functions, variables, acronyms, lists)
       export/office.py  Word export (pandoc, from a LaTeX source of the lists)
       preview.py        Typst rendering of a notation (optional typst package)
       cli.py            command line
       gui/              Tkinter interface: app (main window), groups (group editor),
                         form (the logic without a display), prompts (dialogs)
       typing.py         types for clients (Format, Language)
       logging.py        get_logger
   test/                 test_*.py, and snippet_*.py included in the documentation
   examples/             the example notation file and documents (tested and documented)
   doc/                  this documentation (Sphinx)

Conventions
-----------

- Two words are kept apart: a **format** is LaTeX or Typst
  (:data:`~anatole.typing.Format`, ``fmt`` in code, ``--format``), a **language**
  is a natural language (:data:`~anatole.typing.Language`, a code like ``fr``,
  ``--language``). A text per format is a :class:`~anatole.model.Rendered`, a text
  per language a :class:`~anatole.model.Translated` of them.
- Python 3.12 or later, no runtime dependency; ``typst`` is the optional ``preview`` extra.
  Type aliases are ``type X = ...`` statements.
- ruff (lint and format) and basedpyright (its default, strict, configuration): 0 errors,
  0 warnings. A suppression names its rule and says why (typeshed leaves some Tk options
  untyped).
- NumPy-style docstrings, rendered by the API page.
- A notation, group or file problem is a :class:`~anatole.model.NotationError`
  whose ``problems`` list every problem, each naming the notation (or group) and the field.
  Functions that read user input report every problem at once, never the first only.
- A change to a notation set either keeps it consistent or raises, leaving it as it was: the
  set checks the whole of it after each change (references, cycles, groups, languages).
- The model knows nothing of the interface; the interface logic that needs no display
  (forms, search) is in ``gui/form.py``, tested without Tk.
- The names the exports define are reserved (``RESERVED_NAMES`` in ``anatole.model``):
  a new LaTeX helper is a reserved letters-only name, a new Typst helper a hyphenated name
  (which no notation can take).

Setting up
----------

.. code-block:: console

   $ python3.12 -m venv .venv && . .venv/bin/activate
   $ pip install -e . --group dev        # pip 25.1 or later; or: uv sync --group dev

Checks
------

Before every push:

.. code-block:: console

   $ ruff format --check . && ruff check .
   $ basedpyright
   $ xvfb-run -a pytest            # the GUI tests need a display; they are skipped without
   $ sphinx-build -W --keep-going -E -b html doc doc/_build/html

The tests that need a tool are skipped when it is missing: the GUI tests (Tkinter and a
display), the LaTeX documents (``pdflatex``, ``makeindex``, ``nomencl``, ``acro``,
``glossaries-extra``, ``siunitx``), the Typst documents and preview (``typst`` package), the
Word export (``pypandoc-binary``, ``python-docx``), the documentation build (Sphinx and furo).
Run them all before a push: the skip reasons are listed by ``pytest -rs``.

The example documents are compiled by the tests: ``examples/document.tex`` with the LaTeX
export of ``examples/notations.toml``, and ``examples/document.typ`` with its Typst export.

Checklist for a new feature
---------------------------

- Tests next to the code it exercises (``test/test_<module>.py``), including the problems
  reported for invalid input.
- ``__all__`` of the module, and ``anatole/__init__.py`` or ``typing.py`` when
  clients need it.
- Docstrings, and the module on the :doc:`api` page.
- The :doc:`user_manual`: what it does, its limits, a tested example (``examples/`` or
  ``test/snippet_<topic>.py`` with ``literalinclude`` markers).
- The :doc:`release_notes` and the :doc:`roadmap`.
- When the export changes: compile the example documents (the tests do it), and check the
  output by eye.
- The checks above: ruff, basedpyright, every test with every tool, the documentation.
