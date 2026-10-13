# ANATOLE

**A**NATOLE is a **N**otations **A**nd acronyms manager with **T**ypst **O**r **L**aTeX **E**xporters.

Define each notation, acronym and abbreviation once, use it in **LaTeX** and **Typst**, in
**English**, **French** or any other language.

A notation file (TOML) holds:

- **notations**: a command, a symbol and units written once per format (or once for both),
  a description written once per language;
- **acronyms** (expanded at their first use) and **abbreviations**, with a short and a long
  form per language;
- **styles**, templates applied to symbols: vectors in bold or with an arrow, changed in one
  place;
- **groups**, a tree of sections and subsections that heads the lists, and **tags** that
  select the entries of each document.

Entries refer to each other with `@{name}`: the Reynolds number based on the boundary-layer
thickness uses the notation of the thickness, and follows its changes.

```toml
languages = ["en", "fr"]  # the first one is the default

[styles.vect]
template = { latex = '\boldsymbol{#1}', typst = 'bold(#1)' }

[groups.symbols]
title = { en = "Symbols", fr = "Symboles" }

[groups.symbols.latin]
title = { en = "Latin letters", fr = "Lettres latines" }

[notations.velocity]
group = "symbols.latin"
style = "vect"
symbol = 'u'
description = { en = "Velocity", fr = "Vitesse" }
units = { latex = '\si{\metre\per\second}', typst = 'm/s' }

[notations.redelta]
group = "symbols.latin"
symbol = { latex = '\mathit{Re}_{@{blthickness}}', typst = 'italic("Re")_(@{blthickness})' }
description = { en = "Reynolds number based on @{blthickness}", fr = "Nombre de Reynolds basé sur @{blthickness}" }

[acronyms.cfd]
short = { en = "CFD", fr = "MFN" }
long = { en = "computational fluid dynamics", fr = "mécanique des fluides numérique" }
```

`anatole` exports it, in the language of the document (the default one, or `--language fr`; a
missing translation falls back on the default language):

- to **LaTeX**: `\newcommand{\velocity}{\ensuremath{\vect{u}}}`, and the lists for
  [nomencl](https://ctan.org/pkg/nomencl) and [acro](https://ctan.org/pkg/acro) (the
  default) or [glossaries-extra](https://ctan.org/pkg/glossaries-extra)
  (`--latex-target glossaries`);
- to **Typst**: `#let velocity = $vect(u)$`, `#cfd` (long at its first use, short
  afterwards), `#notation-nomenclature()` and `#notation-acronyms()`.

A graphical interface (Tkinter) browses, searches, creates, edits and translates the entries,
styles and groups, with a Typst preview.

```console
$ pip install -e '.[preview]'
$ anatole gui examples/notations.toml
$ anatole check examples/notations.toml
$ anatole export examples/notations.toml notations.tex
$ anatole export --latex-target glossaries examples/notations.toml notations.tex
$ anatole export --language fr --tag thesis examples/notations.toml notations.typ
```

Python 3.12 or later, no runtime dependency (`typst` for the preview). The documentation
(`doc/`, Sphinx) has the user manual, the API and the developer guide:

```console
$ pip install -e . --group doc
$ sphinx-build -W -b html doc doc/_build/html
```
