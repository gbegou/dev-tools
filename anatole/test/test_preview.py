"""The Typst preview."""

import pytest

from notation_manager import Notation, NotationSet, Rendered, Translated, preview

pytestmark = pytest.mark.skipif(not preview.is_available(), reason="needs the typst package")

PNG = b"\x89PNG\r\n\x1a\n"


def test_render(small: NotationSet) -> None:
    for notation in small:
        for language in small.languages:  # French falls back on English when missing
            assert preview.render(notation, language).startswith(PNG)


def test_render_error_is_typst_message() -> None:
    notation = Notation("broken", Rendered.both("lr(x"), Translated({"en": "Broken"}))
    with pytest.raises(preview.PreviewError, match="unclosed delimiter"):
        _ = preview.render(notation, "en")
