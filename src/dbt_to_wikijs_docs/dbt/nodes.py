# Copyright (c) 2026 spazza
"""The dbt objects the documentation is built from, whatever the artifact format."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

_REF = re.compile(r"ref\(\s*['\"]([^'\"]+)['\"]")


@dataclass(frozen=True)
class DataTest:
    """A generic dbt data test on a model, and optionally on one of its columns."""

    name: str
    column_name: str | None = None
    kwargs: Mapping[str, Any] = field(default_factory=dict)
    where: str | None = None

    @property
    def is_relationship(self) -> bool:
        """Whether this is a `relationships` test, linking to another model."""
        return self.name == "relationships"

    @property
    def referenced_model(self) -> str | None:
        """Model named by the `to: ref('...')` argument, if any."""
        match = _REF.search(str(self.kwargs.get("to") or ""))
        return match.group(1) if match else None

    @property
    def unique_combination(self) -> tuple[str, ...] | None:
        """Columns of a model-level `unique_combination_of_columns` test."""
        if self.name != "unique_combination_of_columns" or self.column_name:
            return None
        return tuple(self.kwargs.get("combination_of_columns") or ())

    def applies_to(self, column: Column) -> bool:
        """Whether the test checks `column`."""
        return self.column_name is not None and self.column_name.lower() == column.key


@dataclass(frozen=True)
class Column:
    """A model column as documented: yml description, database name and type."""

    name: str
    description: str = ""
    data_type: str = ""
    hidden: bool = False

    @property
    def key(self) -> str:
        """Case-insensitive identity: dbt and the database may spell it differently."""
        return self.name.lower()


@dataclass(frozen=True)
class Model:
    """A documented dbt model, with business names and columns in display order."""

    unique_id: str
    name: str
    relation: str
    title: str
    description: str
    area: str
    hidden: bool = False
    columns: tuple[Column, ...] = ()
    tests: tuple[DataTest, ...] = ()

    @property
    def visible_columns(self) -> list[Column]:
        """Columns not marked `meta: {hidden: true}`."""
        return [column for column in self.columns if not column.hidden]

    @property
    def unique_combinations(self) -> list[tuple[str, ...]]:
        """Column combinations that identify a row, from the model-level tests."""
        return [
            combination
            for test in self.tests
            if (combination := test.unique_combination) is not None
        ]

    def column(self, name: str) -> Column | None:
        """Find a column by name, ignoring case."""
        key = name.lower()
        return next((column for column in self.columns if column.key == key), None)

    def tests_on(self, column: Column) -> list[DataTest]:
        """Return the tests checking `column`, in declaration order."""
        return [test for test in self.tests if test.applies_to(column)]
