"""Screen recording calculations; no real display is captured."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import av
import numpy as np
from screen_recording import PROFILES, ScreenOptions, ScreenRecorder, output_size


class ScreenRecordingTests(unittest.TestCase):
    def test_profiles_have_sensible_resource_steps(self):
        self.assertLess(PROFILES["efficient"][1], PROFILES["standard"][1])
        self.assertLess(PROFILES["standard"][1], PROFILES["high"][1])
        self.assertEqual(ScreenOptions().profile, "efficient")
        self.assertFalse(ScreenOptions().enabled)

    def test_output_size_preserves_shape_and_encoder_evenness(self):
        self.assertEqual(output_size(2560, 1440, 1280), (1280, 720))
        self.assertEqual(output_size(1921, 1081, None), (1920, 1080))

    def test_recorder_has_dedicated_mp4_target_and_starts_idle(self):
        with tempfile.TemporaryDirectory() as folder:
            recorder = ScreenRecorder(Path(folder) / "screen-recording.mp4", ScreenOptions(True))
            self.assertEqual(recorder.output.name, "screen-recording.mp4")
            self.assertFalse(recorder.is_running())
            self.assertFalse(recorder.is_paused())
            recorder.pause()
            self.assertTrue(recorder.is_paused())
            recorder.resume()
            self.assertFalse(recorder.is_paused())

    def test_unknown_profile_is_not_silently_accepted(self):
        self.assertNotIn("unknown", PROFILES)

    def test_encoder_writes_a_playable_mp4_without_capturing_real_screen(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "screen-recording.mp4"
            recorder = ScreenRecorder(target, ScreenOptions(True, 1, "efficient"))

            class FakeCapture:
                monitors = [{}, {"left": 0, "top": 0, "width": 96, "height": 64}]

                def __enter__(self):
                    return self

                def __exit__(self, *_args):
                    return False

                def grab(self, _monitor):
                    recorder._stop.set()
                    return np.zeros((64, 96, 4), dtype=np.uint8)

            with patch("screen_recording.mss.mss", return_value=FakeCapture()):
                recorder._capture()
            self.assertTrue(target.exists())
            with av.open(str(target)) as container:
                frames = list(container.decode(video=0))
            self.assertEqual(len(frames), 1)
            self.assertEqual((frames[0].width, frames[0].height), (96, 64))


if __name__ == "__main__":
    unittest.main()
