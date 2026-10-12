"""The command line."""

from pathlib import Path

import pytest

from notation_manager import NotationSet, __version__, load, save
from notation_manager.cli import main

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "notations.toml"


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as caught:
        _ = main(["--version"])
    assert caught.value.code == 0
    assert capsys.readouterr().out == f"notation-manager {__version__}\n"


def test_check(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    assert main(["check", str(EXAMPLE)]) == 0
    assert "6 notations, 3 groups, languages en, fr, valid\n" in capsys.readouterr().out

    bad = tmp_path / "bad.toml"
    _ = bad.write_text("[notations.x]\nsymbol = 'x'\n", encoding="utf-8")
    missing = tmp_path / "missing.toml"
    assert main(["check", str(EXAMPLE), str(bad), str(missing)]) == 1
    captured = capsys.readouterr()
    assert "valid" in captured.out
    assert f"{bad}: notation 'x': description is missing" in captured.err
    assert "missing.toml" in captured.err


def test_list(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["list", str(EXAMPLE)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split() == ["name", "group", "symbol", "description"]
    assert lines[1].split()[:3] == ["velocity", "latin", r"\mathbf{u}"]
    assert main(["list", "--format", "typst", "--language", "fr", str(EXAMPLE)]) == 0
    output = capsys.readouterr().out
    assert "bold(upright(u))" in output
    assert "Vitesse" in output
    assert main(["list", "-l", "de", str(EXAMPLE)]) == 1


@pytest.mark.parametrize(
    ("name", "options", "expected"),
    [
        ("notations.tex", [], r"\newcommand{\velocity}"),
        ("notations.typ", [], "#let velocity ="),
        ("notations.txt", ["--format", "typst"], "#let velocity ="),
        ("notations.tex", ["--language", "fr"], "{Vitesse"),
        ("notations.typ", ["-l", "fr"], "[Vitesse]"),
    ],
)
def test_export(tmp_path: Path, name: str, options: list[str], expected: str) -> None:
    output = tmp_path / name
    assert main(["export", str(EXAMPLE), str(output), *options]) == 0
    text = output.read_text(encoding="utf-8")
    assert expected in text
    assert "from notations.toml" in text


def test_export_unknown_suffix(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    assert main(["export", str(EXAMPLE), str(tmp_path / "notations.txt")]) == 1
    assert "cannot tell the format from the suffix '.txt'" in capsys.readouterr().err


def test_check_missing_translations(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    path = tmp_path / "notations.toml"
    _ = path.write_text(
        "languages = ['en', 'fr']\n[notations.time]\nsymbol = 't'\ndescription = 'Time'\n",
        encoding="utf-8",
    )
    assert main(["check", str(path)]) == 0
    output = capsys.readouterr().out
    assert "valid, 1 missing translations" in output
    assert f"{path}: notation 'time': description is missing in fr" in output
    assert main(["check", "--strict", str(path)]) == 1
    assert "description is missing in fr" in capsys.readouterr().err


def test_usage_error() -> None:
    with pytest.raises(SystemExit) as caught:
        _ = main(["export", str(EXAMPLE)])
    assert caught.value.code == 2


def test_gui_is_the_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    opened: list[Path | None] = []

    def run(path: Path | None = None) -> int:
        opened.append(path)
        return 0

    monkeypatch.setattr("notation_manager.gui.run", run)
    assert main([]) == 0
    assert main(["gui", str(tmp_path / "new.toml")]) == 0
    assert opened == [None, tmp_path / "new.toml"]


def test_verbose_logs(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    path = tmp_path / "notations.toml"
    save(NotationSet(), path)
    with caplog.at_level("INFO", logger="notation_manager"):
        assert main(["-v", "export", str(path), str(tmp_path / "out.typ")]) == 0
    assert "exported 0 notations" in caplog.text
    assert load(path) == NotationSet()
