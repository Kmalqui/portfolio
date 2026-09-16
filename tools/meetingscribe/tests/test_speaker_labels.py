import unittest

import numpy as np

from speaker_labels import TranscriptSegment, label_transcript


class SpeakerLabelTests(unittest.TestCase):
    def test_labels_microphone_dominant_segment_as_myself(self):
        rate = 1_000
        mic = np.r_[np.full(rate, 0.2), np.zeros(rate)].astype(np.float32)
        others = np.r_[np.zeros(rate), np.full(rate, 0.2)].astype(np.float32)
        segments = [
            TranscriptSegment(0, 1, "I will take that."),
            TranscriptSegment(1, 2, "Thank you."),
        ]
        transcript = label_transcript(segments, mic, others, rate, 2)
        self.assertIn("[00:00] Myself: I will take that.", transcript)
        self.assertIn("[00:01] Speaker 1: Thank you.", transcript)

    def test_remote_labels_are_stable_and_bounded(self):
        rate = 8_000
        t = np.arange(rate) / rate
        first = (0.2 * np.sin(2 * np.pi * 180 * t)).astype(np.float32)
        second = (0.2 * np.sin(2 * np.pi * 760 * t)).astype(np.float32)
        meeting = np.concatenate([first, second, first, second])
        segments = [TranscriptSegment(i, i + 1, str(i)) for i in range(4)]
        transcript = label_transcript(segments, np.zeros_like(meeting), meeting, rate, 2)
        labels = [line.split("] ", 1)[1].split(":", 1)[0] for line in transcript.splitlines()]
        self.assertEqual(labels[0], labels[2])
        self.assertEqual(labels[1], labels[3])
        self.assertEqual(set(labels), {"Speaker 1", "Speaker 2"})

    def test_empty_segments_return_empty_text(self):
        self.assertEqual(label_transcript([], np.zeros(0), np.zeros(0), 48_000), "")


if __name__ == "__main__":
    unittest.main()
