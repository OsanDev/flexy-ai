import unittest
from pathlib import Path
from unittest.mock import patch

from app.rendering import RenderValidationError, validate_render_graph

class RenderingValidationTests(unittest.TestCase):
    @patch("app.rendering.storage.get_media")
    @patch("app.rendering.storage.MEDIA_DIR", Path("/tmp/flexy-test-media"))
    def test_accepts_valid_graph(self, get_media):
        media_dir = Path("/tmp/flexy-test-media")
        media_dir.mkdir(exist_ok=True)
        (media_dir / "sample.mp4").write_bytes(b"test")
        get_media.return_value = {"stored_name": "sample.mp4", "mime_type": "video/mp4"}
        result = validate_render_graph({
            "width": 1280, "height": 720, "frame_rate": 30,
            "clips": [{"media_id": "asset-1", "source_start": 1.5, "duration": 4.0}]
        })
        self.assertEqual(result["width"], 1280)
        self.assertEqual(result["clips"][0]["duration"], 4.0)
        (media_dir / "sample.mp4").unlink()
        media_dir.rmdir()

    def test_rejects_empty_clips(self):
        with self.assertRaises(RenderValidationError):
            validate_render_graph({"clips": []})

    @patch("app.rendering.storage.get_media", return_value=None)
    def test_rejects_unknown_media_id(self, _get_media):
        with self.assertRaises(RenderValidationError):
            validate_render_graph({"clips": [{"media_id": "../../etc/passwd", "duration": 2}]})

    def test_rejects_unsupported_frame_rate(self):
        with self.assertRaises(RenderValidationError):
            validate_render_graph({"frame_rate": 27, "clips": [{"media_id": "x", "duration": 2}]})


    @patch("app.rendering.storage.get_media")
    @patch("app.rendering.storage.MEDIA_DIR", Path("/tmp/flexy-test-audio"))
    def test_accepts_audio_track_clip(self, get_media):
        media_dir = Path("/tmp/flexy-test-audio")
        media_dir.mkdir(exist_ok=True)
        (media_dir / "music.wav").write_bytes(b"test")
        get_media.return_value = {"stored_name": "music.wav", "mime_type": "audio/wav"}
        # Video media lookup is mocked separately by the first call order.
        video_file = media_dir / "picture.mp4"
        video_file.write_bytes(b"video")
        get_media.side_effect = [
            {"stored_name": "picture.mp4", "mime_type": "video/mp4"},
            {"stored_name": "music.wav", "mime_type": "audio/wav"},
        ]
        from app.rendering import validate_render_graph
        result = validate_render_graph({
            "clips": [{"media_id": "video-id", "duration": 2}],
            "audio_clips": [{"media_id": "audio-id", "duration": 1.5, "timeline_start": 0.25, "volume": 0.6}],
        })
        self.assertEqual(result["audio_clips"][0]["timeline_start"], 0.25)
        self.assertEqual(result["audio_clips"][0]["volume"], 0.6)
        (media_dir / "music.wav").unlink()
        video_file.unlink()
        media_dir.rmdir()

    def test_rejects_audio_volume_above_limit(self):
        from app.rendering import validate_render_graph
        with patch("app.rendering.storage.get_media", side_effect=[
            {"stored_name": "video.mp4", "mime_type": "video/mp4"},
        ]), patch("app.rendering.storage.MEDIA_DIR", Path("/tmp/flexy-test-volume")):
            media_dir = Path("/tmp/flexy-test-volume")
            media_dir.mkdir(exist_ok=True)
            (media_dir / "video.mp4").write_bytes(b"video")
            with self.assertRaises(RenderValidationError):
                validate_render_graph({
                    "clips": [{"media_id": "video", "duration": 1}],
                    "audio_clips": [{"media_id": "audio", "duration": 1, "volume": 3}],
                })
            (media_dir / "video.mp4").unlink()
            media_dir.rmdir()


    def test_validates_caption_and_fade_transition(self):
        from app.rendering import validate_render_graph
        with patch("app.rendering.storage.get_media") as get_media, patch("app.rendering.storage.MEDIA_DIR", Path("/tmp/flexy-test-caption")):
            media_dir = Path("/tmp/flexy-test-caption")
            media_dir.mkdir(exist_ok=True)
            (media_dir / "clip.mp4").write_bytes(b"video")
            get_media.return_value = {"stored_name": "clip.mp4", "mime_type": "video/mp4"}
            result = validate_render_graph({
                "clips": [{"media_id": "v1", "duration": 2, "transition": "fade"}],
                "captions": [{"text": "Hello FLEXY", "start": 0.5, "duration": 1.2}],
            })
            self.assertEqual(result["clips"][0]["transition"], "fade")
            self.assertEqual(result["captions"][0]["text"], "Hello FLEXY")
            (media_dir / "clip.mp4").unlink()
            media_dir.rmdir()

    def test_rejects_invalid_caption(self):
        from app.rendering import validate_render_graph
        with patch("app.rendering.storage.get_media") as get_media, patch("app.rendering.storage.MEDIA_DIR", Path("/tmp/flexy-test-caption-invalid")):
            media_dir = Path("/tmp/flexy-test-caption-invalid")
            media_dir.mkdir(exist_ok=True)
            (media_dir / "clip.mp4").write_bytes(b"video")
            get_media.return_value = {"stored_name": "clip.mp4", "mime_type": "video/mp4"}
            with self.assertRaises(RenderValidationError):
                validate_render_graph({"clips": [{"media_id": "v1", "duration": 2}], "captions": [{"text": "", "start": 0, "duration": 1}]})
            (media_dir / "clip.mp4").unlink()
            media_dir.rmdir()


    def test_accepts_image_on_visual_track(self):
        from app.rendering import validate_render_graph
        with patch("app.rendering.storage.get_media", return_value={"stored_name": "still.png", "mime_type": "image/png"}), patch("app.rendering.storage.MEDIA_DIR", Path("/tmp/flexy-test-image")):
            media_dir = Path("/tmp/flexy-test-image")
            media_dir.mkdir(exist_ok=True)
            (media_dir / "still.png").write_bytes(b"image")
            result = validate_render_graph({"clips": [{"media_id": "still", "duration": 2}]})
            self.assertTrue(result["clips"][0]["is_image"])
            (media_dir / "still.png").unlink()
            media_dir.rmdir()


    def test_accepts_positioned_overlapping_video_layers_and_gaps(self):
        from app.rendering import validate_render_graph
        with patch("app.rendering.storage.get_media") as get_media, patch("app.rendering.storage.MEDIA_DIR", Path("/tmp/flexy-test-layers")):
            media_dir = Path("/tmp/flexy-test-layers")
            media_dir.mkdir(exist_ok=True)
            for name in ("base.mp4", "overlay.mp4"):
                (media_dir / name).write_bytes(b"video")
            get_media.side_effect = [
                {"stored_name": "base.mp4", "mime_type": "video/mp4"},
                {"stored_name": "overlay.mp4", "mime_type": "video/mp4"},
            ]
            result = validate_render_graph({"clips": [
                {"media_id": "base", "duration": 4, "timeline_start": 2, "track_index": 1},
                {"media_id": "overlay", "duration": 2, "timeline_start": 3, "track_index": 0, "transition": "crossfade"},
            ]})
            self.assertEqual(result["video_duration"], 6)
            self.assertEqual(result["clips"][1]["timeline_start"], 3)
            self.assertEqual(result["clips"][1]["transition"], "crossfade")
            for name in ("base.mp4", "overlay.mp4"):
                (media_dir / name).unlink()
            media_dir.rmdir()

    def test_legacy_video_clips_without_timeline_start_remain_sequential(self):
        from app.rendering import validate_render_graph
        with patch("app.rendering.storage.get_media") as get_media, patch("app.rendering.storage.MEDIA_DIR", Path("/tmp/flexy-test-legacy")):
            media_dir = Path("/tmp/flexy-test-legacy")
            media_dir.mkdir(exist_ok=True)
            (media_dir / "clip.mp4").write_bytes(b"video")
            get_media.return_value = {"stored_name": "clip.mp4", "mime_type": "video/mp4"}
            result = validate_render_graph({"clips": [
                {"media_id": "a", "duration": 2}, {"media_id": "b", "duration": 3}
            ]})
            self.assertEqual([clip["timeline_start"] for clip in result["clips"]], [0, 2])
            self.assertEqual(result["video_duration"], 5)
            (media_dir / "clip.mp4").unlink()
            media_dir.rmdir()


    def test_validates_audio_fades(self):
        from app.rendering import validate_render_graph
        with patch("app.rendering.storage.get_media") as get_media, patch("app.rendering.storage.MEDIA_DIR", Path("/tmp/flexy-test-audio-fades")):
            media_dir = Path("/tmp/flexy-test-audio-fades")
            media_dir.mkdir(exist_ok=True)
            (media_dir / "clip.mp4").write_bytes(b"video")
            (media_dir / "music.wav").write_bytes(b"audio")
            get_media.side_effect = [
                {"stored_name": "clip.mp4", "mime_type": "video/mp4"},
                {"stored_name": "music.wav", "mime_type": "audio/wav"},
            ]
            result = validate_render_graph({
                "clips": [{"media_id": "v", "duration": 5}],
                "audio_clips": [{"media_id": "a", "duration": 4, "fade_in": 0.5, "fade_out": 1.0}],
            })
            self.assertEqual(result["audio_clips"][0]["fade_in"], 0.5)
            self.assertEqual(result["audio_clips"][0]["fade_out"], 1.0)
            for name in ("clip.mp4", "music.wav"):
                (media_dir / name).unlink()
            media_dir.rmdir()

    def test_rejects_audio_fades_longer_than_clip(self):
        from app.rendering import validate_render_graph
        with patch("app.rendering.storage.get_media") as get_media, patch("app.rendering.storage.MEDIA_DIR", Path("/tmp/flexy-test-audio-fades-invalid")):
            media_dir = Path("/tmp/flexy-test-audio-fades-invalid")
            media_dir.mkdir(exist_ok=True)
            (media_dir / "clip.mp4").write_bytes(b"video")
            (media_dir / "music.wav").write_bytes(b"audio")
            get_media.side_effect = [
                {"stored_name": "clip.mp4", "mime_type": "video/mp4"},
                {"stored_name": "music.wav", "mime_type": "audio/wav"},
            ]
            with self.assertRaises(RenderValidationError):
                validate_render_graph({
                    "clips": [{"media_id": "v", "duration": 5}],
                    "audio_clips": [{"media_id": "a", "duration": 2, "fade_in": 1.5, "fade_out": 1}],
                })
            for name in ("clip.mp4", "music.wav"):
                (media_dir / name).unlink()
            media_dir.rmdir()

