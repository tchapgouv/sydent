from twisted.trial import unittest

from sydent.config import SydentConfig
from sydent.config.exceptions import ConfigError


class DatabaseConfigTestCase(unittest.TestCase):
    def test_db_type_postgresql(self):
        sydent_config = SydentConfig()
        sydent_config.parse_config_dict(
            {
                "db": {
                    "db.type": "postgresql",
                    "db.postgresql.host": "localhost",
                    "db.postgresql.port": "5432",
                    "db.postgresql.user": "sydent",
                    "db.postgresql.password": "sydent",
                    "db.postgresql.database": "sydent",
                    "db.postgresql.sslmode": "prefer",
                }
            }
        )

        self.assertEqual(sydent_config.database.database_type, "postgresql")

    def test_db_type_postgres_is_rejected(self):
        sydent_config = SydentConfig()

        with self.assertRaises(ConfigError):
            sydent_config.parse_config_dict(
                {
                    "db": {
                        "db.type": "postgres",
                    }
                }
            )

    def test_db_type_sqlite(self):
        sydent_config = SydentConfig()
        sydent_config.parse_config_dict(
            {
                "db": {
                    "db.type": "sqlite",
                    "db.file": ":memory:",
                }
            }
        )

        self.assertEqual(sydent_config.database.database_type, "sqlite")
        self.assertEqual(sydent_config.database.database_path, ":memory:")
