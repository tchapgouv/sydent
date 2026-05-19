from twisted.trial import unittest

from sydent.db.dbapi import _convert_qmark_to_percent_s


class DbApiAdapterTestCase(unittest.TestCase):
    def test_qmark_conversion(self):
        sql = "SELECT * FROM t WHERE a = ? AND b = ?"
        self.assertEqual(
            _convert_qmark_to_percent_s(sql),
            "SELECT * FROM t WHERE a = %s AND b = %s",
        )

    def test_question_mark_in_string_literal_is_preserved(self):
        sql = "SELECT '?' AS marker, a FROM t WHERE b = ?"
        self.assertEqual(
            _convert_qmark_to_percent_s(sql),
            "SELECT '?' AS marker, a FROM t WHERE b = %s",
        )
