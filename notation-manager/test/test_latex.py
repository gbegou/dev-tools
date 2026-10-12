"""LaTeX export: the generated code, and a document compiled with it (when LaTeX is installed)."""

import shutil
import subprocess
from pathlib import Path

import pytest

from notation_manager import Group, Notation, NotationError, NotationSet, Rendered, to_latex
from notation_manager.export.latex import MAX_GROUPS


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
    notations = NotationSet([Notation("time", Rendered.both("t"), Rendered.both("Time"))])
    text = to_latex(notations, source="notations.toml")
    assert "from notations.toml" in text
    assert r"\nomgroup" not in text
    assert r"\nomenclature[time]{$\time$}{Time}%" in text


def test_too_many_groups() -> None:
    count = MAX_GROUPS + 1
    groups = [Group(f"g{i}", Rendered.both(f"G{i}")) for i in range(count)]
    notations = NotationSet(
        [
            Notation(
                f"n{chr(97 + i // 26)}{chr(97 + i % 26)}",
                Rendered.both("x"),
                Rendered.both("x"),
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
def test_document_compiles(tmp_path: Path, example: NotationSet) -> None:
    _ = (tmp_path / "notations.tex").write_text(to_latex(example), encoding="utf-8")
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
