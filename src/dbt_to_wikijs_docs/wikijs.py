"""Minimal Wiki.js 2.x GraphQL client: the page operations the publisher needs."""

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from dbt_to_wikijs_docs.errors import WikiJsError
from dbt_to_wikijs_docs.page import Page

_LIST_PAGES = """
query ($locale: String) {
  pages { list(locale: $locale, limit: 100000) { id path tags } } }"""

_PAGE_CONTENT = """
query ($id: Int!) {
  pages { single(id: $id) { content title description } } }"""

_CREATE_PAGE = """
mutation ($content: String!, $description: String!, $path: String!, $title: String!,
          $tags: [String]!, $locale: String!) {
  pages { create(content: $content, description: $description, editor: "markdown",
                 isPublished: true, isPrivate: false, locale: $locale, path: $path,
                 tags: $tags, title: $title) {
    responseResult { succeeded errorCode slug message } } } }"""

_UPDATE_PAGE = """
mutation ($id: Int!, $content: String!, $description: String!, $title: String!,
          $tags: [String]!) {
  pages { update(id: $id, content: $content, description: $description,
                 editor: "markdown", isPublished: true, tags: $tags, title: $title) {
    responseResult { succeeded errorCode slug message } } } }"""

_DELETE_PAGE = """
mutation ($id: Int!) {
  pages { delete(id: $id) {
    responseResult { succeeded errorCode slug message } } } }"""

_SCHEMES = ("http", "https")


@dataclass(frozen=True)
class WikiPage:
    """An existing page, as listed by Wiki.js."""

    id: int
    path: str
    tags: tuple[str, ...] = ()

    def has_tag(self, tag: str) -> bool:
        """Whether the page carries `tag`."""
        return tag in self.tags


@dataclass(frozen=True)
class WikiPageContent:
    """The editable part of an existing page."""

    title: str
    description: str
    content: str

    def matches(self, page: Page) -> bool:
        """Whether saving `page` would change nothing."""
        return (self.title, self.description, self.content) == (
            page.title,
            page.description,
            page.content,
        )


class WikiJsClient:
    """Reads and writes pages through the Wiki.js GraphQL API.

    The API key needs read and write access to the pages it touches
    (Wiki.js: Administration > API Access).
    """

    def __init__(
        self, url: str, api_key: str, *, user_agent: str, timeout: float = 60
    ) -> None:
        """Connect to the Wiki.js at `url` (http or https)."""
        if urllib.parse.urlsplit(url).scheme not in _SCHEMES:
            msg = f"Wiki.js URL must start with http:// or https://: {url}"
            raise WikiJsError(msg)
        self.endpoint = url.rstrip("/") + "/graphql"
        self._api_key = api_key
        # Cloudflare's Browser Integrity Check rejects urllib's default
        # "Python-urllib/3.x" signature (HTTP 403, error code 1010)
        self._user_agent = user_agent
        self._timeout = timeout

    def list_pages(self, locale: str) -> dict[str, WikiPage]:
        """Return every page of the locale, keyed by path."""
        data = self._execute(_LIST_PAGES, {"locale": locale})
        return {
            page["path"]: WikiPage(
                id=page["id"], path=page["path"], tags=tuple(page.get("tags") or ())
            )
            for page in data["pages"]["list"]
        }

    def page_content(self, page_id: int) -> WikiPageContent:
        """Return the title, description and content of a page."""
        page = self._execute(_PAGE_CONTENT, {"id": page_id})["pages"]["single"]
        return WikiPageContent(
            title=page["title"],
            description=page["description"],
            content=page["content"],
        )

    def create_page(self, page: Page, *, tags: list[str], locale: str) -> None:
        """Create `page`, published and public."""
        data = self._execute(
            _CREATE_PAGE,
            {
                "path": page.path,
                "title": page.title,
                "description": page.description,
                "content": page.content,
                "tags": tags,
                "locale": locale,
            },
        )
        self._check(data["pages"]["create"], "create", page.path)

    def update_page(self, page_id: int, page: Page, *, tags: list[str]) -> None:
        """Replace the title, description, content and tags of a page."""
        data = self._execute(
            _UPDATE_PAGE,
            {
                "id": page_id,
                "title": page.title,
                "description": page.description,
                "content": page.content,
                "tags": tags,
            },
        )
        self._check(data["pages"]["update"], "update", page.path)

    def delete_page(self, page: WikiPage) -> None:
        """Delete a page."""
        data = self._execute(_DELETE_PAGE, {"id": page.id})
        self._check(data["pages"]["delete"], "delete", page.path)

    def _execute(self, query: str, variables: Mapping[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(  # noqa: S310 - scheme checked in __init__
            self.endpoint,
            data=json.dumps({"query": query, "variables": variables}).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
                "User-Agent": self._user_agent,
            },
        )
        try:
            with urllib.request.urlopen(  # noqa: S310 - scheme checked in __init__
                request, timeout=self._timeout
            ) as response:
                payload = json.loads(response.read())
        except urllib.error.HTTPError as error:
            body = error.read().decode(errors="replace")[:500]
            msg = f"Wiki.js HTTP {error.code}: {body}"
            raise WikiJsError(msg) from None
        except urllib.error.URLError as error:
            msg = f"Cannot reach Wiki.js at {self.endpoint}: {error.reason}"
            raise WikiJsError(msg) from None
        if payload.get("errors"):
            msg = f"Wiki.js GraphQL error: {payload['errors']}"
            raise WikiJsError(msg)
        data: dict[str, Any] = payload["data"]
        return data

    @staticmethod
    def _check(result: Mapping[str, Any], action: str, path: str) -> None:
        status = result["responseResult"]
        if not status["succeeded"]:
            msg = (
                f"Wiki.js refused to {action} {path}: "
                f"{status['message']} ({status['errorCode']})"
            )
            raise WikiJsError(msg)
