"""Tests for owner sign-in and saving to GitHub (no network: fake HTTP session)."""

import base64
import json
import unittest
from pathlib import Path

import vittantra_cloud as cloud


class FakeResponse:
    def __init__(self, status, payload=None):
        self.status_code, self._payload = status, payload or {}

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, existing_sha=None, put_status=200):
        self.existing_sha, self.put_status, self.puts = existing_sha, put_status, []

    def get(self, url, **kwargs):
        return FakeResponse(200, {"sha": self.existing_sha}) if self.existing_sha else FakeResponse(404)

    def put(self, url, headers=None, json=None, timeout=None):
        self.puts.append((url, headers, json))
        return FakeResponse(self.put_status)


SETTINGS = {"token": "t", "repo": "owner/repo", "branch": "main"}
FILE = cloud.BASE_DIR / "advisory_clients.json"


class CloudTests(unittest.TestCase):
    def test_password_check(self):
        self.assertTrue(cloud.password_matches("secret", "secret"))
        self.assertFalse(cloud.password_matches("wrong", "secret"))
        self.assertTrue(cloud.password_matches(" secret ", "secret"))   # stray spaces from copy-paste
        self.assertFalse(cloud.password_matches("Secret", "secret"))     # still case-sensitive
        self.assertFalse(cloud.password_matches("", ""))      # no password configured never signs in

    def test_laptop_is_owner_without_secrets(self):
        self.assertFalse(cloud.cloud_mode())
        self.assertTrue(cloud.is_owner())

    def test_commit_updates_existing_file_with_sha(self):
        session = FakeSession(existing_sha="abc")
        self.assertEqual(cloud.commit_file(FILE, "msg", SETTINGS, session), "")
        url, headers, body = session.puts[0]
        self.assertTrue(url.endswith("/repos/owner/repo/contents/advisory_clients.json"))
        self.assertEqual(body["sha"], "abc")
        self.assertEqual(body["branch"], "main")
        self.assertEqual(json.loads(base64.b64decode(body["content"])), json.loads(FILE.read_text()))

    def test_commit_creates_new_file_and_reports_refusal(self):
        session = FakeSession(put_status=403)
        self.assertIn("Not saved to GitHub (403)", cloud.commit_file(FILE, "msg", SETTINGS, session))
        self.assertNotIn("sha", session.puts[0][2])

    def test_check_explains_token_problems(self):
        class Session:
            def __init__(self, status, payload=None): self.r = FakeResponse(status, payload)
            def get(self, url, **kwargs): return self.r
        self.assertIn("401", cloud.check_github(SETTINGS, Session(401)))
        self.assertIn("Only select repositories", cloud.check_github(SETTINGS, Session(404)))
        self.assertIn("Read and write", cloud.check_github(SETTINGS, Session(200, {"permissions": {"push": False}})))
        self.assertTrue(cloud.check_github(SETTINGS, Session(200, {"permissions": {"push": True}})).startswith("Saving works"))

    def test_no_token_means_no_commit(self):
        self.assertIsNone(cloud.github_settings())           # no secrets in the test environment
        self.assertIn("not set up", cloud.commit_file(FILE, "msg"))

    def test_users_may_only_save_their_own_record(self):
        from unittest import mock
        own = cloud.BASE_DIR / "academy_progress" / "sam.json"
        commits = []
        with mock.patch.object(cloud, "cloud_mode", return_value=True), \
                mock.patch.object(cloud, "is_owner", return_value=False), \
                mock.patch.object(cloud, "progress_path", return_value=own), \
                mock.patch.object(cloud, "commit_file", side_effect=lambda path, msg: commits.append(path) or ""), \
                mock.patch.object(cloud.st, "toast"), mock.patch.object(cloud.st, "session_state", {}):
            cloud.persist(cloud.BASE_DIR / "advisory_clients.json", "client")
            cloud.persist(cloud.BASE_DIR / "academy_progress.json", "owner record")
            cloud.persist(own, "own record")
        self.assertEqual(commits, [own])

    def test_token_never_in_code(self):
        for path in Path(cloud.BASE_DIR).glob("*.py"):
            self.assertNotRegex(path.read_text(errors="ignore"), r"github_pat_[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{30,}")


if __name__ == "__main__":
    unittest.main()