if __name__ == "__main__":
    unittest.main()

class AudioRoleValidationTests(unittest.TestCase):
    @patch("app.rendering.storage.get_media")
    @patch("app.rendering.storage.MEDIA_DIR", Path("/tmp/flexy-test-audio-roles"))
    def test_accepts_dialogue_and_music_roles_and_ducking(self, get_media):
        media_dir = Path("/tmp/flexy-test-audio-roles")
        media_dir.mkdir(exist_ok=True)
        for name in ("picture.mp4", "voice.wav", "music.wav"):
            (media_dir / name).write_bytes(b"test")
        get_media.side_effect = [
            {"stored_name": "picture.mp4", "mime_type": "video/mp4"},
            {"stored_name": "voice.wav", "mime_type": "audio/wav"},
            {"stored_name": "music.wav", "mime_type": "audio/wav"},
        ]
        from app.rendering import validate_render_graph
        result = validate_render_graph({
            "clips": [{"media_id": "v", "duration": 3}],
            "audio_clips": [
                {"media_id": "voice", "duration": 3, "role": "dialogue"},
                {"media_id": "music", "duration": 3, "role": "music"},
            ],
            "ducking": True,
        })
        self.assertEqual([clip["role"] for clip in result["audio_clips"]], ["dialogue", "music"])
        self.assertTrue(result["ducking"])
        for name in ("picture.mp4", "voice.wav", "music.wav"):
            (media_dir / name).unlink()
        media_dir.rmdir()

    @patch("app.rendering.storage.get_media")
    @patch("app.rendering.storage.MEDIA_DIR", Path("/tmp/flexy-test-audio-role-invalid"))
    def test_rejects_unknown_audio_role(self, get_media):
        media_dir = Path("/tmp/flexy-test-audio-role-invalid")
        media_dir.mkdir(exist_ok=True)
        (media_dir / "picture.mp4").write_bytes(b"test")
        (media_dir / "music.wav").write_bytes(b"test")
        get_media.side_effect = [
            {"stored_name": "picture.mp4", "mime_type": "video/mp4"},
            {"stored_name": "music.wav", "mime_type": "audio/wav"},
        ]
        from app.rendering import validate_render_graph, RenderValidationError
        with self.assertRaises(RenderValidationError):
            validate_render_graph({
                "clips": [{"media_id": "v", "duration": 2}],
                "audio_clips": [{"media_id": "a", "duration": 2, "role": "explosion"}],
            })
        for name in ("picture.mp4", "music.wav"):
            (media_dir / name).unlink()
        media_dir.rmdir()

