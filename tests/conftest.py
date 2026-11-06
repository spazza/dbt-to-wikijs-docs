# Copyright (c) 2026 spazza
"""Shared fixtures."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.factories import data_test_node, model_node, write_project

if TYPE_CHECKING:
    from pathlib import Path

SHOP_PYPROJECT = """
[tool.dbt-to-wikijs-docs]
path-prefix = "team/dm"

[tool.dbt-to-wikijs-docs.areas]
sales = { title = "Sales", description = "Sales transactions." }
core = "Core"
"""


@pytest.fixture
def shop_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a project covering every rendering feature, and move into it.

    tests/snapshots holds its expected pages.
    """
    nodes = [
        model_node(
            "dim_shops",
            "models/marts/core/dim_shops.sql",
            "One row per shop. Extra.",
            meta={
                "business_name": "Shops",
                "business_description": "Every shop we run. Open or closed.",
            },
            columns={
                "shop_id": {"name": "shop_id", "description": "Key | id"},
                "secret": {"name": "secret", "meta": {"hidden": True}},
            },
        ),
        model_node(
            "fct_sales",
            "models/marts/sales/fct_sales.sql",
            "One row per sale.",
            alias="sales",
            columns={
                "shop_id": {"name": "shop_id", "description": "The shop."},
                "status": {"name": "status", "description": "multi\nline"},
                "yml_only": {"name": "yml_only", "description": "Not in catalog"},
            },
        ),
        model_node(
            "bridge_x",
            "models/marts/sales/bridge_x.sql",
            "Bridge.",
            meta={"hidden": True},
        ),
        model_node(
            "dim_products", "models/marts/core/dim_products.sql", 'Products "quoted".'
        ),
        model_node("fct_stock", "models/marts/warehouse_stock/fct_stock.sql", "Stock."),
        model_node("root_model", "models/marts/root_model.sql", "At root."),
        model_node("stg_x", "models/staging/stg_x.sql", "Staging."),
        data_test_node(
            "fct_sales",
            "relationships",
            "shop_id",
            {"to": "ref('dim_shops')", "field": "shop_id"},
        ),
        data_test_node("fct_sales", "not_null", "shop_id"),
        data_test_node(
            "fct_sales",
            "accepted_values",
            "status",
            {"values": ["open", "closed"]},
            where="shop_id is not null",
        ),
        data_test_node(
            "fct_sales",
            "unique_combination_of_columns",
            None,
            {"combination_of_columns": ["shop_id", "status"]},
        ),
        data_test_node(
            "fct_sales", "relationships", "bridge_id", {"to": "ref('bridge_x')"}
        ),
        data_test_node(
            "bridge_x", "relationships", "product_id", {"to": "ref('dim_products')"}
        ),
        data_test_node("dim_shops", "unique", "shop_id"),
        data_test_node("dim_shops", "custom_thing", "shop_id"),
        data_test_node(
            "fct_stock", "relationships", "product_id", {"to": 'ref("dim_products")'}
        ),
    ]
    catalog = {
        "model.shop.fct_sales": {
            "columns": {
                "STATUS": {"name": "STATUS", "type": "varchar", "index": 2},
                "SHOP_ID": {"name": "SHOP_ID", "type": "int", "index": 1},
                "AMOUNT": {"name": "AMOUNT", "type": "numeric", "index": 3},
            }
        }
    }
    write_project(
        tmp_path,
        {f"n{i}": node for i, node in enumerate(nodes)},
        catalog,
        SHOP_PYPROJECT,
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path
