"""Tests of the [tool.dbt-to-wikijs-docs] settings."""

from collections.abc import Callable
from pathlib import Path

import pytest

from dbt_to_wikijs_docs import Area, Config, ConfigError


@pytest.fixture
def pyproject(tmp_path: Path) -> Callable[[str], Path]:
    """Return a function writing a pyproject.toml with the given text."""

    def write(text: str) -> Path:
        path = tmp_path / "pyproject.toml"
        path.write_text(text)
        return path

    return write


def test_defaults_without_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A project without pyproject.toml gets the defaults."""
    monkeypatch.chdir(tmp_path)
    assert Config.load() == Config()


def test_missing_explicit_file(tmp_path: Path) -> None:
    """A config file given explicitly must exist."""
    with pytest.raises(ConfigError, match="not found"):
        Config.load(tmp_path / "nope.toml")


def test_reads_tool_table(pyproject: Callable[[str], Path]) -> None:
    """Keys are read with dashes and normalised."""
    config = Config.load(
        pyproject(
            """
[tool.dbt-to-wikijs-docs]
marts-path = "models/gold"
path-prefix = "/team/data-model/"
target-dir = "build"
delete-stale = true
kind-order = ["dim_", "fct_"]

[tool.dbt-to-wikijs-docs.areas]
core = { title = "Core", description = "Shared tables." }
sales = "Sales"
"""
        )
    )
    assert config.marts_path == "models/gold/"
    assert config.path_prefix == "team/data-model"
    assert config.target_dir == Path("build")
    assert config.delete_stale is True
    assert config.kind_order == ("dim_", "fct_")
    assert list(config.areas) == ["core", "sales"]
    assert config.areas["core"] == Area("Core", "Shared tables.")
    assert config.areas["sales"] == Area("Sales")


def test_overrides_win_unless_none(pyproject: Callable[[str], Path]) -> None:
    """Command line values replace the file's; None means not given."""
    config = Config.load(
        pyproject('[tool.dbt-to-wikijs-docs]\nlocale = "it"\ntag = "auto"\n'),
        locale="de",
        tag=None,
    )
    assert (config.locale, config.tag) == ("de", "auto")


def test_unknown_key(pyproject: Callable[[str], Path]) -> None:
    """A typo in a key is an error, not a silently ignored setting."""
    with pytest.raises(ConfigError, match="unknown key 'path_prefx'"):
        Config.load(pyproject('[tool.dbt-to-wikijs-docs]\npath_prefx = "x"\n'))


def test_bad_area(pyproject: Callable[[str], Path]) -> None:
    """An area needs a title."""
    with pytest.raises(ConfigError, match="area 'core'"):
        Config.load(
            pyproject(
                '[tool.dbt-to-wikijs-docs.areas]\ncore = { description = "no title" }\n'
            )
        )


def test_invalid_toml(pyproject: Callable[[str], Path]) -> None:
    """A malformed file is a ConfigError."""
    with pytest.raises(ConfigError):
        Config.load(pyproject("[tool.dbt-to-wikijs-docs\n"))


def test_area_from_folder() -> None:
    """An area not configured is titled from its folder name."""
    assert Area.from_folder("warehouse_stock") == Area("Warehouse Stock")
