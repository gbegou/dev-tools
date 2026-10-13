"""Notations, groups and notation sets: validation and editing."""

from dataclasses import replace

import pytest

from anatole import (
    Acronym,
    Group,
    Notation,
    NotationError,
    NotationSet,
    Rendered,
    Style,
    Translated,
)
from anatole.model import Section

SYMBOL = Rendered(r"\mathbf{u}", "bold(u)")
DESCRIPTION = Translated({"en": "Velocity"})


def notation(name: str = "velocity", **fields: object) -> Notation:
    values: dict[str, object] = {"symbol": SYMBOL, "description": DESCRIPTION, **fields}
    return Notation(name, **values)  # pyright: ignore[reportArgumentType]


def problems(**fields: object) -> tuple[str, ...]:
    name = str(fields.pop("name", "velocity"))
    with pytest.raises(NotationError) as caught:
        _ = notation(name, **fields)
    return caught.value.problems


class TestRendered:
    def test_both(self) -> None:
        assert Rendered.both("x") == Rendered("x", "x")
        assert Rendered.both("x").is_uniform

    def test_get_and_with_text(self) -> None:
        value = Rendered("a", "b")
        assert (value.get("latex"), value.get("typst")) == ("a", "b")
        assert value.with_text("typst", "c") == Rendered("a", "c")
        assert value.with_text("latex", "c") == Rendered("c", "b")

    def test_is_empty(self) -> None:
        assert Rendered().is_empty
        assert not Rendered("a", "").is_empty


class TestTranslated:
    def test_strings_are_the_same_in_every_format(self) -> None:
        value = Translated({"en": "Velocity", "fr": Rendered("Vitesse", "_Vitesse_")})
        assert value.languages == ("en", "fr")
        assert value["en"] == Rendered.both("Velocity")
        assert value.get("fr") == Rendered("Vitesse", "_Vitesse_")
        assert value.get("de") is None
        assert "fr" in value
        assert len(value) == 2
        with pytest.raises(KeyError, match="no translation in 'de'"):
            _ = value["de"]

    def test_resolve_falls_back(self) -> None:
        value = Translated({"en": "Velocity"})
        assert value.resolve("fr", "en") == Rendered.both("Velocity")
        with pytest.raises(KeyError):
            _ = value.resolve("fr", "de")

    def test_with_text_and_only(self) -> None:
        value = Translated({"en": "Velocity"}).with_text("fr", "Vitesse")
        assert value == Translated({"en": "Velocity", "fr": "Vitesse"})
        assert value.with_text("en", "Speed")["en"] == Rendered.both("Speed")
        assert value.only(["fr", "de"]) == Translated({"fr": "Vitesse"})

    def test_equality_and_hash(self) -> None:
        assert Translated({"en": "a"}) == Translated({"en": Rendered.both("a")})
        assert Translated({"en": "a", "fr": "b"}) != Translated({"fr": "b", "en": "a"})
        assert hash(Translated({"en": "a"})) == hash(Translated({"en": "a"}))
        assert Translated() != "a"
        assert repr(Translated({"en": "a"})).startswith("Translated(")


