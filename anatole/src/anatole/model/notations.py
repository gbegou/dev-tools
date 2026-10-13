"""The notation set: entries, styles, a tree of groups, and languages, kept consistent."""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, replace
from typing import ClassVar, Literal, override

from anatole.model.entries import Acronym, Entry, Group, Item, Notation, Style
from anatole.model.texts import LANGUAGE_PATTERN, NotationError, Translated
from anatole.typing import Language

__all__ = ["Kind", "NotationSet", "Section"]

type Kind = Literal["notation", "acronym"]
"""The kinds of entries a list holds: notations, or acronyms and abbreviations."""


def _kind_of(entry: Entry) -> Kind:
    return "notation" if isinstance(entry, Notation) else "acronym"


def _owner(item: Item) -> str:
    if isinstance(item, Acronym):
        return f"{item.kind} {item.name!r}"
    return f"{'style' if isinstance(item, Style) else 'notation'} {item.name!r}"


def _translated_fields(item: Item | Group) -> list[tuple[str, Translated, bool]]:
    """Return the (field, value, required) of the fields written per language."""
    match item:
        case Group():
            return [("title", item.title, True)]
        case Style():
            return [("description", item.description, False)]
        case Notation():
            return [("description", item.description, True)]
        case Acronym():
            return [
                ("short", item.short, True),
                ("long", item.long, True),
                ("description", item.description, False),
            ]


@dataclass(frozen=True, slots=True)
class Section:
    """A group of a list, with its entries and its subsections, in order.

    Attributes
    ----------
    group
        The group; ``None`` for the entries without a group.
    entries
        The entries of the group itself, sorted by sort key.
    subsections
        The subsections that have entries.
    """

    group: Group | None
    entries: tuple[Entry, ...]
    subsections: tuple["Section", ...] = ()

    def all_entries(self) -> list[Entry]:
        """Return the entries of the section and of its subsections, in order."""
        return [*self.entries, *(e for sub in self.subsections for e in sub.all_entries())]


def _check_languages(languages: tuple[Language, ...]) -> list[str]:
    problems: list[str] = []
    if not languages:
        problems.append("languages: at least one language is needed")
    for language in languages:
        if not LANGUAGE_PATTERN.fullmatch(language):
            problems.append(
                f"languages: invalid language code {language!r} (expected a code like en, fr or "
                + "pt-BR)"
            )
        if languages.count(language) > 1:
            problems.append(f"languages: {language!r} is declared twice")
    return list(dict.fromkeys(problems))


