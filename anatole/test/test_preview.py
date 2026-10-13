"""The Typst preview."""

import pytest

from anatole import Notation, NotationSet, Rendered, Style, Translated, preview

pytestmark = pytest.mark.skipif(not preview.is_available(), reason="needs the typst package")

PNG = b"\x89PNG\r\n\x1a\n"


def test_render(small: NotationSet, example: NotationSet) -> None:
    for notations in (small, example):
        for item in [*notations, *notations.styles]:
            for language in notations.languages:  # falls back on English when missing
                assert preview.render(item, notations, language).startswith(PNG)


def test_render_an_unapplied_item(example: NotationSet) -> None:
    """An item being edited, with references and a style, renders with its dependencies."""
    item = Notation(
        "newone",
        Rendered.both("@{redelta}^2"),
        Translated({"en": "Square of @{redelta}"}),
        style="vect",
    )
    assert preview.render(item, example, "en").startswith(PNG)
    style = Style("hat", Rendered(r"\hat{#1}", "hat(#1)"))
    assert preview.render(style, example, "fr").startswith(PNG)


def test_render_unknown_reference(example: NotationSet) -> None:
    item = Notation("newone", Rendered.both("@{nothing}"), Translated({"en": "x"}))
    with pytest.raises(preview.PreviewError, match=r"@\{nothing\}, which is not defined"):
        _ = preview.render(item, example, "en")


def test_render_error_is_typst_message() -> None:
    notation = Notation("broken", Rendered.both("lr(x"), Translated({"en": "Broken"}))
    with pytest.raises(preview.PreviewError, match="unclosed delimiter"):
        _ = preview.render(notation, NotationSet(), "en")
