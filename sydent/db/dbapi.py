# Copyright 2026 New Vector Ltd.
#
# SPDX-License-Identifier: AGPL-3.0-only OR LicenseRef-Element-Commercial

from typing import Any, Iterable, Optional
import re

UPSERT_TABLE_MAPPINGS = {
    "profiles": ("user_id",),
    "threepid_associations": ("medium", "address"),
    "local_threepid_associations": ("medium", "address"),
    "hashing_metadata": ("id",),
}


def _normalize_insert_column_identifiers(sql: str) -> str:
    """Normalize quoted column identifiers in INSERT column lists.

    SQLite statements in Sydent commonly use single-quoted identifiers,
    e.g. INSERT INTO t ('a', 'b') VALUES (?, ?). PostgreSQL expects
    identifiers without single quotes in this context.
    """
    match = re.search(
        r"(\bINSERT\s+INTO\s+\w+\s*\()([^)]*)(\)\s+VALUES\b)",
        sql,
        flags=re.IGNORECASE,
    )
    if not match:
        return sql

    prefix, columns_part, suffix = match.groups()
    normalized_columns = re.sub(r"'([A-Za-z_][A-Za-z0-9_]*)'", r"\1", columns_part)
    return sql[: match.start()] + prefix + normalized_columns + suffix + sql[match.end() :]

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

def _rewrite_insert_or_ignore_statement(sql: str, parameters: Optional[Iterable[Any]] = None) -> tuple[str, Optional[Iterable[Any]]]:
    """Replace "INSERT OR IGNORE" statements with PostgreSQL-compatible syntax.

    This allows us to write "INSERT OR IGNORE" in our SQL queries, which is
    supported by SQLite, and have it automatically rewritten to "INSERT ... ON
    CONFLICT DO NOTHING" for PostgreSQL.
    """
    if re.search(r"^\s*INSERT\s+OR\s+IGNORE\s+INTO\s+", sql, flags=re.IGNORECASE):
        new_sql = re.sub(r"^\s*INSERT\s+OR\s+IGNORE\s+INTO\s+", "INSERT INTO ", sql, flags=re.IGNORECASE)
        new_sql += " ON CONFLICT DO NOTHING"
        return new_sql, parameters
    return sql, parameters

def _extract_columns_from_insert(sql: str) -> tuple[str, ...] | None:
    """Extract all column names from an INSERT statement's column list.
    Handles: INSERT INTO table ('col1', 'col2', 'col3') or INSERT INTO table (col1, col2, col3)
    """
    # Match the full column list between parentheses after table name
    match = re.search(r"\(\s*([^)]+?)\s*\)\s+VALUES", sql, flags=re.IGNORECASE)
    if not match:
        return None
    col_list = match.group(1)
    # Split by comma and extract column names, handling quotes
    columns = re.findall(r"'([^']+)'|\b(\w+)\b", col_list)
    # Each match is a tuple (quoted_col, unquoted_col), one will be empty string
    result = [quoted or unquoted for quoted, unquoted in columns if quoted or unquoted]
    return tuple(result) if result else None

def _rewrite_insert_or_replace_statement(sql: str, parameters: Optional[Iterable[Any]] = None) -> tuple[str, Optional[Iterable[Any]]]:
    """Replace "INSERT OR REPLACE" statements with PostgreSQL-compatible syntax.

    This allows us to write "INSERT OR REPLACE" in our SQL queries, which is
    supported by SQLite, and have it automatically rewritten to "INSERT ... ON
    CONFLICT ... DO UPDATE" for PostgreSQL.
    """
    match = re.search(r"^\s*INSERT\s+OR\s+REPLACE\s+INTO\s+(\w+)\s*\(", sql, flags=re.IGNORECASE)
    if match:
        table = match.group(1)
        if table in UPSERT_TABLE_MAPPINGS:
            conflict_columns = UPSERT_TABLE_MAPPINGS[table]
            new_sql = re.sub(r"^\s*INSERT\s+OR\s+REPLACE\s+INTO\s+", "INSERT INTO ", sql, flags=re.IGNORECASE)
            new_sql = _normalize_insert_column_identifiers(new_sql)
            new_sql += f" ON CONFLICT ({', '.join(conflict_columns)}) DO UPDATE SET "
            columns = _extract_columns_from_insert(sql)
            if columns:
                update_columns = [f"{col} = EXCLUDED.{col}" for col in columns if col not in conflict_columns]
                new_sql += ", ".join(update_columns)
            return new_sql, parameters
        else:
            raise ValueError(f"No UPSERT mapping found for table '{table}'")
    return sql, parameters

