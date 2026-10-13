"""The graphical interface (Tkinter): browse, search, create and edit notations."""

from pathlib import Path

__all__ = ["run"]


def run(path: Path | None = None) -> int:
    """Open the main window on the notation file ``path``, and return the exit code.

    The file is created on the first save when ``path`` is ``None`` or does not exist yet.
    """
    import tkinter as tk  # noqa: PLC0415  # tkinter is optional on some systems

    from anatole.gui.app import NotationApp  # noqa: PLC0415
    from anatole.io import load  # noqa: PLC0415

    notations = load(path) if path is not None and path.exists() else None
    root = tk.Tk()
    _ = NotationApp(root, notations, path)
    root.mainloop()
    return 0
