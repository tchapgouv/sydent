# Copyright 2026 New Vector Ltd.
#
# SPDX-License-Identifier: AGPL-3.0-only OR LicenseRef-Element-Commercial

from typing import Any, Iterable, Optional


def _convert_qmark_to_percent_s(sql: str) -> str:
    """Convert DB-API qmark placeholders to psycopg format placeholders.

    This keeps Sydent SQL queries in the existing qmark style ("?") while
    allowing execution on PostgreSQL drivers expecting "%s" placeholders.
    """
    out = []
    in_single = False
    in_double = False
    i = 0

    while i < len(sql):
        char = sql[i]

        if char == "'" and not in_double:
            if in_single and i + 1 < len(sql) and sql[i + 1] == "'":
                out.append("''")
                i += 2
                continue
            in_single = not in_single
            out.append(char)
            i += 1
            continue

        if char == '"' and not in_single:
            in_double = not in_double
            out.append(char)
            i += 1
            continue

        if char == "?" and not in_single and not in_double:
            out.append("%s")
        else:
            out.append(char)

        i += 1

    return "".join(out)


class QmarkToPyformatCursor:
    def __init__(self, cursor: Any):
        self._cursor = cursor

    def execute(self, sql: str, parameters: Optional[Iterable[Any]] = None) -> Any:
        converted = _convert_qmark_to_percent_s(sql)
        if parameters is None:
            return self._cursor.execute(converted)
        return self._cursor.execute(converted, parameters)

    def executemany(self, sql: str, seq_of_parameters: Iterable[Iterable[Any]]) -> Any:
        converted = _convert_qmark_to_percent_s(sql)
        return self._cursor.executemany(converted, seq_of_parameters)

    def __iter__(self) -> Any:
        return iter(self._cursor)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)


class QmarkToPyformatConnection:
    def __init__(self, connection: Any):
        self._connection = connection

    def cursor(self, *args: Any, **kwargs: Any) -> QmarkToPyformatCursor:
        return QmarkToPyformatCursor(self._connection.cursor(*args, **kwargs))

    def __enter__(self) -> Any:
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> Any:
        return self._connection.__exit__(exc_type, exc_value, traceback)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connection, name)
