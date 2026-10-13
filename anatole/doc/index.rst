ANATOLE
=======

**A**\ NATOLE is a **N**\ otations **A**\ nd acronyms manager with **T**\ ypst **O**\ r **L**\ aTeX **E**\ xporters.

Define each notation, acronym and abbreviation once, in a notation file, and use it in
**LaTeX** and **Typst**, in **English**, **French** or any other language.

.. code-block:: toml

   languages = ["en", "fr"]

   [styles.vect]
   template = { latex = '\boldsymbol{#1}', typst = 'bold(#1)' }

   [notations.velocity]
   style = "vect"
   symbol = 'u'
   description = { en = "Velocity", fr = "Vitesse" }
   units = { latex = '\si{\metre\per\second}', typst = 'm/s' }

   [acronyms.cfd]
   short = { en = "CFD", fr = "MFN" }
   long = { en = "computational fluid dynamics", fr = "mécanique des fluides numérique" }

From this file, ``anatole`` exports a LaTeX file (commands, and lists for ``nomencl`` and
``acro``, or ``glossaries-extra``) and a Typst file (variables, functions, acronyms that expand
at their first use, and lists), in the language of the document. Entries refer to each other
(``@{blthickness}`` in the symbol of ``\redelta``), styles change every vector at once, groups
form sections and subsections, and tags select the entries of each document. A graphical
interface browses, searches, creates, edits and translates them, with a Typst preview.

.. toctree::
   :maxdepth: 2

   user_manual
   api
   developer_guide
   release_notes
   roadmap
