"""The graphical interface, driven without a user (needs a display, e.g. ``xvfb-run``)."""

from collections.abc import Iterator
from pathlib import Path
from typing import final, override

import pytest

from notation_manager import NotationSet, load, preview

try:
    import tkinter as tk
except ModuleNotFoundError:  # Python built without Tk
    pytest.skip("needs tkinter", allow_module_level=True)

from notation_manager.gui.app import NotationApp
from notation_manager.gui.form import GroupForm, NotationForm
from notation_manager.gui.groups import GroupsDialog
from notation_manager.gui.prompts import FileTypes, Prompts


@final
class ScriptedPrompts(Prompts):
    """Prompts that answer from a script and record what they were asked."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.save_answer: bool | None = True
        self.confirm_answer = True
        self.path: Path | None = None
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
    """Type in the editor: the changes are not applied."""
    for name, value in fields.items():
        app.fields[name].set(value)


def tree_names(app: NotationApp) -> list[str]:
    return [
        child.removeprefix("notation:")
        for group in app.tree.get_children()
        for child in app.tree.get_children(group)
    ]


def test_starts_without_asking(root: tk.Tk, small: NotationSet) -> None:
    window = NotationApp(root, small)
    window.prompts = ScriptedPrompts(root)
    assert not window.form_modified
    assert window.current is None
    assert root.title() == "untitled — Notation manager"
    assert tree_names(window) == ["time", "norm", "velocity", "density"]


def test_select_shows_the_notation(app: NotationApp, root: tk.Tk) -> None:
    app.tree.selection_set("notation:density")
    root.update()
    assert app.current == "density"
    assert app.read_form() == NotationForm.from_notation(app.notations["density"])


def test_apply_edits_and_renames(app: NotationApp, root: tk.Tk) -> None:
    app.show("density")
    edit(app, name="rho", description_typst="Mass density")
    assert app.form_modified
    assert app.apply()
    assert "density" not in app.notations
    assert app.notations["rho"].description.typst == "Mass density"
    assert app.dirty
    assert root.title().startswith("*notations.toml")
    assert app.tree.selection() == ("notation:rho",)


def test_apply_shows_the_problems(app: NotationApp) -> None:
    app.show("density")
    edit(app, symbol_latex=r"\rho{")
    assert not app.apply()
    assert "unbalanced braces" in app.problems.get()
    assert app.notations["density"].symbol.latex == r"\rho"
    assert not app.dirty


def test_new_notation(app: NotationApp) -> None:
    app.show("velocity")
    app.new_notation()
    assert app.current is None
    assert app.read_form() == NotationForm(group="latin")
    edit(app, name="pressure", symbol_latex="p", symbol_typst="p")
    edit(app, description_latex="Pressure", description_typst="Pressure")
    assert app.apply()
    assert app.notations["pressure"].group == "latin"
    assert "pressure" in tree_names(app)


def test_unapplied_changes_are_settled(app: NotationApp, root: tk.Tk) -> None:
    app.show("velocity")
    edit(app, description_latex="Speed")
    prompts(app).save_answer = None  # cancel: stay on velocity
    app.tree.selection_set("notation:time")
    root.update()
    assert app.current == "velocity"
    assert app.tree.selection() == ("notation:velocity",)
    prompts(app).save_answer = True  # apply, then move
    app.tree.selection_set("notation:time")
    root.update()
    assert app.current == "time"
    assert app.notations["velocity"].description.latex == "Speed"
    app.show("time")
    edit(app, description_latex="Duration")
    prompts(app).save_answer = False  # discard
    app.new_notation()
    assert app.notations["time"].description.latex == "Time"


def test_duplicate(app: NotationApp) -> None:
    app.show("velocity")
    app.duplicate()
    assert app.current is None
    assert app.read_form().name == ""
    assert app.read_form().symbol_typst == "bold(u)"
    edit(app, name="speed")
    assert app.apply()
    assert app.notations["speed"].symbol == app.notations["velocity"].symbol


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
    edit(app, description_latex="Duration", description_typst="Duration")
    assert app.save()  # applies the editor first
    assert not app.dirty
    assert load(tmp_path / "notations.toml") == app.notations
    assert app.export("latex", tmp_path / "notations.tex")
    assert app.export("typst", tmp_path / "notations.typ")
    assert "Duration" in (tmp_path / "notations.tex").read_text(encoding="utf-8")
    app.new_file()
    assert len(app.notations) == 0
    assert app.open(tmp_path / "notations.toml")
    assert app.notations["time"].description.latex == "Duration"


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
    edit(app, description_latex="Duration")
    prompts(app).save_answer = None
    app.quit()  # cancelled: the window stays
    assert root.winfo_exists()
    assert prompts(app).asked == ["Apply the changes to the notation in the editor?"]


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
        for name, value in form.values().items():
            dialog.fields[name].set(value)

    fill(GroupForm("ops", "Operators", "Operators"))
    assert dialog.apply()
    dialog.move(-5)
    assert [g.key for g in app.notations.groups] == ["ops", "latin", "greek"]
    dialog.show("greek")
    fill(GroupForm("grec", "Grec", "Grec"))
    assert dialog.apply()
    fill(GroupForm("bad key", "", ""))
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