class NotationSet:
    r"""A notation set: entries and styles by name, a tree of groups, and languages.

    The entries are notations, acronyms and abbreviations.

    Parameters
    ----------
    entries
        The notations and acronyms, in the order they are kept (and saved).
    groups
        The groups, in the order of the lists (a subsection after its section).
    languages
        The languages of the texts written per language; the first one is the default
        language, in which every description, title and acronym is required. The other
        translations are optional: the exports fall back on the default language.
    styles
        The styles that notations apply to their symbol.

    Raises
    ------
    NotationError
        If the set is not consistent: two items share a name, an entry refers to an unknown
        group, style or entry, references form a cycle, a subsection has no section, a
        language is invalid, or a translation is missing in the default language or is in a
        language not declared. The message lists every problem.
    """

    _languages: tuple[Language, ...]
    _styles: dict[str, Style]
    _entries: dict[str, Entry]
    _groups: dict[str, Group]

    def __init__(
        self,
        entries: Iterable[Entry] = (),
        groups: Iterable[Group] = (),
        languages: Iterable[Language] = ("en",),
        styles: Iterable[Style] = (),
    ) -> None:
        self._languages = tuple(languages)
        problems = _check_languages(self._languages)
        if problems:
            raise NotationError(problems)
        self._styles, self._entries, self._groups = {}, {}, {}
        for group in groups:
            if group.key in self._groups:
                problems.append(f"group {group.key!r}: defined twice")
            self._groups[group.key] = group
        for item in [*styles, *entries]:
            if item.name in self._styles or item.name in self._entries:
                problems.append(f"{_owner(item)}: the name is already taken")
            elif isinstance(item, Style):
                self._styles[item.name] = item
            else:
                self._entries[item.name] = item
        problems.extend(self._problems())
        if problems:
            raise NotationError(problems)

    # Consistency

    def _translation_problems(self, owner: str, item: Item | Group) -> list[str]:
        problems: list[str] = []
        for name, value, required in _translated_fields(item):
            if (required or len(value)) and self.default_language not in value:
                problems.append(
                    f"{owner}: {name} is missing in the default language {self.default_language}"
                )
            problems.extend(
                f"{owner}: {name} is in {language}, which is not a declared language "
                + f"({', '.join(self._languages)})"
                for language in value.languages
                if language not in self._languages
            )
        return problems

    def _item_problems(self, item: Item) -> list[str]:
        owner = _owner(item)
        problems = self._translation_problems(owner, item)
        if not isinstance(item, Style) and item.group and item.group not in self._groups:
            problems.append(f"{owner}: unknown group {item.group!r}")
        if isinstance(item, Notation) and item.style:
            if item.style in self._entries:
                problems.append(f"{owner}: {item.style!r} is not a style")
            elif item.style not in self._styles:
                problems.append(f"{owner}: unknown style {item.style!r}")
        known = self._styles.keys() | self._entries.keys()
        problems.extend(
            f"{owner}: refers to @{{{name}}}, which is not defined"
            for name in item.references()
            if name not in known and not (isinstance(item, Notation) and name == item.style)
        )
        return problems

    def _cycle_problems(self) -> list[str]:
        """Return a problem for each cycle of references."""
        items = self._items()
        state: dict[str, int] = {}  # 1: being visited, 2: done
        problems: list[str] = []

        def visit(name: str, path: list[str]) -> None:
            state[name] = 1
            for used in items[name].references():
                if used not in items:
                    continue
                if state.get(used) == 1:
                    cycle = [*path[path.index(used) :], used]
                    problems.append(
                        f"{_owner(items[used])}: depends on itself ({' -> '.join(cycle)})"
                    )
                elif used not in state:
                    visit(used, [*path, used])
            state[name] = 2

        for name in items:
            if name not in state:
                visit(name, [name])
        return problems

    def _problems(self) -> list[str]:
        problems: list[str] = []
        for group in self._groups.values():
            problems.extend(self._translation_problems(f"group {group.key!r}", group))
            if group.parent and group.parent not in self._groups:
                problems.append(f"group {group.key!r}: unknown section {group.parent!r}")
        for item in self._items().values():
            problems.extend(self._item_problems(item))
        if not problems:
            problems.extend(self._cycle_problems())
        return problems

    def _items(self) -> dict[str, Item]:
        return {**self._styles, **self._entries}

    def _commit(
        self,
        *,
        styles: dict[str, Style] | None = None,
        entries: dict[str, Entry] | None = None,
        groups: dict[str, Group] | None = None,
        languages: tuple[Language, ...] | None = None,
    ) -> None:
        """Apply a change if the set stays consistent; raise a ``NotationError`` otherwise."""
        saved = (self._styles, self._entries, self._groups, self._languages)
        self._styles = self._styles if styles is None else styles
        self._entries = self._entries if entries is None else entries
        self._groups = self._groups if groups is None else groups
        self._languages = self._languages if languages is None else languages
        problems = self._problems()
        if problems:
            self._styles, self._entries, self._groups, self._languages = saved
            raise NotationError(problems)

    # Items

    def __len__(self) -> int:
        """Return the number of entries (styles aside)."""
        return len(self._entries)

    def __iter__(self) -> Iterator[Entry]:
        """Iterate over the entries (styles aside), in order."""
        return iter(self._entries.values())

    def __contains__(self, name: object) -> bool:
        return name in self._entries or name in self._styles

    def __getitem__(self, name: str) -> Item:
        item = self._entries.get(name) or self._styles.get(name)
        if item is None:
            raise KeyError(f"no entry or style named {name!r}")
        return item

    def notation(self, name: str) -> Notation:
        """Return the notation ``name``; :class:`KeyError` if there is none."""
        item = self._entries.get(name)
        if not isinstance(item, Notation):
            raise KeyError(f"no notation named {name!r}")
        return item

    def acronym(self, name: str) -> Acronym:
        """Return the acronym or abbreviation ``name``; :class:`KeyError` if there is none."""
        item = self._entries.get(name)
        if not isinstance(item, Acronym):
            raise KeyError(f"no acronym or abbreviation named {name!r}")
        return item

    def style(self, name: str) -> Style:
        """Return the style ``name``; :class:`KeyError` if there is none."""
        try:
            return self._styles[name]
        except KeyError:
            raise KeyError(f"no style named {name!r}") from None

    @property
    def notations(self) -> tuple[Notation, ...]:
        """The notations, in order."""
        return tuple(e for e in self._entries.values() if isinstance(e, Notation))

    @property
    def acronyms(self) -> tuple[Acronym, ...]:
        """The acronyms and abbreviations, in order."""
        return tuple(e for e in self._entries.values() if isinstance(e, Acronym))

    @property
    def styles(self) -> tuple[Style, ...]:
        """The styles, in order."""
        return tuple(self._styles.values())

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, NotationSet):
            return NotImplemented
        return (
            self._languages == other._languages
            and list(self._styles.items()) == list(other._styles.items())
            and list(self._entries.items()) == list(other._entries.items())
            and self.groups == other.groups
        )

    __hash__: ClassVar[None] = None  # pyright: ignore[reportIncompatibleMethodOverride]  # mutable

    @override
    def __repr__(self) -> str:
        return (
            f"NotationSet({len(self.notations)} notations, {len(self.acronyms)} acronyms, "
            + f"{len(self._styles)} styles, {len(self._groups)} groups, "
            + f"languages {', '.join(self._languages)})"
        )

    def add(self, item: Item) -> None:
        """Add an entry or a style at the end.

        Raises
        ------
        NotationError
            If the name is taken, or the item is not consistent with the set (unknown group,
            style or reference, a cycle, a translation missing in the default language or in a
            language not declared).
        """
        if item.name in self:
            raise NotationError(f"{_owner(item)}: the name is already taken")
        if isinstance(item, Style):
            self._commit(styles={**self._styles, item.name: item})
        else:
            self._commit(entries={**self._entries, item.name: item})

    def replace(self, name: str, item: Item) -> None:
        """Replace the item ``name`` by ``item``, at the same position.

        The new item may have another name: the references to the old name (and the
        notations of a style) follow the rename. A style stays a style, an entry an entry.

        Raises
        ------
        KeyError
            If there is no item ``name``.
        NotationError
            If the new name is taken by another item, a style would become an entry (or the
            other way round), or the item is not consistent with the set.
        """
        old = self[name]
        if item.name != name and item.name in self:
            raise NotationError(f"{_owner(item)}: the name is already taken")
        if isinstance(old, Style) != isinstance(item, Style):
            raise NotationError(f"{_owner(item)}: a style and an entry cannot replace each other")

        renaming = item.name != name
        styles: dict[str, Style] = {
            key: value.renamed(name, item.name) if renaming else value
            for key, value in self._styles.items()
        }
        entries: dict[str, Entry] = {
            key: value.renamed(name, item.name) if renaming else value
            for key, value in self._entries.items()
        }
        if isinstance(item, Style):
            styles = {
                (item.name if k == name else k): (item if k == name else v)
                for k, v in styles.items()
            }
        else:
            entries = {
                (item.name if k == name else k): (item if k == name else v)
                for k, v in entries.items()
            }
        self._commit(styles=styles, entries=entries)

    def users(self, name: str) -> list[str]:
        """Return the names of the items that use the item ``name`` (by reference or style)."""
        return [item.name for item in self._items().values() if name in item.references()]

    def remove(self, name: str) -> Item:
        """Remove the item ``name`` and return it.

        Raises
        ------
        KeyError
            If there is no item ``name``.
        NotationError
            If other items use it.
        """
        item = self[name]
        if users := self.users(name):
            raise NotationError(
                f"{_owner(item)}: used by {', '.join(repr(user) for user in users)}"
            )
        if isinstance(item, Style):
            del self._styles[name]
        else:
            del self._entries[name]
        return item

    def dependencies(self, names: Iterable[str]) -> list[str]:
        """Return the items that the items ``names`` use, directly or not (``names`` aside)."""
        items, found = self._items(), dict[str, None]()
        pending = [name for name in names if name in items]
        start = set(pending)
        while pending:
            for used in items[pending.pop()].references():
                if used in items and used not in found and used not in start:
                    found[used] = None
                    pending.append(used)
        return list(found)

    def ordered(self) -> list[Item]:
        """Return the styles and entries, each after the items it uses (else in order)."""
        items, done = self._items(), dict[str, Item]()

        def visit(name: str) -> None:
            if name in done:
                return
            for used in items[name].references():
                if used in items:
                    visit(used)
            done[name] = items[name]

        for name in items:
            visit(name)
        return list(done.values())

    # Groups

    @property
    def groups(self) -> tuple[Group, ...]:
        """The groups in the order of the lists, each section followed by its subsections."""
        sections = [group for group in self._groups.values() if not group.parent]
        return tuple(
            ordered for section in sections for ordered in (section, *self.children(section.key))
        )

    def group(self, key: str) -> Group:
        """Return the group ``key``; :class:`KeyError` if there is none."""
        try:
            return self._groups[key]
        except KeyError:
            raise KeyError(f"no group with key {key!r}") from None

    def children(self, key: str) -> tuple[Group, ...]:
        """Return the subsections of the group ``key`` (``""``: the sections), in order."""
        return tuple(group for group in self._groups.values() if group.parent == key)

    def add_group(self, group: Group) -> None:
        """Add a group, last among its siblings.

        Raises
        ------
        NotationError
            If the key is taken, its section does not exist, or the title is not in the default
            language or is in a language not declared.
        """
        if group.key in self._groups:
            raise NotationError(f"group {group.key!r}: the key is already taken")
        self._commit(groups={**self._groups, group.key: group})

    def replace_group(self, key: str, group: Group) -> None:
        """Replace the group ``key`` by ``group``, at the same position.

        When the key changes (in its last level only), the subsections and the entries of the
        group follow it.

        Raises
        ------
        KeyError
            If there is no group ``key``.
        NotationError
            If the new key is taken, moves the group to another section, or the title is not
            consistent with the set.
        """
        if key not in self._groups:
            raise KeyError(f"no group with key {key!r}")
        if group.key != key and group.key in self._groups:
            raise NotationError(f"group {group.key!r}: the key is already taken")
        if group.parent != self._groups[key].parent:
            raise NotationError(
                f"group {group.key!r}: a rename keeps the group in its section "
                + f"({self._groups[key].parent or 'none'})"
            )

        def moved(old: str) -> str:
            if old == key:
                return group.key
            if old.startswith(f"{key}."):
                return group.key + old[len(key) :]
            return old

        groups = {
            moved(old): group if old == key else replace(value, key=moved(old))
            for old, value in self._groups.items()
        }
        entries: dict[str, Entry] = {
            name: replace(entry, group=moved(entry.group)) if entry.group else entry
            for name, entry in self._entries.items()
        }
        self._commit(groups=groups, entries=entries)

    def remove_group(self, key: str) -> Group:
        """Remove the group ``key`` and return it.

        Raises
        ------
        KeyError
            If there is no group ``key``.
        NotationError
            If entries or subsections still belong to the group.
        """
        if key not in self._groups:
            raise KeyError(f"no group with key {key!r}")
        members = [entry.name for entry in self if entry.group == key]
        subsections = [group.key for group in self.children(key)]
        if members or subsections:
            used = ", ".join(repr(name) for name in [*subsections, *members])
            raise NotationError(f"group {key!r}: still used by {used}")
        return self._groups.pop(key)

    def move_group(self, key: str, offset: int) -> None:
        """Move the group ``key`` by ``offset`` positions among its siblings (clamped).

        Raises
        ------
        KeyError
            If there is no group ``key``.
        """
        group = self.group(key)
        siblings = [g.key for g in self.children(group.parent)]
        index = siblings.index(key)
        siblings.insert(max(0, min(len(siblings) - 1, index + offset)), siblings.pop(index))
        others = [k for k in self._groups if k not in siblings]
        self._groups = {k: self._groups[k] for k in [*siblings, *others]}

    def sections(self, kind: Kind | None = None) -> tuple[Section, ...]:
        """Return the entries (of ``kind`` only, unless ``None``) as a tree of sections.

        The entries without a group come first (under ``None``), then each section with its
        subsections, in order; within each, entries are sorted by sort key. Sections and
        subsections without entries are left out.
        """
        selected = [e for e in self if kind is None or _kind_of(e) == kind]

        def section(group: Group | None) -> Section | None:
            key = "" if group is None else group.key
            entries = tuple(
                sorted((e for e in selected if e.group == key), key=lambda e: e.sort_key)
            )
            subsections: tuple[Section, ...] = ()
            if group is not None:
                subsections = tuple(
                    sub for child in self.children(key) if (sub := section(child)) is not None
                )
            if not entries and not subsections:
                return None
            return Section(group, entries, subsections)

        roots = [None, *self.children("")]
        return tuple(s for root in roots if (s := section(root)) is not None)

    # Tags

    @property
    def tags(self) -> tuple[str, ...]:
        """The tags of the entries, sorted."""
        return tuple(sorted({tag for entry in self for tag in entry.tags}))

    def subset(self, tags: Iterable[str]) -> "NotationSet":
        """Return the notation set of the entries selected by ``tags``.

        An entry is selected when it has one of ``tags`` or has no tag at all; the entries
        that selected ones use come along. Styles, groups and languages are kept.
        """
        wanted = set(tags)
        selected = [e.name for e in self if not e.tags or wanted & set(e.tags)]
        names = set(selected) | set(self.dependencies(selected))
        return NotationSet(
            (e for e in self if e.name in names), self.groups, self._languages, self.styles
        )

    # Languages

    @property
    def languages(self) -> tuple[Language, ...]:
        """The languages, the default one first."""
        return self._languages

    @property
    def default_language(self) -> Language:
        """The default language, in which every required text has a translation."""
        return self._languages[0]

    def set_languages(self, languages: Iterable[Language]) -> None:
        """Change the languages; the first one becomes the default language.

        The translations in the languages removed are dropped.

        Raises
        ------
        NotationError
            If a language is invalid, or a text has no translation in the new default
            language; nothing is changed then.
        """
        languages = tuple(languages)
        problems = _check_languages(languages)
        if problems:
            raise NotationError(problems)

        def only[T: Item | Group](item: T) -> T:
            changes = {name: value.only(languages) for name, value, _ in _translated_fields(item)}
            return replace(item, **changes)

        try:
            self._commit(
                styles={k: only(v) for k, v in self._styles.items()},
                entries={k: only(v) for k, v in self._entries.items()},
                groups={k: only(v) for k, v in self._groups.items()},
                languages=languages,
            )
        except NotationError as error:
            raise NotationError(
                problem.replace("the default language", "the new default language")
                for problem in error.problems
            ) from None

    def missing_translations(self, languages: Iterable[Language] | None = None) -> list[str]:
        """Return the translations missing in ``languages`` (by default, every language).

        One message each: ``notation 'velocity': description is missing in fr``. An optional
        text that is not given at all is not missing.
        """
        missing: list[str] = []
        for language in self._languages if languages is None else languages:
            for group in self._groups.values():
                if language not in group.title:
                    missing.append(f"group {group.key!r}: title is missing in {language}")
            for item in self._items().values():
                missing.extend(
                    f"{_owner(item)}: {name} is missing in {language}"
                    for name, value, _ in _translated_fields(item)
                    if len(value) and language not in value
                )
        return missing

    def check_language(self, language: Language) -> None:
        """Check that ``language`` is declared; raise a ``NotationError`` if it is not."""
        if language not in self._languages:
            raise NotationError(
                f"language {language!r} is not declared ({', '.join(self._languages)})"
            )
