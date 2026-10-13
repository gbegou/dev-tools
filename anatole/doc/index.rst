ANATOLE
=======

**A**\ NATOLE is a **N**\ otations **A**\ nd acronyms manager with **T**\ ypst **O**\ r **L**\ aTeX **E**\ xporters.

Define each notation once, in a notation file, and use it in **LaTeX** and **Typst**, in
**English**, **French** or any other language: a command name, a symbol and units written
once per format, and a description written once per language.

.. code-block:: toml

   languages = ["en", "fr"]

   [notations.velocity]
   symbol = { latex = '\mathbf{u}', typst = 'bold(upright(u))' }
   description = { en = "Velocity", fr = "Vitesse" }
   units = { latex = '\si{\metre\per\second}', typst = 'm/s' }

From this file, ``anatole`` exports a LaTeX file (one command per notation, and the
entries of a ``nomencl`` nomenclature) and a Typst file (one variable or function per
notation, and a nomenclature), in the language of the document, so that ``\velocity`` and
``$velocity$`` render the same symbol and the nomenclature lists it with its description in
that language. A graphical interface browses, searches, creates, edits and translates the
notations, with a Typst preview.

.. toctree::
   :maxdepth: 2

   user_manual
   api
   developer_guide
   release_notes
   roadmap
