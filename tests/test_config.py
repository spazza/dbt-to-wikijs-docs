from pathlib import Path

import pytest

from dbt_to_wikijs_docs.config import Area, Config, load_config


def write(tmp_path, text):
    path = tmp_path / "pyproject.toml"
    path.write_text(text)
    return path


def test_defaults_without_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert load_config() == Config()


def test_missing_explicit_file(tmp_path):
    with pytest.raises(SystemExit, match="not found"):
        load_config(tmp_path / "nope.toml")


def test_reads_tool_table(tmp_path):
    path = write(
        tmp_path,
        """
[tool.dbt-to-wikijs-docs]
marts-path = "models/gold"
path-prefix = "/team/data-model/"
target-dir = "build"
kind-order = ["dim_", "fct_"]

[tool.dbt-to-wikijs-docs.areas]
core = { title = "Core", description = "Shared tables." }
sales = "Sales"
""",
    )
    config = load_config(path)
    assert config.marts_path == "models/gold/"
    assert config.path_prefix == "team/data-model"
    assert config.target_dir == Path("build")
    assert config.kind_order == ("dim_", "fct_")
    assert list(config.areas) == ["core", "sales"]
    assert config.areas["core"] == Area("Core", "Shared tables.")
    assert config.areas["sales"] == Area("Sales")


def test_overrides_win(tmp_path):
    path = write(tmp_path, '[tool.dbt-to-wikijs-docs]\nlocale = "it"\ntag = "auto"\n')
    config = load_config(path, {"locale": "de", "tag": None})
    assert (config.locale, config.tag) == ("de", "auto")


def test_unknown_key(tmp_path):
    path = write(tmp_path, '[tool.dbt-to-wikijs-docs]\npath_prefx = "x"\n')
    with pytest.raises(SystemExit, match="unknown key 'path_prefx'"):
        load_config(path)


def test_bad_area(tmp_path):
    path = write(tmp_path, '[tool.dbt-to-wikijs-docs.areas]\ncore = { description = "no title" }\n')
    with pytest.raises(SystemExit, match="area 'core'"):
        load_config(path)
