# Copyright 2026 New Vector Ltd.
#
# SPDX-License-Identifier: AGPL-3.0-only OR LicenseRef-Element-Commercial

import sqlite3
from dataclasses import dataclass
from typing import Any, Type

from sydent.db.dbapi import SqlDialectFormatConnection
from sydent.db.postgresdb import PostgresDatabase
from sydent.db.sqlitedb import SqliteDatabase


@dataclass
class DatabaseHandles:
    connection: Any
    integrity_error: Type[Exception]


class DatabaseFactory:
    @staticmethod
    def build(sydent: Any) -> DatabaseHandles:
        db_config = sydent.config.database

        if db_config.database_type == "sqlite":
            sqlite_database = SqliteDatabase(sydent)
            return DatabaseHandles(
                connection=sqlite_database.db,
                integrity_error=sqlite3.IntegrityError,
            )

        if db_config.database_type == "postgresql":
            postgres_database = PostgresDatabase(sydent)
            connection = postgres_database.db

            try:
                import psycopg2  # type: ignore[import-not-found]
            except ImportError as exc:
                raise RuntimeError(
                    "db.type is set to 'postgresql' but psycopg2 is not installed. "
                    "Install it with 'pip install psycopg2-binary'."
                ) from exc

            return DatabaseHandles(
                connection=SqlDialectFormatConnection(connection),
                integrity_error=psycopg2.IntegrityError,
            )

        raise RuntimeError(
            "Unsupported db.type %r" % (db_config.database_type,)
        )
