from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / "backend/app/main.py"
CLIENT = ROOT / "frontend-reference/apps/web/src/lib/aiDirectorApi.ts"
COMPONENT = ROOT / "frontend-reference/apps/web/src/components/TimelineComposer.tsx"
APP = ROOT / "frontend-reference/apps/web/src/App.tsx"


class AIDirectorIntegrationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = MAIN.read_text()
        cls.client = CLIENT.read_text()
        cls.component = COMPONENT.read_text()
        cls.app = APP.read_text()

    def test_planner_route_is_allowlisted_but_authenticated_and_csrf_protected(self):
        self.assertIn('path == "/api/assistant/plan" and method == "POST"', self.main)
        self.assertIn('def plan_edit(request: EditRequest, http_request: Request, user=Depends(current_user))', self.main)
        self.assertIn('_csrf_check(http_request)', self.main)
        self.assertIn('storage.get_project_for_owner(user.id, request.project_id)', self.main)

    def test_provider_input_is_bounded_metadata_only(self):
        self.assertIn('request.assets[:200]', self.main)
        self.assertIn('asset.get("mime_type"', self.main)
        self.assertIn('asset.get("filename", ""))[:180]', self.main)

    def test_frontend_client_sends_credentials_csrf_and_project_id(self):
        self.assertIn('credentials: "include"', self.client)
        self.assertIn('"X-CSRF-Token": csrfToken()', self.client)
        self.assertIn('project_id: input.projectId', self.client)

    def test_timeline_requests_server_plan_and_shows_provider_result(self):
        self.assertIn('aiDirectorApi.plan({', self.component)
        self.assertIn('AI Director analysis', self.component)
        self.assertIn('directorPlan.provider', self.component)
        self.assertIn('FLEXY_AI_API_KEY', self.component)

    def test_app_passes_current_project_context(self):
        self.assertIn('projectId={projectId.trim()} projectContext={projectPayload}', self.app)


if __name__ == "__main__":
    unittest.main()