class ExportPresetTests(unittest.TestCase):
    def _validate(self, graph):
        from app.rendering import validate_render_graph
        media_dir = Path('/tmp/flexy-export-preset')
        media_dir.mkdir(exist_ok=True)
        (media_dir / 'clip.mp4').write_bytes(b'video')
        try:
            with patch('app.rendering.storage.get_media', return_value={'stored_name': 'clip.mp4', 'mime_type': 'video/mp4'}), patch('app.rendering.storage.MEDIA_DIR', media_dir):
                return validate_render_graph({'clips': [{'media_id': 'v', 'duration': 2}], **graph})
        finally:
            (media_dir / 'clip.mp4').unlink(missing_ok=True)
            media_dir.rmdir()

    def test_1080p_preset_sets_dimensions_and_bitrate(self):
        result = self._validate({'width': 1920, 'height': 1080, 'export_preset': '1080p'})
        self.assertEqual((result['width'], result['height']), (1920, 1080))
        self.assertEqual(result['video_bitrate'], '12M')

    def test_4k_preset_preserves_portrait_orientation(self):
        result = self._validate({'width': 1080, 'height': 1920, 'export_preset': '4k'})
        self.assertEqual((result['width'], result['height']), (2160, 3840))
        self.assertEqual(result['video_bitrate'], '35M')

    def test_custom_bitrate_is_validated(self):
        result = self._validate({'width': 1280, 'height': 720, 'video_bitrate': '8M'})
        self.assertEqual(result['video_bitrate'], '8M')
        with self.assertRaises(Exception):
            self._validate({'width': 1280, 'height': 720, 'video_bitrate': '999M'})

    def test_unknown_export_preset_is_rejected(self):
        with self.assertRaises(Exception):
            self._validate({'export_preset': 'ultra-mega'})

