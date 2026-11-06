"""Tests of the dbt domain model and the artifact loader."""

from collections.abc import Iterable
from pathlib import Path

import pytest

from dbt_to_wikijs_docs import ArtifactError
from dbt_to_wikijs_docs.dbt import (
    ArtifactLoader,
    Column,
    DataTest,
    DbtProject,
    Model,
    Relationship,
)
from tests.factories import data_test_node, model_node, write_project


def make_model(
    name: str, *, hidden: bool = False, tests: Iterable[DataTest] = ()
) -> Model:
    """Build a model with only what the relationship graph looks at."""
    return Model(
        unique_id=f"model.p.{name}",
        name=name,
        relation=f"marts.{name}",
        title=name,
        description="",
        area="core",
        hidden=hidden,
        tests=tuple(tests),
    )


def link(column: str, to: str) -> DataTest:
    """Build a relationships test from `column` to the model `to`."""
    return DataTest("relationships", column, {"to": f"ref('{to}')"})


class TestDataTest:
    """DataTest reads the arguments of the generic tests."""

    def test_referenced_model(self) -> None:
        """Only ref() targets are models of the project."""
        assert link("a", "dim_dates").referenced_model == "dim_dates"
        source = DataTest("relationships", "a", {"to": "source('raw', 'x')"})
        assert source.referenced_model is None

    def test_unique_combination_only_at_model_level(self) -> None:
        """A combination test attached to a column is not a row key."""
        kwargs = {"combination_of_columns": ["a", "b"]}
        model_level = DataTest("unique_combination_of_columns", None, kwargs)
        column_level = DataTest("unique_combination_of_columns", "a", kwargs)
        assert model_level.unique_combination == ("a", "b")
        assert column_level.unique_combination is None

    def test_applies_to_is_case_insensitive(self) -> None:
        """The database may spell a column differently from dbt."""
        assert DataTest("not_null", "Shop_ID").applies_to(Column("SHOP_ID"))


class TestRelationshipGraph:
    """RelationshipGraph links visible models."""

    def test_follows_one_hop_through_hidden_models(self) -> None:
        """A link to a hidden bridge becomes links to what the bridge points to."""
        project = DbtProject(
            [
                make_model(
                    "fct_sales",
                    tests=[link("shop_id", "dim_shops"), link("bridge_id", "bridge")],
                ),
                make_model(
                    "bridge", hidden=True, tests=[link("product_id", "dim_products")]
                ),
                make_model("dim_shops"),
                make_model("dim_products"),
            ]
        )
        graph = project.relationships
        through_bridge = Relationship(
            "fct_sales", "dim_products", "bridge_id", through="bridge"
        )

        assert graph.outgoing("fct_sales") == [
            Relationship("fct_sales", "dim_shops", "shop_id"),
            through_bridge,
        ]
        assert graph.incoming("dim_products") == [through_bridge]
        assert graph.outgoing("bridge") == []

    def test_ignores_self_links_and_models_outside_the_project(self) -> None:
        """Parent-child links and links to staging models are not shown."""
        model = make_model(
            "dim_a", tests=[link("parent_id", "dim_a"), link("x_id", "stg_x")]
        )
        assert DbtProject([model]).relationships.outgoing("dim_a") == []


class TestArtifactLoader:
    """ArtifactLoader turns manifest.json and catalog.json into a DbtProject."""

    def test_missing_manifest(self, tmp_path: Path) -> None:
        """The error says how to produce the artifacts."""
        with pytest.raises(ArtifactError, match="dbt docs generate"):
            ArtifactLoader(tmp_path, "models/marts/").load()

    def test_reads_models_under_marts_path(self, tmp_path: Path) -> None:
        """Only marts are kept, with their area and tests."""
        target = write_project(
            tmp_path,
            {
                "a": model_node(
                    "dim_a", "models/marts/core/dim_a.sql", meta={"business_name": "A"}
                ),
                "b": model_node("stg_b", "models/staging/stg_b.sql"),
                "c": model_node("top", "models/marts/top.sql"),
                "t": data_test_node("dim_a", "not_null", "id"),
            },
        )
        project = ArtifactLoader(target, "models/marts/").load()

        assert [model.name for model in project] == ["dim_a", "top"]
        assert project["dim_a"].title == "A"
        assert project["dim_a"].area == "core"
        assert project["top"].area == "other"
        assert project["dim_a"].tests == (DataTest("not_null", "id"),)

    def test_column_order_and_names(self, tmp_path: Path) -> None:
        """Database order and spelling first, then yml-only columns."""
        columns = {
            "b": {
                "name": "b",
                "description": "B\n  text",
                "meta": {"business_description": "Business B"},
            },
            "a": {"name": "a", "config": {"meta": {"hidden": True}}},
            "yml_only": {"name": "yml_only"},
        }
        catalog = {
            "model.shop.dim_a": {
                "columns": {
                    "A": {"name": "A", "type": "int", "index": 2},
                    "B": {"name": "B", "type": "text", "index": 1},
                }
            }
        }
        target = write_project(
            tmp_path,
            {"a": model_node("dim_a", "models/marts/dim_a.sql", columns=columns)},
            catalog,
        )
        model = ArtifactLoader(target, "models/marts/").load()["dim_a"]

        assert model.columns == (
            Column("B", "Business B", "text"),
            Column("A", "", "int", hidden=True),
            Column("yml_only"),
        )
        assert [column.name for column in model.visible_columns] == ["B", "yml_only"]
