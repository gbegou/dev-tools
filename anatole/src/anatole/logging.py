"""Logging helpers: one logger per module, under the ``notation_manager`` logger."""

import logging

__all__ = ["get_logger"]


def get_logger(name: str) -> logging.Logger:
    """Return the logger of a module of the package.

    Parameters
    ----------
    name
        The module's ``__name__``; names outside the package are put under it.
    """
    if name != "notation_manager" and not name.startswith("notation_manager."):
        name = f"notation_manager.{name}"
    return logging.getLogger(name)
