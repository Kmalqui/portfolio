"""Live worker regressions without devices, downloads, or private recordings."""
import queue
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

import app


def segments(text):
    return iter([SimpleNamespace(text=text)]), None


class LiveTranscriptionTests(unittest.TestCase):
    def run_worker(self, models, chunks=1):
        worker = app.LiveTranscriber("medium")
        worker._queue = queue.Queue()
        audio = np.ones(48_000, dtype=np.float32)
        for _ in range(chunks):
            worker._queue.put(audio)
        worker._queue.put(None)
        texts, errors, statuses = [], [], []
        worker.text_ready.connect(texts.append)
        worker.error.connect(errors.append)
        worker.status.connect(statuses.append)
        with patch.object(app, "WhisperModel", side_effect=models) as factory:
            worker._run()
        self.assertFalse(worker.submit(audio))
        return texts, errors, statuses, factory

    def test_gpu_inference_failure_retries_same_chunk_and_stays_on_cpu(self):
        gpu, cpu = Mock(), Mock()
        gpu.transcribe.side_effect = RuntimeError("Library cublas64_12.dll not found")
        cpu.transcribe.side_effect = [segments("First sentence."), segments("Next sentence.")]
        texts, errors, statuses, factory = self.run_worker([gpu, cpu], chunks=2)
        self.assertEqual(texts, ["First sentence.", "Next sentence."])
        self.assertEqual(errors, [])
        self.assertEqual(gpu.transcribe.call_count, 1)
        self.assertEqual(cpu.transcribe.call_count, 2)
        self.assertIs(gpu.transcribe.call_args.args[0], cpu.transcribe.call_args_list[0].args[0])
        self.assertEqual(factory.call_args.kwargs, {"device": "cpu", "compute_type": "int8", "cpu_threads": 4, "num_workers": 1})
        self.assertTrue(any("switching" in s for s in statuses))

    def test_lazy_iterator_failure_retries_without_partial_duplicate_text(self):
        def broken_segments():
            yield SimpleNamespace(text="Partial text")
            raise RuntimeError("Deferred CUDA failure")
        gpu, cpu = Mock(), Mock()
        gpu.transcribe.return_value = broken_segments(), None
        cpu.transcribe.return_value = segments("Complete text")
        texts, errors, _, _ = self.run_worker([gpu, cpu])
        self.assertEqual(texts, ["Complete text"])
        self.assertEqual(errors, [])

    def test_model_load_failure_uses_cpu(self):
        cpu = Mock()
        cpu.transcribe.return_value = segments("CPU works")
        texts, errors, _, _ = self.run_worker([RuntimeError("No CUDA"), cpu])
        self.assertEqual(texts, ["CPU works"])
        self.assertEqual(errors, [])

    def test_working_gpu_does_not_load_cpu(self):
        gpu = Mock()
        gpu.transcribe.return_value = segments("GPU works")
        texts, errors, _, factory = self.run_worker([gpu])
        self.assertEqual(texts, ["GPU works"])
        self.assertEqual(errors, [])
        self.assertEqual(factory.call_count, 1)

    def test_cpu_failure_is_reported_without_retry_loop(self):
        gpu, cpu = Mock(), Mock()
        gpu.transcribe.side_effect = RuntimeError("GPU unavailable")
        cpu.transcribe.side_effect = RuntimeError("CPU unavailable")
        texts, errors, _, factory = self.run_worker([gpu, cpu])
        self.assertEqual(texts, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("Recording continues", errors[0])
        self.assertEqual(factory.call_count, 2)

    def test_stop_during_inference_does_not_emit_late_text(self):
        worker = app.LiveTranscriber("medium")
        worker.submit(np.ones(48_000, dtype=np.float32))
        gpu = Mock()
        def finish_after_stop(*args, **kwargs):
            worker.stop()
            return segments("Stale result")
        gpu.transcribe.side_effect = finish_after_stop
        texts = []
        worker.text_ready.connect(texts.append)
        with patch.object(app, "WhisperModel", return_value=gpu):
            worker._run()
        self.assertEqual(texts, [])

    def test_eco_uses_small_cpu_budget_without_attempting_gpu(self):
        worker = app.LiveTranscriber("tiny", cpu_threads=2, prefer_gpu=False)
        worker.submit(np.ones(48_000, dtype=np.float32))
        self.assertFalse(worker.can_accept())
        self.assertFalse(worker.submit(np.ones(48_000, dtype=np.float32)))
        cpu = Mock()
        cpu.transcribe.return_value = segments("Eco works")
        worker.text_ready.connect(lambda text: worker.stop())
        with patch.object(app, "WhisperModel", return_value=cpu) as factory:
            worker._run()
        factory.assert_called_once_with("tiny", device="cpu", compute_type="int8", cpu_threads=2, num_workers=1)

    def test_snapshot_is_bounded_and_keeps_backlog_in_order(self):
        recorder = app.Recorder()
        recorder._live_cursor = 0
        block = np.full(app.BLOCK_SIZE, .1, dtype=np.float32)
        recorder._mic_chunks = [block] * 6000  # Ten minutes of recording.
        recorder._system_chunks = [block] * 6000
        first, end = recorder.live_snapshot()
        self.assertEqual(end, app.SAMPLE_RATE * 12)
        self.assertEqual(len(first), end)
        np.testing.assert_allclose(first, .136)
        recorder.commit_live_snapshot(end)
        second, next_end = recorder.live_snapshot()
        self.assertEqual(next_end, app.SAMPLE_RATE * 24)
        self.assertEqual(len(second), app.SAMPLE_RATE * 13)

    def test_snapshot_handles_missing_system_audio_and_short_recordings(self):
        recorder = app.Recorder()
        recorder._live_cursor = 0
        block = np.full(app.BLOCK_SIZE, .1, dtype=np.float32)
        recorder._mic_chunks = [block] * 20
        self.assertIsNone(recorder.live_snapshot())
        recorder._mic_chunks = [block] * 80
        audio, end = recorder.live_snapshot()
        np.testing.assert_allclose(audio, .068)
        self.assertEqual(end, app.SAMPLE_RATE * 8)


if __name__ == "__main__":
    unittest.main()
