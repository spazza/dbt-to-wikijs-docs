# Copyright (c) 2026 spazza
"""All the pages documenting a dbt project."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dbt_to_wikijs_docs.dbt import ArtifactLoader
from dbt_to_wikijs_docs.rendering.index_page import IndexPageRenderer
from dbt_to_wikijs_docs.rendering.links import WikiLinks
from dbt_to_wikijs_docs.rendering.model_page import ModelPageRenderer
from dbt_to_wikijs_docs.rendering.rules import RuleDescriber

if TYPE_CHECKING:
    from dbt_to_wikijs_docs.config import Config
    from dbt_to_wikijs_docs.dbt import DbtProject
    from dbt_to_wikijs_docs.page import Page


class DocumentationSite:
    """One page per visible model, plus the index page."""

    def __init__(self, config: Config, project: DbtProject) -> None:
        """Document `project` as described by `config`."""
        self.config = config
        self.project = project
        links = WikiLinks(config.path_prefix, project)
        self._model_renderer = ModelPageRenderer(
            config, project, links, RuleDescriber(project)
        )
        self._index_renderer = IndexPageRenderer(config, links)

    @classmethod
    def from_artifacts(cls, config: Config) -> DocumentationSite:
        """Document the dbt project whose artifacts are in `config.target_dir`."""
        loader = ArtifactLoader(config.target_dir, config.marts_path)
        return cls(config, loader.load())

    def pages(self) -> list[Page]:
        """Return the model pages sorted by model name, then the index."""
        models = self.project.visible_models
        model_pages = [self._model_renderer.render(model) for model in models]
        return [*model_pages, self._index_renderer.render(models)]
