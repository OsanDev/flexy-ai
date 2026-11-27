import sqlite3, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import storage

class OwnerMediaStorageTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        CREATE TABLE users(id TEXT PRIMARY KEY,email TEXT,is_active INTEGER DEFAULT 1);
        CREATE TABLE projects(id TEXT PRIMARY KEY,owner_id TEXT,name TEXT,project_json TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
          revision INTEGER DEFAULT 1,folder_name TEXT DEFAULT '',is_favorite INTEGER DEFAULT 0);
        CREATE TABLE media(id TEXT PRIMARY KEY,project_id TEXT,filename TEXT,stored_name TEXT,
          mime_type TEXT,size_bytes INTEGER,duration REAL,metadata_json TEXT DEFAULT '{}',
          created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        INSERT INTO users(id,email) VALUES('a','a@test'),('b','b@test');
        INSERT INTO projects(id,owner_id,name,project_json) VALUES
          ('pa','a','A','{}'),('pb','b','B','{}');
        INSERT INTO media(id,project_id,filename,stored_name,mime_type,size_bytes) VALUES
          ('ma','pa','a.mp4','a-file.mp4','video/mp4',10),
          ('mb','pb','b.mp4','b-file.mp4','video/mp4',10);
        """)
        self.original_connect = storage.connect
        storage.connect = lambda: self.db

    def tearDown(self):
        storage.connect = self.original_connect
        self.db.close()

    def test_list_only_owned_project_media(self):
        items = storage.list_project_media_for_owner("a", "pa")
        self.assertEqual([x["id"] for x in items], ["ma"])

    def test_other_users_project_media_list_hidden(self):
        self.assertIsNone(storage.list_project_media_for_owner("a", "pb"))

    def test_media_id_only_lookup_is_owner_scoped(self):
        self.assertIsNone(storage.get_media_for_owner("a", "mb"))
        self.assertEqual(storage.get_media_for_owner("b", "mb")["project_id"], "pb")

    def test_project_scoped_lookup_rejects_mismatched_project(self):
        self.assertIsNone(storage.get_media_for_owner("a", "ma", "pb"))

    def test_add_media_requires_owned_project(self):
        with self.assertRaises(KeyError):
            storage.add_media_for_owner("a", {
              "id":"new","project_id":"pb","filename":"x.mp4","stored_name":"x.mp4",
              "mime_type":"video/mp4","size_bytes":5,"metadata":{}
            })

if __name__ == "__main__":
    unittest.main(verbosity=2)
