"""The Typst preview."""

import pytest

from notation_manager import Notation, NotationSet, Rendered, preview

pytestmark = pytest.mark.skipif(not preview.is_available(), reason="needs the typst package")

PNG = b"\x89PNG\r\n\x1a\n"


def test_render(small: NotationSet) -> None:
    for notation in small:
        assert preview.render(notation).startswith(PNG)


def test_render_error_is_typst_message() -> None:
    notation = Notation("broken", Rendered.both("lr(x"), Rendered.both("Broken"))
    with pytest.raises(preview.PreviewError, match="unclosed delimiter"):
        _ = preview.render(notation)
