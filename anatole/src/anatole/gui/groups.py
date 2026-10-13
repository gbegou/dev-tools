"""The group editor: a dialog to add, rename, retitle, reorder and delete groups."""

import tkinter as tk
from tkinter import ttk
from typing import final

from anatole.gui.form import GroupForm, title_key
from anatole.model import NotationError, NotationSet
from anatole.typing import FORMATS

__all__ = ["GroupsDialog"]

_ERROR_COLOR = "#b00020"


@final
class GroupsDialog:
    """A modal dialog over ``parent`` that edits the groups of ``notations`` in place.

    Attributes
    ----------
    fields
        The variables of the editor fields, by field name of
        :meth:`~anatole.gui.form.GroupForm.values`.
    problems
        The variable of the problems shown in the editor.
    changed
        Whether the groups were changed.
    current
        The key of the group in the editor; ``None`` for a new group.
    window
        The dialog window.
    """

    def __init__(self, parent: tk.Misc, notations: NotationSet) -> None:
        self.notations = notations
        self.changed = False
        self.current: str | None = None
        self.window = tk.Toplevel(parent)
        self.window.title("Groups")
        self.window.transient(parent.winfo_toplevel())
        self.fields = {
            name: tk.StringVar(self.window) for name in GroupForm().values(notations.languages)
        }
        self.problems = tk.StringVar(self.window)

        frame = ttk.Frame(self.window, padding=8)
        frame.pack(fill="both", expand=True)
        _ = frame.columnconfigure(2, weight=1)
        _ = frame.rowconfigure(0, weight=1)
        self.list = ttk.Treeview(frame, show="tree", selectmode="browse", height=12)
        _ = self.list.column("#0", width=160)
        self.list.grid(row=0, column=0, rowspan=2, sticky="nsew")
        _ = self.list.bind("<<TreeviewSelect>>", lambda _event: self._on_select())
        order = ttk.Frame(frame)
        order.grid(row=0, column=1, sticky="n", padx=4)
        ttk.Button(order, text="▲", width=3, command=lambda: self.move(-1)).pack()
        ttk.Button(order, text="▼", width=3, command=lambda: self.move(1)).pack()

        editor = ttk.Frame(frame)
        editor.grid(row=0, column=2, sticky="new")
        _ = editor.columnconfigure((1, 2), weight=1)
        ttk.Label(editor, text="Key").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Entry(editor, textvariable=self.fields["key"], width=24).grid(
            row=0, column=1, columnspan=2, sticky="ew", pady=2, padx=4
        )
        ttk.Label(editor, text="LaTeX").grid(row=1, column=1, sticky="w", padx=4)
        ttk.Label(editor, text="Typst (empty: as LaTeX)").grid(row=1, column=2, sticky="w", padx=4)
        for row, language in enumerate(notations.languages, start=2):
            default = " — default" if language == notations.default_language else ""
            ttk.Label(editor, text=f"Title ({language}{default})").grid(
                row=row, column=0, sticky="w", pady=2
            )
            for column, fmt in enumerate(FORMATS, start=1):
                var = self.fields[title_key(language, fmt)]
                ttk.Entry(editor, textvariable=var, width=24).grid(
                    row=row, column=column, sticky="ew", pady=2, padx=4
                )
        last = len(notations.languages) + 2
        buttons = ttk.Frame(editor)
        buttons.grid(row=last, column=0, columnspan=3, sticky="w", pady=(8, 0))
        for text, command in [("Apply", self.apply), ("New", self.new), ("Delete", self.delete)]:
            ttk.Button(buttons, text=text, command=command).pack(side="left", padx=(0, 4))
        ttk.Label(editor, textvariable=self.problems, foreground=_ERROR_COLOR, wraplength=320).grid(
            row=last + 1, column=0, columnspan=3, sticky="w", pady=(6, 0)
        )
        ttk.Button(frame, text="Close", command=self.window.destroy).grid(
            row=1, column=2, sticky="se"
        )

        self._refresh()
        self.new()
        self.window.grab_set()

    def _refresh(self) -> None:
        self.list.delete(*self.list.get_children())
        for group in self.notations.groups:
            _ = self.list.insert("", "end", iid=f"group:{group.key}", text=group.key)
        item = f"group:{self.current}"
        if self.current is not None and self.list.exists(item):
            self.list.selection_set(item)
            self.list.see(item)

    def read_form(self) -> GroupForm:
        """Return the content of the editor."""
        return GroupForm.from_values({name: var.get() for name, var in self.fields.items()})

    def write_form(self, form: GroupForm) -> None:
        """Show ``form`` in the editor."""
        for name, value in form.values(self.notations.languages).items():
            self.fields[name].set(value)
        self.problems.set("")

    def _on_select(self) -> None:
        selection = self.list.selection()
        if selection:
            key = selection[0].removeprefix("group:")
            if key != self.current:
                self.show(key)

    def show(self, key: str) -> None:
        """Show the group ``key`` in the editor."""
        self.current = key
        self.write_form(GroupForm.from_group(self.notations.group(key)))

    def new(self) -> None:
        """Clear the editor for a new group."""
        self.current = None
        self.list.selection_set(())
        self.write_form(GroupForm())

    def apply(self) -> bool:
        """Apply the editor: replace the group in the editor, or add a new one."""
        try:
            group = self.read_form().to_group()
            if self.current is None:
                self.notations.add_group(group)
            else:
                self.notations.replace_group(self.current, group)
        except NotationError as error:
            self.problems.set("\n".join(error.problems))
            self.window.bell()
            return False
        self.current = group.key
        self.changed = True
        self._refresh()
        return True

    def delete(self) -> None:
        """Delete the group in the editor; it must have no notations."""
        if self.current is None:
            return
        try:
            _ = self.notations.remove_group(self.current)
        except NotationError as error:
            self.problems.set(str(error))
            return
        self.changed = True
        self.new()
        self._refresh()

    def move(self, offset: int) -> None:
        """Move the group in the editor up (``-1``) or down (``1``)."""
        if self.current is None:
            return
        self.notations.move_group(self.current, offset)
        self.changed = True
        self._refresh()
