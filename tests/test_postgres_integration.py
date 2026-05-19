import os
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
