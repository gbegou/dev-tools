"""The Python API, as shown in the user manual."""

from pathlib import Path

import pytest


def snippet_api(tmp_path: Path) -> None:
    # [build]
    from anatole import Group, Notation, NotationSet, Rendered, Translated, save

    notations = NotationSet(
        groups=[Group("latin", Translated({"en": "Latin symbols", "fr": "Symboles latins"}))],
        languages=["en", "fr"],  # the first one is the default language
    )
    notations.add(
        Notation(
            name="velocity",
            symbol=Rendered(latex=r"\mathbf{u}", typst="bold(upright(u))"),
            description=Translated({"en": "Velocity", "fr": "Vitesse"}),
            units=Rendered(latex=r"\si{\metre\per\second}", typst="m/s"),
            group="latin",
        )
    )
    save(notations, tmp_path / "notations.toml")
    # [build]

    # [export]
    from anatole import export, load, to_typst

    notations = load(tmp_path / "notations.toml")
    export(notations, tmp_path / "notations.tex")  # the format follows the suffix
    export(notations, tmp_path / "notations-fr.typ", language="fr")
    print(to_typst(notations, language="fr"))  # #let velocity = $bold(upright(u))$ ...
    # [export]

    latex = (tmp_path / "notations.tex").read_text(encoding="utf-8")
    assert "\\newcommand{\\velocity}" in latex
    assert "{Velocity\\nomunit" in latex
    assert "[Vitesse]" in (tmp_path / "notations-fr.typ").read_text(encoding="utf-8")
    assert "#let velocity = $bold(upright(u))$" in to_typst(notations).splitlines()


def snippet_errors() -> None:
    # [errors]
    from anatole import NotationError, loads

    try:
        _ = loads("[notations.u]\nsymbol = '\\mathbf{u'\ndescription = 'Velocity'\n")
    except NotationError as error:
        for problem in error.problems:
            print(problem)
    # notation 'u': the name must be two letters or more (A-Z, a-z)
    # notation 'u': symbol has unbalanced braces in latex: \mathbf{u
    # [errors]

    with pytest.raises(NotationError) as caught:
        _ = loads("[notations.u]\nsymbol = '\\mathbf{u'\ndescription = 'Velocity'\n")
    assert caught.value.problems == (
        "notation 'u': the name must be two letters or more (A-Z, a-z)",
        "notation 'u': symbol has unbalanced braces in latex: \\mathbf{u",
    )