class RenderProgressTests(unittest.TestCase):
    def test_ffmpeg_progress_callback_reports_intermediate_and_completion(self):
        import io
        from unittest.mock import patch
        from app.rendering import render_mp4

        class FakeProcess:
            def __init__(self, command, **kwargs):
                self.stdout = io.StringIO("out_time_ms=5000000\nprogress=continue\nout_time_ms=10000000\nprogress=end\n")
                self.returncode = None
                Path(command[-1]).write_bytes(b"rendered-video")
            def wait(self, timeout=None):
                self.returncode = 0
                return 0
            def poll(self):
                return self.returncode
            def terminate(self):
                self.returncode = -15
            def kill(self):
                self.returncode = -9

        output = Path('/tmp/flexy-progress-test.mp4')
        output.unlink(missing_ok=True)
        graph = {
            "clips": [{"path": "/tmp/source.mp4", "source_start": 0, "duration": 10,
                       "timeline_start": 0, "track_index": 0, "transition": "none"}],
            "audio_clips": [], "captions": [], "video_duration": 10,
            "width": 1280, "height": 720, "frame_rate": 30, "video_bitrate": "5M",
        }
        values = []
        with patch('app.rendering.shutil.which', return_value='/usr/bin/ffmpeg'), \
             patch('app.rendering.subprocess.Popen', FakeProcess):
            render_mp4(graph, output, progress_callback=values.append)
        self.assertIn(50, values)
        self.assertIn(99, values)
        self.assertEqual(values[-1], 100)
        output.unlink(missing_ok=True)

    def test_rejects_120_fps_for_8k_export(self):
        media_dir = Path("/tmp/flexy-test-8k-120")
        media_dir.mkdir(exist_ok=True)
        (media_dir / "clip.mp4").write_bytes(b"video")
        try:
            with patch("app.rendering.storage.get_media", return_value={
                "stored_name": "clip.mp4", "mime_type": "video/mp4"
            }), patch("app.rendering.storage.MEDIA_DIR", media_dir):
                with self.assertRaisesRegex(RenderValidationError, "supported up to 4K"):
                    validate_render_graph({
                        "export_preset": "8k", "frame_rate": 120,
                        "clips": [{"media_id": "video-1", "duration": 2}],
                    })
        finally:
            (media_dir / "clip.mp4").unlink(missing_ok=True)
            media_dir.rmdir()

    def test_accepts_120_fps_for_4k_export(self):
        media_dir = Path("/tmp/flexy-test-4k-120")
        media_dir.mkdir(exist_ok=True)
        (media_dir / "clip.mp4").write_bytes(b"video")
        try:
            with patch("app.rendering.storage.get_media", return_value={
                "stored_name": "clip.mp4", "mime_type": "video/mp4"
            }), patch("app.rendering.storage.MEDIA_DIR", media_dir):
                result = validate_render_graph({
                    "export_preset": "4k", "frame_rate": 120,
                    "clips": [{"media_id": "video-1", "duration": 2}],
                })
                self.assertEqual(result["width"], 3840)
                self.assertEqual(result["frame_rate"], 120)
        finally:
            (media_dir / "clip.mp4").unlink(missing_ok=True)
            media_dir.rmdir()


