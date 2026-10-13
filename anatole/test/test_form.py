"""The editor forms and the search of the graphical interface (no display needed)."""

import pytest

from anatole import Group, NotationError, NotationSet, Rendered, Translated
from anatole.gui.form import GroupForm, NotationForm, description_key, matches


def test_notation_form_round_trip(small: NotationSet) -> None:
    for notation in small:
        form = NotationForm.from_notation(notation)
        assert form.to_notation() == notation
        assert NotationForm.from_values(form.values(small.languages)) == form


def test_values_cover_the_languages(small: NotationSet) -> None:
    form = NotationForm.from_notation(small["density"])  # English only
    values = form.values(["en", "fr", "pt-BR"])
    assert values[description_key("en", "latex")] == "Density"
    assert values[description_key("fr", "latex")] == ""
    assert values[description_key("pt-BR", "typst")] == ""
    assert NotationForm.from_values(values).to_notation() == small["density"]


def test_typst_is_empty_when_it_is_the_latex_text() -> None:
    form = NotationForm(
        name="velocity",
        symbol=(r"\mathbf{u}", "bold(u)"),
        units=("m/s", ""),
        descriptions={"en": ("Velocity", ""), "fr": ("", "Vitesse"), "de": (" ", "")},
    )
    notation = form.to_notation()
    assert notation.symbol == Rendered(r"\mathbf{u}", "bold(u)")
    assert notation.units == Rendered.both("m/s")
    assert notation.description == Translated({"en": "Velocity", "fr": "Vitesse"})
    assert NotationForm.from_notation(notation).units == ("m/s", "")


def test_notation_form_strips_whitespace() -> None:
    form = NotationForm(
        name=" velocity ",
        arguments=" ",
        symbol=(" u ", "u\n"),
        descriptions={"en": ("Velocity ", " Velocity")},
    )
    notation = form.to_notation()
    assert (notation.name, notation.arguments) == ("velocity", 0)
    assert notation.symbol == Rendered.both("u")
    assert notation.description == Translated({"en": "Velocity"})


def test_notation_form_invalid_arguments() -> None:
    with pytest.raises(NotationError, match="arguments must be an integer, not 'two'"):
        _ = NotationForm(name="ab", arguments="two").to_notation()


def test_notation_form_reports_the_model_problems() -> None:
    with pytest.raises(NotationError) as caught:
        _ = NotationForm(name="ab").to_notation()
    assert caught.value.problems == (
        "notation 'ab': symbol is empty in latex",
        "notation 'ab': symbol is empty in typst",
        "notation 'ab': description has no translation",
    )


def test_group_form_round_trip() -> None:
    group = Group("latin", Translated({"en": "Latin", "fr": Rendered("Latin", "_Latin_")}))
    form = GroupForm.from_group(group)
    assert form.to_group() == group
    assert GroupForm.from_values(form.values(["en", "fr"])) == form


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
        ("vitesse", True),  # French description
        ("velocity latin", True),
        ("velocity greek", False),
        ("pressure", False),
    ],
)
def test_matches(small: NotationSet, query: str, expected: bool) -> None:
    assert matches(small["velocity"], query) is expected