class TestNotation:
    def test_valid(self) -> None:
        value = notation(units=Rendered("m/s", "m/s"), group="latin", sort="u")
        assert value.sort_key == ("u", "velocity")

    def test_sort_key_defaults_to_the_name(self) -> None:
        assert notation("Velocity").sort_key == ("velocity", "Velocity")

    @pytest.mark.parametrize("name", ["", "u", "u2", "my_velocity", "vélocité", "u v"])
    def test_invalid_names(self, name: str) -> None:
        assert any("two letters or more" in problem for problem in problems(name=name))

    @pytest.mark.parametrize("name", ["notationnomenclature", "std", "in", "none", "let"])
    def test_reserved_names(self, name: str) -> None:
        assert any("reserved" in problem for problem in problems(name=name))

    def test_end_names(self) -> None:
        assert any("'end'" in problem for problem in problems(name="endpoint"))

    def test_empty_symbol_names_the_format(self) -> None:
        found = problems(symbol=Rendered(r"\mathbf{u}", " "))
        assert found == ("notation 'velocity': symbol is empty in typst",)

    def test_units_in_one_language_only(self) -> None:
        found = problems(units=Rendered("m/s", ""))
        assert found == ("notation 'velocity': units is given in latex but empty in typst",)

    @pytest.mark.parametrize("latex", [r"\mathbf{u", r"\mathbf}u{", "}{"])
    def test_unbalanced_braces(self, latex: str) -> None:
        assert any("unbalanced braces" in p for p in problems(symbol=Rendered(latex, "u")))

    def test_escaped_braces_balance(self) -> None:
        _ = notation(symbol=Rendered(r"\{ x \}", "{x}"))
        _ = notation(symbol=Rendered(r"\left\{ x \right.", "{x"))

    def test_placeholders_within_arguments(self) -> None:
        _ = notation("norm", symbol=Rendered("|#1|_#2", "|#1|_#2"), arguments=2)
        found = problems(name="norm", symbol=Rendered("|#2|", "|#1|"), arguments=1)
        assert found == (
            "notation 'norm': symbol uses #2 in latex, but takes 1 argument(s) " + "(#1 to #1)",
        )

    def test_placeholder_without_arguments(self) -> None:
        assert any("no placeholder" in p for p in problems(symbol=Rendered("#1", "#1")))

    @pytest.mark.parametrize("arguments", [-1, 10, True, 1.0, "1"])
    def test_invalid_arguments(self, arguments: object) -> None:
        assert any("arguments must be an integer" in p for p in problems(arguments=arguments))

    @pytest.mark.parametrize("sort", ["a@b", "a!b", 'a"b', "a|b", "é"])
    def test_invalid_sort_keys(self, sort: str) -> None:
        assert any("sort key" in problem for problem in problems(sort=sort))

    def test_invalid_group_key(self) -> None:
        assert any("group key" in problem for problem in problems(group="a b"))

    def test_empty_description_names_the_language(self) -> None:
        found = problems(description=Translated({"en": "Velocity", "fr": Rendered("", "Vitesse")}))
        assert found == ("notation 'velocity': description (fr) is empty in latex",)

    def test_description_needs_a_translation(self) -> None:
        assert problems(description=Translated()) == (
            "notation 'velocity': description has no translation",
        )

    @pytest.mark.parametrize("language", ["EN", "english", "e", "fr_FR", ""])
    def test_invalid_language_codes(self, language: str) -> None:
        found = problems(description=Translated({language: "Velocity"}))
        assert any("invalid language code" in problem for problem in found)

    @pytest.mark.parametrize("language", ["en", "fr", "deu", "pt-BR", "zh-Hant-TW"])
    def test_valid_language_codes(self, language: str) -> None:
        _ = notation(description=Translated({language: "Velocity"}))

    def test_every_problem_is_reported(self) -> None:
        found = problems(name="x", symbol=Rendered("", ""), description=Translated())
        assert len(found) == 4


class TestGroup:
    def test_valid(self) -> None:
        assert Group("latin-1_a", Translated({"en": "Latin"})).key == "latin-1_a"

    def test_invalid(self) -> None:
        with pytest.raises(NotationError) as caught:
            _ = Group("a b", Translated({"en": Rendered("", "x")}))
        assert caught.value.problems == (
            "group 'a b': the key must be keys of letters, digits, '_' or '-', joined by '.'",
            "group 'a b': title (en) is empty in latex",
        )


