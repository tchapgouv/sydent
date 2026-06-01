from twisted.trial import unittest

from sydent.db.dbapi import (
    UPSERT_TABLE_MAPPINGS,
    _rewrite_insert_or_ignore_statement,
    _rewrite_insert_or_replace_statement,
    _rewrite_replace_into_statement,
)


class DbInsertionRewriteTestCase(unittest.TestCase):
    def test_insert_or_ignore_rewriting(self):
        sql = "INSERT or   ignore INTO accounts (user_id) VALUES (?)"
        parameters = ("@alice:example.com",)
        self.assertEqual(
            _rewrite_insert_or_ignore_statement(sql, parameters),
            ("INSERT INTO accounts (user_id) VALUES (?) ON CONFLICT DO NOTHING", ("@alice:example.com",)),
        )
    def test_insert_or_ignore_rewriting_not_needed(self):
        sql = "INSERT INTO accounts (user_id) VALUES (?)"
        parameters = ("@alice:example.com",)
        self.assertEqual(
            _rewrite_insert_or_ignore_statement(sql, parameters),
            (sql, parameters),
        )

    def test_insert_or_replace_rewriting(self):
        sql = "INSERT OR REPLACE INTO profiles ('user_id', 'display_name') VALUES (?, ?)"
        parameters = ("@alice:example.com", "alice example")
        self.assertEqual(
            _rewrite_insert_or_replace_statement(sql, parameters),
            ("INSERT INTO profiles (user_id, display_name) VALUES (?, ?) ON CONFLICT (user_id) DO UPDATE SET display_name = EXCLUDED.display_name", ("@alice:example.com", "alice example")),
        )

    def test_replace_into_rewriting_with_composite_conflict_key(self):
        sql = (
            "REPLACE INTO local_threepid_associations "
            "('medium', 'address', 'mxid', 'ts') VALUES (?, ?, ?, ?)"
        )
        parameters = ("email", "alice@example.com", "@alice:example.com", 123456789)

        rewritten_sql, rewritten_params = _rewrite_replace_into_statement(sql, parameters)

        self.assertEqual(
            rewritten_sql,
            "INSERT INTO local_threepid_associations (medium, address, mxid, ts) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (medium, address) DO UPDATE SET mxid = EXCLUDED.mxid, ts = EXCLUDED.ts",
        )
        self.assertEqual(rewritten_params, parameters)

    def test_insert_or_replace_rewriting_excludes_conflict_columns_from_update(self):
        sql = (
            "INSERT OR REPLACE INTO local_threepid_associations "
            "('medium', 'address', 'mxid', 'ts') VALUES (?, ?, ?, ?)"
        )
        parameters = ("email", "alice@example.com", "@alice:example.com", 123456789)

        rewritten_sql, _ = _rewrite_insert_or_replace_statement(sql, parameters)

        self.assertIn("ON CONFLICT (medium, address)", rewritten_sql)
        self.assertIn("mxid = EXCLUDED.mxid", rewritten_sql)
        self.assertIn("ts = EXCLUDED.ts", rewritten_sql)
        self.assertNotIn("medium = EXCLUDED.medium", rewritten_sql)
        self.assertNotIn("address = EXCLUDED.address", rewritten_sql)

    def test_insert_or_replace_rewriting_table_not_in_mappings(self):
        sql = "INSERT OR REPLACE INTO other_table ('id', 'value') VALUES (?, ?)"
        parameters = (1, "test")

        self.assertNotIn("other_table", UPSERT_TABLE_MAPPINGS)
        with self.assertRaisesRegex(
            ValueError,
            "No UPSERT mapping found for table 'other_table'",
        ):
            _rewrite_insert_or_replace_statement(sql, parameters)

    def test_insert_or_replace_rewriting_not_needed(self):
        sql = "INSERT INTO profiles ('user_id', 'display_name') VALUES (?, ?)"
        parameters = ("@alice:example.com", "alice example")
        self.assertEqual(
            _rewrite_insert_or_replace_statement(sql, parameters),
            (sql, parameters),
        )