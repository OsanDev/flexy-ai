import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import storage

class OwnerProjectStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name)
        self.db_path = self.data_dir / 'test.sqlite3'
        self.media_dir = self.data_dir / 'media'
        self.render_dir = self.data_dir / 'renders'
        self.patches = [
            patch.object(storage, 'DATA_DIR', self.data_dir),
            patch.object(storage, 'DB_PATH', self.db_path),
            patch.object(storage, 'MEDIA_DIR', self.media_dir),
            patch.object(storage, 'RENDER_DIR', self.render_dir),
        ]
        for item in self.patches: item.start()
        storage.init_db()
        with storage.connect() as db:
            db.execute("INSERT INTO users(id,email,password_hash) VALUES('a','a@example.test','hash')")
            db.execute("INSERT INTO users(id,email,password_hash) VALUES('b','b@example.test','hash')")
            # Legacy project is intentionally ownerless.
            db.execute("INSERT INTO projects(id,name,project_json) VALUES('legacy','Legacy','{}')")

    def tearDown(self):
        for item in reversed(self.patches): item.stop()
        self.tmp.cleanup()

    def test_new_project_is_bound_to_owner(self):
        row = storage.save_project_for_owner('a','p1','Project A',{'title':'A'},0)
        self.assertEqual(row['owner_id'], 'a')

    def test_owner_cannot_read_other_users_project(self):
        storage.save_project_for_owner('b','p2','Project B',{'title':'B'},0)
        self.assertIsNone(storage.get_project_for_owner('a','p2'))

    def test_owner_cannot_overwrite_other_or_legacy_project(self):
        storage.save_project_for_owner('b','p2','Project B',{'title':'B'},0)
        with self.assertRaises(KeyError):
            storage.save_project_for_owner('a','p2','Hijack',{},0)
        with self.assertRaises(KeyError):
            storage.save_project_for_owner('a','legacy','Claim',{},0)

    def test_listing_is_scoped_and_legacy_is_hidden(self):
        storage.save_project_for_owner('a','p1','Project A',{},0)
        storage.save_project_for_owner('b','p2','Project B',{},0)
        self.assertEqual([p['id'] for p in storage.list_projects_for_owner('a')], ['p1'])

    def test_update_and_delete_are_scoped(self):
        storage.save_project_for_owner('a','p1','Project A',{},0)
        self.assertIsNone(storage.rename_project_for_owner('b','p1','Changed'))
        self.assertIsNone(storage.delete_project_for_owner('b','p1'))
        renamed = storage.rename_project_for_owner('a','p1','Changed')
        self.assertEqual(renamed['name'], 'Changed')
        self.assertIsNotNone(storage.delete_project_for_owner('a','p1'))

    def test_revision_conflict_is_preserved(self):
        storage.save_project_for_owner('a','p1','Project A',{},0)
        storage.save_project_for_owner('a','p1','Project A2',{},1)
        with self.assertRaises(storage.ProjectVersionConflict):
            storage.save_project_for_owner('a','p1','Stale',{},1)

if __name__ == '__main__':
    unittest.main(verbosity=2)