class TestNotationSet:
    def test_container(self, small: NotationSet) -> None:
        assert len(small) == 4
        assert "velocity" in small
        assert "pressure" not in small
        assert [n.name for n in small] == ["velocity", "density", "time", "norm"]
        assert small.notation("density").group == "greek"
        with pytest.raises(KeyError, match="no entry or style named 'pressure'"):
            _ = small["pressure"]

    def test_construction_reports_every_problem(self) -> None:
        with pytest.raises(NotationError) as caught:
            _ = NotationSet(
                [notation(), notation(), notation("pressure", group="latin")],
                [Group("greek", Translated({"en": "G"})), Group("greek", Translated({"en": "G"}))],
            )
        assert caught.value.problems == (
            "group 'greek': defined twice",
            "notation 'velocity': the name is already taken",
            "notation 'pressure': unknown group 'latin'",
        )

    def test_add(self, small: NotationSet) -> None:
        small.add(notation("pressure", group="latin"))
        assert list(small)[-1].name == "pressure"
        with pytest.raises(NotationError, match="already taken"):
            small.add(notation())
        with pytest.raises(NotationError, match="unknown group 'other'"):
            small.add(notation("other", group="other"))

    def test_replace_keeps_the_position(self, small: NotationSet) -> None:
        small.replace("density", notation("rho", group="greek"))
        assert [n.name for n in small] == ["velocity", "rho", "time", "norm"]
        with pytest.raises(NotationError, match="already taken"):
            small.replace("rho", notation("time"))
        with pytest.raises(NotationError, match="unknown group"):
            small.replace("rho", notation("rho", group="other"))
        with pytest.raises(KeyError):
            small.replace("density", notation("density"))

    def test_remove(self, small: NotationSet) -> None:
        assert small.remove("time").name == "time"
        assert "time" not in small
        with pytest.raises(KeyError):
            _ = small.remove("time")

    def test_groups(self, small: NotationSet) -> None:
        assert [g.key for g in small.groups] == ["latin", "greek"]
        assert small.group("greek").title == Translated({"en": "Greek", "fr": "Grec"})
        with pytest.raises(KeyError):
            _ = small.group("other")
        small.add_group(Group("ops", Translated({"en": "Operators"})))
        with pytest.raises(NotationError, match="already taken"):
            small.add_group(Group("ops", Translated({"en": "Operators"})))

    def test_rename_group_moves_its_notations(self, small: NotationSet) -> None:
        small.replace_group("greek", Group("grec", Translated({"en": "Grec"})))
        assert [g.key for g in small.groups] == ["latin", "grec"]
        assert small.notation("density").group == "grec"
        with pytest.raises(NotationError, match="already taken"):
            small.replace_group("grec", Group("latin", Translated({"en": "Latin"})))

    def test_remove_group(self, small: NotationSet) -> None:
        with pytest.raises(NotationError, match="still used by 'density'"):
            _ = small.remove_group("greek")
        _ = small.remove("density")
        assert small.remove_group("greek").key == "greek"
        with pytest.raises(KeyError):
            _ = small.remove_group("greek")

    def test_move_group(self, small: NotationSet) -> None:
        small.move_group("greek", -1)
        assert [g.key for g in small.groups] == ["greek", "latin"]
        small.move_group("greek", -5)  # clamped
        assert [g.key for g in small.groups] == ["greek", "latin"]
        small.move_group("greek", 5)
        assert [g.key for g in small.groups] == ["latin", "greek"]
        with pytest.raises(KeyError):
            small.move_group("other", 1)

    def test_nomenclature_order(self, small: NotationSet) -> None:
        small.add(notation("alpha", group="latin", sort="z"))
        small.add(notation("pressure", group="latin"))
        sections = small.sections()
        assert [
            (s.group.key if s.group else None, [e.name for e in s.entries]) for s in sections
        ] == [
            (None, ["norm", "time"]),
            ("latin", ["pressure", "velocity", "alpha"]),
            ("greek", ["density"]),
        ]

    def test_nomenclature_skips_empty_groups(self, small: NotationSet) -> None:
        _ = small.remove("density")
        assert [s.group.key for s in small.sections() if s.group] == ["latin"]

    def test_equality(self, small: NotationSet) -> None:
        other = NotationSet(small, small.groups, small.languages)
        assert small == other
        small.move_group("greek", -1)
        assert small != other
        assert small != "not a set"


