"""LaTeX export: the generated code, and a document compiled with it (when LaTeX is installed)."""

import shutil
import subprocess
from pathlib import Path

import pytest

from anatole import (
    Group,
    Notation,
    NotationError,
    NotationSet,
    Rendered,
    Translated,
    to_latex,
)
from anatole.export.latex import MAX_GROUPS


def test_commands(small: NotationSet) -> None:
    text = to_latex(small)
    assert r"\newcommand{\velocity}{\ensuremath{\mathbf{u}}}" in text
    assert r"\newcommand{\norm}[1]{\ensuremath{\lVert #1 \rVert}}" in text
    assert r"\providecommand{\time}" in to_latex(small, definition="providecommand")


def test_entries_in_nomenclature_order(small: NotationSet) -> None:
    entries = [line.strip() for line in to_latex(small).splitlines() if "\\nomenclature[" in line]
    assert entries == [
        r"\nomenclature[Anorm]{$\norm{\cdot}$}{Norm}%",
        r"\nomenclature[Atime]{$\time$}{Time}%",
        r"\nomenclature[Bvelocity]{$\velocity$}{Velocity\nomunit{\si{m/s}}}%",
        r"\nomenclature[Cdensity]{$\density$}{Density}%",
    ]


def test_group_titles(small: NotationSet) -> None:
    text = to_latex(small)
    assert r"\@namedef{notation@group@B}{Latin}" in text
    assert r"\@namedef{notation@group@C}{Greek}" in text
    assert r"\renewcommand{\nomgroup}" in text


def test_without_groups() -> None:
    notations = NotationSet([Notation("time", Rendered.both("t"), Translated({"en": "Time"}))])
    text = to_latex(notations, source="notations.toml")
    assert "from notations.toml, in en" in text
    assert r"\nomgroup" not in text
    assert r"\nomenclature[time]{$\time$}{Time}%" in text


def test_too_many_groups() -> None:
    count = MAX_GROUPS + 1
    groups = [Group(f"g{i}", Translated({"en": f"G{i}"})) for i in range(count)]
    notations = NotationSet(
        [
            Notation(
                f"n{chr(97 + i // 26)}{chr(97 + i % 26)}",
                Rendered.both("x"),
                Translated({"en": "x"}),
                group=f"g{i}",
            )
            for i in range(count)
        ],
        groups,
    )
    with pytest.raises(NotationError, match=f"{count} groups have notations"):
        _ = to_latex(notations)
    _ = notations.remove("naa")
    assert r"\@namedef{notation@group@Z}" in to_latex(notations)


def test_language(small: NotationSet, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("WARNING", logger="anatole"):
        text = to_latex(small, language="fr")
    assert r"\@namedef{notation@group@C}{Grec}" in text
    assert r"{$\velocity$}{Vitesse\nomunit{\si{m/s}}}%" in text
    assert r"{$\density$}{Density}%" in text  # no French translation: English
    assert caplog.messages == [
        "notation 'density': description is missing in fr: the export uses the default "
        + "language en",
        "notation 'norm': description is missing in fr: the export uses the default language en",
    ]
    assert to_latex(small) == to_latex(small, language="en")
    with pytest.raises(NotationError, match="language 'de' is not declared"):
        _ = to_latex(small, language="de")


def test_descriptions_per_format() -> None:
    description = Translated({"en": Rendered(r"\emph{Time}", "_Time_")})
    text = to_latex(NotationSet([Notation("time", Rendered.both("t"), description)]))
    assert r"{$\time$}{\emph{Time}}%" in text


EXAMPLES = Path(__file__).resolve().parent.parent / "examples"

LATEX_TOOLS = ("pdflatex", "makeindex", "kpsewhich")


def latex_available() -> bool:
    if not all(shutil.which(tool) for tool in LATEX_TOOLS):
        return False
    found = subprocess.run(
        ["kpsewhich", "nomencl.sty", "siunitx.sty"], capture_output=True, text=True, check=False
    )
    return len(found.stdout.split()) == 2


@pytest.mark.skipif(not latex_available(), reason="needs pdflatex, makeindex, nomencl, siunitx")
@pytest.mark.parametrize(
    ("language", "title"), [("en", "Latin symbols"), ("fr", "Symboles latins")]
)
def test_document_compiles(tmp_path: Path, example: NotationSet, language: str, title: str) -> None:
    text = to_latex(example, language=language)
    _ = (tmp_path / "notations.tex").write_text(text, encoding="utf-8")
    _ = shutil.copy(EXAMPLES / "document.tex", tmp_path)

    def run(*command: str) -> None:
        result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, check=False)
        assert result.returncode == 0, result.stdout[-3000:]

    latex = ("pdflatex", "-interaction=nonstopmode", "-halt-on-error", "document.tex")
    run(*latex)
    run("makeindex", "document.nlo", "-s", "nomencl.ist", "-o", "document.nls")
    run(*latex)
    listing = (tmp_path / "document.nls").read_text(encoding="utf-8")
    # Groups in order, entries sorted within each.
    order = [
        r"\nomgroup{A}",
        r"\reynolds",
        r"\nomgroup{B}",
        r"\pressure",
        r"\velocity",
        r"\nomgroup{C}",
        r"\viscosity",
        r"\density",
        r"\nomgroup{D}",
        r"\norm",
    ]
    positions = [listing.index(item) for item in order]
    assert positions == sorted(positions)
    assert title in (tmp_path / "notations.tex").read_text(encoding="utf-8")