class RenderProcessControlTests(unittest.TestCase):
    def _graph(self):
        return {
            "clips": [{"path": "/tmp/source.mp4", "source_start": 0, "duration": 2,
                       "timeline_start": 0, "track_index": 0, "transition": "none"}],
            "audio_clips": [], "captions": [], "video_duration": 2,
            "width": 1280, "height": 720, "frame_rate": 30, "video_bitrate": "5M",
        }

    def test_cancellation_is_checked_even_when_ffmpeg_emits_no_progress(self):
        import io
        from app.rendering import render_mp4, RenderCancelledError

        class SilentProcess:
            instance = None
            def __init__(self, *_args, **_kwargs):
                self.stdout = io.StringIO("")
                self.returncode = None
                self.terminated = False
                SilentProcess.instance = self
            def poll(self):
                return self.returncode
            def terminate(self):
                self.terminated = True
                self.returncode = -15
            def wait(self, timeout=None):
                return self.returncode
            def kill(self):
                self.returncode = -9

        output = Path("/tmp/flexy-silent-cancel.mp4")
        with patch("app.rendering.shutil.which", return_value="/usr/bin/ffmpeg"), \
             patch("app.rendering.subprocess.Popen", SilentProcess):
            with self.assertRaises(RenderCancelledError):
                render_mp4(self._graph(), output, cancel_check=lambda: True)
        self.assertTrue(SilentProcess.instance.terminated)
        output.unlink(missing_ok=True)

    def test_timeout_is_checked_even_when_ffmpeg_emits_no_progress(self):
        import io
        from app.rendering import render_mp4, MAX_RENDER_SECONDS

        class SilentProcess:
            instance = None
            def __init__(self, *_args, **_kwargs):
                self.stdout = io.StringIO("")
                self.returncode = None
                self.terminated = False
                SilentProcess.instance = self
            def poll(self):
                return self.returncode
            def terminate(self):
                self.terminated = True
                self.returncode = -15
            def wait(self, timeout=None):
                return self.returncode
            def kill(self):
                self.returncode = -9

        output = Path("/tmp/flexy-silent-timeout.mp4")
        with patch("app.rendering.shutil.which", return_value="/usr/bin/ffmpeg"), \
             patch("app.rendering.subprocess.Popen", SilentProcess), \\
             patch("app.rendering.MAX_RENDER_SECONDS", -1):
            with self.assertRaisesRegex(RuntimeError, "60-minute time limit"):
                render_mp4(self._graph(), output)
        self.assertTrue(SilentProcess.instance.terminated)
        output.unlink(missing_ok=True)
