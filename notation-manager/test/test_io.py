"""Notation files: reading, writing, and the problems reported for invalid files."""

import tomllib
from pathlib import Path

import pytest

from notation_manager import (
    Notation,
    NotationError,
    NotationSet,
    Rendered,
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
    assert len(example) == 6
    assert [g.key for g in example.groups] == ["latin", "greek", "operators"]
    assert example["velocity"].symbol == Rendered(r"\mathbf{u}", "bold(upright(u))")
    assert example["velocity"].description == Rendered.both("Velocity")
    assert example["norm"].arguments == 1
    assert example["density"].sort == "rho"


def test_round_trip(example: NotationSet, small: NotationSet) -> None:
    for notations in (example, small):
        assert loads(dumps(notations)) == notations


def test_round_trip_of_awkward_strings() -> None:
    texts = ["it's", 'say "hi"', "a\\b", "tab\there", "line\nbreak", "ünïcode ∇", "\x01"]
    notations = NotationSet(
        Notation(f"n{chr(97 + i)}", Rendered.both("x"), Rendered(text, "y"))
        for i, text in enumerate(texts)
    )
    text = dumps(notations)
    assert tomllib.loads(text)  # valid TOML
    assert loads(text) == notations


def test_dumps_is_readable() -> None:
    notations = NotationSet(
        [Notation("velocity", Rendered(r"\mathbf{u}", "bold(u)"), Rendered.both("Velocity"))]
    )
    assert dumps(notations) == (
        "version = 1\n"
        "\n"
        "[notations.velocity]\n"
        "symbol = { latex = '\\mathbf{u}', typst = 'bold(u)' }\n"
        "description = 'Velocity'\n"
    )


def test_to_dict_leaves_defaults_out(small: NotationSet) -> None:
    data = to_dict(small)
    notations = data["notations"]
    assert isinstance(notations, dict)
    assert notations["time"] == {"symbol": "t", "description": "Time"}
    assert from_dict(data) == small


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
        title = { latex = "Greek", typst = 3 }

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
        """
    )
    assert found == (
        "file: unknown key(s) colour (expected version, groups, notations)",
        "group 'latin': unknown key(s) titel (expected title)",
        "group 'latin': title is missing",
        "group 'greek': title.typst must be a string",
        "notation 'velocity': unknown key(s) unit "
        + "(expected group, arguments, sort, symbol, description, units)",
        "notation 'velocity': symbol has unknown language(s) html (expected latex, typst)",
        "notation 'pressure': description is missing",
        "notation 'pressure': group must be a string",
        "notation 'pressure': sort must be a string",
        "notation 'pressure': arguments must be an integer",
        "notation 'pressure': symbol must be a string or a table with keys latex and typst",
        "notation 'density': symbol is missing",
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
