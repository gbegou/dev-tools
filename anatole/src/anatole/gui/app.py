"""The main window: a searchable tree of entries and styles, an editor, a Typst preview."""

import base64
import re
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import final

from anatole import preview
from anatole.export import TARGETS, Target, export
from anatole.gui.form import KINDS, ItemForm, Kind, kind_of, language_key, matches
from anatole.gui.groups import GroupsDialog
from anatole.gui.prompts import FileTypes, Prompts
from anatole.io import load, save
from anatole.model import Acronym, Item, Notation, NotationError, NotationSet, Style, Translated
from anatole.typing import FORMATS, Format

__all__ = ["NotationApp"]

NOTATION_FILES: FileTypes = [("Notation files", "*.toml"), ("All files", "*")]
EXPORT_FILES: dict[Format, FileTypes] = {
    "latex": [("LaTeX", "*.tex"), ("All files", "*")],
    "typst": [("Typst", "*.typ"), ("All files", "*")],
}
NO_GROUP = "(no group)"
STYLES = "Styles"
PREVIEW_DELAY_MS = 400
_ERROR_COLOR = "#b00020"
_LANGUAGE_ROW = 20  # the first row of the texts per language in the editor grid
_BUTTONS_ROW = 200  # below them, however many languages there are

# The fields each kind shows (the texts per language aside).
_FIELDS: dict[Kind, tuple[str, ...]] = {
    "notation": ("group", "arguments", "style", "sort", "tags", "symbol", "units"),
    "acronym": ("group", "sort", "tags"),
    "abbreviation": ("group", "sort", "tags"),
    "style": ("symbol",),
}
_LANGUAGE_FIELDS: dict[Kind, tuple[str, ...]] = {
    "notation": ("description",),
    "acronym": ("short", "long", "description"),
    "abbreviation": ("short", "long", "description"),
    "style": ("description",),
}
_LABELS = {"description": "Description", "short": "Short form", "long": "Long form"}


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
        The name of the item in the editor; ``None`` for a new item.
    dirty
        Whether the notations have changes that are not saved.
    fields
        The variables of the editor fields, by field name of
        :meth:`~anatole.gui.form.ItemForm.values`.
    language
        The variable of the language shown in the tree and the preview, and exported.
    target
        The variable of the LaTeX target of the exports.
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
        self.fields = {name: tk.StringVar(root) for name in ItemForm().values(())}
        self.language = tk.StringVar(root, value=self.notations.default_language)
        self.target = tk.StringVar(root, value=TARGETS[0])
        self.search = tk.StringVar(root)
        self._status = tk.StringVar(root)
        self.problems = tk.StringVar(root)
        self.preview_image: tk.PhotoImage | None = None
        self._preview_job: str | None = None
        self._rows: dict[str, list[tk.Widget]] = {}
        self._language_rows: list[tuple[str, list[tk.Widget]]] = []

        root.minsize(1000, 600)
        root.protocol("WM_DELETE_WINDOW", self.quit)
        self._build_menu()
        top = ttk.Frame(root, padding=(8, 8, 8, 0))
        top.pack(fill="x")
        ttk.Label(top, text="Search").pack(side="left")
        self.search_entry = ttk.Entry(top, textvariable=self.search)
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(6, 12))
        ttk.Label(top, text="Language").pack(side="left")
        self.language_box = ttk.Combobox(top, textvariable=self.language, state="readonly", width=8)
        self.language_box.pack(side="left", padx=(6, 12))
        _ = self.language_box.bind("<<ComboboxSelected>>", lambda _event: self._language_changed())
        ttk.Label(top, text="LaTeX lists").pack(side="left")
        ttk.Combobox(
            top, textvariable=self.target, values=list(TARGETS), state="readonly", width=13
        ).pack(side="left", padx=(6, 0))
        panes = ttk.PanedWindow(root, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=8, pady=8)
        tree_frame = ttk.Frame(panes)
        self.editor = ttk.Frame(panes, padding=(8, 0, 0, 0))
        # typeshed leaves the pane options untyped.
        panes.add(tree_frame, weight=1)  # pyright: ignore[reportUnknownMemberType]
        panes.add(self.editor, weight=1)  # pyright: ignore[reportUnknownMemberType]
        self.tree = self._build_tree(tree_frame)
        (
            self.heading,
            self.kind_box,
            self.name_entry,
            self.symbol_label,
            self.preview_label,
        ) = self._build_editor(self.editor)
        self.group_box = self._combobox("group")
        self.style_box = self._combobox("style")
        ttk.Label(root, textvariable=self._status, anchor="w", padding=(8, 0, 8, 4)).pack(fill="x")

        for sequence, action in [
            ("<Control-s>", self.save),
            ("<Control-o>", self.open),
            ("<Control-n>", self.new_item),
            ("<Control-Return>", self.apply),
            ("<Control-f>", self.search_entry.focus_set),
        ]:
            _ = root.bind(sequence, lambda _event, action=action: action())
        for var in self.fields.values():
            _ = var.trace_add("write", self._on_form_write)
        _ = self.fields["kind"].trace_add("write", self._on_kind_write)
        _ = self.search.trace_add("write", self._on_search_write)

        self._build_languages()
        self.write_form(ItemForm())
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
        file.add_command(label="Export to LaTeX…", command=lambda: self.export("latex"))
        file.add_command(label="Export to Typst…", command=lambda: self.export("typst"))
        file.add_separator()
        file.add_command(label="Quit", command=self.quit)
        menu.add_cascade(label="File", menu=file)

        edit = tk.Menu(menu, tearoff=False)
        edit.add_command(label="New item", accelerator="Ctrl+N", command=self.new_item)
        edit.add_command(label="Apply", accelerator="Ctrl+Enter", command=self.apply)
        edit.add_command(label="Duplicate", command=self.duplicate)
        edit.add_command(label="Delete", command=self.delete)
        edit.add_separator()
        edit.add_command(label="Groups…", command=self.edit_groups)
        edit.add_command(label="Languages…", command=self.edit_languages)
        menu.add_cascade(label="Edit", menu=edit)
        _ = self.root.configure(menu=menu)

    def _build_tree(self, frame: ttk.Frame) -> ttk.Treeview:
        tree = ttk.Treeview(frame, columns=("kind", "symbol", "description"), selectmode="browse")
        _ = tree.heading("#0", text="Name")
        _ = tree.heading("kind", text="Kind")
        _ = tree.heading("symbol", text="Symbol / short form")
        _ = tree.heading("description", text="Description")
        _ = tree.column("#0", width=170)
        _ = tree.column("kind", width=90)
        _ = tree.column("symbol", width=150)
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

    def _row(self, name: str, row: int, text: str, *widgets: tk.Widget) -> ttk.Label:
        """Place a labelled row of the editor; ``_show_kind`` shows or hides it."""
        label = ttk.Label(self.editor, text=text)
        label.grid(row=row, column=0, sticky="w", pady=2)
        for column, widget in enumerate(widgets, start=1):
            span = 3 - len(widgets)
            widget.grid(row=row, column=column, columnspan=span, sticky="ew", pady=2, padx=2)
        self._rows[name] = [label, *widgets]
        return label

    def _entry(self, name: str) -> ttk.Entry:
        return ttk.Entry(self.editor, textvariable=self.fields[name])

    def _combobox(self, name: str) -> ttk.Combobox:
        widget = self._rows[name][1]
        assert isinstance(widget, ttk.Combobox)
        return widget

    def _build_editor(
        self, frame: ttk.Frame
    ) -> tuple[ttk.Label, ttk.Combobox, ttk.Entry, ttk.Label, ttk.Label]:
        _ = frame.columnconfigure((1, 2), weight=1)
        heading = ttk.Label(frame, font="TkHeadingFont")
        heading.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
        kind_box = ttk.Combobox(
            frame, textvariable=self.fields["kind"], values=list(KINDS), state="readonly"
        )
        _ = self._row("kind", 1, "Kind", kind_box)
        name_entry = self._entry("name")
        _ = self._row("name", 2, "Name", name_entry)
        _ = self._row(
            "group",
            3,
            "Group",
            ttk.Combobox(frame, textvariable=self.fields["group"], state="readonly"),
        )
        _ = self._row(
            "arguments",
            4,
            "Arguments",
            ttk.Spinbox(frame, from_=0, to=9, width=4, textvariable=self.fields["arguments"]),
        )
        _ = self._row(
            "style",
            5,
            "Style",
            ttk.Combobox(frame, textvariable=self.fields["style"], state="readonly"),
        )
        _ = self._row("sort", 6, "Sort key", self._entry("sort"))
        _ = self._row("tags", 7, "Tags", self._entry("tags"))
        header = [
            ttk.Label(frame, text="LaTeX", font="TkHeadingFont"),
            ttk.Label(frame, text="Typst (empty: as LaTeX)", font="TkHeadingFont"),
        ]
        for column, label in enumerate(header, start=1):
            label.grid(row=8, column=column, sticky="w", pady=(10, 2), padx=2)
        symbol_label = self._row(
            "symbol", 9, "Symbol", self._entry("symbol:latex"), self._entry("symbol:typst")
        )
        _ = self._row("units", 10, "Units", self._entry("units:latex"), self._entry("units:typst"))

        buttons = ttk.Frame(frame)
        buttons.grid(row=_BUTTONS_ROW, column=0, columnspan=3, sticky="ew", pady=(10, 4))
        for text, command in [
            ("Apply", self.apply),
            ("Revert", self.revert),
            ("New", self.new_item),
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
        preview_label = ttk.Label(preview_frame, anchor="nw", justify="left", wraplength=440)
        preview_label.pack(fill="both", expand=True)
        return heading, kind_box, name_entry, symbol_label, preview_label

    def _build_languages(self) -> None:
        """(Re)build the rows of the texts per language: one per field and language."""
        for _, widgets in self._language_rows:
            for widget in widgets:
                widget.destroy()
        self._language_rows = []
        for name in [name for name in self.fields if name.count(":") == 2]:
            del self.fields[name]
        row = _LANGUAGE_ROW
        for field_name in ("short", "long", "description"):
            for language in self.notations.languages:
                default = ", default" if language == self.notations.default_language else ""
                label = ttk.Label(self.editor, text=f"{_LABELS[field_name]} ({language}{default})")
                label.grid(row=row, column=0, sticky="w", pady=2)
                widgets: list[tk.Widget] = [label]
                for column, fmt in enumerate(FORMATS, start=1):
                    var = tk.StringVar(self.root)
                    _ = var.trace_add("write", self._on_form_write)
                    self.fields[language_key(field_name, language, fmt)] = var
                    entry = ttk.Entry(self.editor, textvariable=var)
                    entry.grid(row=row, column=column, sticky="ew", pady=2, padx=2)
                    widgets.append(entry)
                self._language_rows.append((field_name, widgets))
                row += 1
        languages = self.notations.languages
        _ = self.language_box.configure(values=list(languages))
        if self.language.get() not in languages:
            self.language.set(self.notations.default_language)
        self._show_kind()

    def _show_kind(self) -> None:
        """Show the rows of the kind in the editor, hide the others."""
        kind = self._kind()
        shown = {"kind", "name", *_FIELDS[kind]}
        for name, widgets in self._rows.items():
            for widget in widgets:
                if name in shown:
                    widget.grid()
                else:
                    widget.grid_remove()
        _ = self.symbol_label.configure(text="Template (#1)" if kind == "style" else "Symbol")
        for field_name, widgets in self._language_rows:
            for widget in widgets:
                if field_name in _LANGUAGE_FIELDS[kind]:
                    widget.grid()
                else:
                    widget.grid_remove()

    def _kind(self) -> Kind:
        kind = self.fields["kind"].get()
        return kind if kind in KINDS else "notation"

    # State

    def _values(self) -> dict[str, str]:
        return {name: var.get() for name, var in self.fields.items()}

    def read_form(self) -> ItemForm:
        """Return the content of the editor."""
        return ItemForm.from_values(self._values())

    def write_form(self, form: ItemForm) -> None:
        """Show ``form`` in the editor, as its unmodified state."""
        values = form.values(self.notations.languages)
        for name, value in values.items():
            self.fields[name].set(value)
        self._loaded = values
        self.problems.set("")
        title = f"{form.kind.capitalize()} {self.current}" if self.current else "New item"
        _ = self.heading.configure(text=title)
        # The kind of an existing item is fixed: an entry does not become a style.
        _ = self.kind_box.configure(state="disabled" if self.current else "readonly")

    @property
    def form_modified(self) -> bool:
        """Whether the editor holds changes that are not applied."""
        return self._values() != self._loaded

    def _set_dirty(self, dirty: bool) -> None:
        self.dirty = dirty
        self._update_title()

    def _update_title(self) -> None:
        name = self.path.name if self.path else "untitled"
        self.root.title(f"{'*' if self.dirty else ''}{name} — ANATOLE")

    def _on_form_write(self, _name: str, _index: str, _mode: str) -> None:
        if self._preview_job is not None:
            self.root.after_cancel(self._preview_job)
        self._preview_job = self.root.after(PREVIEW_DELAY_MS, self.update_preview)

    def _on_kind_write(self, _name: str, _index: str, _mode: str) -> None:
        self._show_kind()

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
        answer = self.prompts.ask_save("Apply the changes to the item in the editor?")
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

    def _summary(self, item: Item) -> tuple[str, str]:
        """Return the symbol (or short form) and description of ``item``.

        They are in the selected language; a text in the default language is marked when it
        has no translation.
        """
        language, default = self.language.get(), self.notations.default_language

        def text(value: Translated) -> str:
            if not len(value):
                return ""
            shown = value.resolve(language, default).latex
            return shown if language in value else f"[{default}] {shown}"

        match item:
            case Style():
                return item.template.latex, text(item.description)
            case Notation():
                return item.symbol.latex, text(item.description)
            case _:
                return text(item.short), text(item.long)

    def _insert(self, parent: str, item: Item) -> None:
        symbol, description = self._summary(item)
        _ = self.tree.insert(
            parent,
            "end",
            iid=f"item:{item.name}",
            text=item.name,
            values=(kind_of(item), symbol, description),
        )

    def refresh_tree(self, select: str | None = None) -> None:
        """Rebuild the tree from the notations, filtered by the search.

        The entries are under their section and subsection, the styles under *Styles*. The
        texts are in the selected language. Select the item ``select``, the one in the editor
        by default.
        """
        select = select if select is not None else self.current
        language = self.language.get()
        _ = self.tree.heading("description", text=f"Description ({language})")
        self.tree.delete(*self.tree.get_children())
        query = self.search.get()
        entries = [entry for entry in self.notations if matches(entry, query)]
        styles = [style for style in self.notations.styles if matches(style, query)]
        if styles or not query:
            node = self.tree.insert("", "end", iid="styles", text=STYLES, open=True)
            for style in styles:
                self._insert(node, style)
        for group_key, text in [("", NO_GROUP), *((g.key, g.key) for g in self.notations.groups)]:
            members = [entry for entry in entries if entry.group == group_key]
            if not members and (query or not group_key):
                continue
            parent_key = group_key.rpartition(".")[0]
            parent = f"group:{parent_key}" if parent_key else ""
            if parent and not self.tree.exists(parent):
                parent = self.tree.insert("", "end", iid=parent, text=parent_key, open=True)
            node = self.tree.insert(
                parent,
                "end",
                iid=f"group:{group_key}",
                text=text.rpartition(".")[2] if group_key else text,
                values=("group", self._group_title(group_key), ""),
                open=True,
            )
            for entry in members:
                self._insert(node, entry)
        _ = self.group_box.configure(values=["", *(g.key for g in self.notations.groups)])
        _ = self.style_box.configure(values=["", *(s.name for s in self.notations.styles)])
        item = f"item:{select}"
        if select and self.tree.exists(item):
            self.tree.selection_set(item)
            self.tree.see(item)
        else:
            self.tree.selection_set(())
        missing = len(self.notations.missing_translations())
        self._status.set(
            f"{len(entries)} of {len(self.notations)} entries, "
            + f"{len(self.notations.styles)} styles"
            + (f", {missing} missing translations" if missing else "")
        )

    def _group_title(self, key: str) -> str:
        if not key:
            return ""
        title = self.notations.group(key).title
        return title.resolve(self.language.get(), self.notations.default_language).latex

    def _on_select(self) -> None:
        selection = self.tree.selection()
        if not selection or not selection[0].startswith("item:"):
            return
        name = selection[0].removeprefix("item:")
        if name == self.current:
            return
        if not self._settle_form():
            self.refresh_tree()  # back to the item in the editor
            return
        self.show(name)
        # Applying the changes selected the previous item again: select the new one.
        self.tree.selection_set(selection[0])

    def show(self, name: str) -> None:
        """Show the item ``name`` in the editor (unapplied changes are lost)."""
        self.current = name
        self.write_form(ItemForm.from_item(self.notations[name]))

    # Item actions

    def apply(self) -> bool:
        """Apply the editor to the notation set.

        Replace the item in the editor, or add a new one. Return whether it succeeded; the
        problems are shown in the editor otherwise.
        """
        try:
            item = self.read_form().to_item()
            if self.current is None:
                self.notations.add(item)
            else:
                self.notations.replace(self.current, item)
        except NotationError as error:
            self.problems.set("\n".join(error.problems))
            self.root.bell()
            return False
        self.current = item.name
        self.write_form(ItemForm.from_item(item))
        self._set_dirty(True)
        self.refresh_tree()
        self._status.set(f"Applied {item.name}")
        return True

    def revert(self) -> None:
        """Discard the changes in the editor."""
        self.write_form(ItemForm.from_values(self._loaded))

    def new_item(self, kind: Kind | None = None) -> None:
        """Clear the editor for a new item, of ``kind``.

        By default, the new item has the kind and the group of the current one.
        """
        if not self._settle_form():
            return
        loaded = ItemForm.from_values(self._loaded)
        self.current = None
        self.tree.selection_set(())
        self.write_form(ItemForm(kind=kind or loaded.kind, group=loaded.group))
        self.name_entry.focus_set()

    def duplicate(self) -> None:
        """Start a new item from the one in the editor; it needs a new name."""
        if not self._settle_form():
            return
        values = dict(self._loaded)
        self.current = None
        self.tree.selection_set(())
        self.write_form(ItemForm(kind=ItemForm.from_values(values).kind))
        for name, value in values.items():
            self.fields[name].set("" if name == "name" else value)
        self.name_entry.focus_set()
        self._status.set("Duplicate: give it a new name, then apply")

    def delete(self) -> None:
        """Delete the item in the editor, after confirmation (not if other items use it)."""
        if self.current is None:
            return
        if not self.prompts.confirm(f"Delete {self.current}?"):
            return
        try:
            _ = self.notations.remove(self.current)
        except NotationError as error:
            self.prompts.error(str(error))
            return
        self.current = None
        self._set_dirty(True)
        loaded = ItemForm.from_values(self._loaded)
        self.write_form(ItemForm(kind=loaded.kind, group=loaded.group))
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
        texts = self._count_translations(removed)
        if texts and not self.prompts.confirm(
            f"Drop the {texts} translations in {', '.join(removed)}?"
        ):
            return
        try:
            self.notations.set_languages(languages)
        except NotationError as error:
            self.prompts.error(str(error))
            return
        self._set_dirty(True)
        self._build_languages()
        if self.current is not None:
            self.show(self.current)
        else:
            self.write_form(ItemForm.from_values(self._loaded))
        self.refresh_tree()

    def _count_translations(self, languages: list[str]) -> int:
        """Return how many texts have a translation in one of ``languages``."""
        values: list[Translated] = [group.title for group in self.notations.groups]
        for item in [*self.notations, *self.notations.styles]:
            values.append(item.description)
            if isinstance(item, Acronym):
                values.extend([item.short, item.long])
        return sum(language in value for language in languages for value in values)

    def update_preview(self) -> None:
        """Render the item in the editor with Typst, in the selected language.

        Show why it cannot be rendered otherwise.
        """
        self._preview_job = None
        self.preview_image = None
        if not preview.is_available():
            _ = self.preview_label.configure(
                image="",
                text="Install the typst package for a preview: pip install 'anatole[preview]'",
            )
            return
        try:
            item = self.read_form().to_item()
            png = preview.render(item, self.notations, self.language.get())
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
        self._build_languages()
        self.write_form(ItemForm())
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
        """Export to the format ``fmt``, in the selected language (and LaTeX target).

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
        target: Target = "glossaries" if self.target.get() == "glossaries" else "nomencl+acro"
        try:
            export(self.notations, path, fmt, language=language, target=target, source=source)
        except (OSError, NotationError) as error:
            self.prompts.error(str(error))
            return False
        self._status.set(f"Exported to {path} ({language})")
        return True

    def quit(self) -> None:
        """Close the window, after settling the unsaved changes."""
        if self._settle_file():
            self.root.destroy()
