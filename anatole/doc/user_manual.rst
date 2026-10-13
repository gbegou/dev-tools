User manual
===========

Installation
------------

Python 3.12 or later, with no other dependency. The graphical interface needs Tkinter (part
of most Python installations; ``python3-tk`` on Debian and Ubuntu). The Typst preview in the
interface needs the ``typst`` package:

.. code-block:: console

   $ pip install anatole             # or: pip install -e . from a checkout
   $ pip install 'anatole[preview]'  # with the Typst preview
   $ pip install 'anatole[office]'   # with the Word export (pandoc)

This installs the ``anatole`` command (also ``python -m anatole``).

In short
--------

1. Write the notations and acronyms in a notation file (by hand, or with ``anatole gui``),
   with their descriptions in one language or several (English, French...).
2. Export them, in the language of the document: ``anatole export notations.toml
   notations.tex`` and ``anatole export --language fr notations.toml notations.typ``.
3. Use them: ``\velocity`` and ``\ac{cfd}`` in LaTeX, ``$velocity$`` and ``#cfd`` in Typst,
   and print the lists.

The notation file
-----------------

A notation file is a TOML file. Two things vary in it:

- the **format**, LaTeX or Typst: the code of a symbol differs (``\mathbf{u}``,
  ``bold(u)``), and so may the units and, rarely, a text that holds markup;
- the **language**, English, French...: the descriptions, the group titles and the acronyms
  are translated.

Here is the example of the repository, ``examples/notations.toml``, in English and French:

.. literalinclude:: ../examples/notations.toml
   :language: toml

It holds three kinds of **entries**, listed in the document, and **styles**:

``[notations.<name>]``
   A notation: a command (``\velocity``, ``velocity``), its symbol, units and description.
``[acronyms.<name>]``
   An acronym: printed long with its short form at its first use (*computational fluid
   dynamics (CFD)*), short afterwards (*CFD*).
``[abbreviations.<name>]``
   An abbreviation: always printed short (*w.r.t.*), listed with its long form.
``[styles.<name>]``
   A style: a template applied to symbols, such as the vector style. Changing the template
   changes every symbol that uses it.

Their names are commands, letters only, two or more (``A-Z``, ``a-z``): LaTeX control words
are letters only, and Typst math reads a single letter as a variable, not as a name. A name is
used once, whatever the kind.

The file also declares:

``version``
   The version of the file format, ``1``; optional.
``languages``
   The language codes of the texts (``en``, ``fr``, ``de``, ``pt-BR``: the codes of Typst's
   ``text(lang:)`` and of BCP 47); ``["en"]`` when it is left out. The first one is the
   **default language**: every description, title and acronym has a translation in it. The
   other translations are optional; an export in a language falls back on the default
   language for the ones missing, with a warning.
``[groups.<section>]``, ``[groups.<section>.<subsection>]``
   The groups, a tree of sections and subsections (two levels), each with a ``title``. They
   are the headings of the lists, in the order of the file. An entry names its group with its
   key, ``symbols.latin`` for a subsection.

Notations
~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 15 10 75

   * - Field
     - Required
     - Content
   * - ``symbol``
     - yes
     - The symbol, per format, as math-mode code without the ``$`` delimiters. With a style,
       the argument of the style (``u`` for a bold ``u``).
   * - ``description``
     - yes
     - The description, per language, as text-mode markup.
   * - ``units``
     - no
     - The units, per format, as text-mode markup (not translated).
   * - ``style``
     - no
     - The name of the style applied to the symbol.
   * - ``group``
     - no
     - The key of the notation's group.
   * - ``arguments``
     - no
     - The number of arguments, 0 (the default) to 9.
   * - ``sort``
     - no
     - The sort key in the lists (the name by default).
   * - ``tags``
     - no
     - Tags that select the notation for an export (see `Tags`_).

Acronyms and abbreviations
~~~~~~~~~~~~~~~~~~~~~~~~~~

``short`` and ``long`` (required) are the short and long forms, per language
(``short = { en = "CFD", fr = "MFN" }``); ``description`` (optional) adds a sentence to the
list; ``group``, ``sort`` and ``tags`` are as for notations.

Styles
~~~~~~

