"""Tests for user accounts: password storage, username rules and who may save what."""

import json
import tempfile
import unittest
from pathlib import Path

import vittantra_accounts as accounts


class AccountTests(unittest.TestCase):

    def test_password_is_never_stored(self):
        users, problem = accounts.add_user({}, "Alex_1", "correct horse")
        self.assertEqual(problem, "")
        record = users["alex_1"]
        self.assertNotIn("correct horse", json.dumps(users))
        self.assertEqual(len(record["salt"]), 32)
        self.assertEqual(record["iterations"], accounts.ITERATIONS)

    def test_same_password_gives_different_fingerprints(self):
        a, _ = accounts.add_user({}, "aaa", "same password")
        b, _ = accounts.add_user({}, "bbb", "same password")
        self.assertNotEqual(a["aaa"]["hash"], b["bbb"]["hash"])   # random salt per account

    def test_login(self):
        users, _ = accounts.add_user({}, "Priya", "longpassword")
        self.assertEqual(accounts.check_login(users, " PRIYA ", "longpassword"), "priya")
        self.assertIsNone(accounts.check_login(users, "priya", "wrongpassword"))
        self.assertIsNone(accounts.check_login(users, "nobody", "longpassword"))

    def test_username_and_password_rules(self):
        self.assertIn("reserved", accounts.add_user({}, "owner", "longpassword")[1])
        self.assertIn("3–20", accounts.add_user({}, "a b", "longpassword")[1])
        self.assertIn("at least", accounts.add_user({}, "sam", "short")[1])
        users, _ = accounts.add_user({}, "sam", "longpassword")
        self.assertIn("taken", accounts.add_user(users, "SAM", "otherpassword")[1])

    def test_add_user_does_not_modify_input(self):
        users = {}
        accounts.add_user(users, "sam", "longpassword")
        self.assertEqual(users, {})

    def test_files_round_trip_and_bad_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "users.json"
            self.assertEqual(accounts.load_users(path), {})
            users, _ = accounts.add_user({}, "sam", "longpassword")
            accounts.save_users(users, path)
            self.assertEqual(accounts.check_login(accounts.load_users(path), "sam", "longpassword"), "sam")
            path.write_text("not json")
            self.assertEqual(accounts.load_users(path), {})

    def test_each_user_gets_own_progress_file(self):
        self.assertEqual(accounts.progress_file("Sam").name, "sam.json")
        self.assertEqual(accounts.progress_file("sam").parent, accounts.PROGRESS_DIR)


if __name__ == "__main__":
    unittest.main()
