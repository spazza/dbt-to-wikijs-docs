# Copyright (c) 2026 spazza
"""Mermaid diagram of a model and its neighbours."""

from __future__ import annotations

import re


class ModelDiagram:
    """Mermaid flowchart centred on one model, with the models linked to and from it."""

    def __init__(self, key: str, label: str) -> None:
        """Start a diagram showing the model `key`, labelled `label`."""
        self._center = self._node_id(key)
        self._lines = [f"  {self._center}{self._label(label)}"]
        self._seen: set[tuple[str, str]] = set()

    def links_to(self, key: str, label: str) -> None:
        """Draw an arrow from the centre to `key`, once."""
        if ("to", key) not in self._seen:
            self._seen.add(("to", key))
            target = f"{self._node_id(key)}{self._label(label)}"
            self._lines.append(f"  {self._center} --> {target}")

    def linked_from(self, key: str, label: str) -> None:
        """Draw an arrow from `key` to the centre, once."""
        if ("from", key) not in self._seen:
            self._seen.add(("from", key))
            source = f"{self._node_id(key)}{self._label(label)}"
            self._lines.append(f"  {source} --> {self._center}")

    def render(self) -> str:
        """Return the Mermaid source of the diagram."""
        return "\n".join(["graph LR", *self._lines])

    @staticmethod
    def _node_id(key: str) -> str:
        return re.sub(r"\W", "_", key)

    @staticmethod
    def _label(text: str) -> str:
        return '["' + text.replace('"', "'") + '"]'
