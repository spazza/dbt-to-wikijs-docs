# Copyright (c) 2026 spazza
"""The documented models of a dbt project and the relationships between them."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence

    from dbt_to_wikijs_docs.dbt.nodes import Model

# model name -> [(target model, column holding the link)]
_DirectLinks = dict[str, list[tuple[str, "str | None"]]]


@dataclass(frozen=True)
class Relationship:
    """A link from one visible model to another, declared by a relationships test."""

    source: str
    target: str
    column: str | None
    # hidden link table the relationship passes through, if any
    through: str | None = None


class DbtProject:
    """The models under the marts path, keyed by name."""

    def __init__(self, models: Iterable[Model]) -> None:
        """Index `models` by name; a later model replaces an earlier namesake."""
        self._models = {model.name: model for model in models}

    def __getitem__(self, name: str) -> Model:
        """Return the model called `name`."""
        return self._models[name]

    def __contains__(self, name: object) -> bool:
        """Whether a model is called `name`."""
        return name in self._models

    def __iter__(self) -> Iterator[Model]:
        """Iterate over the models in manifest order."""
        return iter(self._models.values())

    def __len__(self) -> int:
        """Return the number of models."""
        return len(self._models)

    @property
    def visible_models(self) -> list[Model]:
        """Models not marked `meta: {hidden: true}`, sorted by name."""
        return sorted(
            (model for model in self if not model.hidden), key=lambda model: model.name
        )

    @cached_property
    def relationships(self) -> RelationshipGraph:
        """Relationships between the visible models."""
        return RelationshipGraph.from_project(self)

    def title_of(self, name: str) -> str:
        """Return the business name of a model, or `name` if it is not a model."""
        return self._models[name].title if name in self._models else name


class RelationshipGraph:
    """Relationships between visible models, in both directions."""

    def __init__(self, relationships: Iterable[Relationship]) -> None:
        """Index `relationships` by source and by target."""
        self._outgoing: dict[str, list[Relationship]] = defaultdict(list)
        self._incoming: dict[str, list[Relationship]] = defaultdict(list)
        for relationship in relationships:
            self._outgoing[relationship.source].append(relationship)
            self._incoming[relationship.target].append(relationship)

    @classmethod
    def from_project(cls, project: DbtProject) -> RelationshipGraph:
        """Build the graph of the relationships tests of `project`.

        A hidden model (e.g. a many-to-many bridge) is not documented, so a
        link to it is replaced by links to the visible models it points to.
        """
        return cls(cls._resolve(project, cls._direct_links(project)))

    def outgoing(self, model_name: str) -> Sequence[Relationship]:
        """Return the relationships from `model_name` to other models."""
        return self._outgoing.get(model_name, [])

    def incoming(self, model_name: str) -> Sequence[Relationship]:
        """Return the relationships from other models to `model_name`."""
        return self._incoming.get(model_name, [])

    @staticmethod
    def _direct_links(project: DbtProject) -> _DirectLinks:
        """Links declared by relationships tests between two models of the project."""
        links: _DirectLinks = defaultdict(list)
        for model in project:
            for test in model.tests:
                target = test.referenced_model
                if (
                    test.is_relationship
                    and target is not None
                    and target in project
                    and target != model.name
                ):
                    links[model.name].append((target, test.column_name))
        return links

    @staticmethod
    def _resolve(project: DbtProject, links: _DirectLinks) -> Iterator[Relationship]:
        """Keep the links between visible models; follow one hop through hidden ones."""
        for source, targets in links.items():
            if project[source].hidden:
                continue
            for target, column in targets:
                if not project[target].hidden:
                    yield Relationship(source, target, column)
                    continue
                for next_target, _ in links.get(target, []):
                    if not project[next_target].hidden and next_target != source:
                        yield Relationship(source, next_target, column, through=target)
