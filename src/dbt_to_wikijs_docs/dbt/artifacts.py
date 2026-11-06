"""Reading the artifacts written by `dbt docs generate` into the domain objects.

This is the only module that knows the layout of manifest.json and catalog.json.
"""

import json
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from dbt_to_wikijs_docs.dbt.nodes import Column, DataTest, Model
from dbt_to_wikijs_docs.dbt.project import DbtProject
from dbt_to_wikijs_docs.errors import ArtifactError
from dbt_to_wikijs_docs.text import collapse_whitespace

Node = dict[str, Any]

# area of the models directly in the marts folder, not in a subfolder
ROOT_AREA = "other"


class ArtifactLoader:
    """Builds a DbtProject from the models under `marts_path`."""

    def __init__(self, target_dir: Path, marts_path: str) -> None:
        """Read the artifacts of `target_dir`, keeping the models of `marts_path`."""
        self.target_dir = target_dir
        self.marts_path = marts_path

    def load(self) -> DbtProject:
        """Read the artifacts; the catalog is optional, the manifest is not."""
        manifest = self._read("manifest.json")
        catalog = self._read("catalog.json", required=False)

        nodes = list(manifest.get("nodes", {}).values())
        model_nodes = [
            node
            for node in nodes
            if node["resource_type"] == "model" and self._in_marts(node)
        ]
        tests = self._tests_by_model(nodes, {node["name"] for node in model_nodes})
        catalog_nodes = catalog.get("nodes", {})
        return DbtProject(
            self._model(
                node, tests[node["name"]], catalog_nodes.get(node["unique_id"]) or {}
            )
            for node in model_nodes
        )

    def _read(self, file_name: str, *, required: bool = True) -> Node:
        path = self.target_dir / file_name
        if not path.exists():
            if required:
                msg = f"{path} not found: run `dbt docs generate` first"
                raise ArtifactError(msg)
            return {}
        try:
            data: Node = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as error:
            msg = f"Cannot read {path}: {error}"
            raise ArtifactError(msg) from error
        return data

    def _in_marts(self, node: Node) -> bool:
        return _file_path(node).startswith(self.marts_path)

    def _area(self, node: Node) -> str:
        """Return the folder right under the marts path (e.g. "core", "sales")."""
        parts = _file_path(node)[len(self.marts_path) :].split("/")
        return parts[0] if len(parts) > 1 else ROOT_AREA

    @staticmethod
    def _tests_by_model(
        nodes: Iterable[Node], model_names: set[str]
    ) -> dict[str, list[DataTest]]:
        """Group the generic tests by the name of the model they are attached to."""
        tests: dict[str, list[DataTest]] = defaultdict(list)
        for node in nodes:
            metadata = node.get("test_metadata")
            attached = node.get("attached_node")
            if node["resource_type"] != "test" or not metadata or not attached:
                continue
            model_name = attached.split(".")[-1]
            if model_name in model_names:
                tests[model_name].append(
                    DataTest(
                        name=metadata["name"],
                        column_name=node.get("column_name"),
                        kwargs=metadata.get("kwargs") or {},
                        where=(node.get("config") or {}).get("where"),
                    )
                )
        return tests

    def _model(self, node: Node, tests: list[DataTest], catalog_node: Node) -> Model:
        meta = _meta(node)
        name = node["name"]
        return Model(
            unique_id=node["unique_id"],
            name=name,
            relation=f"{node['schema']}.{node.get('alias') or name}",
            title=meta.get("business_name") or name,
            description=collapse_whitespace(
                meta.get("business_description") or node.get("description")
            ),
            area=self._area(node),
            hidden=bool(meta.get("hidden")),
            columns=self._columns(node, catalog_node),
            tests=tuple(tests),
        )

    @staticmethod
    def _columns(node: Node, catalog_node: Node) -> tuple[Column, ...]:
        """List the columns in database order, then those only in the yml files.

        A stale or missing catalog must not hide a documented column.
        """
        in_database = {
            name.lower(): column
            for name, column in (catalog_node.get("columns") or {}).items()
        }
        documented = {
            name.lower(): spec for name, spec in (node.get("columns") or {}).items()
        }
        order = sorted(in_database, key=lambda key: in_database[key].get("index", 0))
        order += [key for key in documented if key not in in_database]

        columns = []
        for key in order:
            database = in_database.get(key, {})
            spec = documented.get(key, {})
            meta = _meta(spec)
            columns.append(
                Column(
                    name=database.get("name") or spec.get("name") or key,
                    description=collapse_whitespace(
                        meta.get("business_description") or spec.get("description")
                    ),
                    data_type=database.get("type") or "",
                    hidden=bool(meta.get("hidden")),
                )
            )
        return tuple(columns)


def _meta(node: Node) -> dict[str, Any]:
    """Merge the meta of a node or column: dbt fills `meta` and `config.meta`."""
    meta = dict((node.get("config") or {}).get("meta") or {})
    meta.update(node.get("meta") or {})
    return meta


def _file_path(node: Node) -> str:
    return str(node["original_file_path"]).replace("\\", "/")
