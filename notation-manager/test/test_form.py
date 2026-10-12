"""The editor forms and the search of the graphical interface (no display needed)."""

import pytest

from notation_manager import Group, NotationError, NotationSet, Rendered
from notation_manager.gui.form import GroupForm, NotationForm, matches


def test_notation_form_round_trip(small: NotationSet) -> None:
    for notation in small:
        form = NotationForm.from_notation(notation)
        assert form.to_notation() == notation
        assert NotationForm(**form.values()) == form


def test_notation_form_strips_whitespace() -> None:
    form = NotationForm(
        name=" velocity ",
        arguments=" ",
        symbol_latex=" u ",
        symbol_typst="u\n",
        description_latex="Velocity ",
        description_typst=" Velocity",
    )
    notation = form.to_notation()
    assert (notation.name, notation.arguments) == ("velocity", 0)
    assert notation.symbol == Rendered.both("u")
    assert notation.description == Rendered.both("Velocity")


def test_notation_form_invalid_arguments() -> None:
    with pytest.raises(NotationError, match="arguments must be an integer, not 'two'"):
        _ = NotationForm(name="ab", arguments="two").to_notation()


def test_notation_form_reports_the_model_problems() -> None:
    with pytest.raises(NotationError) as caught:
        _ = NotationForm(name="ab").to_notation()
    assert len(caught.value.problems) == 4  # symbol and description, in both languages


def test_group_form_round_trip() -> None:
    group = Group("latin", Rendered("Latin", "Latines"))
    form = GroupForm.from_group(group)
    assert form.to_group() == group
    assert GroupForm(**form.values()) == form


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("", True),
        ("velo", True),
        ("VELOCITY", True),
        ("mathbf", True),  # LaTeX symbol
        ("bold", True),  # Typst symbol
        ("m/s", True),  # units
        ("latin", True),  # group
        ("velocity latin", True),
        ("velocity greek", False),
        ("pressure", False),
    ],
)
def test_matches(small: NotationSet, query: str, expected: bool) -> None:
    assert matches(small["velocity"], query) is expected
