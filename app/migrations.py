"""Explicit migration entry point for disposable verification connections."""
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Connection

ROOT = Path(__file__).resolve().parent.parent


def migration_config() -> Config:
    return Config(str(ROOT / "alembic.ini"))


def migration_head() -> str:
    return ScriptDirectory.from_config(migration_config()).get_current_head()


def upgrade_connection(connection: Connection, revision: str = "head") -> None:
    config = migration_config()
    config.attributes["connection"] = connection
    command.upgrade(config, revision)
