import os
import uuid
from types import SimpleNamespace

from twisted.trial import unittest

from sydent.config import SydentConfig
from sydent.db.factory import DatabaseFactory
from sydent.db.postgresdb import CURRENT_SCHEMA_VERSION


class PostgresIntegrationTestCase(unittest.TestCase):
    def test_postgres_factory_initializes_schema(self):
        if os.environ.get("SYDENT_RUN_POSTGRES_TESTS") != "1":
            self.skipTest("Set SYDENT_RUN_POSTGRES_TESTS=1 to run PostgreSQL integration tests")

        sydent_config = SydentConfig()
        sydent_config.parse_config_dict(
            {
                "db": {
                    "db.type": "postgresql",
                    "db.postgresql.host": os.environ.get("SYDENT_PG_HOST", "localhost"),
                    "db.postgresql.port": os.environ.get("SYDENT_PG_PORT", "5432"),
                    "db.postgresql.user": os.environ.get("SYDENT_PG_USER", "sydent"),
                    "db.postgresql.password": os.environ.get("SYDENT_PG_PASSWORD", "sydent"),
                    "db.postgresql.database": os.environ.get("SYDENT_PG_DATABASE", "sydent"),
                    "db.postgresql.sslmode": os.environ.get("SYDENT_PG_SSLMODE", "prefer"),
                }
            }
        )

        dummy_sydent = SimpleNamespace(config=sydent_config)
        handles = DatabaseFactory.build(dummy_sydent)

        try:
            cur = handles.connection.cursor()
            cur.execute(
                "SELECT version FROM sydent_schema_version WHERE singleton = ?",
                (True,),
            )
            row = cur.fetchone()
            self.assertEqual(row[0], CURRENT_SCHEMA_VERSION)
        finally:
            handles.connection.close()

    def test_postgres_cursor_rewrites_sqlite_style_upserts(self):
        if os.environ.get("SYDENT_RUN_POSTGRES_TESTS") != "1":
            self.skipTest("Set SYDENT_RUN_POSTGRES_TESTS=1 to run PostgreSQL integration tests")

        sydent_config = SydentConfig()
        sydent_config.parse_config_dict(
            {
                "db": {
                    "db.type": "postgresql",
                    "db.postgresql.host": os.environ.get("SYDENT_PG_HOST", "localhost"),
                    "db.postgresql.port": os.environ.get("SYDENT_PG_PORT", "5432"),
                    "db.postgresql.user": os.environ.get("SYDENT_PG_USER", "sydent"),
                    "db.postgresql.password": os.environ.get("SYDENT_PG_PASSWORD", "sydent"),
                    "db.postgresql.database": os.environ.get("SYDENT_PG_DATABASE", "sydent"),
                    "db.postgresql.sslmode": os.environ.get("SYDENT_PG_SSLMODE", "prefer"),
                }
            }
        )

        dummy_sydent = SimpleNamespace(config=sydent_config)
        handles = DatabaseFactory.build(dummy_sydent)

        # Use unique identifiers so the test is isolated and repeatable.
        user_id = f"@upsert-test-{uuid.uuid4().hex}:example.org"
        url = "https://terms.example.org/v1"
        local_medium = "email"
        local_address = f"replace-{uuid.uuid4().hex}@example.org"

        try:
            cur = handles.connection.cursor()

            # Validate INSERT OR IGNORE rewrite + qmark placeholder conversion.
            cur.execute(
                "INSERT OR IGNORE INTO accepted_terms_urls (user_id, url) VALUES (?, ?)",
                (user_id, url),
            )
            cur.execute(
                "INSERT OR IGNORE INTO accepted_terms_urls (user_id, url) VALUES (?, ?)",
                (user_id, url),
            )
            cur.execute(
                "SELECT COUNT(*) FROM accepted_terms_urls WHERE user_id = ? AND url = ?",
                (user_id, url),
            )
            row = cur.fetchone()
            self.assertEqual(row[0], 1)

            # Validate INSERT OR REPLACE rewrite against hashing_metadata(id).
            cur.execute(
                "INSERT OR REPLACE INTO hashing_metadata (id, lookup_pepper) VALUES (0, ?)",
                ("pepper-one",),
            )
            cur.execute(
                "INSERT OR REPLACE INTO hashing_metadata (id, lookup_pepper) VALUES (0, ?)",
                ("pepper-two",),
            )
            cur.execute(
                "SELECT lookup_pepper FROM hashing_metadata WHERE id = ?",
                (0,),
            )
            row = cur.fetchone()
            self.assertEqual(row[0], "pepper-two")

            # Validate REPLACE INTO rewrite against local_threepid_associations
            # with a composite conflict key (medium, address).
            cur.execute(
                "REPLACE INTO local_threepid_associations ('medium', 'address', 'mxid', 'ts') VALUES (?, ?, ?, ?)",
                (local_medium, local_address, "@alice:example.org", 100),
            )
            cur.execute(
                "REPLACE INTO local_threepid_associations ('medium', 'address', 'mxid', 'ts') VALUES (?, ?, ?, ?)",
                (local_medium, local_address, "@bob:example.org", 200),
            )
            cur.execute(
                "SELECT COUNT(*), mxid, ts FROM local_threepid_associations WHERE medium = ? AND address = ? GROUP BY mxid, ts",
                (local_medium, local_address),
            )
            row = cur.fetchone()
            self.assertEqual(row[0], 1)
            self.assertEqual(row[1], "@bob:example.org")
            self.assertEqual(row[2], 200)

            handles.connection.commit()
        finally:
            handles.connection.close()
