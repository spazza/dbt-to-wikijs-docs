# Copyright (c) 2026 spazza
"""Generic dbt tests explained as business rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from dbt_to_wikijs_docs.dbt import DataTest, DbtProject


class RuleDescriber:
    """Turns the generic dbt tests of a column into rules a business reader gets.

    Tests without a description here (custom or package tests) are not shown.
    """

    def __init__(self, project: DbtProject) -> None:
        """Describe tests of `project`, naming linked models by business name."""
        self._project = project
        self._describers: dict[str, Callable[[DataTest], str | None]] = {
            "not_null": lambda _test: "Always filled",
            "unique": lambda _test: "Unique",
            "accepted_values": self._accepted_values,
            "relationships": self._relationship,
        }

    def describe(self, test: DataTest) -> str | None:
        """Return the rule checked by `test`, or None if it has no description."""
        describer = self._describers.get(test.name)
        text = describer(test) if describer else None
        if text and test.where:
            text += f" (when {test.where})"
        return text

    @staticmethod
    def _accepted_values(test: DataTest) -> str:
        values = test.kwargs.get("values") or []
        return "One of: " + ", ".join(str(value) for value in values)

    def _relationship(self, test: DataTest) -> str | None:
        target = test.referenced_model
        return f"Links to {self._project.title_of(target)}" if target else None
