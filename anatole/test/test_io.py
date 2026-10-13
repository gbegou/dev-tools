"""Notation files: reading, writing, and the problems reported for invalid files."""

import tomllib
from pathlib import Path

import pytest

from anatole import (
    Notation,
    NotationError,
    NotationSet,
    Rendered,
    Translated,
    dumps,
    from_dict,
    load,
    loads,
    save,
    to_dict,
)


def problems(text: str) -> tuple[str, ...]:
    with pytest.raises(NotationError) as caught:
        _ = loads(text)
    return caught.value.problems


def test_example_loads(example: NotationSet) -> None:
    assert (len(example.notations), len(example.acronyms), len(example.styles)) == (8, 3, 1)
    assert [g.key for g in example.groups] == [
        "symbols",
        "symbols.latin",
        "symbols.greek",
        "symbols.subscripts",
        "operators",
        "acronyms",
        "abbreviations",
    ]
    assert example.languages == ("en", "fr")
    velocity = example.notation("velocity")
    assert (velocity.symbol, velocity.style) == (Rendered.both("u"), "vect")
    assert velocity.description == Translated({"en": "Velocity", "fr": "Vitesse"})
    assert example.style("vect").template == Rendered(r"\boldsymbol{#1}", "bold(#1)")
    assert example.notation("redelta").references() == ["blthickness"]
    assert example.notation("norm").arguments == 1
    cfd = example.acronym("cfd")
    assert cfd.short == Translated({"en": "CFD", "fr": "MFN"})
    assert not cfd.abbreviation
    assert example.acronym("wrt").abbreviation
    assert example.acronym("les").tags == ("turbulence",)


def test_round_trip(example: NotationSet, small: NotationSet) -> None:
    for notations in (example, small):
        assert loads(dumps(notations)) == notations


def test_round_trip_of_awkward_strings() -> None:
    texts = ["it's", 'say "hi"', "a\\b", "tab\there", "line\nbreak", "ünïcode ∇", "\x01"]
    notations = NotationSet(
        Notation(f"n{chr(97 + i)}", Rendered(text, "y"), Translated({"en": Rendered(text, "z")}))
        for i, text in enumerate(texts)
    )
    text = dumps(notations)
    assert tomllib.loads(text)  # valid TOML
    assert loads(text) == notations


def test_dumps_is_readable() -> None:
    notations = NotationSet(
        [Notation("velocity", Rendered(r"\mathbf{u}", "bold(u)"), Translated({"en": "Velocity"}))]
    )
    assert dumps(notations) == (
        "version = 1\n"
        "languages = ['en']\n"
        "\n"
        "[notations.velocity]\n"
        "symbol = { latex = '\\mathbf{u}', typst = 'bold(u)' }\n"
        "description = 'Velocity'\n"
    )


def test_to_dict_leaves_defaults_out(small: NotationSet) -> None:
    data = to_dict(small)
    notations = data["notations"]
    assert isinstance(notations, dict)
    assert notations["time"] == {"symbol": "t", "description": {"en": "Time", "fr": "Temps"}}
    assert notations["density"]["description"] == {"en": "Density"}
    assert from_dict(data) == small


def test_one_language_writes_strings() -> None:
    notations = loads(
        "[notations.velocity]\nsymbol = 'u'\ndescription = 'Velocity'\n"
        + "[notations.speed]\nsymbol = 'v'\n"
        + "description = { latex = '\\emph{Speed}', typst = '_Speed_' }\n"
    )
    assert notations.languages == ("en",)
    data = to_dict(notations)["notations"]
    assert isinstance(data, dict)
    assert data["velocity"] == {"symbol": "u", "description": "Velocity"}
    assert data["speed"] == {
        "symbol": "v",
        "description": {"latex": "\\emph{Speed}", "typst": "_Speed_"},
    }
    assert loads(dumps(notations)) == notations


def test_strings_are_in_the_default_language() -> None:
    notations = loads(
        "languages = ['fr', 'en']\n[groups.g]\ntitle = 'Groupe'\n"
        + "[notations.ab]\nsymbol = 'x'\ndescription = 'Vitesse'\ngroup = 'g'\n"
    )
    assert notations["ab"].description == Translated({"fr": "Vitesse"})
    assert notations.group("g").title == Translated({"fr": "Groupe"})


def test_save_and_load(tmp_path: Path, small: NotationSet) -> None:
    path = tmp_path / "notations.toml"
    save(small, path)
    assert load(path) == small


def test_load_prefixes_problems_with_the_path(tmp_path: Path) -> None:
    path = tmp_path / "bad.toml"
    _ = path.write_text("[notations.x]\nsymbol = 'x'\ndescription = 'x'\n", encoding="utf-8")
    with pytest.raises(NotationError) as caught:
        _ = load(path)
    assert caught.value.problems == (
        f"{path}: notation 'x': the name must be two letters or more (A-Z, a-z)",
    )


def test_invalid_toml() -> None:
    (problem,) = problems("[notations\n")
    assert problem.startswith("file: invalid TOML:")


def test_unsupported_version() -> None:
    assert problems("version = 2") == ("file: format version 2 is not supported (expected 1)",)


