"""The Python API, as shown in the user manual."""

from pathlib import Path

import pytest


def snippet_api(tmp_path: Path) -> None:
    # [build]
    from notation_manager import Group, Notation, NotationSet, Rendered, save

    notations = NotationSet(groups=[Group("latin", Rendered.both("Latin symbols"))])
    notations.add(
        Notation(
            name="velocity",
            symbol=Rendered(latex=r"\mathbf{u}", typst="bold(upright(u))"),
            description=Rendered.both("Velocity"),
            units=Rendered(latex=r"\si{\metre\per\second}", typst="m/s"),
            group="latin",
        )
    )
    save(notations, tmp_path / "notations.toml")
    # [build]

    # [export]
    from notation_manager import export, load, to_typst

    notations = load(tmp_path / "notations.toml")
    export(notations, tmp_path / "notations.tex")  # the language follows the suffix
    export(notations, tmp_path / "notations.typ")
    print(to_typst(notations).splitlines()[6])  # #let velocity = $bold(upright(u))$
    # [export]

    assert "\\newcommand{\\velocity}" in (tmp_path / "notations.tex").read_text(encoding="utf-8")
    assert to_typst(notations).splitlines()[6] == "#let velocity = $bold(upright(u))$"


def snippet_errors() -> None:
    # [errors]
    from notation_manager import NotationError, loads

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
