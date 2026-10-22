"""Package metadata stays consistent with the code."""

from pathlib import Path

import tomllib

import qday

ROOT = Path(__file__).resolve().parent.parent
PROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf8"))["project"]


def test_version_matches_the_package():
    assert PROJECT["version"] == qday.__version__


def test_pypi_readme_and_license_exist():
    assert (ROOT / PROJECT["readme"]).is_file()
    for path in PROJECT["license-files"]:
        assert (ROOT / path).is_file()


def test_pypi_readme_uses_only_absolute_links():
    """Relative links and images break on PyPI, which renders the README outside the repository."""
    import re

    text = (ROOT / PROJECT["readme"]).read_text(encoding="utf8")
    links = re.findall(r"\]\(([^)]+)\)|src=\"([^\"]+)\"", text)
    assert all((a or b).startswith("https://") for a, b in links)


def test_cli_entry_point_is_declared():
    assert PROJECT["scripts"]["qday"] == "qday.cli:main"
