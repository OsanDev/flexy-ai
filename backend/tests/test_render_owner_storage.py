import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import storage


class OwnerRenderStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.patches = [
            patch.object(storage, "DATA_DIR", root),
            patch.object(storage, "DB_PATH", root / "test.sqlite3"),
            patch.object(storage, "MEDIA_DIR", root / "media"),
            patch.object(storage, "RENDER_DIR", root / "renders"),
        ]
        for item in self.patches:
            item.start()
        storage.init_db()
        with storage.connect() as db:
            db.execute("INSERT INTO users(id,email,password_hash) VALUES('a','a@test','hash')")
            db.execute("INSERT INTO users(id,email,password_hash) VALUES('b','b@test','hash')")
        storage.save_project_for_owner("a", "pa", "A", {}, 0)
        storage.save_project_for_owner("b", "pb", "B", {}, 0)
        self.assertTrue(storage.create_job_for_owner("a", "ja", "pa"))
        self.assertTrue(storage.create_job_for_owner("b", "jb", "pb"))

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.tmp.cleanup()

    def test_create_rejects_foreign_and_legacy_projects(self):
        self.assertFalse(storage.create_job_for_owner("a", "bad", "pb"))
        self.assertIsNone(storage.get_job("bad"))

    def test_job_lookup_and_history_are_owner_scoped(self):
        self.assertIsNone(storage.get_job_for_owner("a", "jb"))
        self.assertEqual(storage.get_job_for_owner("b", "jb")["project_id"], "pb")
        self.assertIsNone(storage.list_project_renders_for_owner("a", "pb"))
        self.assertEqual([x["id"] for x in storage.list_project_renders_for_owner("a", "pa")], ["ja"])

    def test_cancel_is_owner_scoped(self):
        self.assertIsNone(storage.request_job_cancel_for_owner("a", "jb"))
        self.assertEqual(storage.get_job("jb")["status"], "queued")
        self.assertEqual(storage.request_job_cancel_for_owner("b", "jb")["status"], "cancelling")

    def test_delete_terminal_job_is_owner_scoped(self):
        storage.update_job("jb", status="failed", progress=0, error="failed")
        self.assertIsNone(storage.delete_terminal_job_for_owner("a", "jb"))
        self.assertIsNotNone(storage.delete_terminal_job_for_owner("b", "jb"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
