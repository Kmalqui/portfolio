from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str


def _slice(audio: np.ndarray, start: float, end: float, sample_rate: int) -> np.ndarray:
    left = max(0, int(start * sample_rate))
    right = min(len(audio), max(left, int(end * sample_rate)))
    return np.asarray(audio[left:right], dtype=np.float32)


def _rms(audio: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0


def _voice_features(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    """Small, dependency-free voice signature used for approximate local grouping."""
    if audio.size < 32:
        return np.zeros(11, dtype=np.float32)
    audio = audio - float(np.mean(audio))
    peak = float(np.max(np.abs(audio)))
    if peak:
        audio = audio / peak
    window = np.hanning(len(audio))
    spectrum = np.abs(np.fft.rfft(audio * window)) + 1e-7
    frequencies = np.fft.rfftfreq(len(audio), 1 / sample_rate)
    edges = (80, 180, 300, 500, 800, 1250, 2000, 3200, 5000)
    bands = []
    for low, high in zip(edges, edges[1:]):
        values = spectrum[(frequencies >= low) & (frequencies < high)]
        bands.append(float(np.log(np.mean(values) + 1e-7)) if values.size else -16.0)
    centroid = float(np.sum(frequencies * spectrum) / np.sum(spectrum)) / 5000
    zcr = float(np.mean(np.signbit(audio[1:]) != np.signbit(audio[:-1])))
    spread = float(np.sqrt(np.sum(((frequencies / 5000 - centroid) ** 2) * spectrum) / np.sum(spectrum)))
    return np.asarray([*bands, centroid, zcr, spread], dtype=np.float32)


def _cluster(features: np.ndarray, count: int) -> np.ndarray:
    count = max(1, min(count, len(features)))
    if count == 1:
        return np.zeros(len(features), dtype=np.int32)
    normalized = (features - features.mean(axis=0)) / (features.std(axis=0) + 1e-5)
    # Deterministic farthest-first seeds keep labels stable between runs.
    seeds = [0]
    while len(seeds) < count:
        distance = np.min(
            np.stack([np.sum((normalized - normalized[index]) ** 2, axis=1) for index in seeds]),
            axis=0,
        )
        seeds.append(int(np.argmax(distance)))
    centers = normalized[seeds].copy()
    labels = np.full(len(features), -1, dtype=np.int32)
    for _ in range(20):
        distances = np.stack([np.sum((normalized - center) ** 2, axis=1) for center in centers], axis=1)
        updated = np.argmin(distances, axis=1).astype(np.int32)
        if np.array_equal(updated, labels):
            break
        labels = updated
        for index in range(count):
            members = normalized[labels == index]
            if len(members):
                centers[index] = members.mean(axis=0)
    # Speaker 1 is whichever remote voice appears first, not an arbitrary cluster id.
    order = []
    for label in labels:
        if int(label) not in order:
            order.append(int(label))
    mapping = {old: new for new, old in enumerate(order)}
    return np.asarray([mapping[int(label)] for label in labels], dtype=np.int32)


def label_transcript(
    segments: list[TranscriptSegment],
    microphone: np.ndarray,
    meeting_audio: np.ndarray,
    sample_rate: int,
    other_speakers: int = 2,
) -> str:
    if not segments:
        return ""
    identities: list[str | None] = []
    remote_features = []
    remote_positions = []
    for position, segment in enumerate(segments):
        mic = _slice(microphone, segment.start, segment.end, sample_rate)
        others = _slice(meeting_audio, segment.start, segment.end, sample_rate)
        mic_level, others_level = _rms(mic), _rms(others)
        if mic_level >= 0.0015 and mic_level > others_level * 1.25:
            identities.append("Myself")
        else:
            identities.append(None)
            remote_positions.append(position)
            remote_features.append(_voice_features(others, sample_rate))
    if remote_features:
        clusters = _cluster(np.stack(remote_features), other_speakers)
        for position, cluster in zip(remote_positions, clusters):
            identities[position] = f"Speaker {int(cluster) + 1}"
    lines = []
    for identity, segment in zip(identities, segments):
        minutes, seconds = divmod(max(0, int(segment.start)), 60)
        lines.append(f"[{minutes:02d}:{seconds:02d}] {identity}: {segment.text.strip()}")
    return "\n".join(lines)