``template`` (required) is the template, per format, with ``#1`` for the symbol it is applied
to: ``template = { latex = '\boldsymbol{#1}', typst = 'bold(#1)' }`` for vectors in bold,
``{ latex = '\vec{#1}', typst = 'arrow(#1)' }`` for vectors with an arrow. ``description``
(optional) says what it is for. A notation with ``style = "vect"`` and ``symbol = 'u'`` has
the symbol ``\vect{u}``; the style is also a command of the documents (``\vect{x}``,
``$vect(x)$``) for the vectors that are not notations.

Texts per format and per language
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Fields per format
   ``symbol``, ``units`` and ``template`` are a string, the same in both formats
   (``symbol = 'p'``), or a table with one string per format
   (``symbol = { latex = '\mathbf{u}', typst = 'bold(upright(u))' }``). TOML literal
   strings, between single quotes, need no escaping of backslashes.

Fields per language
   ``description``, ``title``, ``short`` and ``long`` are a table with one entry per
   language (``description = { en = "Velocity", fr = "Vitesse" }``), each entry a string, the
   same in both formats, or a table with one string per format, for a text that holds
   markup. A string, or a table of formats, alone is the text in the default language: a file
   in one language writes ``description = "Velocity"``.

References between entries
~~~~~~~~~~~~~~~~~~~~~~~~~~

A text refers to another entry with ``@{name}``, so that it uses its notation and follows its
changes. The Reynolds number based on the boundary-layer thickness writes:

.. code-block:: toml

   [notations.redelta]
   symbol = { latex = '\mathit{Re}_{@{blthickness}}', typst = 'italic("Re")_(@{blthickness})' }
   description = { en = "Reynolds number based on @{blthickness}" }

The exports write ``{\blthickness}`` in LaTeX (the braces keep the space after it in a
text) and ``#blthickness`` in Typst (``#blthickness;`` before a letter); a notation with
arguments or a style is written ``\norm`` and ``norm``, and its arguments follow:
``@{norm}{x}`` in LaTeX, ``@{norm}(x)`` in Typst math. A reference to an acronym prints it:
``\ac{cfd}`` (acro), ``\gls{cfd}`` (glossaries), ``#cfd`` (Typst).

References are checked: the entry must exist, and references must not form a cycle. Renaming
an entry (in the interface or with :meth:`~anatole.model.NotationSet.replace`) renames the
references to it; an entry that others use cannot be deleted. The exports define each command
after the ones it uses.

Sorting
~~~~~~~

Within its group, a list sorts the entries by sort key (or name), regardless of case. Set
``sort`` to sort a notation by its symbol rather than by its name: ``sort = "rho"`` for
``\density``. The sort key is letters, digits, spaces, ``_``, ``.`` and ``-`` (characters that
``makeindex`` sorts without quoting). The entries without a group come first, with no title.

Tags
~~~~

One notation file can serve several documents: ``tags = ["thesis"]`` marks the entries of a
document, and ``anatole export --tag thesis`` exports the entries that have the tag, those
that have no tag (shared by every document), and the entries they use (so that ``\redelta``
always comes with ``\blthickness``).

Validation
~~~~~~~~~~

Reading a file checks every entry and reports every problem at once, each naming the entry
(or group) and the field; nothing is read when there is a problem. The checks are:

- the names are two letters or more, used once; they are not Typst keywords (``in``,
  ``none``, ``let``...), nor names that the exports define (``std``,
  ``notationnomenclature``...), nor names that start with ``end`` (LaTeX does not define
  those with ``\newcommand``);
- the languages are valid codes, declared once; every required text has a translation in
  the default language, and no text has one in a language not declared;
- the symbol and each translation are given in both formats; the units are given in both
  formats or in none;
- the braces of the LaTeX texts balance (``\{`` and ``\}`` aside);
- the placeholders are ``#1`` to ``#N``, for a notation of ``N`` arguments (``#1`` for a
  style);
- the references are well formed, name existing entries, and form no cycle; the styles
  exist;
- the groups exist, have at most two levels, and a subsection's section exists;
- the keys of the file and of its tables are known (a misspelled ``unit`` is an error, not
  ignored), and each value has the right type.

.. literalinclude:: ../test/snippet_api.py
   :language: python
   :start-after: # [errors]
   :end-before: # [errors]
   :dedent:

