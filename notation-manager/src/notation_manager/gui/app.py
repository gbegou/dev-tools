"""The main window: a searchable tree of notations, an editor, a Typst preview."""

import base64
import re
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import final

from notation_manager import preview
from notation_manager.export import export
from notation_manager.gui.form import NotationForm, description_key, matches
from notation_manager.gui.groups import GroupsDialog
from notation_manager.gui.prompts import FileTypes, Prompts
from notation_manager.io import load, save
from notation_manager.model import NotationError, NotationSet
from notation_manager.typing import FORMATS, Format

__all__ = ["NotationApp"]

NOTATION_FILES: FileTypes = [("Notation files", "*.toml"), ("All files", "*")]
EXPORT_FILES: dict[Format, FileTypes] = {
    "latex": [("LaTeX", "*.tex"), ("All files", "*")],
    "typst": [("Typst", "*.typ"), ("All files", "*")],
}
FORMAT_NAMES: dict[Format, str] = {"latex": "LaTeX", "typst": "Typst"}
NO_GROUP = "(no group)"
PREVIEW_DELAY_MS = 400
_ERROR_COLOR = "#b00020"
_DESCRIPTION_ROW = 8  # the first row of the descriptions in the editor grid
_BUTTONS_ROW = 100  # below the descriptions, however many languages there are


