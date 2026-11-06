"""Publish dbt model documentation to Wiki.js."""

from importlib.metadata import version

from .publisher import main

__version__ = version("dbt-to-wikijs-docs")
__all__ = ["main", "__version__"]