class TestLanguages:
    def test_default(self) -> None:
        notations = NotationSet()
        assert notations.languages == ("en",)
        assert notations.default_language == "en"

    def test_declared(self, small: NotationSet) -> None:
        assert small.languages == ("en", "fr")
        assert small.default_language == "en"
        small.check_language("fr")
        with pytest.raises(NotationError, match="language 'de' is not declared \\(en, fr\\)"):
            small.check_language("de")

    @pytest.mark.parametrize(
        ("languages", "problem"),
        [
            ((), "at least one language"),
            (("en", "en"), "'en' is declared twice"),
            (("English",), "invalid language code 'English'"),
        ],
    )
    def test_invalid_languages(self, languages: tuple[str, ...], problem: str) -> None:
        with pytest.raises(NotationError, match=problem):
            _ = NotationSet(languages=languages)

    def test_translations_must_be_declared_and_in_the_default_language(self) -> None:
        with pytest.raises(NotationError) as caught:
            _ = NotationSet(
                [notation(description=Translated({"fr": "Vitesse", "de": "Geschwindigkeit"}))],
                [Group("latin", Translated({"fr": "Latin"}))],
                languages=("en", "fr"),
            )
        assert caught.value.problems == (
            "group 'latin': title is missing in the default language en",
            "notation 'velocity': description is missing in the default language en",
            "notation 'velocity': description is in de, which is not a declared language (en, fr)",
        )

    def test_add_and_replace_check_the_translations(self, small: NotationSet) -> None:
        with pytest.raises(NotationError, match="missing in the default language en"):
            small.add(notation("speed", description=Translated({"fr": "Vitesse"})))
        with pytest.raises(NotationError, match="not a declared language"):
            small.replace("time", notation("time", description=Translated({"en": "T", "de": "Z"})))
        with pytest.raises(NotationError, match="missing in the default language"):
            small.add_group(Group("ops", Translated({"fr": "Opérateurs"})))
        with pytest.raises(NotationError, match="not a declared language"):
            small.replace_group("greek", Group("greek", Translated({"en": "G", "it": "G"})))

    def test_missing_translations(self, small: NotationSet) -> None:
        assert small.missing_translations() == [
            "notation 'density': description is missing in fr",
            "notation 'norm': description is missing in fr",
        ]
        assert small.missing_translations(["en"]) == []

    def test_set_languages_adds_and_reorders(self, small: NotationSet) -> None:
        small.set_languages(["en", "fr", "de"])
        assert small.languages == ("en", "fr", "de")
        assert len(small.missing_translations(["de"])) == 6
        for name in ("density", "norm"):
            french = small[name].description.with_text("fr", name.title())
            small.replace(name, replace(small[name], description=french))
        small.set_languages(["fr", "en"])
        assert small.default_language == "fr"

    def test_set_languages_needs_the_new_default(self, small: NotationSet) -> None:
        with pytest.raises(NotationError) as caught:
            small.set_languages(["fr", "en"])
        assert caught.value.problems == (
            "notation 'density': description is missing in the new default language fr",
            "notation 'norm': description is missing in the new default language fr",
        )
        assert small.languages == ("en", "fr")  # unchanged

    def test_set_languages_drops_the_removed_translations(self, small: NotationSet) -> None:
        small.set_languages(["en"])
        assert small["velocity"].description == Translated({"en": "Velocity"})
        assert small.group("greek").title == Translated({"en": "Greek"})
        with pytest.raises(NotationError, match="invalid language code"):
            small.set_languages(["EN"])

    def test_equality_includes_the_languages(self, small: NotationSet) -> None:
        other = NotationSet(small, small.groups, ["en", "fr"])
        assert other == small
        other.set_languages(["en", "fr", "de"])
        assert other != small


def acronym(name: str = "cfd", **fields: object) -> Acronym:
    values: dict[str, object] = {
        "short": Translated({"en": name.upper()}),
        "long": Translated({"en": f"long {name}"}),
        **fields,
    }
    return Acronym(name, **values)  # pyright: ignore[reportArgumentType]


VECT = Style("vect", Rendered(r"\boldsymbol{#1}", "bold(#1)"))


class TestStyle:
    def test_valid(self) -> None:
        assert VECT.references() == []

    def test_template_takes_one_argument(self) -> None:
        with pytest.raises(NotationError, match="uses #2 in latex, but takes 1 argument"):
            _ = Style("pair", Rendered("#1 #2", "#1"))

    def test_notation_with_a_style(self) -> None:
        notations = NotationSet([notation("velocity", style="vect")], styles=[VECT])
        assert notations.notation("velocity").references() == ["vect"]
        assert notations.style("vect") == VECT
        assert notations.styles == (VECT,)
        assert notations.users("vect") == ["velocity"]

    def test_unknown_style(self) -> None:
        with pytest.raises(NotationError, match="unknown style 'vect'"):
            _ = NotationSet([notation("velocity", style="vect")])

    def test_an_entry_is_not_a_style(self) -> None:
        with pytest.raises(NotationError, match="'time' is not a style"):
            _ = NotationSet([notation("time"), notation("velocity", style="time")])

    def test_rename_moves_the_notations(self) -> None:
        notations = NotationSet([notation("velocity", style="vect")], styles=[VECT])
        notations.replace("vect", Style("vector", VECT.template))
        assert notations.notation("velocity").style == "vector"

    def test_style_and_entry_do_not_replace_each_other(self) -> None:
        notations = NotationSet([notation()], styles=[VECT])
        with pytest.raises(NotationError, match="cannot replace each other"):
            notations.replace("vect", notation("vect"))


