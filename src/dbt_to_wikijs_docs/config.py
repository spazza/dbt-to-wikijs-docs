"""Settings read from the `[tool.dbt-to-wikijs-docs]` table of the dbt project's pyproject.toml.

Example:

    [tool.dbt-to-wikijs-docs]
    marts-path = "models/marts/"
    path-prefix = "analytics/data-model"
    index-title = "Data model"

    [tool.dbt-to-wikijs-docs.areas]
    core = { title = "Core", description = "Shared tables used across all reports." }
    sales = { title = "Sales", description = "Sales transactions." }

Every key is optional. Command line options override the file; the Wiki.js
API key is only read from the WIKIJS_API_KEY environment variable.
"""

import sys
from dataclasses import dataclass, field, fields
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

TOOL_NAME = "dbt-to-wikijs-docs"

DEFAULT_BANNER = (
    "> This page is generated automatically from the data warehouse "
    "documentation (dbt). Changes made here are overwritten: ask the data "
    "team to change the text.\n"
    "{.is-info}\n"
)


@dataclass(frozen=True)
class Area:
    title: str
    description: str = ""


@dataclass
class Config:
    # dbt
    target_dir: Path = Path("target")
    marts_path: str = "models/marts/"
    # Wiki.js
    url: str | None = None
    path_prefix: str = "data-model"
    locale: str = "en"
    tag: str = "dbt-generated"
    user_agent: str = "dbt-to-wikijs-docs"
    # page content
    banner: str = DEFAULT_BANNER
    index_title: str = "Data model"
    index_description: str = "Business documentation of the data warehouse tables."
    index_intro: str = "Business documentation of the data warehouse tables used for reporting."
    # index sections, one per folder under marts_path, listed in this order
    areas: dict[str, Area] = field(default_factory=dict)
    # model name prefixes, listed in this order inside each index section
    kind_order: tuple[str, ...] = ("fct_", "dim_")

    def __post_init__(self):
        self.target_dir = Path(self.target_dir)
        self.marts_path = self.marts_path.replace("\\", "/").strip("/") + "/"
        self.path_prefix = self.path_prefix.strip("/")
        self.kind_order = tuple(self.kind_order)


def load_config(pyproject=None, overrides=None):
    """Build the Config from pyproject.toml (if any) and non-None `overrides`.

    `pyproject` defaults to ./pyproject.toml; a missing default file is fine,
    a missing explicit file is an error.
    """
    settings = {}
    path = Path(pyproject) if pyproject else Path("pyproject.toml")
    if path.exists():
        with path.open("rb") as file:
            table = tomllib.load(file).get("tool", {}).get(TOOL_NAME, {})
        settings = _parse(table, path)
    elif pyproject:
        raise SystemExit(f"Config file not found: {path}")
    settings.update({key: value for key, value in (overrides or {}).items() if value is not None})
    return Config(**settings)


def _parse(table, path):
    known = {f.name for f in fields(Config)}
    settings = {}
    for key, value in table.items():
        name = key.replace("-", "_")
        if name not in known:
            raise SystemExit(f"{path}: unknown key '{key}' in [tool.{TOOL_NAME}]")
        settings[name] = value
    if "areas" in settings:
        areas = {}
        for folder, area in settings["areas"].items():
            if isinstance(area, str):
                area = {"title": area}
            if not isinstance(area, dict) or set(area) - {"title", "description"} or "title" not in area:
                raise SystemExit(f"{path}: area '{folder}' needs a title and an optional description")
            areas[folder] = Area(**area)
        settings["areas"] = areas
    return settings
