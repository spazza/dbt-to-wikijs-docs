"""The index page listing the documented models by area."""

from collections import defaultdict
from collections.abc import Iterable

from dbt_to_wikijs_docs.config import Area, Config
from dbt_to_wikijs_docs.dbt import Model
from dbt_to_wikijs_docs.page import Page
from dbt_to_wikijs_docs.rendering.links import WikiLinks
from dbt_to_wikijs_docs.rendering.markdown import MarkdownDocument
from dbt_to_wikijs_docs.text import first_sentence


class IndexPageRenderer:
    """Renders the index: one section per area, each a table of its models."""

    def __init__(self, config: Config, links: WikiLinks) -> None:
        """Render the index described by `config`, linking pages with `links`."""
        self._config = config
        self._links = links

    def render(self, models: Iterable[Model]) -> Page:
        """Return the index page listing `models`."""
        document = MarkdownDocument()
        document.add(self._config.banner)
        document.paragraph(self._config.index_intro)
        for area, members in self._group_by_area(models):
            section = self._config.areas.get(area) or Area.from_folder(area)
            document.heading(section.title)
            document.paragraph(section.description)
            document.table(
                ("Table", "Description"),
                [
                    (self._links.link_to(model.name), first_sentence(model.description))
                    for model in members
                ],
            )
        return Page(
            path=self._links.index_path,
            title=self._config.index_title,
            description=self._config.index_description,
            content=document.render(),
        )

    def _group_by_area(self, models: Iterable[Model]) -> list[tuple[str, list[Model]]]:
        """Group by area: configured areas first, in order, then the others."""
        by_area: dict[str, list[Model]] = defaultdict(list)
        for model in models:
            by_area[model.area].append(model)
        return [
            (area, sorted(by_area[area], key=self._model_order))
            for area in sorted(by_area, key=self._area_order)
        ]

    def _area_order(self, area: str) -> tuple[int, str]:
        configured = list(self._config.areas)
        rank = configured.index(area) if area in configured else len(configured)
        return (rank, area)

    def _model_order(self, model: Model) -> tuple[int, str]:
        """Sort by kind (fct_ before dim_ by default), then by business name."""
        kinds = self._config.kind_order
        kind = next(
            (
                rank
                for rank, prefix in enumerate(kinds)
                if model.name.startswith(prefix)
            ),
            len(kinds),
        )
        return (kind, model.title.lower())
