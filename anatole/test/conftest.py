"""Shared fixtures: the example notation file, and a small notation set."""

from pathlib import Path

import pytest

from anatole import Group, Notation, NotationSet, Rendered, Translated, load

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "examples" / "notations.toml"


@pytest.fixture
def example() -> NotationSet:
    """The notations of ``examples/notations.toml`` (in English and French)."""
    return load(EXAMPLE)


@pytest.fixture
def small() -> NotationSet:
    """English and French; two groups, an ungrouped notation, a notation with an argument,
    and descriptions not translated in French (``density``, ``norm``)."""
    return NotationSet(
        [
            Notation(
                "velocity",
                Rendered(r"\mathbf{u}", "bold(u)"),
                Translated({"en": "Velocity", "fr": "Vitesse"}),
                Rendered(r"\si{m/s}", "m/s"),
                group="latin",
            ),
            Notation(
                "density", Rendered(r"\rho", "rho"), Translated({"en": "Density"}), group="greek"
            ),
            Notation("time", Rendered.both("t"), Translated({"en": "Time", "fr": "Temps"})),
            Notation(
                "norm",
                Rendered(r"\lVert #1 \rVert", "norm(#1)"),
                Translated({"en": "Norm"}),
                arguments=1,
            ),
        ],
        [
            Group("latin", Translated({"en": "Latin", "fr": "Latin"})),
            Group("greek", Translated({"en": "Greek", "fr": "Grec"})),
        ],
        languages=("en", "fr"),
    )
