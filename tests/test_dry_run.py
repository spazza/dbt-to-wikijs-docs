import json

from dbt_to_wikijs_docs import main


def model(name, path, description, meta=None, columns=None):
    return {
        "unique_id": f"model.shop.{name}",
        "resource_type": "model",
        "name": name,
        "original_file_path": path,
        "schema": "marts",
        "alias": name,
        "description": description,
        "config": {"meta": meta or {}},
        "meta": {},
        "columns": columns or {},
    }


def relationship(model_name, column, to):
    return {
        "resource_type": "test",
        "attached_node": f"model.shop.{model_name}",
        "column_name": column,
        "test_metadata": {"name": "relationships", "kwargs": {"to": f"ref('{to}')"}},
        "config": {},
    }


def dbt_project(tmp_path):
    nodes = {
        "a": model("dim_shops", "models/gold/core/dim_shops.sql", "One row per shop.", {"business_name": "Shops"}),
        "b": model(
            "fct_sales",
            "models/gold/sales/fct_sales.sql",
            "One row per sale. More details.",
            columns={"shop_id": {"name": "shop_id", "description": "The shop."}},
        ),
        "c": model("int_hidden", "models/gold/sales/int_hidden.sql", "Hidden.", {"hidden": True}),
        "d": model("stg_x", "models/staging/stg_x.sql", "Not a mart."),
        "t": relationship("fct_sales", "shop_id", "dim_shops"),
    }
    target = tmp_path / "target"
    target.mkdir()
    (target / "manifest.json").write_text(json.dumps({"nodes": nodes}))
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.dbt-to-wikijs-docs]
marts-path = "models/gold"
path-prefix = "team/data-model"
index-title = "Our data"

[tool.dbt-to-wikijs-docs.areas]
sales = { title = "Sales", description = "Sales transactions." }
core = "Core"
"""
    )


def test_dry_run(tmp_path, monkeypatch, capsys):
    dbt_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    assert main(["--dry-run", "out"]) == 0

    out = tmp_path / "out" / "team" / "data-model"
    assert sorted(p.name for p in out.iterdir()) == ["dim_shops.md", "fct_sales.md"]
    index = (tmp_path / "out" / "team" / "data-model.md").read_text()
    assert index.startswith("<!-- title: Our data -->")
    # configured area order: sales before core
    assert index.index("## Sales") < index.index("## Core")
    assert "[Shops](/team/data-model/dim_shops)" in index
    sales = (out / "fct_sales.md").read_text()
    assert "**[Shops](/team/data-model/dim_shops)** through `shop_id`" in sales
    assert "Wrote 3 pages" in capsys.readouterr().out