class TestAcronym:
    def test_valid(self) -> None:
        value = acronym("wrt", abbreviation=True, group="g", tags=("a",))
        assert (value.kind, value.sort_key) == ("abbreviation", ("wrt", "wrt"))
        assert acronym().kind == "acronym"

    def test_short_and_long_are_required(self) -> None:
        with pytest.raises(NotationError) as caught:
            _ = acronym(short=Translated(), long=Translated())
        assert caught.value.problems == (
            "acronym 'cfd': short has no translation",
            "acronym 'cfd': long has no translation",
        )

    def test_default_language_required(self) -> None:
        with pytest.raises(NotationError, match="long is missing in the default language en"):
            _ = NotationSet([acronym(long=Translated({"fr": "long"}))], languages=["en", "fr"])

    def test_optional_description(self) -> None:
        with pytest.raises(NotationError, match="description is missing in the default language"):
            _ = NotationSet([acronym(description=Translated({"fr": "x"}))], languages=["en", "fr"])

    def test_kinds_in_the_set(self) -> None:
        notations = NotationSet([notation(), acronym(), acronym("wrt", abbreviation=True)])
        assert [n.name for n in notations.notations] == ["velocity"]
        assert [a.name for a in notations.acronyms] == ["cfd", "wrt"]
        assert notations.acronym("cfd").long == Translated({"en": "long cfd"})
        with pytest.raises(KeyError):
            _ = notations.notation("cfd")
        with pytest.raises(KeyError):
            _ = notations.acronym("velocity")
        with pytest.raises(KeyError):
            _ = notations.style("velocity")

    @pytest.mark.parametrize("tags", [("a b",), ("a", "a")])
    def test_invalid_tags(self, tags: tuple[str, ...]) -> None:
        with pytest.raises(NotationError, match="tag"):
            _ = acronym(tags=tags)


DELTA = Notation("blthickness", Rendered(r"\delta", "delta"), Translated({"en": "Thickness"}))
REDELTA = Notation(
    "redelta",
    Rendered(r"\mathit{Re}_{@{blthickness}}", 'italic("Re")_(@{blthickness})'),
    Translated({"en": "Reynolds number based on @{blthickness}"}),
)


class TestReferences:
    def test_references(self) -> None:
        assert REDELTA.references() == ["blthickness"]
        notations = NotationSet([REDELTA, DELTA])
        assert notations.users("blthickness") == ["redelta"]
        assert notations.dependencies(["redelta"]) == ["blthickness"]
        assert [item.name for item in notations.ordered()] == ["blthickness", "redelta"]

    def test_unknown_reference(self) -> None:
        with pytest.raises(NotationError) as caught:
            _ = NotationSet([REDELTA])
        assert caught.value.problems == (
            "notation 'redelta': refers to @{blthickness}, which is not defined",
        )

    @pytest.mark.parametrize("text", ["@{x y}", "@{}", "@{delta", "@{a1}"])
    def test_malformed_reference(self, text: str) -> None:
        with pytest.raises(NotationError, match="malformed reference"):
            _ = notation(symbol=Rendered.both(text))

    def test_cycle(self) -> None:
        cyclic = Notation("blthickness", Rendered.both("@{redelta}"), Translated({"en": "x"}))
        with pytest.raises(NotationError) as caught:
            _ = NotationSet([REDELTA, cyclic])
        (problem,) = caught.value.problems
        assert "depends on itself" in problem
        assert "redelta" in problem
        assert "blthickness" in problem

    def test_self_reference(self) -> None:
        with pytest.raises(NotationError, match="depends on itself"):
            _ = NotationSet([notation("velocity", symbol=Rendered.both("@{velocity}"))])

    def test_rename_follows(self) -> None:
        notations = NotationSet([DELTA, REDELTA])
        notations.replace("blthickness", replace(DELTA, name="delta"))
        assert notations.notation("redelta").symbol == Rendered(
            r"\mathit{Re}_{@{delta}}", 'italic("Re")_(@{delta})'
        )
        assert notations.notation("redelta").description["en"].latex.endswith("@{delta}")

    def test_remove_used(self) -> None:
        notations = NotationSet([DELTA, REDELTA])
        with pytest.raises(NotationError, match="used by 'redelta'"):
            _ = notations.remove("blthickness")
        _ = notations.remove("redelta")
        _ = notations.remove("blthickness")
        assert len(notations) == 0

    def test_failed_change_leaves_the_set(self) -> None:
        notations = NotationSet([DELTA, REDELTA])
        cyclic = replace(DELTA, symbol=Rendered.both("@{redelta}"))
        with pytest.raises(NotationError):
            notations.replace("blthickness", cyclic)
        assert notations.notation("blthickness") == DELTA


