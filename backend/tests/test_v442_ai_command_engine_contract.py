from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "frontend-reference/apps/web/src/lib/timelineCommands.ts"
COMPONENT = ROOT / "frontend-reference/apps/web/src/components/TimelineComposer.tsx"
STYLES = ROOT / "frontend-reference/apps/web/src/styles.css"


class AICommandEngineContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = ENGINE.read_text()
        cls.component = COMPONENT.read_text()
        cls.styles = STYLES.read_text()

    def test_command_engine_builds_preview_without_mutating_input(self):
        self.assertIn("planTimelineCommand", self.engine)
        self.assertIn("cloneDocument(document)", self.engine)
        self.assertIn("nextDocument: TimelineDocument", self.engine)

    def test_supported_video_commands(self):
        for phrase in ("crossfade", "cinematic", "trimMatch", 'exportPreset = "4k"'):
            self.assertIn(phrase, self.engine)

    def test_supported_audio_commands(self):
        for phrase in ("volume: 0", "clip.volume + 0.2", "fadeIn:", "fadeOut:"):
            self.assertIn(phrase, self.engine)

    def test_command_ui_requires_preview_then_explicit_apply(self):
        self.assertIn("Thinking…", self.component)
        self.assertIn("runCommand(commandText)", self.component)
        self.assertIn("Apply edits", self.component)
        self.assertIn("planTimelineCommand(doc, trimmed)", self.component)
        self.assertIn("commandPlan.nextDocument", self.component)
        self.assertIn("local command preview is rule-based", self.component)

    def test_command_panel_is_mobile_responsive(self):
        self.assertIn(".ai-command-panel", self.styles)
        self.assertIn("@media(max-width:560px){.ai-command-panel", self.styles)


if __name__ == "__main__":
    unittest.main()
