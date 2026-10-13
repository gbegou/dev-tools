"""Notations, groups and notation sets: validation and editing."""

from dataclasses import replace

import pytest

from anatole import Group, Notation, NotationError, NotationSet, Rendered, Translated

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
            "notation 'norm': symbol uses #2 in latex, but the notation takes 1 argument(s) "
            + "(#1 to #1)",
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
            "group 'a b': the key must be letters, digits, '_' or '-'",
            "group 'a b': title (en) is empty in latex",
        )


class TestNotationSet:
    def test_container(self, small: NotationSet) -> None:
        assert len(small) == 4
        assert "velocity" in small
        assert "pressure" not in small
        assert [n.name for n in small] == ["velocity", "density", "time", "norm"]
        assert small["density"].group == "greek"
        with pytest.raises(KeyError, match="no notation named 'pressure'"):
            _ = small["pressure"]

    def test_construction_reports_every_problem(self) -> None:
        with pytest.raises(NotationError) as caught:
            _ = NotationSet(
                [notation(), notation(), notation("pressure", group="latin")],
                [Group("greek", Translated({"en": "G"})), Group("greek", Translated({"en": "G"}))],
            )
        assert caught.value.problems == (
            "group 'greek': defined twice",
            "notation 'velocity': defined twice",
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
        assert small["density"].group == "grec"
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
        sections = small.nomenclature()
        assert [(g.key if g else None, [n.name for n in m]) for g, m in sections] == [
            (None, ["norm", "time"]),
            ("latin", ["pressure", "velocity", "alpha"]),
            ("greek", ["density"]),
        ]

    def test_nomenclature_skips_empty_groups(self, small: NotationSet) -> None:
        _ = small.remove("density")
        assert [g.key for g, _ in small.nomenclature() if g] == ["latin"]

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
