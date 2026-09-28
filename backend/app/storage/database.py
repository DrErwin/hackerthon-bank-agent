"""SQLite file locations and transaction helpers for the local demo."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from typing import Iterator


@dataclass(frozen=True)
class StoragePaths:
    directory: Path

    @classmethod
    def from_env(cls) -> "StoragePaths":
        return cls(Path(os.environ.get("BANK_AGENT_DATA_DIR", Path.home() / ".ai-banking-agent")))

    @property
    def application(self) -> Path:
        return self.directory / "application.sqlite3"

    @property
    def bank(self) -> Path:
        return self.directory / "mock_bank.sqlite3"


def parameter_digest(parameters: dict) -> str:
    encoded = json.dumps(parameters, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


@contextmanager
def transaction(path: Path) -> Iterator[sqlite3.Connection]:
    connection = connect(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()
