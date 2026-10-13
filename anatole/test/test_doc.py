"""The documentation builds without warnings (Sphinx ``-W --keep-going``, fresh environment)."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

DOC = Path(__file__).resolve().parent.parent / "doc"


@pytest.mark.skipif(
    importlib.util.find_spec("sphinx") is None or importlib.util.find_spec("furo") is None,
    reason="needs the doc dependency group (sphinx, furo)",
)
def test_documentation_builds(tmp_path: Path) -> None:
    command = [sys.executable, "-m", "sphinx", "-W", "--keep-going", "-E", "-q"]
    command += ["-b", "html", "-d", str(tmp_path / "doctrees"), str(DOC), str(tmp_path / "html")]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