@final
class NotationApp:
    """The main window, built in ``root``.

    Parameters
    ----------
    root
        The Tk root window.
    notations
        The notations to show; an empty set by default.
    path
        The file the notations come from, where *Save* writes.

    Attributes
    ----------
    current
        The name of the notation in the editor; ``None`` for a new notation.
    dirty
        Whether the notations have changes that are not saved.
    fields
        The variables of the editor fields, by field name of
        :meth:`~notation_manager.gui.form.NotationForm.values`.
    language
        The variable of the language shown in the tree and the preview, and exported.
    search
        The variable of the search field.
    problems
        The variable of the problems shown under the editor.
    prompts
        The dialogs the window opens (tests replace them).
    """

    def __init__(
        self, root: tk.Tk, notations: NotationSet | None = None, path: Path | None = None
    ) -> None:
        self.root = root
        self.notations = notations if notations is not None else NotationSet()
        self.path = path
        self.dirty = False
        self.prompts = Prompts(root)
        self.current: str | None = None
        self._loaded: dict[str, str] = {}
        self.fields = {name: tk.StringVar(root) for name in NotationForm().values(())}
        self.language = tk.StringVar(root, value=self.notations.default_language)
        self.search = tk.StringVar(root)
        self._status = tk.StringVar(root)
        self.problems = tk.StringVar(root)
        self.preview_image: tk.PhotoImage | None = None
        self._preview_job: str | None = None
        self._description_widgets: list[tk.Widget] = []

        root.minsize(980, 560)
        root.protocol("WM_DELETE_WINDOW", self.quit)
        self._build_menu()
        top = ttk.Frame(root, padding=(8, 8, 8, 0))
        top.pack(fill="x")
        ttk.Label(top, text="Search").pack(side="left")
        self.search_entry = ttk.Entry(top, textvariable=self.search)
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(6, 12))
        ttk.Label(top, text="Language").pack(side="left")
        self.language_box = ttk.Combobox(top, textvariable=self.language, state="readonly", width=8)
        self.language_box.pack(side="left", padx=(6, 0))
        _ = self.language_box.bind("<<ComboboxSelected>>", lambda _event: self._language_changed())
        panes = ttk.PanedWindow(root, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=8, pady=8)
        tree_frame = ttk.Frame(panes)
        self.editor = ttk.Frame(panes, padding=(8, 0, 0, 0))
        # typeshed leaves the pane options untyped.
        panes.add(tree_frame, weight=1)  # pyright: ignore[reportUnknownMemberType]
        panes.add(self.editor, weight=1)  # pyright: ignore[reportUnknownMemberType]
        self.tree = self._build_tree(tree_frame)
        self.heading, self.name_entry, self.group_box, self.preview_label = self._build_editor(
            self.editor
        )
        ttk.Label(root, textvariable=self._status, anchor="w", padding=(8, 0, 8, 4)).pack(fill="x")

        for sequence, action in [
            ("<Control-s>", self.save),
            ("<Control-o>", self.open),
            ("<Control-n>", self.new_notation),
            ("<Control-Return>", self.apply),
            ("<Control-f>", self.search_entry.focus_set),
        ]:
            _ = root.bind(sequence, lambda _event, action=action: action())
        for var in self.fields.values():
            _ = var.trace_add("write", self._on_form_write)
        _ = self.search.trace_add("write", self._on_search_write)

        self._build_descriptions()
        self.write_form(NotationForm())
        self.refresh_tree()
        self._update_title()

    # Construction

    def _build_menu(self) -> None:
        menu = tk.Menu(self.root)
        file = tk.Menu(menu, tearoff=False)
        file.add_command(label="New file", command=self.new_file)
        file.add_command(label="Open…", accelerator="Ctrl+O", command=self.open)
        file.add_command(label="Save", accelerator="Ctrl+S", command=self.save)
        file.add_command(label="Save as…", command=self.save_as)
        file.add_separator()
        for fmt in FORMATS:
            file.add_command(
                label=f"Export to {FORMAT_NAMES[fmt]}…",
                command=lambda fmt=fmt: self.export(fmt),
            )
        file.add_separator()
        file.add_command(label="Quit", command=self.quit)
        menu.add_cascade(label="File", menu=file)

        edit = tk.Menu(menu, tearoff=False)
        edit.add_command(label="New notation", accelerator="Ctrl+N", command=self.new_notation)
        edit.add_command(label="Apply", accelerator="Ctrl+Enter", command=self.apply)
        edit.add_command(label="Duplicate notation", command=self.duplicate)
        edit.add_command(label="Delete notation", command=self.delete)
        edit.add_separator()
        edit.add_command(label="Groups…", command=self.edit_groups)
        edit.add_command(label="Languages…", command=self.edit_languages)
        menu.add_cascade(label="Edit", menu=edit)
        _ = self.root.configure(menu=menu)

    def _build_tree(self, frame: ttk.Frame) -> ttk.Treeview:
        tree = ttk.Treeview(frame, columns=("symbol", "description"), selectmode="browse")
        _ = tree.heading("#0", text="Name")
        _ = tree.heading("symbol", text="Symbol (LaTeX)")
        _ = tree.heading("description", text="Description")
        _ = tree.column("#0", width=160)
        _ = tree.column("symbol", width=140)
        _ = tree.column("description", width=220)

        def scroll_tree(action: str, amount: str, unit: str = "units") -> None:
            if action == "moveto":
                tree.yview_moveto(float(amount))
            else:
                tree.yview_scroll(int(amount), "pages" if unit == "pages" else "units")

        scroll = ttk.Scrollbar(frame, orient="vertical", command=scroll_tree)
        _ = tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        _ = tree.bind("<<TreeviewSelect>>", lambda _event: self._on_select())
        _ = tree.bind("<Delete>", lambda _event: self.delete())
        return tree

    def _build_editor(
        self, frame: ttk.Frame
    ) -> tuple[ttk.Label, ttk.Entry, ttk.Combobox, ttk.Label]:
        _ = frame.columnconfigure((1, 2), weight=1)
        heading = ttk.Label(frame, font="TkHeadingFont")
        heading.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))

        def label(row: int, text: str) -> None:
            ttk.Label(frame, text=text).grid(row=row, column=0, sticky="w", pady=2)

        label(1, "Name")
        name_entry = ttk.Entry(frame, textvariable=self.fields["name"])
        name_entry.grid(row=1, column=1, columnspan=2, sticky="ew", pady=2, padx=2)
        label(2, "Group")
        group_box = ttk.Combobox(frame, textvariable=self.fields["group"], state="readonly")
        group_box.grid(row=2, column=1, columnspan=2, sticky="ew", pady=2, padx=2)
        label(3, "Arguments")
        ttk.Spinbox(frame, from_=0, to=9, width=4, textvariable=self.fields["arguments"]).grid(
            row=3, column=1, sticky="w", pady=2, padx=2
        )
        label(4, "Sort key")
        ttk.Entry(frame, textvariable=self.fields["sort"]).grid(
            row=4, column=1, columnspan=2, sticky="ew", pady=2, padx=2
        )

        ttk.Label(frame, text="LaTeX", font="TkHeadingFont").grid(
            row=5, column=1, sticky="w", pady=(10, 2), padx=2
        )
        ttk.Label(frame, text="Typst (empty: as LaTeX)", font="TkHeadingFont").grid(
            row=5, column=2, sticky="w", pady=(10, 2), padx=2
        )
        for row, (text, field) in enumerate([("Symbol", "symbol"), ("Units", "units")], start=6):
            label(row, text)
            for column, fmt in enumerate(FORMATS, start=1):
                ttk.Entry(frame, textvariable=self.fields[f"{field}:{fmt}"]).grid(
                    row=row, column=column, sticky="ew", pady=2, padx=2
                )

        buttons = ttk.Frame(frame)
        buttons.grid(row=_BUTTONS_ROW, column=0, columnspan=3, sticky="ew", pady=(10, 4))
        for text, command in [
            ("Apply", self.apply),
            ("Revert", self.revert),
            ("New", self.new_notation),
            ("Duplicate", self.duplicate),
            ("Delete", self.delete),
        ]:
            ttk.Button(buttons, text=text, command=command).pack(side="left", padx=(0, 4))

        ttk.Label(frame, textvariable=self.problems, foreground=_ERROR_COLOR, justify="left").grid(
            row=_BUTTONS_ROW + 1, column=0, columnspan=3, sticky="w"
        )
        preview_frame = ttk.LabelFrame(frame, text="Preview (Typst)", padding=6)
        preview_frame.grid(row=_BUTTONS_ROW + 2, column=0, columnspan=3, sticky="nsew", pady=6)
        _ = frame.rowconfigure(_BUTTONS_ROW + 2, weight=1)
        preview_label = ttk.Label(preview_frame, anchor="nw", justify="left", wraplength=420)
        preview_label.pack(fill="both", expand=True)
        return heading, name_entry, group_box, preview_label

    def _build_descriptions(self) -> None:
        """(Re)build the description rows of the editor: one per language."""
        for widget in self._description_widgets:
            widget.destroy()
        self._description_widgets = []
        for name in [name for name in self.fields if name.startswith("description:")]:
            del self.fields[name]
        for row, language in enumerate(self.notations.languages, start=_DESCRIPTION_ROW):
            default = " — default" if language == self.notations.default_language else ""
            label = ttk.Label(self.editor, text=f"Description ({language}{default})")
            label.grid(row=row, column=0, sticky="w", pady=2)
            self._description_widgets.append(label)
            for column, fmt in enumerate(FORMATS, start=1):
                var = tk.StringVar(self.root)
                _ = var.trace_add("write", self._on_form_write)
                self.fields[description_key(language, fmt)] = var
                entry = ttk.Entry(self.editor, textvariable=var)
                entry.grid(row=row, column=column, sticky="ew", pady=2, padx=2)
                self._description_widgets.append(entry)
        languages = self.notations.languages
        _ = self.language_box.configure(values=list(languages))
        if self.language.get() not in languages:
            self.language.set(self.notations.default_language)

    # State

    def _values(self) -> dict[str, str]:
        return {name: var.get() for name, var in self.fields.items()}

    def read_form(self) -> NotationForm:
        """Return the content of the editor."""
        return NotationForm.from_values(self._values())

    def write_form(self, form: NotationForm) -> None:
        """Show ``form`` in the editor, as its unmodified state."""
        values = form.values(self.notations.languages)
        for name, value in values.items():
            self.fields[name].set(value)
        self._loaded = values
        self.problems.set("")
        title = f"Notation \\{self.current}" if self.current else "New notation"
        _ = self.heading.configure(text=title)

    @property
    def form_modified(self) -> bool:
        """Whether the editor holds changes that are not applied."""
        return self._values() != self._loaded

    def _set_dirty(self, dirty: bool) -> None:
        self.dirty = dirty
        self._update_title()

    def _update_title(self) -> None:
        name = self.path.name if self.path else "untitled"
        self.root.title(f"{'*' if self.dirty else ''}{name} — Notation manager")

    def _on_form_write(self, _name: str, _index: str, _mode: str) -> None:
        if self._preview_job is not None:
            self.root.after_cancel(self._preview_job)
        self._preview_job = self.root.after(PREVIEW_DELAY_MS, self.update_preview)

    def _on_search_write(self, _name: str, _index: str, _mode: str) -> None:
        self.refresh_tree()

    def _language_changed(self) -> None:
        self.refresh_tree()
        self.update_preview()

    def _settle_form(self) -> bool:
        """Settle the changes in the editor before it shows something else.

        Apply them or discard them, as asked; return ``False`` when cancelled (or when they
        cannot be applied).
        """
        if not self.form_modified:
            return True
        answer = self.prompts.ask_save("Apply the changes to the notation in the editor?")
        if answer is None:
            return False
        return self.apply() if answer else True

    def _settle_file(self) -> bool:
        """Settle the unsaved changes before the file is closed.

        Save them or discard them, as asked; return ``False`` when cancelled.
        """
        if not self._settle_form():
            return False
        if not self.dirty:
            return True
        answer = self.prompts.ask_save("Save the changes to the notation file?")
        if answer is None:
            return False
        return self.save() if answer else True

    # Tree

    def refresh_tree(self, select: str | None = None) -> None:
        """Rebuild the tree from the notations, filtered by the search.

        The descriptions are shown in the selected language, or in the default one (marked)
        when they have no translation in it. Select the notation ``select``, the one in the
        editor by default.
        """
        select = select if select is not None else self.current
        language, default = self.language.get(), self.notations.default_language
        _ = self.tree.heading("description", text=f"Description ({language})")
        self.tree.delete(*self.tree.get_children())
        query = self.search.get()
        shown = [notation for notation in self.notations if matches(notation, query)]
        sections = [("", NO_GROUP), *((group.key, group.key) for group in self.notations.groups)]
        for key, text in sections:
            members = [notation for notation in shown if notation.group == key]
            if not members and (query or not key):
                continue
            parent = self.tree.insert("", "end", iid=f"group:{key}", text=text, open=True)
            for notation in members:
                description = notation.description.resolve(language, default).latex
                if language not in notation.description:
                    description = f"[{default}] {description}"
                _ = self.tree.insert(
                    parent,
                    "end",
                    iid=f"notation:{notation.name}",
                    text=notation.name,
                    values=(notation.symbol.latex, description),
                )
        _ = self.group_box.configure(values=["", *(group.key for group in self.notations.groups)])
        item = f"notation:{select}"
        if select and self.tree.exists(item):
            self.tree.selection_set(item)
            self.tree.see(item)
        else:
            self.tree.selection_set(())
        missing = len(self.notations.missing_translations())
        self._status.set(
            f"{len(shown)} of {len(self.notations)} notations"
            + (f", {missing} missing translations" if missing else "")
        )

    def _on_select(self) -> None:
        selection = self.tree.selection()
        if not selection or not selection[0].startswith("notation:"):
            return
        name = selection[0].removeprefix("notation:")
        if name == self.current:
            return
        if not self._settle_form():
            self.refresh_tree()  # back to the notation in the editor
            return
        self.show(name)
        # Applying the changes selected the previous notation again: select the new one.
        self.tree.selection_set(selection[0])

    def show(self, name: str) -> None:
        """Show the notation ``name`` in the editor (unapplied changes are lost)."""
        self.current = name
        self.write_form(NotationForm.from_notation(self.notations[name]))

    # Notation actions

    def apply(self) -> bool:
        """Apply the editor to the notation set.

        Replace the notation in the editor, or add a new one. Return whether it succeeded;
        the problems are shown in the editor otherwise.
        """
        try:
            notation = self.read_form().to_notation()
            if self.current is None:
                self.notations.add(notation)
            else:
                self.notations.replace(self.current, notation)
        except NotationError as error:
            self.problems.set("\n".join(error.problems))
            self.root.bell()
            return False
        self.current = notation.name
        self.write_form(NotationForm.from_notation(notation))
        self._set_dirty(True)
        self.refresh_tree()
        self._status.set(f"Applied \\{notation.name}")
        return True

    def revert(self) -> None:
        """Discard the changes in the editor."""
        self.write_form(NotationForm.from_values(self._loaded))

    def new_notation(self) -> None:
        """Clear the editor for a new notation, in the group of the current one."""
        if not self._settle_form():
            return
        group = self._loaded.get("group", "")
        self.current = None
        self.tree.selection_set(())
        self.write_form(NotationForm(group=group))
        self.name_entry.focus_set()

    def duplicate(self) -> None:
        """Start a new notation from the one in the editor; it needs a new name."""
        if not self._settle_form():
            return
        values = dict(self._loaded)
        self.current = None
        self.tree.selection_set(())
        self.write_form(NotationForm())
        for name, value in values.items():
            self.fields[name].set("" if name == "name" else value)
        self.name_entry.focus_set()
        self._status.set("Duplicate: give it a new name, then apply")

    def delete(self) -> None:
        """Delete the notation in the editor, after confirmation."""
        if self.current is None:
            return
        if not self.prompts.confirm(f"Delete the notation \\{self.current}?"):
            return
        _ = self.notations.remove(self.current)
        self.current = None
        self._set_dirty(True)
        self.write_form(NotationForm(group=self._loaded.get("group", "")))
        self.refresh_tree()

    def edit_groups(self) -> None:
        """Open the group editor, and wait until it is closed."""
        dialog = GroupsDialog(self.root, self.notations)
        self.root.wait_window(dialog.window)
        self.groups_edited(dialog)

    def groups_edited(self, dialog: GroupsDialog) -> None:
        """Update the window after the group editor ``dialog`` is closed."""
        if not dialog.changed:
            return
        self._set_dirty(True)
        if self.current is not None:
            self.show(self.current)  # the group key may have changed
        self.refresh_tree()

    def edit_languages(self) -> None:
        """Ask for the languages (the default one first), and change them.

        Dropping the translations of the languages removed is confirmed first.
        """
        if not self._settle_form():
            return
        answer = self.prompts.ask_text(
            "Languages",
            "Language codes (en, fr, de, pt-BR...), the default one first:",
            ", ".join(self.notations.languages),
        )
        if answer is None:
            return
        languages = tuple(code for code in re.split(r"[\s,;]+", answer) if code)
        removed = [code for code in self.notations.languages if code not in languages]
        texts = [
            *(notation.description for notation in self.notations),
            *(group.title for group in self.notations.groups),
        ]
        dropped = sum(code in text for code in removed for text in texts)
        if dropped and not self.prompts.confirm(
            f"Drop the {dropped} translations in {', '.join(removed)}?"
        ):
            return
        try:
            self.notations.set_languages(languages)
        except NotationError as error:
            self.prompts.error(str(error))
            return
        self._set_dirty(True)
        self._build_descriptions()
        if self.current is not None:
            self.show(self.current)
        else:
            self.write_form(NotationForm.from_values(self._loaded))
        self.refresh_tree()

    def update_preview(self) -> None:
        """Render the notation in the editor with Typst, in the selected language.

        Show why it cannot be rendered otherwise.
        """
        self._preview_job = None
        self.preview_image = None
        if not preview.is_available():
            _ = self.preview_label.configure(
                image="",
                text="Install the typst package for a preview: "
                + "pip install 'notation-manager[preview]'",
            )
            return
        try:
            png = preview.render(self.read_form().to_notation(), self.language.get())
        except (NotationError, preview.PreviewError) as error:
            _ = self.preview_label.configure(image="", text=str(error))
            return
        self.preview_image = tk.PhotoImage(master=self.root, data=base64.b64encode(png).decode())
        _ = self.preview_label.configure(image=self.preview_image, text="")

    # File actions

    def new_file(self) -> None:
        """Start an empty notation set, in the languages of the current one."""
        if self._settle_file():
            self._replace_set(NotationSet(languages=self.notations.languages), None)

    def open(self, path: Path | None = None) -> bool:
        """Open a notation file (asked for when ``path`` is ``None``)."""
        if not self._settle_file():
            return False
        path = path or self.prompts.open_path(NOTATION_FILES)
        if path is None:
            return False
        try:
            notations = load(path)
        except (OSError, NotationError) as error:
            self.prompts.error(str(error))
            return False
        self._replace_set(notations, path)
        return True

    def _replace_set(self, notations: NotationSet, path: Path | None) -> None:
        self.notations = notations
        self.path = path
        self.current = None
        self._set_dirty(False)
        self._build_descriptions()
        self.write_form(NotationForm())
        self.refresh_tree()

    def save(self) -> bool:
        """Save to the current file (asked for when there is none); return whether it saved."""
        if not self._settle_form():
            return False
        if self.path is None:
            return self.save_as()
        try:
            save(self.notations, self.path)
        except OSError as error:
            self.prompts.error(str(error))
            return False
        self._set_dirty(False)
        self._status.set(f"Saved {self.path}")
        return True

    def save_as(self) -> bool:
        """Save to a file asked for; return whether it saved."""
        path = self.prompts.save_path(NOTATION_FILES, ".toml")
        if path is None:
            return False
        self.path = path
        return self.save()

    def export(self, fmt: Format, path: Path | None = None) -> bool:
        """Export to the format ``fmt``, in the selected language.

        Write to ``path``, asked for when ``None``; return whether it exported.
        """
        if not self._settle_form():
            return False
        suffix = ".tex" if fmt == "latex" else ".typ"
        path = path or self.prompts.save_path(EXPORT_FILES[fmt], suffix)
        if path is None:
            return False
        source = self.path.name if self.path else None
        language = self.language.get()
        try:
            export(self.notations, path, fmt, language=language, source=source)
        except (OSError, NotationError) as error:
            self.prompts.error(str(error))
            return False
        self._status.set(f"Exported to {path} ({language})")
        return True

    def quit(self) -> None:
        """Close the window, after settling the unsaved changes."""
        if self._settle_file():
            self.root.destroy()
