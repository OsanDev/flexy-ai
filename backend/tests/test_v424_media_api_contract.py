import ast, unittest
from pathlib import Path
MAIN = Path(__file__).resolve().parents[1] / "app" / "main.py"
class MediaApiContractTests(unittest.TestCase):
    def test_all_media_routes_require_current_user(self):
        tree = ast.parse(MAIN.read_text(encoding="utf-8"))
        found = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                paths = []
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                        if isinstance(dec.func.value, ast.Name) and dec.func.value.id == "app":
                            if dec.args and isinstance(dec.args[0], ast.Constant):
                                p = str(dec.args[0].value)
                                if "/media" in p or p.startswith("/api/media/"):
                                    paths.append(p)
                if paths:
                    args = {a.arg for a in node.args.args + node.args.kwonlyargs}
                    self.assertIn("user", args, node.name)
                    self.assertTrue(any(isinstance(d, ast.Call) and isinstance(d.func, ast.Name)
                                        and d.func.id == "Depends" for d in node.args.defaults + node.args.kw_defaults if d),
                                    node.name)
                    found.extend(paths)
        self.assertGreaterEqual(len(found), 10)
    def test_media_uses_owner_scoped_storage(self):
        text = MAIN.read_text(encoding="utf-8")
        self.assertIn("storage.get_media_for_owner(user.id", text)
        self.assertIn("storage.add_media_for_owner(user.id", text)
        self.assertIn("storage.list_project_media_for_owner(user.id", text)
if __name__ == "__main__":
    unittest.main(verbosity=2)