``anatole check notations.toml`` runs the same checks, and lists the translations missing (an
error only with ``--strict``). The checks do not compile the symbols: a LaTeX or Typst error in
a symbol shows in the preview of the interface (Typst) or when the document is compiled.

Languages
---------

An export is in one language: the descriptions, group titles and acronyms are written in it,
so that a document in French gets its lists in French. The default language is exported
unless another is asked for (``--language fr`` on the command line, the *Language* selector
of the interface, ``language="fr"`` in Python). A translation missing in that language falls
back on the default language, with a warning for each one; ``anatole check`` lists them
beforehand.

The symbols, units and command names do not depend on the language: ``\velocity`` is the
same command in an English and a French document. A document in two languages (an English
abstract in a French thesis) inputs the export of one of them.

The words that the packages write themselves are theirs to translate:
``\usepackage[french]{nomencl}`` titles the LaTeX nomenclature *Liste des symboles*, and
``notation-nomenclature(title: [Notations])`` changes the Typst heading.

LaTeX
-----

Export with ``anatole export notations.toml notations.tex`` (or the *File* menu of the
interface). The file defines one command per style and notation, usable in text and math
mode, each after the ones it uses:

.. code-block:: latex

   \newcommand{\vect}[1]{\ensuremath{\boldsymbol{#1}}}
   \newcommand{\velocity}{\ensuremath{\vect{u}}}
   \newcommand{\blthickness}{\ensuremath{\delta}}
   \newcommand{\redelta}{\ensuremath{\mathit{Re}_{{\blthickness}}}}
   \newcommand{\norm}[1]{\ensuremath{\left\lVert #1 \right\rVert}}

The lists go to one of two **targets** (``--latex-target``, or *LaTeX lists* in the
interface).

nomencl and acro (the default)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The notations go to a ``nomencl`` nomenclature, the acronyms and abbreviations to ``acro``.
Input the file in the preamble, after both packages; call ``\notationnomenclature`` before
``\printnomenclature``, and ``\notationacronyms`` where the acronyms go
(``examples/document.tex``):

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

- The section and subsection titles head the nomenclature groups (``\nomgroup`` is
  redefined). ``nomencl`` tells groups apart by the first letter of the sort prefix (``A`` for
  the notations without a group, then ``B``, ``C``...), so a document has at most 25 groups
  with notations.
- The units go to ``\nomunit``, right-aligned; ``nomencl`` 5.6 does not define it, so the
  file defines it when it is missing, as the ``nomencl`` documentation suggests. ``\si{...}``
  needs ``siunitx``.
- The entries are declared where ``\notationnomenclature`` is called, not in the preamble,
  where ``nomencl`` would lose them.
- Each acronym is ``\DeclareAcronym{cfd}{...}``, tagged with its group; an abbreviation has
  ``first-style = short``, and a final period becomes ``\acdot``, so that ``acro`` does not
  double it at the end of a sentence. ``\notationacronyms`` prints a list per group, with
  every acronym (``display=all``).

glossaries
~~~~~~~~~~

Everything goes to ``glossaries-extra``: one glossary per group, sorted in the order of the
lists (``sort=def``), without an external tool (the file calls ``\makenoidxglossaries``).
Acronyms are ``\gls{cfd}``; ``\notationglossaries`` prints every list
(``examples/document-glossaries.tex``):

.. literalinclude:: ../examples/document-glossaries.tex
   :language: latex
   :start-after: % [preamble]
   :end-before: % [preamble]

.. literalinclude:: ../examples/document-glossaries.tex
   :language: latex
   :start-after: % [body]
   :end-before: % [body]

- The notations are glossary entries named by their command, with their units in the symbol
  column (style ``long4col``); acronyms are ``\newacronym`` (style ``long-short``),
  abbreviations ``\newabbreviation`` (style ``short-nolong``, final period not doubled).
- Every entry is listed, used or not (``\glsaddallunused``): the notations are printed with
  their commands, which ``glossaries`` does not see.

Common to both
~~~~~~~~~~~~~~

- The list headings use ``\notationtoplevel`` (``section``) for the sections and
  ``\notationsublevel`` (``subsection``) for the subsections, starred: define them before
  ``\input`` to change them (``\newcommand{\notationtoplevel}{chapter}`` in a book).
- ``\newcommand`` fails when LaTeX or a package already defines the name (``\time`` is a TeX
  primitive, for one): rename the notation. From Python,
  :func:`~anatole.export.latex.to_latex` takes ``definition="providecommand"`` (keep the
  existing command) or ``"renewcommand"`` (replace it).

Typst
-----

Export with ``anatole export notations.toml notations.typ``. The file defines one function per
style, one variable per notation (or a function for a notation with arguments), and one per
acronym, each after the ones it uses:

.. code-block:: text

   #let vect = (arg1) => $bold(#(arg1))$
   #let velocity = $vect(u)$
   #let redelta = $italic("Re")_(#blthickness)$
   #let norm = (arg1) => $lr(|| #(arg1) ||)$
   #let cfd = anatole-acronym("cfd", [CFD], [computational fluid dynamics], expand: true)

An acronym (``#cfd``) prints its long form with its short form at its first use, its short
form afterwards; an abbreviation always prints its short form. ``notation-groups`` and
``acronym-groups`` hold the lists, and ``notation-nomenclature()`` and ``notation-acronyms()``
print them. Import the file where the notations are used (``examples/document.typ``):

.. literalinclude:: ../examples/document.typ
   :language: typst
   :start-after: // [import]
   :end-before: // [import]

.. literalinclude:: ../examples/document.typ
   :language: typst
   :start-after: // [body]
   :end-before: // [body]

``notation-nomenclature`` and ``notation-acronyms`` take these parameters:

==================== ================================== =========================================
Parameter            Default                            Meaning
==================== ================================== =========================================
``title``            ``[Nomenclature]``, ``[Acronyms]`` A heading (not numbered); ``none``: none.
``columns``          ``(auto, 1fr, auto)``              The three columns.
``align``            ``(left, left, right)``            Their alignment.
``column-gutter``    ``1em``                            The space between columns.
``row-gutter``       ``0.8em``                          The space between rows.
``section-title``    a larger ``strong``                How a section title is shown.
``subsection-title`` ``strong``                         How a subsection title is shown.
==================== ================================== =========================================

For another layout, iterate ``notation-groups`` or ``acronym-groups``: each section is a
dictionary with ``key``, ``title`` (``none`` for the entries without a group), ``entries``
and ``subsections`` (sections themselves); a notation has ``name``, ``symbol``,
``description`` and ``units`` (``none`` when there are none), an acronym ``name``, ``short``,
``long``, ``description`` and ``abbreviation``.

- The export needs Typst 0.13 or later: it uses the ``std`` module, so that entries named
  like Typst functions (``grid``, ``title``...) do not break the lists.
- An entry named like a Typst function shadows it in the documents that import the file; its
  own symbol can still use the function (``#let norm = (arg1) => $norm(...)$`` calls the
  builtin ``norm``: an anonymous function does not see its own name).
- The helpers have hyphenated names, which no entry can take.

Word
----

Word has no commands like ``\velocity``: the export to Word is the **lists**, the nomenclature
and the acronyms, as a ``.docx`` document to copy into a report or to attach to it::

   anatole export notations.toml notations.docx
   anatole export --language fr --reference-doc my-template.docx notations.toml notations.docx

(or *File › Export to Word* in the interface). It needs pandoc, which ``pip install
'anatole[office]'`` installs (the ``pypandoc-binary`` package).

.. literalinclude:: ../test/snippet_api.py
   :language: python
   :start-after: # [word]
   :end-before: # [word]
   :dedent:

- The lists follow the tree of groups: a heading per list, section and subsection (Word's
  *Heading 1* to *Heading 3*), then a table: symbol, description and units for the
  notations, short and long forms for the acronyms and abbreviations.
- Every symbol is a **Word equation**, editable, written from the LaTeX symbol with its style
  and references expanded (``\boldsymbol{u}`` for ``\velocity``); a reference in a
  description becomes an equation too, and a reference to an acronym its short form.
- **Units written with siunitx** (``\si{\metre\per\second}``, ``\SI{3}{\metre}``) are
  converted, with their prefixes and powers (*m s⁻¹*, *kg m⁻³*, *km²*, *°C*, *μm*).
- What pandoc cannot convert is **reported, by entry**, and the document is written anyway:
  an unknown unit is left out (``notation 'length': Word: \furlong is not converted (left
  out)``), an unknown command in a symbol is kept as TeX (``the math \unknowncmd{x} is not
  converted``). The command line prints these problems, the interface shows them.
- ``--reference-doc`` (``reference_doc`` in Python) takes the styles of a Word document of
  yours: fonts, headings, tables.
- Word cannot expand an acronym at its first use by itself: the list is there to copy from.

Graphical interface
-------------------

``anatole gui notations.toml`` (or just ``anatole``) opens the interface.

- At the top, the search field filters the entries on every field (name, kind, group, sort
  key, tags, symbols, units, texts in every language), all words matching; the *Language*
  selector chooses the language of the texts shown, of the preview and of the exports; *LaTeX
  lists* chooses the LaTeX target of the exports.
- On the left, the styles, then the entries by section and subsection, with their kind,
  symbol (or short form) and description (or long form) in the selected language
  (``[en] Density`` when it falls back on the default language). The status bar counts the
  translations missing.
- On the right, the editor of the selected item. Its *Kind* (notation, acronym, abbreviation,
  style) is chosen for a new item and fixed afterwards; it shows the fields of that kind, the
  texts per format in a LaTeX and a Typst column, and the texts per language in a row per
  language. An empty Typst field takes the LaTeX text (and the other way round), so that a
  text common to both formats is typed once; a language left empty has no translation.
  *Apply* (Ctrl+Enter) checks the item and applies it, or shows its problems under the
  editor; *Revert* discards the changes; *New* (Ctrl+N) starts an item of the same kind, in
  the same group; *Duplicate* copies it; *Delete* removes it (not when other entries use it).
  Selecting another item with changes not applied asks whether to apply them.
- Under the editor, the item rendered by Typst as in its list, with the entries it refers to
  (with the ``typst`` package), updated as you type, or the problem.
- *Edit › Groups* adds, renames, retitles (in each language), reorders and deletes groups: a
  key ``symbols.vectors`` makes a subsection of ``symbols``; a rename keeps a group in its
  section and moves its subsections and entries; a group with entries or subsections cannot
  be deleted.
- *Edit › Languages* sets the languages, the default one first (``en, fr``): add one, make
  another the default (every required text needs a translation in it), or remove one (its
  translations are dropped, after confirmation).
- *File* opens and saves notation files (Ctrl+O, Ctrl+S) and exports to LaTeX, Typst and
  Word (with the problems of the Word export, if any).
  Closing with unsaved changes asks whether to save them.

The interface rewrites the file when it saves: comments are lost, and strings are written
as TOML literal strings when they can be.

Command line
------------

``anatole gui [FILE]``
   Open the interface (the default command).
``anatole check [--strict] FILE...``
   Check notation files: report every problem, and list the translations missing. Exit with
   1 if a file is invalid, or, with ``--strict``, if translations are missing.
``anatole list [-f {latex,typst}] [-l LANGUAGE] [--tag TAG]... FILE``
   List the styles and entries: kind, name, group, symbol (or short form) in a format (LaTeX
   by default) and description (or long form) in a language (the default one by default).
``anatole export [-f {latex,typst,docx}] [-l LANGUAGE] [-t {nomencl+acro,glossaries}] [--tag TAG]... [--reference-doc DOCX] FILE OUTPUT``
   Export a notation file. The output follows the suffix of ``OUTPUT`` (``.tex`` and
   ``.sty``: LaTeX, ``.typ``: Typst, ``.docx``: Word) unless ``--format`` is given; the texts are in the
   default language unless ``--language`` is given; ``--latex-target`` chooses the LaTeX
   packages of the lists; ``--tag`` selects entries (see `Tags`_).

``-v`` logs what is read and written. The exit code is 0 on success, 1 when a file cannot
be read, is invalid or cannot be exported, and 2 on a usage error. The warnings (a
translation missing in the language exported) go to the standard error.

Python
------

The package builds, reads, writes and exports notation sets
(:class:`~anatole.model.NotationSet`):

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

:func:`~anatole.io.to_dict` and :func:`~anatole.io.from_dict` convert to and from the dict of
a notation file, to store notations elsewhere (JSON, a database...). See the :doc:`api`.
