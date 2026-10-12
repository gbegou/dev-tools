"""Shared fixtures: the example notation file, and a small notation set."""

from pathlib import Path

import pytest

from notation_manager import Group, Notation, NotationSet, Rendered, load

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "examples" / "notations.toml"


@pytest.fixture
def example() -> NotationSet:
    """The notations of ``examples/notations.toml``."""
    return load(EXAMPLE)


@pytest.fixture
def small() -> NotationSet:
    """Two groups, an ungrouped notation and a notation with an argument."""
    return NotationSet(
        [
            Notation(
                "velocity",
                Rendered(r"\mathbf{u}", "bold(u)"),
                Rendered.both("Velocity"),
                Rendered(r"\si{m/s}", "m/s"),
                group="latin",
            ),
            Notation("density", Rendered(r"\rho", "rho"), Rendered.both("Density"), group="greek"),
            Notation("time", Rendered.both("t"), Rendered.both("Time")),
            Notation(
                "norm",
                Rendered(r"\lVert #1 \rVert", "norm(#1)"),
                Rendered.both("Norm"),
                arguments=1,
            ),
        ],
        [Group("latin", Rendered.both("Latin")), Group("greek", Rendered.both("Greek"))],
    )
