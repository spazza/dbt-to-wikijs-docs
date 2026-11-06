"""Settings read from the `[tool.dbt-to-wikijs-docs]` table of pyproject.toml.

A dbt project configures the tool like this:

    [tool.dbt-to-wikijs-docs]
    marts-path = "models/marts/"
    path-prefix = "analytics/data-model"
    index-title = "Data model"

    [tool.dbt-to-wikijs-docs.areas]
    core = { title = "Core", description = "Shared tables used across all reports." }
    sales = { title = "Sales", description = "Sales transactions." }

Every key is optional. Command line options override the file; the Wiki.js
API key is only read from the environment.
"""

import sys
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

from dbt_to_wikijs_docs.errors import ConfigError

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from collections.abc import Mapping, Sequence

TOOL_NAME = "dbt-to-wikijs-docs"
DEFAULT_PYPROJECT = Path("pyproject.toml")

DEFAULT_BANNER = (
    "> This page is generated automatically from the data warehouse "
    "documentation (dbt). Changes made here are overwritten: ask the data "
    "team to change the text.\n"
    "{.is-info}\n"
)


@dataclass(frozen=True)
class Area:
    """A section of the index page: the models of one folder of the marts path."""

    title: str
    description: str = ""

    @classmethod
    def from_folder(cls, folder: str) -> "Area":
        """Build the section of a folder the configuration does not describe."""
        return cls(folder.replace("_", " ").title())

    @classmethod
    def parse(cls, folder: str, raw: object, source: Path) -> "Area":
        """Build an area from its TOML value: a title, or a title and description."""
        if isinstance(raw, str):
            return cls(raw)
        if (
            isinstance(raw, dict)
            and "title" in raw
            and raw.keys()
            <= {
                "title",
                "description",
            }
        ):
            return cls(**raw)
        msg = f"{source}: area '{folder}' needs a title and an optional description"
        raise ConfigError(msg)


@dataclass(frozen=True)
class Config:
    """Everything that varies between dbt projects."""

    # dbt
    target_dir: Path = Path("target")
    marts_path: str = "models/marts/"
    # Wiki.js
    url: str | None = None
    path_prefix: str = "data-model"
    locale: str = "en"
    tag: str = "dbt-generated"
    # delete the generated pages of models that no longer exist
    delete_stale: bool = False
    user_agent: str = TOOL_NAME
    # page content
    banner: str = DEFAULT_BANNER
    index_title: str = "Data model"
    index_description: str = "Business documentation of the data warehouse tables."
    index_intro: str = (
        "Business documentation of the data warehouse tables used for reporting."
    )
    # index sections, one per folder under marts_path, listed in this order
    areas: Mapping[str, Area] = field(default_factory=dict)
    # model name prefixes, listed in this order inside each index section
    kind_order: Sequence[str] = ("fct_", "dim_")

    def __post_init__(self) -> None:
        """Normalise the values the TOML file and the command line give loosely."""
        marts_path = self.marts_path.replace("\\", "/").strip("/") + "/"
        object.__setattr__(self, "target_dir", Path(self.target_dir))
        object.__setattr__(self, "marts_path", marts_path)
        object.__setattr__(self, "path_prefix", self.path_prefix.strip("/"))
        object.__setattr__(self, "kind_order", tuple(self.kind_order))

    @classmethod
    def load(
        cls, pyproject: Path | None = None, **overrides: str | Path | bool | None
    ) -> "Config":
        """Read pyproject.toml and apply the `overrides` that are not None.

        `pyproject` defaults to ./pyproject.toml, which may be missing; an
        explicit file must exist.
        """
        settings = cls._read_table(
            pyproject or DEFAULT_PYPROJECT, required=pyproject is not None
        )
        settings.update(
            {key: value for key, value in overrides.items() if value is not None}
        )
        return cls(**settings)

    @classmethod
    def _read_table(cls, source: Path, *, required: bool) -> dict[str, Any]:
        if not source.exists():
            if required:
                msg = f"Config file not found: {source}"
                raise ConfigError(msg)
            return {}
        try:
            with source.open("rb") as file:
                document = tomllib.load(file)
        except tomllib.TOMLDecodeError as error:
            msg = f"{source}: {error}"
            raise ConfigError(msg) from error

        known = {f.name for f in fields(cls)}
        settings: dict[str, Any] = {}
        for key, value in document.get("tool", {}).get(TOOL_NAME, {}).items():
            name = key.replace("-", "_")
            if name not in known:
                msg = f"{source}: unknown key '{key}' in [tool.{TOOL_NAME}]"
                raise ConfigError(msg)
            settings[name] = value
        if "areas" in settings:
            settings["areas"] = {
                folder: Area.parse(folder, raw, source)
                for folder, raw in settings["areas"].items()
            }
        return settings
