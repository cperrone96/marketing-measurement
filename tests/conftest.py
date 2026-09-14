"""Shared pytest configuration for local database-engine test paths."""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--engine",
        action="store",
        choices=("duckdb", "postgresql"),
        default="duckdb",
        help="Database engine used to execute the SQL models.",
    )