def test_every_problem_is_reported() -> None:
    found = problems(
        """
        colour = 1

        [groups.latin]
        titel = "Latin"

        [groups.greek]
        title = { en = { latex = "Greek", typst = 3 } }

        [groups.ops]
        title = { en = "Operators", latex = "Ops" }

        [notations.velocity]
        group = "latin"
        symbol = { latex = 'u', typst = 'u', html = 'u' }
        description = "Velocity"
        unit = "m/s"

        [notations.pressure]
        symbol = 1
        group = 2
        sort = 3
        arguments = "one"

        [notations.density]
        description = "Density"

        [notations.viscosity]
        symbol = 'mu'
        description = 1
        """
    )
    assert found == (
        "file: unknown key(s) colour (expected version, languages, styles, groups, notations, "
        + "acronyms, abbreviations)",
        "group 'latin': title is missing",
        "group 'latin': unknown key titel (expected title, or a table for a subsection)",
        "group 'greek': title.en.typst must be a string",
        "group 'ops': title mixes languages and formats: "
        + "write title.<language> = { latex = ..., typst = ... }",
        "notation 'velocity': unknown key(s) unit "
        + "(expected group, style, arguments, sort, tags, symbol, description, units)",
        "notation 'velocity': symbol has unknown format(s) html (expected latex, typst)",
        "notation 'pressure': group must be a string",
        "notation 'pressure': sort must be a string",
        "notation 'pressure': arguments must be an integer",
        "notation 'pressure': description is missing",
        "notation 'pressure': symbol must be a string or a table with keys latex and typst",
        "notation 'density': symbol is missing",
        "notation 'viscosity': description must be a string or a table with one entry per "
        + "language",
    )


def test_tables_must_be_tables() -> None:
    assert problems("notations = 1") == ("notations: must be a table",)
    assert problems("groups = 1\n[notations.ab]\nsymbol='a'\ndescription='a'\ngroup='x'") == (
        "groups: must be a table",
        "notation 'ab': unknown group 'x'",
    )
    assert problems("[notations]\nvelocity = 1") == ("notation 'velocity': must be a table",)


def test_boolean_arguments_are_rejected() -> None:
    (problem,) = problems("[notations.ab]\nsymbol='a'\ndescription='a'\narguments=true")
    assert "arguments must be an integer from 0 to 9, not True" in problem


def test_empty_file() -> None:
    assert loads("") == NotationSet()


def test_languages_must_be_a_list_of_codes() -> None:
    assert problems("languages = 'en'") == (
        'languages: must be a list of language codes, like ["en", "fr"]',
    )
    assert problems("languages = ['en', 'EN']") == (
        "languages: invalid language code 'EN' (expected a code like en, fr or pt-BR)",
    )


def test_undeclared_languages() -> None:
    assert problems("[notations.ab]\nsymbol = 'x'\ndescription = { en = 'a', de = 'b' }") == (
        "notation 'ab': description is in de, which is not a declared language (en)",
    )


def test_styles_acronyms_and_tree_round_trip() -> None:
    text = """
languages = ["en", "fr"]

[styles.vect]
template = { latex = '\\vec{#1}', typst = 'arrow(#1)' }

[groups.symbols]
title = "Symbols"

[groups.symbols.latin]
title = { en = "Latin", fr = "Latin" }

[notations.velocity]
group = "symbols.latin"
style = "vect"
tags = ["thesis", "paper"]
symbol = "u"
description = "Velocity"

[acronyms.cfd]
short = { en = "CFD", fr = "MFN" }
long = "computational fluid dynamics"
description = "Numerical simulation of flows"

[abbreviations.wrt]
sort = "w"
short = "w.r.t."
long = "with respect to"
"""
    notations = loads(text)
    assert notations.notation("velocity").tags == ("thesis", "paper")
    assert notations.group("symbols.latin").parent == "symbols"
    assert notations.acronym("wrt").abbreviation
    assert notations.acronym("cfd").description == Translated(
        {"en": "Numerical simulation of flows"}
    )
    dumped = dumps(notations)
    assert "[groups.symbols.latin]" in dumped
    assert "[abbreviations.wrt]" in dumped
    assert "tags = ['thesis', 'paper']" in dumped
    assert loads(dumped) == notations


def test_acronym_problems() -> None:
    assert problems("[acronyms.cfd]\nshort = 'CFD'\ntags = 'x'\nlong = 3") == (
        "acronym 'cfd': tags must be a list of strings",
        "acronym 'cfd': long must be a string or a table with one entry per language",
    )
    assert problems("[abbreviations.wrt]\nshort = 'w.r.t.'") == (
        "abbreviation 'wrt': long is missing",
    )


def test_style_problems() -> None:
    assert problems("[styles.vect]\ndescription = 'Vector'") == (
        "style 'vect': template is missing",
    )
    assert problems("[styles.vect]\ntemplate = '#2'") == (
        "style 'vect': template uses #2 in latex, but takes 1 argument(s) (#1 to #1)",
        "style 'vect': template uses #2 in typst, but takes 1 argument(s) (#1 to #1)",
    )


def test_reference_problems() -> None:
    assert problems("[notations.re]\nsymbol = '@{delta}'\ndescription = 'x'") == (
        "notation 're': refers to @{delta}, which is not defined",
    )
