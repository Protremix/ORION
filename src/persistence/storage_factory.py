"""ORION Physical Intelligence OS - Storage Factory Subsystem.
Architecture Version: v0.5 (Luna Phase 3 Condition C1 Compliance)

Provides a factory pattern for instantiating the appropriate persistence layer.
Attempts to instantiate PostgresStorageManager, and automatically falls back to
SQLite StorageManager if PostgreSQL is unavailable.

License: Apache 2.0
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union

try:
    from src.persistence.postgres_storage import PostgresStorageManager
except ImportError:
    PostgresStorageManager = None
from src.persistence.storage import StorageManager

logger = logging.getLogger("orion.persistence.factory")


class StorageFactory:
    """Factory for creating persistent storage managers with automatic fallback."""

    @staticmethod
    def create_storage_manager(
        prefer_postgres: bool = True,
        db_path: Union[str, Path] = ":memory:",
        pg_dsn: Optional[str] = None,
        pg_config: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Union[PostgresStorageManager, StorageManager]:
        """Instantiates PostgresStorageManager if available, falling back to SQLite StorageManager.

        Args:
            prefer_postgres: If True, attempts to connect to PostgreSQL first.
            db_path: SQLite database file path used for fallback or when SQLite is preferred.
            pg_dsn: Optional PostgreSQL connection DSN.
            pg_config: Optional dictionary with PostgreSQL connection options.
            **kwargs: Additional parameters passed to storage manager.

        Returns:
            An initialized PostgresStorageManager or StorageManager instance.
        """
        if prefer_postgres and PostgresStorageManager is not None:
            try:
                config = dict(pg_config or {})
                if pg_dsn:
                    config["dsn"] = pg_dsn
                config.update(kwargs)
                pg_manager = PostgresStorageManager(**config)
                logger.info("Successfully initialized PostgreSQL StorageManager.")
                return pg_manager
            except Exception as e:
                logger.warning(
                    f"PostgreSQL storage unavailable ({e}). Falling back to SQLite StorageManager."
                )

        logger.info(f"Initializing SQLite StorageManager with db_path='{db_path}'.")
        return StorageManager(db_path=db_path)


def get_storage_manager(
    prefer_postgres: bool = True,
    db_path: Union[str, Path] = ":memory:",
    pg_dsn: Optional[str] = None,
    pg_config: Optional[Dict[str, Any]] = None,
    **kwargs
) -> Union[PostgresStorageManager, StorageManager]:
    """Helper function to create a storage manager instance with automatic fallback."""
    return StorageFactory.create_storage_manager(
        prefer_postgres=prefer_postgres,
        db_path=db_path,
        pg_dsn=pg_dsn,
        pg_config=pg_config,
        **kwargs
    )
