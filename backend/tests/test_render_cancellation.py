import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.rendering import RenderCancelledError, render_mp4
from app import storage


class RenderCancellationTests(unittest.TestCase):
    def test_renderer_stops_ffmpeg_when_cancel_requested(self):
        process = MagicMock()
        process.stdout = iter(["out_time_ms=1000000\n"])
        process.poll.side_effect = [None, 0]
        process.wait.return_value = 0
        graph = {
            "clips": [{"path": "/tmp/source.mp4", "source_start": 0, "duration": 2,
                       "timeline_start": 0, "track_index": 0, "transition": "none", "is_image": False}],
            "audio_clips": [], "captions": [], "video_duration": 2,
            "width": 1280, "height": 720, "frame_rate": 30, "video_bitrate": "5M",
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "out.mp4"
            with patch("app.rendering.shutil.which", return_value="/usr/bin/ffmpeg"), \
                 patch("app.rendering.subprocess.Popen", return_value=process), \\
                 patch("app.rendering.probe_video_encoders", return_value={"ffmpeg_available": True, "available": ["libx264"], "hardware": []}):
                with self.assertRaises(RenderCancelledError):
                    render_mp4(graph, output, cancel_check=lambda: True)
        process.terminate.assert_called_once()
        process.wait.assert_called()

    def test_start_job_does_not_overwrite_cancel_request(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "test.sqlite3"
            with patch.object(storage, "DB_PATH", db_path):
                storage.init_db()
                storage.save_project("p1", "Test", {})
                storage.create_job("j1", "p1")
                cancelled = storage.request_job_cancel("j1")
                self.assertEqual(cancelled["status"], "cancelling")
                self.assertFalse(storage.start_job("j1"))
                self.assertEqual(storage.get_job("j1")["status"], "cancelling")

    def test_cancel_request_only_changes_active_jobs(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "test.sqlite3"
            with patch.object(storage, "DB_PATH", db_path):
                storage.init_db()
                storage.save_project("p1", "Test", {})
                storage.create_job("j1", "p1")
                storage.start_job("j1")
                storage.update_job("j1", status="completed", progress=100, output_name="j1.mp4")
                result = storage.request_job_cancel("j1")
                self.assertEqual(result["status"], "completed")

    def test_cancellation_wins_race_against_output_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "test.sqlite3"
            with patch.object(storage, "DB_PATH", db_path):
                storage.init_db()
                storage.save_project("p1", "Test", {})
                storage.create_job("j1", "p1")
                storage.start_job("j1")
                storage.request_job_cancel("j1")
                self.assertFalse(storage.complete_job_if_processing("j1", "j1.mp4"))
                self.assertEqual(storage.get_job("j1")["status"], "cancelling")


if __name__ == "__main__":
    unittest.main()
