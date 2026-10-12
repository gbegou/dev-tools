notation-manager
================

Define each notation once, in a notation file, and use it in **LaTeX** and **Typst**:
a command name, a symbol, a description and units, each written once per language.

.. code-block:: toml

   [notations.velocity]
   symbol = { latex = '\mathbf{u}', typst = 'bold(upright(u))' }
   description = "Velocity"
   units = { latex = '\si{\metre\per\second}', typst = 'm/s' }

From this file, ``notation-manager`` exports a LaTeX file (one command per notation, and the
entries of a ``nomencl`` nomenclature) and a Typst file (one variable or function per
notation, and a nomenclature), so that ``\velocity`` and ``$velocity$`` render the same
symbol and the nomenclature lists it in both. A graphical interface browses, searches,
creates and edits the notations, with a Typst preview.

.. toctree::
   :maxdepth: 2

   user_manual
   api
   developer_guide
   release_notes
   roadmap
