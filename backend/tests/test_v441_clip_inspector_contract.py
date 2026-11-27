from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
COMPONENT = ROOT / "frontend-reference/apps/web/src/components/TimelineComposer.tsx"
STYLES = ROOT / "frontend-reference/apps/web/src/styles.css"


class ClipInspectorContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.component = COMPONENT.read_text()
        cls.styles = STYLES.read_text()

    def test_clip_selection_is_wired_for_all_tracks(self):
        self.assertEqual(self.component.count("onSelect:() => setSelectedClip"), 3)
        self.assertIn('aria-pressed={!!item.selected}', self.component)
        self.assertIn('setSelectedClip(null)', self.component)

    def test_video_properties_include_position_source_duration_and_transition(self):
        for field in ("selectedVideo.timelineStart", "selectedVideo.sourceStart",
                      "selectedVideo.duration", "selectedVideo.transition"):
            self.assertIn(field, self.component)

    def test_audio_properties_include_volume_and_fades(self):
        for field in ("selectedAudio.volume", "selectedAudio.fadeIn", "selectedAudio.fadeOut"):
            self.assertIn(field, self.component)

    def test_caption_properties_are_editable(self):
        for field in ("selectedCaption.text", "selectedCaption.start", "selectedCaption.duration"):
            self.assertIn(field, self.component)

    def test_selected_clip_has_visible_focus_and_mobile_controls(self):
        self.assertIn(".track-clip.selected", self.styles)
        self.assertIn("@media(max-width:560px){.clip-inspector", self.styles)
        self.assertIn("min-height:42px", self.styles)


if __name__ == "__main__":
    unittest.main()
