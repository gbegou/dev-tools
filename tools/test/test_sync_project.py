"""Tests of tools/sync_project.sh, through its command line: the --keep option.

A project in a temporary directory, laid out as the script expects: ``project/demo`` (the
official repository) and ``project/gh/demo`` (the GitHub copy, with a bare ``origin`` that
the script fetches). The official side has a file the GitHub copy never had
(``modulefiles/dspod/sator/dev``, added there by hand) and one the GitHub copy removed
(``notes.txt``); a to-official sync removes both, unless --keep protects the first.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "sync_project.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("rsync") is None,
    reason="sync_project.sh needs git and rsync",
)

# commits in the temporary repositories, whatever the git configuration of the machine
GIT_ENV = {
    "GIT_AUTHOR_NAME": "test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}


def git(repo: Path, *args: str) -> None:
    """Run git in ``repo`` (an error fails the test)."""
    _ = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        env={**os.environ, **GIT_ENV},
    )


def commit(repo: Path, files: dict[str, str]) -> None:
    """A repository on branch main holding exactly ``files`` (path: content), committed."""
    repo.mkdir(parents=True)
    git(repo, "init", "--quiet", "--initial-branch=main")
    for name, content in files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        _ = (repo / name).write_text(content)
    git(repo, "add", "-A")
    git(repo, "commit", "--quiet", "-m", "files")


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """``project/`` with the official repository and its GitHub copy (pushed to origin)."""
    root = tmp_path / "project"
    commit(
        root / "demo",
        {
            "src/a.py": "old\n",
            "notes.txt": "removed on GitHub\n",
            "modulefiles/dspod/sator/dev": "added on the official side\n",
        },
    )
    github = root / "gh" / "demo"
    commit(github, {"src/a.py": "new\n", "modulefiles/dspod/.common": "shared\n"})
    origin = tmp_path / "origin.git"
    _ = subprocess.run(["git", "init", "--quiet", "--bare", str(origin)], check=True)
    git(github, "remote", "add", "origin", str(origin))
    git(github, "push", "--quiet", "origin", "main")
    return root


def sync(root: Path, *options: str) -> subprocess.CompletedProcess[str]:
    """``sync_project.sh [options] demo to-official origin/main``, run from ``root``."""
    return subprocess.run(
        ["bash", str(TOOL), *options, "demo", "to-official", "origin/main"],
        cwd=root,
        capture_output=True,
        text=True,
        env={**os.environ, **GIT_ENV, "ROOT": str(root)},
        check=False,
    )


def has_line(output: str, pattern: str) -> bool:
    """Whether a line of the output matches ``pattern`` (a regex, whitespace-tolerant)."""
    return re.search(rf"^{pattern}$", output, re.MULTILINE) is not None


def test_without_keep_the_added_file_is_removed(project: Path) -> None:
    done = sync(project)
    assert done.returncode == 0, done.stderr
    assert has_line(done.stdout, r"removed\s+notes\.txt")
    assert has_line(done.stdout, r"removed\s+modulefiles/dspod/sator/dev")
    assert has_line(done.stdout, r"updated\s+src/a\.py")
    assert has_line(done.stdout, r"added\s+modulefiles/dspod/\.common")
    # a dry run writes nothing
    assert (project / "demo" / "notes.txt").exists()
    assert (project / "demo" / "src" / "a.py").read_text() == "old\n"


def test_keep_protects_the_matching_files_only(project: Path) -> None:
    done = sync(project, "--keep", "modulefiles/*")
    assert done.returncode == 0, done.stderr
    assert has_line(
        done.stdout, r"kept\s+modulefiles/dspod/sator/dev\s+\(--keep modulefiles/\*\)"
    )
    assert not has_line(done.stdout, r"removed\s+modulefiles/dspod/sator/dev")
    assert has_line(done.stdout, r"removed\s+notes\.txt")
    assert "no file of the destination to keep" not in done.stdout

    done = sync(project, "--apply", "--keep", "modulefiles/*")
    assert done.returncode == 0, done.stderr
    official = project / "demo"
    assert (
        official / "modulefiles/dspod/sator/dev"
    ).read_text() == "added on the official side\n"
    assert not (official / "notes.txt").exists()
    # the rest of the sync is unchanged: updates and additions go through
    assert (official / "src/a.py").read_text() == "new\n"
    assert (official / "modulefiles/dspod/.common").read_text() == "shared\n"


@pytest.mark.parametrize(
    "option", [["--keep", "modulefiles"], ["--keep=/modulefiles/"]]
)
def test_keep_a_directory(project: Path, option: list[str]) -> None:
    done = sync(project, *option)
    assert done.returncode == 0, done.stderr
    assert has_line(done.stdout, r"kept\s+modulefiles/dspod/sator/dev\s+\(--keep \S+\)")
    assert has_line(done.stdout, r"removed\s+notes\.txt")


def test_keep_reports_unused_patterns_and_needs_a_pattern(project: Path) -> None:
    done = sync(project, "--keep", "modulefiles/*", "--keep", "docs/*")
    assert done.returncode == 0, done.stderr
    assert (
        "--keep 'docs/*': no file of the destination to keep (a typo?)" in done.stdout
    )
    assert "--keep 'modulefiles/*': no file" not in done.stdout

    done = subprocess.run(
        ["bash", str(TOOL), "--keep"], capture_output=True, text=True, check=False
    )
    assert done.returncode == 2
    assert "--keep needs a pattern" in done.stderr
