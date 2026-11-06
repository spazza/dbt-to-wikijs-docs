# Copyright (c) 2026 spazza
r"""Publish business documentation of the dbt marts to Wiki.js (2.x).

Reads the artifacts written by `dbt docs generate` (target/manifest.json and,
when present, target/catalog.json), keeps the enabled models under the
marts path (default models/marts/) that are not marked
`meta: {hidden: true}`, and renders one Markdown page per mart plus an index
page, using the business layer in the yml files
(`config.meta.business_name` / `business_description`, column
`business_description` and `hidden`), falling back to `description`.

Settings live in the [tool.dbt-to-wikijs-docs] table of the dbt project's
pyproject.toml; command line options override them.

Usage (after `dbt docs generate`):
    # review locally, no network
    dbt-to-wikijs-docs --dry-run docs_preview

    # publish (CI step)
    WIKIJS_URL=https://wiki.example.com WIKIJS_API_KEY=... \
        dbt-to-wikijs-docs
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from dbt_to_wikijs_docs.config import TOOL_NAME, Config
from dbt_to_wikijs_docs.errors import ConfigError, DbtToWikiJsError
from dbt_to_wikijs_docs.publishing import DirectoryWriter, WikiJsPublisher
from dbt_to_wikijs_docs.rendering import DocumentationSite
from dbt_to_wikijs_docs.wikijs import WikiJsClient

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence

URL_VARIABLE = "WIKIJS_URL"
API_KEY_VARIABLE = "WIKIJS_API_KEY"

logger = logging.getLogger("dbt_to_wikijs_docs")


def build_parser() -> argparse.ArgumentParser:
    """Return the command line parser; its defaults are None so config can apply."""
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description=(__doc__ or "").split("\n\n", maxsplit=1)[0],
        epilog=(
            f"Defaults come from [tool.{TOOL_NAME}] in pyproject.toml; "
            "options given here override them."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="pyproject.toml to read settings from (default: ./pyproject.toml)",
    )
    parser.add_argument(
        "--target-dir", type=Path, help="dbt target directory (default: target)"
    )
    parser.add_argument(
        "--marts-path", help="folder of the documented models (default: models/marts/)"
    )
    parser.add_argument(
        "--path-prefix", help="Wiki.js path of the section (default: data-model)"
    )
    parser.add_argument("--locale", help="Wiki.js locale (default: en)")
    parser.add_argument(
        "--tag", help="tag marking generated pages (default: dbt-generated)"
    )
    parser.add_argument(
        "--dry-run",
        metavar="DIR",
        type=Path,
        help="write the Markdown pages to DIR instead of publishing",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line and return its exit code."""
    args = build_parser().parse_args(argv)
    with _console_logging():
        try:
            return _run(args)
        except DbtToWikiJsError as error:
            failure = error
        # logged outside the except block: the message is enough, no traceback
        logger.error("%s: error: %s", TOOL_NAME, failure)
        return 1


def _run(args: argparse.Namespace) -> int:
    config = Config.load(
        args.config,
        target_dir=args.target_dir,
        marts_path=args.marts_path,
        path_prefix=args.path_prefix,
        locale=args.locale,
        tag=args.tag,
    )
    pages = DocumentationSite.from_artifacts(config).pages()

    if args.dry_run:
        DirectoryWriter(args.dry_run).write(pages)
        logger.info(
            "Wrote %d pages to %s/%s", len(pages), args.dry_run, config.path_prefix
        )
        return 0

    publisher = WikiJsPublisher(
        _client(config),
        prefix=config.path_prefix,
        tag=config.tag,
        locale=config.locale,
    )
    logger.info(publisher.publish(pages).summary())
    return 0


def _client(config: Config) -> WikiJsClient:
    url = os.environ.get(URL_VARIABLE) or config.url
    api_key = os.environ.get(API_KEY_VARIABLE)
    if not url or not api_key:
        msg = (
            f"Set {URL_VARIABLE} (or `url` in the config) and {API_KEY_VARIABLE}, "
            "or use --dry-run."
        )
        raise ConfigError(msg)
    return WikiJsClient(url, api_key, user_agent=config.user_agent)


@contextmanager
def _console_logging() -> Generator[None, None, None]:
    """Show progress on stdout and errors on stderr while the command runs."""
    stdout = logging.StreamHandler(sys.stdout)
    stdout.addFilter(lambda record: record.levelno < logging.ERROR)
    stderr = logging.StreamHandler(sys.stderr)
    stderr.setLevel(logging.ERROR)
    handlers = (stdout, stderr)

    previous_level = logger.level
    logger.setLevel(logging.INFO)
    for handler in handlers:
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    try:
        yield
    finally:
        for handler in handlers:
            logger.removeHandler(handler)
        logger.setLevel(previous_level)
