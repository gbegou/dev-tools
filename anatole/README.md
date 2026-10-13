# ANATOLE

**A**NATOLE is a **N**otations **A**nd acronyms manager with **T**ypst **O**r **L**aTeX **E**xporters.

Define each notation once, use it in **LaTeX** and **Typst**, in **English**, **French** or
any other language.

A notation file (TOML) holds notations: a command name, a symbol and units written once per
format (or once for both), and a description written once per language:

```toml
languages = ["en", "fr"]  # the first one is the default

[groups.latin]
title = { en = "Latin symbols", fr = "Symboles latins" }

[notations.velocity]
group = "latin"
symbol = { latex = '\mathbf{u}', typst = 'bold(upright(u))' }
description = { en = "Velocity", fr = "Vitesse" }
units = { latex = '\si{\metre\per\second}', typst = 'm/s' }
```

`anatole` exports it, in the language of the document (the default one, or
`--language fr`; a missing translation falls back on the default language):

- to **LaTeX**: `\newcommand{\velocity}{\ensuremath{\mathbf{u}}}`, and
  `\notationnomenclature`, which declares the [nomencl](https://ctan.org/pkg/nomencl)
  entries (groups, sort keys, units);
- to **Typst**: `#let velocity = $bold(upright(u))$`, and `#notation-nomenclature()`.

A graphical interface (Tkinter) browses, searches, creates, edits and translates the
notations and groups, with a Typst preview.

```console
$ pip install -e '.[preview]'
$ anatole gui examples/notations.toml
$ anatole check examples/notations.toml
$ anatole export examples/notations.toml notations.tex
$ anatole export --language fr examples/notations.toml notations.typ
```

Python 3.12 or later, no runtime dependency (`typst` for the preview). The documentation
(`doc/`, Sphinx) has the user manual, the API and the developer guide:

```console
$ pip install -e . --group doc
$ sphinx-build -W -b html doc doc/_build/html
```
