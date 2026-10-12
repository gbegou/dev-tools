# notation-manager

Define each notation once, use it in **LaTeX** and **Typst**.

A notation file (TOML) holds notations: a command name, a symbol, a description and units,
each written once per language (or once for both):

```toml
[groups.latin]
title = "Latin symbols"

[notations.velocity]
group = "latin"
symbol = { latex = '\mathbf{u}', typst = 'bold(upright(u))' }
description = "Velocity"
units = { latex = '\si{\metre\per\second}', typst = 'm/s' }
```

`notation-manager` exports it:

- to **LaTeX**: `\newcommand{\velocity}{\ensuremath{\mathbf{u}}}`, and
  `\notationnomenclature`, which declares the [nomencl](https://ctan.org/pkg/nomencl)
  entries (groups, sort keys, units);
- to **Typst**: `#let velocity = $bold(upright(u))$`, and `#notation-nomenclature()`.

A graphical interface (Tkinter) browses, searches, creates and edits the notations and
groups, with a Typst preview.

```console
$ pip install -e '.[preview]'
$ notation-manager gui examples/notations.toml
$ notation-manager check examples/notations.toml
$ notation-manager export examples/notations.toml notations.tex
$ notation-manager export examples/notations.toml notations.typ
```

Python 3.12 or later, no runtime dependency (`typst` for the preview). The documentation
(`doc/`, Sphinx) has the user manual, the API and the developer guide:

```console
$ pip install -e . --group doc
$ sphinx-build -W -b html doc doc/_build/html
```
