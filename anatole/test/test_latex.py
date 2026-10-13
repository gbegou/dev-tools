"""LaTeX export: the generated code, and documents compiled with it (when LaTeX is installed)."""

import shutil
import subprocess
from pathlib import Path

import pytest

from anatole import (
    Acronym,
    Group,
    Notation,
    NotationError,
    NotationSet,
    Rendered,
    Translated,
    to_latex,
)
from anatole.export.latex import MAX_GROUPS

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def lines_with(text: str, needle: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if needle in line]


def test_commands(small: NotationSet) -> None:
    text = to_latex(small)
    assert r"\newcommand{\velocity}{\ensuremath{\mathbf{u}}}" in text
    assert r"\newcommand{\norm}[1]{\ensuremath{\lVert #1 \rVert}}" in text
    assert r"\providecommand{\time}" in to_latex(small, definition="providecommand")


def test_styles_and_references(example: NotationSet) -> None:
    text = to_latex(example)
    assert r"\newcommand{\vect}[1]{\ensuremath{\boldsymbol{#1}}}" in text
    assert r"\newcommand{\velocity}{\ensuremath{\vect{u}}}" in text
    assert r"\newcommand{\redelta}{\ensuremath{\mathit{Re}_{{\blthickness}}}}" in text
    assert r"{Reynolds number based on {\blthickness}}" in text
    definitions = [line.split("}")[0] for line in lines_with(text, r"\newcommand{")]
    # Each command after the ones it uses.
    assert definitions.index(r"\newcommand{\vect") < definitions.index(r"\newcommand{\velocity")
    assert definitions.index(r"\newcommand{\blthickness") < definitions.index(
        r"\newcommand{\redelta"
    )


def test_acronym_references() -> None:
    notations = NotationSet(
        [
            Acronym("cfd", Translated({"en": "CFD"}), Translated({"en": "fluid dynamics"})),
            Notation("time", Rendered.both("t"), Translated({"en": "Time in @{cfd}"})),
        ]
    )
    assert r"{Time in \ac{cfd}}" in to_latex(notations)
    assert r"description={Time in \gls{cfd}}" in to_latex(notations, target="glossaries")


def test_nomencl_entries_in_order(small: NotationSet) -> None:
    assert lines_with(to_latex(small), r"\nomenclature[") == [
        r"\nomenclature[Anorm]{$\norm{\cdot}$}{Norm}%",
        r"\nomenclature[Atime]{$\time$}{Time}%",
        r"\nomenclature[Bvelocity]{$\velocity$}{Velocity\nomunit{\si{m/s}}}%",
        r"\nomenclature[Cdensity]{$\density$}{Density}%",
    ]


def test_nomencl_section_and_subsection_titles(example: NotationSet) -> None:
    assert lines_with(to_latex(example), r"\@namedef") == [
        r"\@namedef{notation@group@B}{\item[\large\bfseries Symbols]"
        + r"\item[\bfseries Latin letters]}",
        r"\@namedef{notation@group@C}{\item[\bfseries Greek letters]}",
        r"\@namedef{notation@group@D}{\item[\bfseries Subscripts]}",
        r"\@namedef{notation@group@E}{\item[\large\bfseries Operators]}",
    ]


def test_acro(example: NotationSet) -> None:
    text = to_latex(example, language="fr")
    assert lines_with(text, r"\DeclareAcronym") == [
        r"\DeclareAcronym{cfd}{short = {MFN}, long = {mécanique des fluides numérique}, "
        + "tag = {anatole-acronyms}}",
        r"\DeclareAcronym{les}{short = {SGE}, long = {simulation des grandes échelles}, "
        + "tag = {anatole-acronyms}}",
        r"\DeclareAcronym{wrt}{short = {p.r.à}, long = {par rapport à}, "
        + "tag = {anatole-abbreviations}, first-style = short}",
    ]
    english = to_latex(example)
    assert r"short = {w.r.t\acdot}" in english  # acro adds the final period itself
    assert lines_with(english, r"\printacronyms") == [
        r"\printacronyms[include=anatole-acronyms, heading=none, display=all]%",
        r"\printacronyms[include=anatole-abbreviations, heading=none, display=all]%",
    ]


