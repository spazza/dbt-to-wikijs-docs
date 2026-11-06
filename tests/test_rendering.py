# Copyright (c) 2026 spazza
"""Tests of the Markdown rendering."""

from __future__ import annotations

from pathlib import Path

import pytest

from dbt_to_wikijs_docs import Config, DocumentationSite
from dbt_to_wikijs_docs.dbt import DataTest, DbtProject, Model
from dbt_to_wikijs_docs.rendering.diagram import ModelDiagram
from dbt_to_wikijs_docs.rendering.markdown import MarkdownDocument
from dbt_to_wikijs_docs.rendering.rules import RuleDescriber

SNAPSHOTS = Path(__file__).parent / "snapshots"


def test_markdown_blocks_and_tables() -> None:
    """Blocks are separated by a blank line, empty ones dropped, cells escaped."""
    document = MarkdownDocument()
    document.heading("Title")
    document.paragraph("")
    document.bullets(["one", "two"])
    document.table(("", "Name"), [("a|b", "multi\nline")])
    assert document.render() == (
        "## Title\n\n- one\n- two\n\n| | Name |\n|---|---|\n| a\\|b | multi line |\n"
    )


def test_diagram_deduplicates_edges() -> None:
    """Each link is drawn once per direction; ids and labels are made safe."""
    diagram = ModelDiagram("fct.sales", 'The "sales"')
    diagram.links_to("dim_shops", "Shops")
    diagram.links_to("dim_shops", "Shops")
    diagram.linked_from("dim_shops", "Shops")
    assert diagram.render() == (
        "graph LR\n"
        "  fct_sales[\"The 'sales'\"]\n"
        '  fct_sales --> dim_shops["Shops"]\n'
        '  dim_shops["Shops"] --> fct_sales'
    )


@pytest.mark.parametrize(
    ("test", "rule"),
    [
        (DataTest("not_null", "a", where="b > 0"), "Always filled (when b > 0)"),
        (DataTest("accepted_values", "a", {"values": [1, "x"]}), "One of: 1, x"),
        (
            DataTest("relationships", "a", {"to": "ref('dim_shops')"}),
            "Links to Shops",
        ),
        (DataTest("relationships", "a", {"to": "source('raw', 'x')"}), None),
        (DataTest("expect_column_values_to_be_between", "a"), None),
    ],
)
def test_rule_describer(test: DataTest, rule: str | None) -> None:
    """Known tests become rules; others are not shown."""
    shops = Model(
        unique_id="m",
        name="dim_shops",
        relation="m.s",
        title="Shops",
        description="",
        area="core",
    )
    assert RuleDescriber(DbtProject([shops])).describe(test) == rule


@pytest.mark.usefixtures("shop_project")
def test_pages_match_snapshots() -> None:
    """Every rendering feature at once; regenerate tests/snapshots on purpose only."""
    pages = DocumentationSite.from_artifacts(Config.load()).pages()

    assert [page.path for page in pages] == [
        "team/dm/dim_products",
        "team/dm/dim_shops",
        "team/dm/fct_sales",
        "team/dm/fct_stock",
        "team/dm/root_model",
        "team/dm",
    ]
    for page in pages:
        expected = (SNAPSHOTS / f"{page.path}.md").read_text()
        assert f"<!-- title: {page.title} -->\n{page.content}" == expected, page.path
    assert pages[1].description == "Every shop we run."
