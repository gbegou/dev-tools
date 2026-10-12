User manual
===========

Installation
------------

Python 3.12 or later, with no other dependency. The graphical interface needs Tkinter (part
of most Python installations; ``python3-tk`` on Debian and Ubuntu). The Typst preview in the
interface needs the ``typst`` package:

.. code-block:: console

   $ pip install notation-manager             # or: pip install -e . from a checkout
   $ pip install 'notation-manager[preview]'  # with the Typst preview

This installs the ``notation-manager`` command (also ``python -m notation_manager``).

In short
--------

1. Write the notations in a notation file (by hand, or with ``notation-manager gui``).
2. Export them: ``notation-manager export notations.toml notations.tex`` and
   ``notation-manager export notations.toml notations.typ``.
3. Use them: ``\velocity`` in LaTeX, ``$velocity$`` in Typst, and print the nomenclature.

The notation file
-----------------

A notation file is a TOML file. Here is the example of the repository,
``examples/notations.toml``:

.. literalinclude:: ../examples/notations.toml
   :language: toml

``version``
   The version of the file format, ``1``; optional.

``[groups.<key>]``
   A group, shown under its ``title`` in the nomenclature. The key is letters, digits,
   ``_`` and ``-``. The groups appear in the nomenclature in the order of the file.

``[notations.<name>]``
   A notation. The name is the command: ``velocity`` gives ``\velocity`` in LaTeX and
   ``velocity`` in Typst. It is two letters or more, letters only (``A-Z``, ``a-z``): LaTeX
   control words are letters only, and Typst math reads a single letter as a variable, not
   as a name. The fields are:

   .. list-table::
      :header-rows: 1
      :widths: 15 10 75

      * - Field
        - Required
        - Content
      * - ``symbol``
        - yes
        - The symbol, as math-mode code without the ``$`` delimiters.
      * - ``description``
        - yes
        - The description, as text-mode markup.
      * - ``units``
        - no
        - The units, as text-mode markup.
      * - ``group``
        - no
        - The key of the notation's group.
      * - ``arguments``
        - no
        - The number of arguments, 0 (the default) to 9.
      * - ``sort``
        - no
        - The sort key in the nomenclature (the name by default).

Rendered fields
   ``symbol``, ``description``, ``units`` and ``title`` are each a string, the same in every
   language (``description = "Velocity"``), or a table with one string per language
   (``symbol = { latex = '\mathbf{u}', typst = 'bold(upright(u))' }``). TOML literal strings,
   between single quotes, need no escaping of backslashes.

Arguments
   A notation with arguments uses the placeholders ``#1`` to ``#9`` in its symbol, in both
   languages: ``symbol = { latex = '\left\lVert #1 \right\rVert', typst = 'lr(|| #1 ||)' }``
   with ``arguments = 1``. In the nomenclature, the arguments are shown as a centered dot.

Sorting
   Within its group, the nomenclature sorts the notations by sort key (or name), regardless
   of case. Set ``sort`` to sort a notation by its symbol rather than by its name:
   ``sort = "rho"`` for ``\density``. The sort key is letters, digits, spaces, ``_``, ``.``
   and ``-`` (characters that ``makeindex`` sorts without quoting). The notations without a
   group come first, with no title.

Validation
~~~~~~~~~~

Reading a file checks every notation and reports every problem at once, each naming the
notation (or group) and the field; nothing is read when there is a problem. The checks are:

- the name is two letters or more; it is not a Typst keyword (``in``, ``none``, ``let``...),
  nor ``std`` or ``notationnomenclature`` (which the exports define), nor a name that starts
  with ``end`` (LaTeX does not define those with ``\newcommand``);
- the symbol and the description are given in every language; the units are given in every
  language or in none;
- the braces of the LaTeX texts balance (``\{`` and ``\}`` aside);
- the placeholders are ``#1`` to ``#N``, for a notation of ``N`` arguments;
- the group exists, the keys of the file and of its tables are known (a misspelled ``unit``
  is an error, not ignored), and each value has the right type.

.. literalinclude:: ../test/snippet_api.py
   :language: python
   :start-after: # [errors]
   :end-before: # [errors]
   :dedent:

``notation-manager check notations.toml`` runs the same checks. The checks do not compile
the symbols: a LaTeX or Typst error in a symbol shows in the preview of the interface (Typst)
or when the document is compiled.

LaTeX
-----

Export with ``notation-manager export notations.toml notations.tex`` (or the *File* menu of
the interface). The file defines one command per notation, in text and math mode:

