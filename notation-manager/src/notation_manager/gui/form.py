"""The logic of the graphical interface that needs no display: the editor forms and the search."""

from dataclasses import dataclass

from notation_manager.model import Group, Notation, NotationError, Rendered

__all__ = ["GroupForm", "NotationForm", "matches"]


@dataclass(slots=True)
class NotationForm:
    """The text fields of the notation editor."""

    name: str = ""
    group: str = ""
    arguments: str = "0"
    sort: str = ""
    symbol_latex: str = ""
    symbol_typst: str = ""
    description_latex: str = ""
    description_typst: str = ""
    units_latex: str = ""
    units_typst: str = ""

    @classmethod
    def from_notation(cls, notation: Notation) -> "NotationForm":
        """Return the form that shows ``notation``."""
        return cls(
            name=notation.name,
            group=notation.group,
            arguments=str(notation.arguments),
            sort=notation.sort,
            symbol_latex=notation.symbol.latex,
            symbol_typst=notation.symbol.typst,
            description_latex=notation.description.latex,
            description_typst=notation.description.typst,
            units_latex=notation.units.latex,
            units_typst=notation.units.typst,
        )

    def values(self) -> dict[str, str]:
        """Return the fields by name, in order (``NotationForm(**values)`` rebuilds the form)."""
        return {
            "name": self.name,
            "group": self.group,
            "arguments": self.arguments,
            "sort": self.sort,
            "symbol_latex": self.symbol_latex,
            "symbol_typst": self.symbol_typst,
            "description_latex": self.description_latex,
            "description_typst": self.description_typst,
            "units_latex": self.units_latex,
            "units_typst": self.units_typst,
        }

    def to_notation(self) -> Notation:
        """Return the notation that the form describes.

        Surrounding whitespace is stripped from every field.

        Raises
        ------
        NotationError
            If a field is invalid; the message lists every problem.
        """
        try:
            arguments = int(self.arguments.strip() or "0")
        except ValueError:
            raise NotationError(
                f"notation {self.name.strip()!r}: arguments must be an integer, "
                + f"not {self.arguments!r}"
            ) from None
        return Notation(
            name=self.name.strip(),
            symbol=Rendered(self.symbol_latex.strip(), self.symbol_typst.strip()),
            description=Rendered(self.description_latex.strip(), self.description_typst.strip()),
            units=Rendered(self.units_latex.strip(), self.units_typst.strip()),
            group=self.group.strip(),
            arguments=arguments,
            sort=self.sort.strip(),
        )


@dataclass(slots=True)
class GroupForm:
    """The text fields of the group editor."""

    key: str = ""
    title_latex: str = ""
    title_typst: str = ""

    @classmethod
    def from_group(cls, group: Group) -> "GroupForm":
        """Return the form that shows ``group``."""
        return cls(key=group.key, title_latex=group.title.latex, title_typst=group.title.typst)

    def values(self) -> dict[str, str]:
        """Return the fields by name, in order (``GroupForm(**values)`` rebuilds the form)."""
        return {"key": self.key, "title_latex": self.title_latex, "title_typst": self.title_typst}

    def to_group(self) -> Group:
        """Return the group that the form describes (whitespace stripped).

        Raises
        ------
        NotationError
            If a field is invalid.
        """
        return Group(
            key=self.key.strip(),
            title=Rendered(self.title_latex.strip(), self.title_typst.strip()),
        )


def matches(notation: Notation, query: str) -> bool:
    """Return whether ``notation`` matches a search.

    Every word of ``query`` must appear, regardless of case, in the name, the group, the sort
    key, or a rendering of the symbol, description or units.
    """
    haystack = " ".join(
        [
            notation.name,
            notation.group,
            notation.sort,
            *(
                text
                for value in (notation.symbol, notation.description, notation.units)
                for text in (value.latex, value.typst)
            ),
        ]
    ).casefold()
    return all(word in haystack for word in query.casefold().split())
