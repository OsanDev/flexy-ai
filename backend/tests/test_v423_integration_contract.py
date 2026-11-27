import unittest
from pathlib import Path
BASE = Path(__file__).resolve().parents[1] / "app"
MAIN = (BASE / "main.py").read_text(encoding="utf-8")
class IntegrationContractTests(unittest.TestCase):
    def test_auth_router_mounted(self):
        self.assertIn("app.include_router(auth_router)", MAIN)
    def test_core_project_routes_are_owner_scoped(self):
        self.assertIn("storage.save_project_for_owner(", MAIN)
        self.assertIn("storage.list_projects_for_owner(user.id)", MAIN)
        self.assertIn("storage.rename_project_for_owner(user.id", MAIN)
        self.assertIn("storage.delete_project_for_owner(user.id", MAIN)
    def test_unintegrated_api_routes_fail_closed(self):
        self.assertIn("fail_closed_unintegrated_routes", MAIN)
        self.assertIn("status_code=503", MAIN)
    def test_password_hash_dependency_declared(self):
        req = (BASE.parent / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("argon2-cffi", req)
if __name__ == "__main__":
    unittest.main(verbosity=2)
