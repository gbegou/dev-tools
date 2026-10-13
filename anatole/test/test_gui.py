"""The graphical interface, driven without a user (needs a display, e.g. ``xvfb-run``)."""

from collections.abc import Iterator
from pathlib import Path
from typing import cast, final, override

import pytest

from anatole import NotationSet, Rendered, Translated, load, preview

try:
    import tkinter as tk
except ModuleNotFoundError:  # Python built without Tk
    pytest.skip("needs tkinter", allow_module_level=True)

from anatole.export import office
from anatole.gui.app import NotationApp
from anatole.gui.form import GroupForm, ItemForm
from anatole.gui.groups import GroupsDialog
from anatole.gui.prompts import FileTypes, Prompts


@final
class ScriptedPrompts(Prompts):
    """Prompts that answer from a script and record what they were asked."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.save_answer: bool | None = True
        self.confirm_answer = True
        self.path: Path | None = None
        self.text: str | None = None
        self.asked: list[str] = []
        self.errors: list[str] = []

    @override
    def ask_save(self, message: str) -> bool | None:
        self.asked.append(message)
        return self.save_answer

    @override
    def confirm(self, message: str) -> bool:
        self.asked.append(message)
        return self.confirm_answer

    @override
    def ask_text(self, title: str, message: str, initial: str = "") -> str | None:
        self.asked.append(initial)
        return self.text

    @override
    def error(self, message: str) -> None:
        self.errors.append(message)

    @override
    def open_path(self, file_types: FileTypes) -> Path | None:
        return self.path

    @override
    def save_path(self, file_types: FileTypes, suffix: str) -> Path | None:
        return self.path


@pytest.fixture
def root() -> Iterator[tk.Tk]:
    try:
        window = tk.Tk()
    except tk.TclError as error:
        pytest.skip(f"no display: {error}")
    window.withdraw()
    yield window
    window.destroy()


@pytest.fixture
def app(root: tk.Tk, small: NotationSet, tmp_path: Path) -> NotationApp:
    window = NotationApp(root, small, tmp_path / "notations.toml")
    window.prompts = ScriptedPrompts(root)
    return window


def prompts(app: NotationApp) -> ScriptedPrompts:
    assert isinstance(app.prompts, ScriptedPrompts)
    return app.prompts


def edit(app: NotationApp, **fields: str) -> None:
    """Type in the editor: the changes are not applied.

    ``symbol_latex`` is the field ``symbol:latex``, ``description_fr_typst`` the field
    ``description:fr:typst``.
    """
    for name, value in fields.items():
        app.fields[name.replace("_", ":")].set(value)


def tree_items(app: NotationApp, node: str = "") -> list[str]:
    """Return the tree nodes under ``node``, depth first."""
    found: list[str] = []
    for child in app.tree.get_children(node):
        found.append(child)
        found.extend(tree_items(app, child))
    return found


def tree_names(app: NotationApp) -> list[str]:
    """Return the entries of the tree, in order (styles aside)."""
    return [
        node.removeprefix("item:")
        for node in tree_items(app)
        if node.startswith("item:") and app.tree.parent(node) != "styles"
    ]


def test_starts_without_asking(root: tk.Tk, small: NotationSet) -> None:
    window = NotationApp(root, small)
    window.prompts = ScriptedPrompts(root)
    assert not window.form_modified
    assert window.current is None
    assert root.title() == "untitled — ANATOLE"
    assert tree_names(window) == ["time", "norm", "velocity", "density"]


def test_select_shows_the_notation(app: NotationApp, root: tk.Tk) -> None:
    app.tree.selection_set("item:density")
    root.update()
    assert app.current == "density"
    assert app.read_form() == ItemForm.from_item(app.notations["density"])


def test_apply_edits_and_renames(app: NotationApp, root: tk.Tk) -> None:
    app.show("density")
    edit(app, name="rho", description_en_typst="Mass density")
    assert app.form_modified
    assert app.apply()
    assert "density" not in app.notations
    assert app.notations["rho"].description["en"].typst == "Mass density"
    assert app.dirty
    assert root.title().startswith("*notations.toml")
    assert app.tree.selection() == ("item:rho",)


def test_apply_shows_the_problems(app: NotationApp) -> None:
    app.show("density")
    edit(app, symbol_latex=r"\rho{")
    assert not app.apply()
    assert "unbalanced braces" in app.problems.get()
    assert app.notations.notation("density").symbol.latex == r"\rho"
    assert not app.dirty


def test_new_notation(app: NotationApp) -> None:
    app.show("velocity")
    app.new_item()
    assert app.current is None
    assert app.read_form() == ItemForm(group="latin")
    edit(app, name="pressure", symbol_latex="p", symbol_typst="p")
    edit(app, description_en_latex="Pressure", description_fr_latex="Pression")
    assert app.apply()
    assert app.notations.notation("pressure").group == "latin"
    assert "pressure" in tree_names(app)


def test_unapplied_changes_are_settled(app: NotationApp, root: tk.Tk) -> None:
    app.show("velocity")
    edit(app, description_en_latex="Speed")
    prompts(app).save_answer = None  # cancel: stay on velocity
    app.tree.selection_set("item:time")
    root.update()
    assert app.current == "velocity"
    assert app.tree.selection() == ("item:velocity",)
    prompts(app).save_answer = True  # apply, then move
    app.tree.selection_set("item:time")
    root.update()
    assert app.current == "time"
    assert app.notations["velocity"].description["en"].latex == "Speed"
    app.show("time")
    edit(app, description_en_latex="Duration")
    prompts(app).save_answer = False  # discard
    app.new_item()
    assert app.notations["time"].description["en"].latex == "Time"


def test_duplicate(app: NotationApp) -> None:
    app.show("velocity")
    app.duplicate()
    assert app.current is None
    assert app.read_form().name == ""
    assert app.read_form().symbol == (r"\mathbf{u}", "bold(u)")
    edit(app, name="speed")
    assert app.apply()
    assert app.notations.notation("speed").symbol == app.notations.notation("velocity").symbol


def test_delete(app: NotationApp) -> None:
    app.show("time")
    prompts(app).confirm_answer = False
    app.delete()
    assert "time" in app.notations
    prompts(app).confirm_answer = True
    app.delete()
    assert "time" not in app.notations
    assert "time" not in tree_names(app)
    assert app.current is None


def test_search(app: NotationApp) -> None:
    app.search.set("rho")
    assert tree_names(app) == ["density"]
    app.search.set("")
    assert len(tree_names(app)) == 4


def test_save_open_export(app: NotationApp, tmp_path: Path) -> None:
    app.show("time")
    edit(app, description_en_latex="Duration")
    assert app.save()  # applies the editor first
    assert not app.dirty
    assert load(tmp_path / "notations.toml") == app.notations
    assert app.export("latex", tmp_path / "notations.tex")
    assert app.export("typst", tmp_path / "notations.typ")
    assert "Duration" in (tmp_path / "notations.tex").read_text(encoding="utf-8")
    app.new_file()
    assert len(app.notations) == 0
    assert app.open(tmp_path / "notations.toml")
    assert app.notations["time"].description["en"].latex == "Duration"


def test_save_as_and_errors(app: NotationApp, tmp_path: Path) -> None:
    app.path = None
    prompts(app).path = None  # cancelled
    assert not app.save()
    prompts(app).path = tmp_path / "other.toml"
    assert app.save()
    assert app.path == tmp_path / "other.toml"
    assert not app.open(tmp_path / "missing.toml")
    assert prompts(app).errors


def test_quit_asks_to_save(app: NotationApp, root: tk.Tk) -> None:
    app.show("time")
    edit(app, description_en_latex="Duration")
    prompts(app).save_answer = None
    app.quit()  # cancelled: the window stays
    assert root.winfo_exists()
    assert prompts(app).asked == ["Apply the changes to the item in the editor?"]


@pytest.mark.skipif(not preview.is_available(), reason="needs the typst package")
def test_preview(app: NotationApp) -> None:
    app.show("norm")
    app.update_preview()
    assert app.preview_image is not None
    edit(app, symbol_typst="lr(x")
    app.update_preview()
    assert app.preview_image is None
    assert "unclosed delimiter" in app.preview_label["text"]


def test_groups_dialog(app: NotationApp, root: tk.Tk) -> None:
    app.show("density")
    dialog = GroupsDialog(root, app.notations)

    def fill(form: GroupForm) -> None:
        for name, value in form.values(app.notations.languages).items():
            dialog.fields[name].set(value)

    fill(GroupForm("ops", {"en": ("Operators", ""), "fr": ("Opérateurs", "")}))
    assert dialog.apply()
    dialog.move(-5)
    assert [g.key for g in app.notations.groups] == ["ops", "latin", "greek"]
    dialog.show("greek")
    fill(GroupForm("grec", {"en": ("Greek", ""), "fr": ("Grec", "")}))
    assert dialog.apply()
    fill(GroupForm("bad key", {"fr": ("Mauvais", "")}))
    assert not dialog.apply()
    dialog.delete()  # used by density: refused
    assert "still used" in dialog.problems.get()
    dialog.show("ops")
    dialog.delete()
    dialog.window.destroy()
    app.groups_edited(dialog)
    assert [g.key for g in app.notations.groups] == ["latin", "grec"]
    assert app.read_form().group == "grec"
    assert app.dirty


def descriptions(app: NotationApp) -> list[str]:
    return [cast(str, app.tree.set(f"item:{name}", "description")) for name in tree_names(app)]


def test_display_language(app: NotationApp, tmp_path: Path) -> None:
    assert descriptions(app) == ["Time", "Norm", "Velocity", "Density"]
    app.language.set("fr")
    app.refresh_tree()
    assert descriptions(app) == ["Temps", "[en] Norm", "Vitesse", "[en] Density"]
    assert app.export("typst", tmp_path / "notations.typ")
    assert "[Vitesse]" in (tmp_path / "notations.typ").read_text(encoding="utf-8")


def test_translate(app: NotationApp) -> None:
    app.show("density")
    assert app.fields["description:fr:latex"].get() == ""
    edit(app, description_fr_latex="Masse volumique")
    assert app.apply()
    assert app.notations["density"].description == Translated(
        {"en": "Density", "fr": "Masse volumique"}
    )
    assert app.notations.missing_translations() == ["notation 'norm': description is missing in fr"]


def test_default_language_is_required(app: NotationApp) -> None:
    app.show("time")
    edit(app, description_en_latex="")
    assert not app.apply()
    assert "missing in the default language en" in app.problems.get()


def test_edit_languages(app: NotationApp) -> None:
    prompts(app).text = None  # cancelled
    app.edit_languages()
    assert prompts(app).asked == ["en, fr"]
    prompts(app).text = "en fr de"
    app.edit_languages()
    assert app.notations.languages == ("en", "fr", "de")
    assert "description:de:typst" in app.fields
    assert app.dirty
    prompts(app).text = "fr, en"  # density has no French description
    app.edit_languages()
    assert app.notations.languages == ("en", "fr", "de")
    assert "missing in the new default language fr" in prompts(app).errors[-1]
    prompts(app).text = "en"
    prompts(app).confirm_answer = False  # keep the French translations
    app.edit_languages()
    assert app.notations.languages == ("en", "fr", "de")
    prompts(app).confirm_answer = True
    app.edit_languages()
    assert app.notations.languages == ("en",)
    assert "description:fr:latex" not in app.fields
    assert app.notations["velocity"].description == Translated({"en": "Velocity"})
    assert cast(tuple[str, ...], app.language_box.cget("values")) == ("en",)


@pytest.fixture
def rich(root: tk.Tk, example: NotationSet, tmp_path: Path) -> NotationApp:
    window = NotationApp(root, example, tmp_path / "notations.toml")
    window.prompts = ScriptedPrompts(root)
    return window


def test_tree_of_groups_and_styles(rich: NotationApp) -> None:
    app = rich
    assert app.tree.get_children("styles") == ("item:vect",)
    assert app.tree.get_children("group:symbols") == (
        "group:symbols.latin",
        "group:symbols.greek",
        "group:symbols.subscripts",
    )
    assert app.tree.get_children("group:symbols.latin") == (
        "item:velocity",
        "item:pressure",
        "item:redelta",
    )
    assert cast(str, app.tree.set("item:wrt", "kind")) == "abbreviation"


def test_kind_shows_its_fields(rich: NotationApp, root: tk.Tk) -> None:
    app = rich
    root.deiconify()
    app.show("cfd")
    root.update()
    assert app.kind_box.instate(["disabled"])  # an existing item keeps its kind
    assert not app.symbol_label.winfo_ismapped()
    app.new_item("style")
    root.update()
    assert app.symbol_label.winfo_ismapped()
    assert app.symbol_label.cget("text") == "Template (#1)"
    assert app.kind_box.instate(["readonly", "!disabled"])


def test_new_acronym(rich: NotationApp) -> None:
    app = rich
    app.show("cfd")
    app.new_item()
    assert app.read_form().kind == "acronym"
    assert app.read_form().group == "acronyms"
    edit(app, name="dns", short_en_latex="DNS", long_en_latex="direct numerical simulation")
    assert app.apply()
    dns = app.notations.acronym("dns")
    assert (dns.short["en"].typst, dns.group) == ("DNS", "acronyms")
    assert "item:dns" in app.tree.get_children("group:acronyms")


def test_style_change_applies_to_every_vector(rich: NotationApp) -> None:
    app = rich
    app.show("vect")
    edit(app, symbol_latex=r"\vec{#1}", symbol_typst="arrow(#1)")
    assert app.apply()
    assert app.notations.style("vect").template == Rendered(r"\vec{#1}", "arrow(#1)")
    assert app.notations.notation("velocity").style == "vect"


def test_rename_carries_the_references(rich: NotationApp) -> None:
    app = rich
    app.show("blthickness")
    edit(app, name="delta")
    assert app.apply()
    assert app.notations.notation("redelta").symbol.latex == r"\mathit{Re}_{@{delta}}"


def test_delete_a_used_item_is_refused(rich: NotationApp) -> None:
    app = rich
    app.show("blthickness")
    app.delete()
    assert "used by 'redelta'" in prompts(app).errors[-1]
    assert "blthickness" in app.notations


def test_unknown_reference_is_a_problem(rich: NotationApp) -> None:
    app = rich
    app.show("pressure")
    edit(app, symbol_latex="@{nothing}")
    assert not app.apply()
    assert "refers to @{nothing}, which is not defined" in app.problems.get()


@pytest.mark.skipif(not preview.is_available(), reason="needs the typst package")
def test_preview_with_references(rich: NotationApp) -> None:
    app = rich
    for name in ("redelta", "velocity", "vect", "cfd"):
        app.show(name)
        app.update_preview()
        assert app.preview_image is not None, name


def test_export_target(rich: NotationApp, tmp_path: Path) -> None:
    app = rich
    app.target.set("glossaries")
    assert app.export("latex", tmp_path / "notations.tex")
    text = (tmp_path / "notations.tex").read_text(encoding="utf-8")
    assert r"\newglossaryentry{velocity}" in text


def test_groups_dialog_subsections(rich: NotationApp, root: tk.Tk) -> None:
    app = rich
    dialog = GroupsDialog(root, app.notations)

    def fill(form: GroupForm) -> None:
        for name, value in form.values(app.notations.languages).items():
            dialog.fields[name].set(value)

    fill(GroupForm("symbols.vectors", {"en": ("Vectors", ""), "fr": ("Vecteurs", "")}))
    assert dialog.apply()
    assert dialog.list.get_children("group:symbols")[-1] == "group:symbols.vectors"
    fill(GroupForm("operators.vectors", {"en": ("Vectors", "")}))
    assert not dialog.apply()  # a rename keeps the group in its section
    assert "keeps the group in its section" in dialog.problems.get()
    fill(GroupForm("a.b.c", {"en": ("Deep", "")}))
    dialog.new()
    fill(GroupForm("a.b.c", {"en": ("Deep", "")}))
    assert not dialog.apply()
    assert "at most 2 levels" in dialog.problems.get()
    dialog.window.destroy()
    app.groups_edited(dialog)
    assert app.tree.exists("group:symbols.vectors")


@pytest.mark.skipif(not office.is_available(), reason="needs pandoc (anatole[office])")
def test_export_to_word(rich: NotationApp, tmp_path: Path) -> None:
    app = rich
    assert app.export("docx", tmp_path / "notations.docx")
    assert (tmp_path / "notations.docx").exists()
    assert prompts(app).errors == []
    app.show("pressure")
    edit(app, units_latex=r"\si{\furlong}", units_typst="furlong")
    assert app.apply()
    assert app.export("docx", tmp_path / "other.docx")
    assert "pressure': Word: \\furlong is not converted" in prompts(app).errors[-1]
