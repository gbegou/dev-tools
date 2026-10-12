"""The dialogs the graphical interface opens, behind one class that tests replace."""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

__all__ = ["FileTypes", "Prompts"]

type FileTypes = list[tuple[str, str]]
"""File dialog filters: (label, pattern) pairs."""


class Prompts:
    """The dialogs, opened over ``parent``."""

    parent: tk.Misc

    def __init__(self, parent: tk.Misc) -> None:
        self.parent = parent

    def ask_save(self, message: str) -> bool | None:
        """Ask whether to keep changes: ``True`` (keep), ``False`` (discard), ``None`` (cancel)."""
        return messagebox.askyesnocancel("Unsaved changes", message, parent=self.parent)

    def confirm(self, message: str) -> bool:
        """Ask to confirm an action."""
        return messagebox.askokcancel("Confirm", message, parent=self.parent)

    def error(self, message: str) -> None:
        """Show an error."""
        _ = messagebox.showerror("Error", message, parent=self.parent)

    def open_path(self, file_types: FileTypes) -> Path | None:
        """Ask for a file to open; ``None`` when cancelled."""
        name = filedialog.askopenfilename(parent=self.parent, filetypes=file_types)
        return Path(name) if name else None

    def save_path(self, file_types: FileTypes, suffix: str) -> Path | None:
        """Ask for a file to write; ``None`` when cancelled."""
        name = filedialog.asksaveasfilename(
            parent=self.parent, filetypes=file_types, defaultextension=suffix
        )
        return Path(name) if name else None
