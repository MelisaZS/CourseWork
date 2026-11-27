
"""Shared pytest fixtures for test isolation."""

import pytest

import config


@pytest.fixture(autouse=True)
def isolate_database(tmp_path_factory, monkeypatch):
    """Use a separate temporary database for every test."""
    db_dir = tmp_path_factory.mktemp("db_isolation")
    monkeypatch.setattr(
        config,
        "DB_PATH",
        db_dir / "company.db",
    )