.. code-block:: latex

   \newcommand{\velocity}{\ensuremath{\mathbf{u}}}
   \newcommand{\norm}[1]{\ensuremath{\left\lVert #1 \right\rVert}}

and ``\notationnomenclature``, which declares the ``nomencl`` entry of every notation. Input
the file in the preamble, after ``nomencl``, and call ``\notationnomenclature`` in the
document, before ``\printnomenclature`` (``examples/document.tex``):

.. literalinclude:: ../examples/document.tex
   :language: latex
   :start-after: % [preamble]
   :end-before: % [preamble]

.. literalinclude:: ../examples/document.tex
   :language: latex
   :start-after: % [body]
   :end-before: % [body]

Build the nomenclature with ``makeindex``, as ``nomencl`` documents::

   pdflatex document
   makeindex document.nlo -s nomencl.ist -o document.nls
   pdflatex document

(``latexmk`` does it with a custom dependency, see the ``nomencl`` documentation.)

Details
   - ``\newcommand`` fails when LaTeX or a package already defines the name (``\time`` is a
     TeX primitive, for one): rename the notation. From Python,
     :func:`~notation_manager.export.latex.to_latex` takes ``definition="providecommand"``
     (keep the existing command) or ``"renewcommand"`` (replace it).
   - The units go to ``\nomunit``, right-aligned. ``nomencl`` 5.6 does not define it, so the
     file defines it when it is missing, as the ``nomencl`` documentation suggests. The
     units are LaTeX code: ``\si{...}`` needs ``siunitx``.
   - With groups, the file redefines ``\nomgroup`` to print the group titles in bold.
     ``nomencl`` tells groups apart by the first letter of the sort prefix (``A`` for the
     notations without a group, then ``B``, ``C``...), so a document has at most 25 groups
     with notations.
   - The entries are declared where ``\notationnomenclature`` is called, not in the
     preamble, where ``nomencl`` would lose them.

Typst
-----

Export with ``notation-manager export notations.toml notations.typ``. The file defines one
variable per notation, or a function for a notation with arguments:

.. code-block:: text

   #let velocity = $bold(upright(u))$
   #let norm = (arg1) => $lr(|| #(arg1) ||)$

and the nomenclature: ``notation-groups`` holds the entries by group, in nomenclature order,
and ``notation-nomenclature()`` prints them. Import the file where the notations are used
(``examples/document.typ``):

.. literalinclude:: ../examples/document.typ
   :language: typst
   :start-after: // [import]
   :end-before: // [import]

.. literalinclude:: ../examples/document.typ
   :language: typst
   :start-after: // [body]
   :end-before: // [body]

``notation-nomenclature`` takes these parameters:

================= ============================ ============================================
Parameter         Default                      Meaning
================= ============================ ============================================
``title``         ``[Nomenclature]``           A heading (not numbered); ``none`` for none.
``columns``       ``(auto, 1fr, auto)``        The symbol, description and units columns.
``align``         ``(left, left, right)``      Their alignment.
``column-gutter`` ``1em``                      The space between columns.
``row-gutter``    ``0.8em``                    The space between rows.
``group-title``   ``title => strong(title)``   How a group title is shown.
================= ============================ ============================================

For another layout, iterate ``notation-groups``: each group is a dictionary with ``key``,
``title`` (``none`` for the notations without a group) and ``entries``, and each entry has
``name``, ``symbol``, ``description`` and ``units`` (``none`` when there are none).

Details
   - The export needs Typst 0.13 or later: it uses the ``std`` module, so that notations
     named like Typst functions (``grid``, ``title``...) do not break the nomenclature.
   - A notation named like a Typst function shadows it in the documents that import the
     file; its own symbol can still use the function (``#let norm = (arg1) => $norm(...)$``
     calls the builtin ``norm``: an anonymous function does not see its own name).
   - The helpers have hyphenated names, which no notation can take.

Graphical interface
-------------------

``notation-manager gui notations.toml`` (or just ``notation-manager``) opens the interface.

- On the left, the notations by group; the search field filters them on every field (name,
  group, sort key, symbols, descriptions, units), all words matching.
- On the right, the editor of the selected notation: its name, group, number of arguments
  and sort key, then its symbol, description and units in LaTeX and in Typst. *Apply*
  (Ctrl+Enter) checks the notation and applies it, or shows its problems under the editor;
  *Revert* discards the changes; *New* (Ctrl+N) and *Duplicate* start a new notation;
  *Delete* removes it. Selecting another notation with changes not applied asks whether to
  apply them.
- Under the editor, the notation rendered by Typst as in the nomenclature (with the
  ``typst`` package), updated as you type, or the Typst error.
- *Edit › Groups* adds, renames, retitles, reorders and deletes groups (a group with
  notations cannot be deleted; renaming a group moves its notations).
- *File* opens and saves notation files (Ctrl+O, Ctrl+S) and exports to LaTeX and Typst.
  Closing with unsaved changes asks whether to save them.

The interface rewrites the file when it saves: comments are lost, and strings are written
as TOML literal strings when they can be.

Command line
------------

``notation-manager gui [FILE]``
   Open the interface (the default command).
``notation-manager check FILE...``
   Check notation files; report every problem, exit with 1 if a file is invalid.
``notation-manager list [-l {latex,typst}] FILE``
   List the notations: name, group, symbol and description in one language.
``notation-manager export [-l {latex,typst}] FILE OUTPUT``
   Export a notation file; the language follows the suffix of ``OUTPUT`` (``.tex`` and
   ``.sty``: LaTeX, ``.typ``: Typst) unless ``--language`` is given.

``-v`` logs what is read and written. The exit code is 0 on success, 1 when a file cannot
be read, is invalid or cannot be exported, and 2 on a usage error.

Python
------

The package builds, reads, writes and exports notation sets
(:class:`~notation_manager.model.NotationSet`):

.. literalinclude:: ../test/snippet_api.py
   :language: python
   :start-after: # [build]
   :end-before: # [build]
   :dedent:

.. literalinclude:: ../test/snippet_api.py
   :language: python
   :start-after: # [export]
   :end-before: # [export]
   :dedent:

:func:`~notation_manager.io.to_dict` and :func:`~notation_manager.io.from_dict` convert to
and from the dict of a notation file, to store notations elsewhere (JSON, a database...).
See the :doc:`api`.
