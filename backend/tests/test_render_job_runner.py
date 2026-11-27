import unittest
from unittest.mock import patch

from app import main


class QueuedRenderCancellationTests(unittest.TestCase):
    @patch("app.main.render_mp4")
    @patch("app.main.storage.update_job")
    @patch("app.main.storage.get_job", return_value={"status": "cancelling"})
    @patch("app.main.storage.start_job", return_value=False)
    def test_queued_cancel_is_finalized_without_starting_ffmpeg(
        self, start_job, get_job, update_job, render_mp4
    ):
        main.run_render_job("job-queued-cancelled", {"clips": []})

        start_job.assert_called_once_with("job-queued-cancelled")
        get_job.assert_called_once_with("job-queued-cancelled")
        update_job.assert_called_once_with(
            "job-queued-cancelled",
            status="cancelled",
            progress=0,
            output_name=None,
            error="Render cancelled before processing started.",
        )
        render_mp4.assert_not_called()


if __name__ == "__main__":
    unittest.main()
