"""The unit exchanged between rendering and publishing."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Page:
    """A rendered wiki page, ready to be written or published."""

    path: str
    title: str
    description: str
    content: str
