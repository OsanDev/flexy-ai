import json
import os
import unittest
from unittest.mock import patch
from app.ai_director import build_edit_plan

class FakeResponse:
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self):
        return json.dumps({"choices":[{"message":{"content":json.dumps({
            "summary":"Model planned a vertical short", "aspect_ratio_id":"portrait",
            "suggestions":[{"kind":"hook","title":"Open with the hook","detail":"Lead with the strongest supplied story beat."}],
            "warnings":[]})}}]}).encode()

class AIDirectorTests(unittest.TestCase):
    def test_detects_vertical_reel_preset(self):
        plan=build_edit_plan('Make a vertical Instagram reel',[],{'id':'p','width':1920,'height':1080})
        self.assertEqual(plan['aspect_ratio']['id'],'portrait'); self.assertEqual(plan['provider'],'local_rules')
    def test_detects_square_preset(self):
        self.assertEqual(build_edit_plan('Create a square feed post',[],{})['aspect_ratio']['id'],'square')
    def test_adds_caption_audio_and_long_footage_guidance(self):
        plan=build_edit_plan('Add captions and background music',[{'type':'video','duration':45},{'type':'audio','duration':20}],{})
        kinds={x['kind'] for x in plan['suggestions']}
        self.assertTrue({'captions','audio','review_cuts'}.issubset(kinds))
    def test_empty_project_recommends_import(self):
        self.assertEqual(build_edit_plan('Make a cinematic edit',[],{})['suggestions'][0]['kind'],'import_media')
    def test_transcript_is_incorporated(self):
        plan=build_edit_plan('Create a story edit',[],{},'Today we begin a new journey')
        self.assertIn('transcript',{x['kind'] for x in plan['suggestions']})
    def test_local_plan_contains_editable_timeline_draft(self):
        plan = build_edit_plan('Create a dynamic 10-second highlight reel', [
            {'id': 'v1', 'type': 'video', 'duration': 8},
            {'id': 'v2', 'type': 'video', 'duration': 8},
            {'id': 'a1', 'type': 'audio', 'duration': 12},
        ], {'id': 'p'})
        draft = plan['timeline_draft']
        self.assertEqual(draft['target_duration'], 10)
        self.assertEqual(len(draft['clips']), 2)
        self.assertEqual(draft['clips'][0]['duration'], 2.5)
        self.assertEqual(draft['clips'][1]['start'], 2.5)
        self.assertEqual(draft['audio_clips'][0]['volume'], 0.35)

    def test_timeline_draft_warns_when_no_visual_assets(self):
        plan = build_edit_plan('Make a 20 second video', [{'id': 'a1', 'type': 'audio', 'duration': 20}], {})
        self.assertEqual(plan['timeline_draft']['clips'], [])
        self.assertTrue(plan['timeline_draft']['warnings'])

    @patch.dict(os.environ, {'FLEXY_AI_API_KEY':'test-key','FLEXY_AI_MODEL':'test-model'})
    @patch('app.ai_director.urllib.request.urlopen', return_value=FakeResponse())
    def test_configured_model_provider_returns_structured_plan(self, mocked):
        plan=build_edit_plan('Make a reel',[],{'id':'p'},'A short transcript')
        self.assertEqual(plan['provider'],'openai_compatible')
        self.assertEqual(plan['aspect_ratio']['id'],'portrait')
        self.assertEqual(plan['suggestions'][0]['kind'],'hook')
        self.assertTrue(mocked.called)

if __name__=='__main__': unittest.main()
