"""Builders of fake dbt artifacts."""

import json
from pathlib import Path
from typing import Any

Node = dict[str, Any]


def model_node(name: str, path: str, description: str = "", **fields: object) -> Node:
    """Build a manifest model node; `meta` goes to `config.meta`, the rest as is."""
    node: Node = {
        "unique_id": f"model.shop.{name}",
        "resource_type": "model",
        "name": name,
        "original_file_path": path,
        "schema": "marts",
        "alias": None,
        "description": description,
        "config": {"meta": fields.pop("meta", {})},
        "meta": {},
        "columns": {},
    }
    node.update(fields)
    return node


def data_test_node(
    model_name: str,
    name: str,
    column: str | None = None,
    kwargs: dict[str, object] | None = None,
    where: str | None = None,
) -> Node:
    """Build a manifest node of a generic test attached to `model_name`."""
    return {
        "resource_type": "test",
        "attached_node": f"model.shop.{model_name}",
        "column_name": column,
        "test_metadata": {"name": name, "kwargs": kwargs or {}},
        "config": {"where": where} if where else {},
    }


def write_project(
    root: Path,
    nodes: dict[str, Node],
    catalog: dict[str, Node] | None = None,
    pyproject: str | None = None,
) -> Path:
    """Write target/manifest.json, and catalog.json and pyproject.toml if given."""
    target = root / "target"
    target.mkdir(parents=True)
    (target / "manifest.json").write_text(json.dumps({"nodes": nodes}))
    if catalog is not None:
        (target / "catalog.json").write_text(json.dumps({"nodes": catalog}))
    if pyproject is not None:
        (root / "pyproject.toml").write_text(pyproject)
    return target
