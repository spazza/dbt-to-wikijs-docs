"""Writing the rendered pages to a local folder (dry run) or to Wiki.js."""

import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Protocol

from dbt_to_wikijs_docs.page import Page
from dbt_to_wikijs_docs.wikijs import WikiPage, WikiPageContent

logger = logging.getLogger(__name__)


class WikiPageStore(Protocol):
    """The page operations WikiJsPublisher needs; WikiJsClient provides them."""

    def list_pages(self, locale: str) -> dict[str, WikiPage]:
        """Return every page of the locale, keyed by path."""
        ...

    def page_content(self, page_id: int) -> WikiPageContent:
        """Return the title, description and content of a page."""
        ...

    def create_page(self, page: Page, *, tags: list[str], locale: str) -> None:
        """Create `page`."""
        ...

    def update_page(self, page_id: int, page: Page, *, tags: list[str]) -> None:
        """Replace the content of a page."""
        ...


class DirectoryWriter:
    """Writes each page to <directory>/<wiki path>.md, for review without network."""

    def __init__(self, directory: Path) -> None:
        """Write the pages under `directory`."""
        self.directory = directory

    def write(self, pages: Iterable[Page]) -> list[Path]:
        """Write `pages`, with their title in a comment, and return the files."""
        written = []
        for page in pages:
            file = self.directory / f"{page.path}.md"
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(f"<!-- title: {page.title} -->\n{page.content}")
            written.append(file)
        return written


class Outcome(Enum):
    """What publishing did to one page."""

    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"
    SKIPPED = "skipped"


@dataclass
class PublishReport:
    """What publishing did to each page, and the generated pages left behind."""

    outcomes: dict[str, Outcome] = field(default_factory=dict)
    stale: list[str] = field(default_factory=list)

    def count(self, outcome: Outcome) -> int:
        """Return the number of pages with `outcome`."""
        return sum(1 for value in self.outcomes.values() if value is outcome)

    def summary(self) -> str:
        """Return a one-line summary of the counts."""
        counts = ", ".join(
            f"{self.count(outcome)} {outcome.value}" for outcome in Outcome
        )
        return f"Done: {counts}, {len(self.stale)} stale."


class WikiJsPublisher:
    """Publishes pages to Wiki.js without ever losing hand-written content.

    * every generated page carries `tag`; an existing page at the same path
      without it was written by hand and is never overwritten;
    * a page is only saved when it changed, so the page history only records
      real documentation changes;
    * nothing is deleted: generated pages under `prefix` that are no longer
      rendered are reported as stale.
    """

    def __init__(
        self, client: WikiPageStore, *, prefix: str, tag: str, locale: str
    ) -> None:
        """Publish through `client` the pages under `prefix`, marked with `tag`."""
        self._client = client
        self._prefix = prefix
        self._tag = tag
        self._locale = locale

    def publish(self, pages: Sequence[Page]) -> PublishReport:
        """Create or update `pages`, then report the stale generated pages."""
        existing = self._client.list_pages(self._locale)
        report = PublishReport()
        for page in pages:
            current = existing.get(page.path)
            report.outcomes[page.path] = self._publish_page(page, current)
        report.stale = self._stale_paths(existing, pages)
        for path in report.stale:
            logger.warning(
                "STALE     %s: generated earlier but no longer a mart; "
                "delete it in Wiki.js if not needed",
                path,
            )
        return report

    def _publish_page(self, page: Page, current: WikiPage | None) -> Outcome:
        if current is None:
            self._client.create_page(page, tags=[self._tag], locale=self._locale)
            logger.info("created   %s", page.path)
            return Outcome.CREATED
        if not current.has_tag(self._tag):
            logger.warning(
                "SKIPPED   %s: an existing page without the '%s' tag "
                "(written by hand) is never overwritten",
                page.path,
                self._tag,
            )
            return Outcome.SKIPPED
        if self._client.page_content(current.id).matches(page):
            return Outcome.UNCHANGED
        self._client.update_page(current.id, page, tags=[self._tag])
        logger.info("updated   %s", page.path)
        return Outcome.UPDATED

    def _stale_paths(
        self, existing: Mapping[str, WikiPage], pages: Sequence[Page]
    ) -> list[str]:
        rendered = {page.path for page in pages}
        return sorted(
            path
            for path, page in existing.items()
            if page.has_tag(self._tag)
            and path.startswith(self._prefix + "/")
            and path not in rendered
        )
