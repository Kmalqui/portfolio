import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import soundfile as sf

import app
from audio_cleanup import CleanupSettings, VoiceCleanup


class AudioCleanupTests(unittest.TestCase):
    def test_mac_uses_virtual_input_without_requesting_speaker_loopback(self):
        microphone = Mock()
        microphone.id, microphone.name = "mic", "Built-in Microphone"
        blackhole = Mock()
        blackhole.id, blackhole.name = "blackhole", "BlackHole 2ch"
        threads = [Mock(), Mock()]
        with patch.object(app, "IS_MAC", True), patch.object(
            app.Recorder, "microphones", return_value=[microphone, blackhole]
        ), patch.object(
            app.Recorder, "system_audio_sources", return_value=[microphone, blackhole]
        ), patch.object(
            app.threading, "Thread", side_effect=threads
        ) as thread_factory, patch.object(app.sc, "get_microphone") as get_loopback:
            app.Recorder().start(app.AudioSelection("mic", "blackhole"))
        get_loopback.assert_not_called()
        self.assertIs(thread_factory.call_args_list[0].kwargs["args"][0], microphone)
        self.assertIs(thread_factory.call_args_list[1].kwargs["args"][0], blackhole)
        for thread in threads:
            thread.start.assert_called_once()

    def test_windows_still_resolves_selected_speaker_loopback(self):
        microphone = Mock()
        microphone.id, microphone.name = "mic", "Microphone"
        speaker = Mock()
        speaker.id, speaker.name = "speaker", "Speakers"
        loopback = Mock()
        with patch.object(app, "IS_MAC", False), patch.object(
            app.Recorder, "microphones", return_value=[microphone]
        ), patch.object(
            app.Recorder, "system_audio_sources", return_value=[speaker]
        ), patch.object(app.sc, "get_microphone", return_value=loopback) as get_loopback, patch.object(
            app.threading, "Thread", side_effect=[Mock(), Mock()]
        ) as thread_factory:
            app.Recorder().start(app.AudioSelection("mic", "speaker"))
        get_loopback.assert_called_once_with("speaker", include_loopback=True)
        self.assertIs(thread_factory.call_args_list[1].kwargs["args"][0], loopback)

    def test_recorder_pause_state_can_resume(self):
        recorder = app.Recorder()
        self.assertFalse(recorder.is_paused())
        recorder.pause()
        self.assertTrue(recorder.is_paused())
        recorder.resume()
        self.assertFalse(recorder.is_paused())

    def test_off_is_exact_passthrough(self):
        audio = np.random.default_rng(1).normal(0, .1, 4800).astype(np.float32)
        self.assertIs(VoiceCleanup(CleanupSettings()).process(audio), audio)

    def test_quiet_background_is_reduced_not_hard_muted(self):
        audio = np.full(48000, .0003, np.float32)
        result = VoiceCleanup(CleanupSettings(noise_reduction=True)).process(audio)
        self.assertLess(float(np.mean(result[-4800:])), .00006)
        self.assertGreater(float(np.min(result)), 0)

    def test_speech_above_threshold_is_preserved_without_leveling(self):
        audio = np.full(48000, .03, np.float32)
        np.testing.assert_allclose(VoiceCleanup(CleanupSettings(noise_reduction=True)).process(audio), audio)

    def test_leveling_is_bounded_and_silence_stays_silent(self):
        processor = VoiceCleanup(CleanupSettings(level_volume=True))
        audio = np.full(48000, .02, np.float32)
        result = processor.process(audio)
        self.assertGreater(float(result[-1]), .04)
        self.assertLessEqual(float(result.max()), .06001)
        np.testing.assert_array_equal(processor.process(np.zeros(4800, np.float32)), 0)
        self.assertLessEqual(float(np.max(processor.process(np.ones(4800, np.float32)))), .980001)

    def test_streaming_matches_whole_buffer(self):
        settings = CleanupSettings(noise_reduction=True, level_volume=True)
        audio = np.random.default_rng(2).normal(0, .02, 48000).astype(np.float32)
        processor = VoiceCleanup(settings)
        streamed = np.concatenate([processor.process(block) for block in np.split(audio, 10)])
        np.testing.assert_allclose(streamed, VoiceCleanup(settings).process(audio))

    def test_capture_keeps_original_and_uses_cleanup_for_transcription(self):
        for is_mic, clean_others in ((True, False), (False, False), (False, True)):
            with self.subTest(is_mic=is_mic, clean_others=clean_others), tempfile.TemporaryDirectory() as folder:
                recorder = app.Recorder()
                recorder.cleanup_settings = CleanupSettings(noise_reduction=True, clean_others=clean_others)
                recorder.original_folder = Path(folder)
                audio = np.full(app.BLOCK_SIZE, .0003, np.float32)
                device = Mock()
                stream = device.recorder.return_value.__enter__ = Mock()
                capture = Mock()
                stream.return_value = capture
                device.recorder.return_value.__exit__ = Mock(return_value=False)
                def read(**kwargs):
                    recorder._stop.set()
                    return audio.copy()
                capture.record.side_effect = read
                chunks, errors = [], []
                recorder.error.connect(errors.append)
                recorder._capture(device, chunks, is_mic)
                self.assertEqual(errors, [])
                filename = "microphone-original.wav" if is_mic else "meeting-audio-original.wav"
                original, rate = sf.read(Path(folder) / filename)
                self.assertEqual(rate, app.SAMPLE_RATE)
                np.testing.assert_allclose(original, audio, atol=1/32768)
                if is_mic or clean_others:
                    self.assertLess(float(chunks[0][-1]), float(audio[-1]))
                else:
                    np.testing.assert_array_equal(chunks[0], audio)


if __name__ == "__main__":
    unittest.main()
