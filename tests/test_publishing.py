"""Tests of the dry-run writer and the Wiki.js publisher."""

import logging
from pathlib import Path

import pytest

from dbt_to_wikijs_docs import DirectoryWriter, Outcome, Page, WikiJsPublisher
from dbt_to_wikijs_docs.wikijs import WikiPage, WikiPageContent

TAG = "dbt-generated"


class FakeWikiPageStore:
    """In-memory WikiPageStore that records every call."""

    def __init__(self, pages: list[tuple[WikiPage, WikiPageContent]]) -> None:
        """Hold the existing `pages`."""
        self.pages = pages
        self.calls: list[tuple[object, ...]] = []

    def list_pages(self, locale: str) -> dict[str, WikiPage]:
        """Return the existing pages by path."""
        self.calls.append(("list", locale))
        return {page.path: page for page, _ in self.pages}

    def page_content(self, page_id: int) -> WikiPageContent:
        """Return the content of an existing page."""
        return next(content for page, content in self.pages if page.id == page_id)

    def create_page(self, page: Page, *, tags: list[str], locale: str) -> None:
        """Record a creation."""
        self.calls.append(("create", page.path, tuple(tags), locale))

    def update_page(self, page_id: int, page: Page, *, tags: list[str]) -> None:
        """Record an update."""
        self.calls.append(("update", page_id, page.path, tuple(tags)))


def existing(
    page_id: int, path: str, content: str, tags: tuple[str, ...] = (TAG,)
) -> tuple[WikiPage, WikiPageContent]:
    """Build a page already in Wiki.js."""
    return WikiPage(page_id, path, tags), WikiPageContent(path, "", content)


def test_publish_rules(caplog: pytest.LogCaptureFixture) -> None:
    """Create new pages, update changed ones, never touch hand-written ones."""
    pages = [
        Page("dm/new", "dm/new", "", "new"),
        Page("dm/same", "dm/same", "", "same"),
        Page("dm/manual", "dm/manual", "", "generated"),
        Page("dm", "dm", "", "index v2"),
    ]
    store = FakeWikiPageStore(
        [
            existing(1, "dm", "index v1"),
            existing(2, "dm/same", "same"),
            existing(3, "dm/manual", "by hand", tags=()),
            existing(4, "dm/gone", "x"),
            existing(5, "other/gone", "x"),
        ]
    )
    publisher = WikiJsPublisher(store, prefix="dm", tag=TAG, locale="en")

    with caplog.at_level(logging.INFO):
        report = publisher.publish(pages)

    assert store.calls == [
        ("list", "en"),
        ("create", "dm/new", (TAG,), "en"),
        ("update", 1, "dm", (TAG,)),
    ]
    assert report.outcomes == {
        "dm/new": Outcome.CREATED,
        "dm/same": Outcome.UNCHANGED,
        "dm/manual": Outcome.SKIPPED,
        "dm": Outcome.UPDATED,
    }
    assert report.stale == ["dm/gone"]
    assert report.summary() == (
        "Done: 1 created, 1 updated, 1 unchanged, 1 skipped, 1 stale."
    )
    assert "SKIPPED   dm/manual" in caplog.text


def test_directory_writer(tmp_path: Path) -> None:
    """Each page becomes <wiki path>.md with its title in a comment."""
    written = DirectoryWriter(tmp_path).write([Page("dm/a", "A", "", "body\n")])
    assert written == [tmp_path / "dm" / "a.md"]
    assert written[0].read_text() == "<!-- title: A -->\nbody\n"