def _rewrite_replace_into_statement(sql: str, parameters: Optional[Iterable[Any]] = None) -> tuple[str, Optional[Iterable[Any]]]:
    """Replace "REPLACE INTO" statements with PostgreSQL-compatible syntax.

    This allows us to write "REPLACE INTO" in our SQL queries, which is
    supported by SQLite, and have it automatically rewritten to "INSERT ... ON
    CONFLICT ... DO UPDATE" for PostgreSQL.
    """
    match = re.search(r"^\s*REPLACE\s+INTO\s+(\w+)\s*\(", sql, flags=re.IGNORECASE)
    if match:
        table = match.group(1)
        if table in UPSERT_TABLE_MAPPINGS:
            conflict_columns = UPSERT_TABLE_MAPPINGS[table]
            new_sql = re.sub(r"^\s*REPLACE\s+INTO\s+", "INSERT INTO ", sql, flags=re.IGNORECASE)
            new_sql = _normalize_insert_column_identifiers(new_sql)
            new_sql += f" ON CONFLICT ({', '.join(conflict_columns)}) DO UPDATE SET "
            columns = _extract_columns_from_insert(sql)
            if columns:
                update_columns = [f"{col} = EXCLUDED.{col}" for col in columns if col not in conflict_columns]
                new_sql += ", ".join(update_columns)
            return new_sql, parameters
        else:
            raise ValueError(f"No UPSERT mapping found for table '{table}'")
    return sql, parameters

class SqlDialectFormatCursor:
    def __init__(self, cursor: Any):
        self._cursor = cursor

    def execute(self, sql: str, parameters: Optional[Iterable[Any]] = None) -> Any:
        # Chain SQL dialect rewrites: apply all transformations in sequence
        sql, parameters = _rewrite_insert_or_ignore_statement(sql, parameters)
        sql, parameters = _rewrite_insert_or_replace_statement(sql, parameters)
        sql, parameters = _rewrite_replace_into_statement(sql, parameters)
        # Finally, convert placeholders from ? to %s for psycopg2
        converted = _convert_qmark_to_percent_s(sql)
        if parameters is None:
            return self._cursor.execute(converted)
        return self._cursor.execute(converted, parameters)

    def executemany(self, sql: str, seq_of_parameters: Iterable[Iterable[Any]]) -> Any:
        # Chain SQL dialect rewrites
        sql, _ = _rewrite_insert_or_ignore_statement(sql, None)
        sql, _ = _rewrite_insert_or_replace_statement(sql, None)
        sql, _ = _rewrite_replace_into_statement(sql, None)
        # Convert placeholders
        converted = _convert_qmark_to_percent_s(sql)
        return self._cursor.executemany(converted, seq_of_parameters)

    def __iter__(self) -> Any:
        return iter(self._cursor)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)


class SqlDialectFormatConnection:
    def __init__(self, connection: Any):
        self._connection = connection

    def cursor(self, *args: Any, **kwargs: Any) -> SqlDialectFormatCursor:
        return SqlDialectFormatCursor(self._connection.cursor(*args, **kwargs))

    def __enter__(self) -> Any:
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> Any:
        return self._connection.__exit__(exc_type, exc_value, traceback)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connection, name)
