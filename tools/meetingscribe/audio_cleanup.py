"""Small, original NumPy-only audio controls; no cloud or learned denoiser."""
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class CleanupSettings:
    noise_reduction: bool = False
    level_volume: bool = False
    threshold_db: int = -50
    clean_others: bool = False

    @property
    def enabled(self):
        return self.noise_reduction or self.level_volume


class VoiceCleanup:
    """Soft downward expansion and conservative gain leveling in 10 ms frames.

    Quiet-background reduction attenuates low-level audio, not noise mixed with
    speech. A nonzero floor and smoothed gain avoid a hard mute at the threshold.
    Separate instances must be used for separate capture streams.
    """

    def __init__(self, settings: CleanupSettings, sample_rate: int = 48000):
        self.settings = settings
        self.frame_size = max(1, sample_rate // 100)
        self.threshold = 10 ** (settings.threshold_db / 20)
        self.gate_gain = 1.0
        self.volume_gain = 1.0
        self.previous_gain = 1.0

    def process(self, audio: np.ndarray) -> np.ndarray:
        if not self.settings.enabled:
            return audio
        result = np.empty_like(audio, dtype=np.float32)
        for start in range(0, len(audio), self.frame_size):
            frame = audio[start:start + self.frame_size]
            rms = float(np.sqrt(np.mean(frame * frame)))
            if self.settings.noise_reduction:
                target = max(0.126, min(1.0, (rms / self.threshold) ** 2))
                speed = 0.7 if target > self.gate_gain else 0.05
                self.gate_gain += speed * (target - self.gate_gain)
            if self.settings.level_volume and rms >= self.threshold:
                target = max(0.25, min(3.0, 0.1 / max(rms, 1e-8)))
                speed = 0.2 if target < self.volume_gain else 0.02
                self.volume_gain += speed * (target - self.volume_gain)
            gain = self.gate_gain * self.volume_gain
            ramp = np.linspace(self.previous_gain, gain, len(frame), dtype=np.float32)
            result[start:start + len(frame)] = frame * ramp
            self.previous_gain = gain
        return np.clip(result, -0.98, 0.98)
