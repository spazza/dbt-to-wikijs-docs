"""Exceptions raised by the package; the command line turns them into a message."""


class DbtToWikiJsError(Exception):
    """Base class of every error raised on purpose by this package."""


class ConfigError(DbtToWikiJsError):
    """The [tool.dbt-to-wikijs-docs] settings cannot be read or are invalid."""


class ArtifactError(DbtToWikiJsError):
    """The dbt artifacts are missing or cannot be read."""


class WikiJsError(DbtToWikiJsError):
    """Wiki.js cannot be reached or rejected a request."""