def test_glossaries(example: NotationSet) -> None:
    text = to_latex(example, target="glossaries")
    assert r"\makenoidxglossaries" in text
    assert [line.split("}")[0] for line in lines_with(text, r"\newglossary*")] == [
        r"\newglossary*{anatole-symbols.latin",
        r"\newglossary*{anatole-symbols.greek",
        r"\newglossary*{anatole-symbols.subscripts",
        r"\newglossary*{anatole-operators",
        r"\newglossary*{anatole-acronyms",
        r"\newglossary*{anatole-abbreviations",
    ]
    # In list order, as the glossaries are sorted by definition.
    names = [line.split("{")[1].split("}")[0] for line in lines_with(text, r"\newglossaryentry")]
    assert names == [
        *("pressure", "redelta", "velocity", "blthickness", "viscosity", "density"),
        *("freestream", "norm"),
    ]
    assert r"\newacronym[type=anatole-acronyms, sort={cfd}]{cfd}{CFD}" in text
    assert r"\newabbreviation[type=anatole-abbreviations, sort={wrt}, category=abbreviation]" in (
        text
    )
    assert r"\notationheading{\notationtoplevel}{Symbols}%" in text
    assert r"\notationheading{\notationsublevel}{Latin letters}%" in text


def test_without_groups() -> None:
    notations = NotationSet([Notation("time", Rendered.both("t"), Translated({"en": "Time"}))])
    text = to_latex(notations, source="notations.toml")
    assert "from notations.toml, in en" in text
    assert r"\nomgroup" not in text
    assert r"\nomenclature[time]{$\time$}{Time}%" in text


def test_language(small: NotationSet, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("WARNING", logger="anatole"):
        text = to_latex(small, language="fr")
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
    assert to_latex(notations, target="glossaries")  # one glossary per group: no limit
    _ = notations.remove("naa")
    assert r"\@namedef{notation@group@Z}" in to_latex(notations)


def latex_available(*packages: str) -> bool:
    if not all(shutil.which(tool) for tool in ("pdflatex", "makeindex", "kpsewhich")):
        return False
    files = [f"{package}.sty" for package in packages]
    found = subprocess.run(["kpsewhich", *files], capture_output=True, text=True, check=False)
    return len(found.stdout.split()) == len(files)


def run(directory: Path, *command: str) -> None:
    result = subprocess.run(command, cwd=directory, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout[-3000:]


LANGUAGES = [("en", "Latin letters"), ("fr", "Lettres latines")]


@pytest.mark.skipif(
    not latex_available("nomencl", "acro", "siunitx"), reason="needs pdflatex, nomencl, acro"
)
@pytest.mark.parametrize(("language", "title"), LANGUAGES)
def test_nomencl_acro_document_compiles(
    tmp_path: Path, example: NotationSet, language: str, title: str
) -> None:
    text = to_latex(example, language=language)
    _ = (tmp_path / "notations.tex").write_text(text, encoding="utf-8")
    _ = shutil.copy(EXAMPLES / "document.tex", tmp_path)
    latex = ("pdflatex", "-interaction=nonstopmode", "-halt-on-error", "document.tex")
    run(tmp_path, *latex)
    run(tmp_path, "makeindex", "document.nlo", "-s", "nomencl.ist", "-o", "document.nls")
    run(tmp_path, *latex)
    run(tmp_path, *latex)
    listing = (tmp_path / "document.nls").read_text(encoding="utf-8")
    # Groups in order, entries sorted within each.
    order = [
        r"\nomgroup{B}",
        r"[{$\pressure",
        r"[{$\redelta",
        r"[{$\velocity",
        r"\nomgroup{C}",
        r"[{$\blthickness",
        r"[{$\viscosity",
        r"[{$\density",
        r"\nomgroup{D}",
        r"[{$\freestream",
        r"\nomgroup{E}",
        r"[{$\norm",
    ]
    positions = [listing.index(item) for item in order]
    assert positions == sorted(positions)
    assert title in text


@pytest.mark.skipif(
    not latex_available("glossaries-extra", "siunitx"), reason="needs pdflatex, glossaries-extra"
)
@pytest.mark.parametrize(("language", "title"), LANGUAGES)
def test_glossaries_document_compiles(
    tmp_path: Path, example: NotationSet, language: str, title: str
) -> None:
    text = to_latex(example, language=language, target="glossaries")
    _ = (tmp_path / "notations.tex").write_text(text, encoding="utf-8")
    _ = shutil.copy(EXAMPLES / "document-glossaries.tex", tmp_path)
    latex = ("pdflatex", "-interaction=nonstopmode", "-halt-on-error", "document-glossaries.tex")
    run(tmp_path, *latex)
    run(tmp_path, *latex)
    assert (tmp_path / "document-glossaries.pdf").exists()
    assert title in text