def tree() -> NotationSet:
    def group(key: str) -> Group:
        return Group(key, Translated({"en": key.title()}))

    return NotationSet(
        [
            notation("velocity", group="symbols.latin"),
            notation("pressure", group="symbols.latin", sort="a"),
            notation("density", group="symbols.greek"),
            notation("time", group="symbols"),
            notation("norm", group="operators"),
            acronym("cfd", group="acronyms"),
        ],
        [group(k) for k in ("symbols", "symbols.latin", "symbols.greek", "operators", "acronyms")],
    )


class TestGroupTree:
    def test_depth(self) -> None:
        group = Group("symbols.latin", Translated({"en": "Latin"}))
        assert (group.parent, group.depth) == ("symbols", 2)
        with pytest.raises(NotationError, match="at most 2 levels"):
            _ = Group("a.b.c", Translated({"en": "x"}))

    def test_section_must_exist(self) -> None:
        with pytest.raises(NotationError, match="unknown section 'symbols'"):
            _ = NotationSet(groups=[Group("symbols.latin", Translated({"en": "x"}))])

    def test_order_and_children(self) -> None:
        notations = tree()
        assert [g.key for g in notations.groups] == [
            "symbols",
            "symbols.latin",
            "symbols.greek",
            "operators",
            "acronyms",
        ]
        assert [g.key for g in notations.children("")] == ["symbols", "operators", "acronyms"]
        assert [g.key for g in notations.children("symbols")] == ["symbols.latin", "symbols.greek"]

    def test_sections(self) -> None:
        def names(sections: tuple[Section, ...]) -> list[object]:
            return [
                (
                    s.group.key if s.group else None,
                    [e.name for e in s.entries],
                    names(s.subsections),
                )
                for s in sections
            ]

        notations = tree()
        assert names(notations.sections("notation")) == [
            (
                "symbols",
                ["time"],
                [
                    ("symbols.latin", ["pressure", "velocity"], []),
                    ("symbols.greek", ["density"], []),
                ],
            ),
            ("operators", ["norm"], []),
        ]
        assert names(notations.sections("acronym")) == [("acronyms", ["cfd"], [])]
        assert [e.name for e in notations.sections()[0].all_entries()] == [
            "time",
            "pressure",
            "velocity",
            "density",
        ]

    def test_rename_section_moves_subsections_and_entries(self) -> None:
        notations = tree()
        notations.replace_group("symbols", Group("syms", Translated({"en": "Symbols"})))
        assert [g.key for g in notations.groups][:3] == ["syms", "syms.latin", "syms.greek"]
        assert notations.notation("velocity").group == "syms.latin"
        assert notations.notation("time").group == "syms"

    def test_rename_keeps_the_section(self) -> None:
        notations = tree()
        with pytest.raises(NotationError, match="keeps the group in its section"):
            notations.replace_group(
                "symbols.latin", Group("operators.latin", Translated({"en": "x"}))
            )

    def test_remove_needs_an_empty_group(self) -> None:
        notations = tree()
        used = r"still used by 'symbols\.latin', 'symbols\.greek'"
        with pytest.raises(NotationError, match=used):
            _ = notations.remove_group("symbols")

    def test_move_among_siblings(self) -> None:
        notations = tree()
        notations.move_group("symbols.greek", -1)
        notations.move_group("acronyms", -10)
        assert [g.key for g in notations.groups] == [
            "acronyms",
            "symbols",
            "symbols.greek",
            "symbols.latin",
            "operators",
        ]


class TestSubset:
    def test_tags_select_and_bring_dependencies(self) -> None:
        notations = NotationSet(
            [
                replace(DELTA, tags=("thesis",)),
                replace(REDELTA, tags=("paper",)),
                notation("velocity"),
                notation("pressure", tags=("thesis",)),
            ]
        )
        assert notations.tags == ("paper", "thesis")
        paper = notations.subset(["paper"])
        assert [e.name for e in paper] == ["blthickness", "redelta", "velocity"]
        assert [e.name for e in notations.subset(["thesis"])] == [
            "blthickness",
            "velocity",
            "pressure",
        ]
        assert [e.name for e in notations.subset([])] == ["velocity"]
