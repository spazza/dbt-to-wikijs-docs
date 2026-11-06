# Copyright (c) 2026 spazza
"""Publish business documentation of dbt models to Wiki.js.

Command line: `dbt-to-wikijs-docs` (see cli.py). As a library:

```python
config = Config.load()
pages = DocumentationSite.from_artifacts(config).pages()
client = WikiJsClient(url, api_key, user_agent=config.user_agent)
publisher = WikiJsPublisher(
    client, prefix=config.path_prefix, tag=config.tag, locale=config.locale
)
publisher.publish(pages)
```
"""

from importlib.metadata import version

from dbt_to_wikijs_docs.cli import main
from dbt_to_wikijs_docs.config import Area, Config
from dbt_to_wikijs_docs.errors import (
    ArtifactError,
    ConfigError,
    DbtToWikiJsError,
    WikiJsError,
)
from dbt_to_wikijs_docs.page import Page
from dbt_to_wikijs_docs.publishing import (
    DirectoryWriter,
    Outcome,
    PublishReport,
    WikiJsPublisher,
)
from dbt_to_wikijs_docs.rendering import DocumentationSite
from dbt_to_wikijs_docs.wikijs import WikiJsClient

__version__ = version("dbt-to-wikijs-docs")
__all__ = [
    "Area",
    "ArtifactError",
    "Config",
    "ConfigError",
    "DbtToWikiJsError",
    "DirectoryWriter",
    "DocumentationSite",
    "Outcome",
    "Page",
    "PublishReport",
    "WikiJsClient",
    "WikiJsError",
    "WikiJsPublisher",
    "__version__",
    "main",
]
