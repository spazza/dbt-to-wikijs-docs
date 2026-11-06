# Copyright (c) 2026 spazza
"""The page documenting one model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dbt_to_wikijs_docs.page import Page
from dbt_to_wikijs_docs.rendering.diagram import ModelDiagram
from dbt_to_wikijs_docs.rendering.markdown import MarkdownDocument
from dbt_to_wikijs_docs.text import first_sentence

if TYPE_CHECKING:
    from dbt_to_wikijs_docs.config import Config
    from dbt_to_wikijs_docs.dbt import Column, DbtProject, Model, Relationship
    from dbt_to_wikijs_docs.rendering.links import WikiLinks
    from dbt_to_wikijs_docs.rendering.rules import RuleDescriber


class ModelPageRenderer:
    """Renders a model page: overview, connected tables and columns."""

    def __init__(
        self,
        config: Config,
        project: DbtProject,
        links: WikiLinks,
        rules: RuleDescriber,
    ) -> None:
        """Render pages with the banner of `config` and the links of `links`."""
        self._config = config
        self._project = project
        self._links = links
        self._rules = rules

    def render(self, model: Model) -> Page:
        """Return the page of `model`."""
        document = MarkdownDocument()
        document.add(self._config.banner)
        document.paragraph(model.description)
        self._add_overview(document, model)
        self._add_connections(document, model)
        self._add_columns(document, model)
        return Page(
            path=self._links.path_of(model.name),
            title=model.title,
            description=first_sentence(model.description),
            content=document.render(),
        )

    def _add_overview(self, document: MarkdownDocument, model: Model) -> None:
        rows = [("Table in the data warehouse", f"`{model.relation}`")]
        rows += [
            (
                "Each row is unique by",
                ", ".join(f"`{column}`" for column in combination),
            )
            for combination in model.unique_combinations
        ]
        document.heading("Overview")
        document.table(("", ""), rows)

    def _add_connections(self, document: MarkdownDocument, model: Model) -> None:
        graph = self._project.relationships
        outgoing, incoming = graph.outgoing(model.name), graph.incoming(model.name)
        if not outgoing and not incoming:
            return

        diagram = ModelDiagram(model.name, model.title)
        for relationship in outgoing:
            diagram.links_to(
                relationship.target, self._project.title_of(relationship.target)
            )
        for relationship in incoming:
            diagram.linked_from(
                relationship.source, self._project.title_of(relationship.source)
            )

        document.heading("Connected tables")
        document.bullets(
            [self._describe_outgoing(model, relationship) for relationship in outgoing]
            + [self._describe_incoming(relationship) for relationship in incoming]
        )
        document.code("mermaid", diagram.render())

    def _describe_outgoing(self, model: Model, relationship: Relationship) -> str:
        text = f"**{self._links.link_to(relationship.target)}**"
        if relationship.column and self._is_shown(model, relationship.column):
            text += f" through `{relationship.column}`"
        if relationship.through:
            text += f" (via the link table `{relationship.through}`)"
        return text

    def _describe_incoming(self, relationship: Relationship) -> str:
        text = f"Used by **{self._links.link_to(relationship.source)}**"
        if relationship.through:
            text += f" (via the link table `{relationship.through}`)"
        return text

    @staticmethod
    def _is_shown(model: Model, column_name: str) -> bool:
        column = model.column(column_name)
        return column is None or not column.hidden

    def _add_columns(self, document: MarkdownDocument, model: Model) -> None:
        rows = [
            (
                f"`{column.name}`",
                column.description,
                column.data_type,
                "; ".join(self._rules_of(model, column)),
            )
            for column in model.visible_columns
        ]
        if rows:
            document.heading("Columns")
            document.table(("Column", "Description", "Type", "Rules"), rows)

    def _rules_of(self, model: Model, column: Column) -> list[str]:
        return [
            rule
            for test in model.tests_on(column)
            if (rule := self._rules.describe(test))
        ]
