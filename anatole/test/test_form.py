"""The editor forms and the search of the graphical interface (no display needed)."""

import pytest

from anatole import (
    Acronym,
    Group,
    Notation,
    NotationError,
    NotationSet,
    Rendered,
    Style,
    Translated,
)
from anatole.gui.form import GroupForm, ItemForm, kind_of, language_key, matches


def test_round_trip_of_every_kind(example: NotationSet) -> None:
    for item in [*example, *example.styles]:
        form = ItemForm.from_item(item)
        assert form.kind == kind_of(item)
        assert form.to_item() == item
        assert ItemForm.from_values(form.values(example.languages)) == form


def test_kinds(example: NotationSet) -> None:
    assert [kind_of(example[name]) for name in ("vect", "velocity", "cfd", "wrt")] == [
        "style",
        "notation",
        "acronym",
        "abbreviation",
    ]


def test_values_cover_the_languages(small: NotationSet) -> None:
    form = ItemForm.from_item(small["density"])  # English only
    values = form.values(["en", "fr", "pt-BR"])
    assert values[language_key("description", "en", "latex")] == "Density"
    assert values[language_key("description", "fr", "latex")] == ""
    assert values[language_key("short", "pt-BR", "typst")] == ""
    assert ItemForm.from_values(values).to_item() == small["density"]


def test_typst_is_empty_when_it_is_the_latex_text() -> None:
    form = ItemForm(
        name="velocity",
        symbol=(r"\mathbf{u}", "bold(u)"),
        units=("m/s", ""),
        descriptions={"en": ("Velocity", ""), "fr": ("", "Vitesse"), "de": (" ", "")},
    )
    notation = form.to_item()
    assert isinstance(notation, Notation)
    assert ItemForm.from_item(notation).units == ("m/s", "")
    assert notation.description == Translated({"en": "Velocity", "fr": "Vitesse"})


def test_notation_fields() -> None:
    form = ItemForm(
        name=" velocity ",
        arguments=" ",
        style=" vect ",
        tags="thesis, paper  draft",
        symbol=(" u ", "u\n"),
        descriptions={"en": ("Velocity ", " Velocity")},
    )
    notation = form.to_item()
    assert notation.name == "velocity"
    assert notation == ItemForm.from_item(notation).to_item()
    assert ItemForm.from_item(notation).tags == "thesis paper draft"


def test_acronym_and_abbreviation() -> None:
    form = ItemForm(
        kind="abbreviation",
        name="wrt",
        tags="a",
        shorts={"en": ("w.r.t.", "")},
        longs={"en": ("with respect to", ""), "fr": ("par rapport à", "")},
    )
    item = form.to_item()
    assert item == Acronym(
        "wrt",
        Translated({"en": "w.r.t."}),
        Translated({"en": "with respect to", "fr": "par rapport à"}),
        tags=("a",),
        abbreviation=True,
    )
    form.kind = "acronym"
    assert isinstance(item := form.to_item(), Acronym)
    assert not item.abbreviation


def test_style() -> None:
    form = ItemForm(kind="style", name="vect", symbol=(r"\vec{#1}", "arrow(#1)"), group="ignored")
    assert form.to_item() == Style("vect", Rendered(r"\vec{#1}", "arrow(#1)"))


def test_invalid_arguments() -> None:
    with pytest.raises(NotationError, match="arguments must be an integer, not 'two'"):
        _ = ItemForm(name="ab", arguments="two").to_item()


def test_reports_the_model_problems() -> None:
    with pytest.raises(NotationError) as caught:
        _ = ItemForm(name="ab").to_item()
    assert caught.value.problems == (
        "notation 'ab': symbol is empty in latex",
        "notation 'ab': symbol is empty in typst",
        "notation 'ab': description has no translation",
    )


def test_group_form_round_trip() -> None:
    group = Group("symbols.latin", Translated({"en": "Latin", "fr": Rendered("Latin", "_L_")}))
    form = GroupForm.from_group(group)
    assert form.to_group() == group
    assert GroupForm.from_values(form.values(["en", "fr"])) == form


@pytest.mark.parametrize(
    ("name", "query", "expected"),
    [
        ("velocity", "", True),
        ("velocity", "VELO", True),
        ("velocity", "vitesse", True),  # French description
        ("velocity", "vect", True),  # style
        ("velocity", "symbols.latin", True),  # group
        ("velocity", "m/s", True),  # units
        ("velocity", "velocity greek", False),
        ("cfd", "numérique", True),  # French long form
        ("cfd", "MFN", True),  # French short form
        ("wrt", "abbreviation", True),  # kind
        ("les", "turbulence", True),  # tag
        ("vect", "boldsymbol", True),  # template
    ],
)
def test_matches(example: NotationSet, name: str, query: str, expected: bool) -> None:
    assert matches(example[name], query) is expected
