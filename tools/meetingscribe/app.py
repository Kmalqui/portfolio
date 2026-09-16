from __future__ import annotations

import json
import os
import queue
import re
import shutil
import sys
import subprocess
import threading
from contextlib import ExitStack
from dataclasses import asdict
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import requests
import soundcard as sc
import soundfile as sf
from faster_whisper import WhisperModel
from audio_cleanup import CleanupSettings, VoiceCleanup
import bubbly_theme
import updater
from screen_recording import PROFILES as SCREEN_PROFILES, ScreenOptions, ScreenRecorder, available_monitors
from speaker_labels import TranscriptSegment, label_transcript
from PySide6.QtCore import QObject, QRectF, QSettings, QSize, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QColor, QDesktopServices, QFont, QIcon, QPainter, QPalette, QPen
from PySide6.QtWidgets import (
    QApplication,
    QAbstractButton,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


APP_NAME = "MeetingScribe"
APP_VERSION = "0.3.14-beta"
SAMPLE_RATE = 48_000
BLOCK_SIZE = 4_800
LIVE_CHUNK_SECONDS = 12
LIVE_PROFILES = {
    "eco": ("tiny", 2, False, 12_000),
    "balanced": ("small", 4, True, 8_000),
}
APP_STYLESHEET = """
QWidget { color: #173329; font-family: "Segoe UI"; font-size: 13px; }
QMainWindow, QWidget#appRoot {
    background: #f3f6ef;
    color: #173329;
    font-family: "Segoe UI";
    font-size: 13px;
}
QLabel#brandTitle { color: #102a22; font-size: 28px; font-weight: 800; }
QLabel#brandSubtitle { color: #607269; font-size: 13px; }
QLabel#sectionTitle { color: #173329; font-size: 15px; font-weight: 700; }
QLabel#sectionHint, QLabel#meterState { color: #718078; font-size: 11px; }
QLabel#fieldLabel { color: #42564d; font-weight: 600; }
QFrame#card, QFrame#workspaceCard {
    background: #ffffff;
    border: 1px solid #dce5dc;
    border-radius: 14px;
}
QFrame#meterPanel {
    background: #f7faf5;
    border: 1px solid #dce5dc;
    border-radius: 10px;
}
QFrame#consentCard {
    background: #fff8e8;
    border: 1px solid #ead39a;
    border-radius: 12px;
}
QLabel#consentTitle { color: #765612; font-weight: 700; }
QComboBox, QSpinBox {
    min-height: 34px;
    padding: 2px 10px;
    border: 1px solid #cdd8cf;
    border-radius: 8px;
    background: #fbfdf9;
    selection-background-color: #9fca3d;
    color: #173329;
}
QComboBox:hover, QComboBox:focus, QSpinBox:hover, QSpinBox:focus {
    border-color: #789c2d;
}
QPlainTextEdit {
    padding: 10px;
    border: 1px solid #d5dfd7;
    border-radius: 9px;
    background: #fbfcfa;
    color: #20362e;
    selection-background-color: #cfe993;
}
QPlainTextEdit:focus { border-color: #82aa31; background: #ffffff; }
QPushButton {
    min-height: 34px;
    padding: 4px 14px;
    border: 1px solid #c9d4cb;
    border-radius: 8px;
    background: #ffffff;
    color: #214438;
    font-weight: 600;
}
QPushButton:hover { background: #edf5e3; border-color: #96b65b; }
QPushButton:pressed { background: #e0edce; }
QPushButton:disabled { color: #9aa69f; background: #eef1ed; border-color: #dde3dd; }
QPushButton#recordButton {
    min-height: 48px;
    border: none;
    border-radius: 11px;
    background: #9fca3d;
    color: #102a22;
    font-size: 15px;
    font-weight: 800;
}
QPushButton#recordButton:hover { background: #aed94c; }
QPushButton#recordButton:disabled { background: #e0e9cf; color: #738365; }
QPushButton#recordButton[recording="true"] { background: #dc5b55; color: #ffffff; }
QPushButton#recordButton[processing="true"] { background: #315c4d; color: #ffffff; }
QLabel#timer {
    min-width: 112px;
    padding: 8px 12px;
    border: 1px solid #d8e1d9;
    border-radius: 9px;
    background: #ffffff;
    color: #173329;
    font-size: 19px;
    font-weight: 700;
}
QLabel#statusPill {
    padding: 8px 12px;
    border-radius: 9px;
    background: #e9f3df;
    color: #345d25;
    font-weight: 600;
}
QProgressBar {
    min-height: 13px;
    max-height: 13px;
    border: none;
    border-radius: 6px;
    background: #dfe7df;
}
QProgressBar::chunk { border-radius: 6px; background: #8fbd35; }
QCheckBox { spacing: 9px; color: #5d4919; font-weight: 600; }
QCheckBox::indicator { width: 18px; height: 18px; }
QSplitter::handle { height: 8px; background: transparent; }
QStatusBar { background: #f3f6ef; color: #718078; }
QLabel#privacyBadge { padding: 7px 11px; border-radius: 10px; background: #dff0bb; color: #375a22; font-size: 10px; font-weight: 800; }
QComboBox#liveMode { min-height: 20px; padding: 1px 8px; font-size: 12px; }
QPushButton#clarityButton { min-height: 20px; padding: 1px 8px; font-size: 12px; }
"""


DARK_STYLESHEET = """
QWidget { color: #e4eee8; }
QMainWindow, QWidget#appRoot, QStatusBar { background: #151e1b; color: #b0c2b7; }
QLabel#brandTitle, QLabel#sectionTitle { color: #edf5ef; }
QLabel#brandSubtitle, QLabel#sectionHint, QLabel#meterState { color: #a8beb0; }
QLabel#fieldLabel { color: #d1e1d6; }
QFrame#card, QFrame#workspaceCard { background: #202d26; border-color: #3a4e40; }
QFrame#meterPanel { background: #19251f; border-color: #3a4e40; }
QFrame#consentCard { background: #332d1d; border-color: #71613a; }
QLabel#consentTitle, QCheckBox { color: #f2d68e; }
QComboBox, QSpinBox, QPlainTextEdit { background: #17221c; color: #e4eee8; border-color: #4b6051; selection-background-color: #436729; selection-color: #ffffff; }
QComboBox QAbstractItemView { background: #202d26; color: #e4eee8; selection-background-color: #436729; }
QPlainTextEdit:focus { background: #1b2921; border-color: #9fca3d; }
QPushButton { background: #293b2e; color: #e4eee8; border-color: #4b6051; }
QPushButton:hover { background: #354c3b; border-color: #9fca3d; }
QPushButton:pressed { background: #405a36; }
QPushButton:disabled { background: #233029; color: #889a8d; border-color: #34463a; }
QPushButton#recordButton { background: #9fca3d; color: #102a22; }
QPushButton#recordButton:hover { background: #aed94c; }
QPushButton#recordButton:disabled { background: #35462c; color: #a4b696; }
QPushButton#recordButton[recording="true"] { background: #a83430; color: #ffffff; }
QPushButton#recordButton[processing="true"] { background: #315c4d; color: #ffffff; }
QLabel#timer { background: #19251f; border-color: #4b6051; color: #e4eee8; }
QLabel#statusPill { background: #2c4125; color: #d0edab; }
QLabel#privacyBadge { background: #2c4125; color: #d0edab; }
QProgressBar { background: #3a4e40; }
QToolTip { background: #293b2e; color: #edf5ef; border: 1px solid #4b6051; }
"""


def apply_theme(app: QApplication, theme: str = "light") -> None:
    """Apply matching widget and native-control palettes immediately."""
    app.setStyle("Fusion")
    palette = QPalette()
    for role, color in (
        (QPalette.ColorRole.Window, "#f3f6ef"),
        (QPalette.ColorRole.WindowText, "#173329"),
        (QPalette.ColorRole.Base, "#ffffff"),
        (QPalette.ColorRole.AlternateBase, "#f7faf5"),
        (QPalette.ColorRole.Text, "#20362e"),
        (QPalette.ColorRole.Button, "#ffffff"),
        (QPalette.ColorRole.ButtonText, "#214438"),
        (QPalette.ColorRole.Highlight, "#cfe993"),
        (QPalette.ColorRole.HighlightedText, "#173329"),
        (QPalette.ColorRole.PlaceholderText, "#718078"),
        (QPalette.ColorRole.ToolTipBase, "#ffffff"),
        (QPalette.ColorRole.ToolTipText, "#173329"),
    ):
        palette.setColor(role, QColor(color))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#87958c"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#87958c"))
    if theme == "dark":
        for role, color in (
            (QPalette.ColorRole.Window, "#151e1b"),
            (QPalette.ColorRole.WindowText, "#e4eee8"),
            (QPalette.ColorRole.Base, "#17221c"),
            (QPalette.ColorRole.AlternateBase, "#202d26"),
            (QPalette.ColorRole.Text, "#e4eee8"),
            (QPalette.ColorRole.Button, "#293b2e"),
            (QPalette.ColorRole.ButtonText, "#e4eee8"),
            (QPalette.ColorRole.Highlight, "#436729"),
            (QPalette.ColorRole.HighlightedText, "#ffffff"),
            (QPalette.ColorRole.PlaceholderText, "#a8beb0"),
            (QPalette.ColorRole.ToolTipBase, "#293b2e"),
            (QPalette.ColorRole.ToolTipText, "#edf5ef"),
        ):
            palette.setColor(role, QColor(color))
    for role, color in bubbly_theme.palette_colors(theme == "dark").items():
        palette.setColor(getattr(QPalette.ColorRole, role), QColor(color))
    app.setPalette(palette)
    app.setFont(QFont("Segoe UI", 10))
    arrow = resource_path(f"assets/chevron-{'dark' if theme == 'dark' else 'light'}.svg").as_posix()
    app.setStyleSheet(APP_STYLESHEET + (DARK_STYLESHEET if theme == "dark" else "") + bubbly_theme.COMMON + (bubbly_theme.DARK if theme == "dark" else bubbly_theme.LIGHT) + f'QComboBox::down-arrow {{ image: url("{arrow}"); width: 12px; height: 8px; }}')


DEFAULT_PROMPT = """You are an expert meeting-note assistant. Convert the transcript into clean Markdown.

Include:
# A specific meeting title
**Date:** the supplied recording date
## Executive Summary
## Discussion Points
## Decisions
## Action Items

For each action item, include the owner and deadline when stated. Never invent names, dates, decisions, or tasks. If an owner or deadline is unknown, say "Not specified". Do not repeat the full transcript; MeetingScribe adds it above these organized notes.
"""


def resource_path(relative_path: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative_path


def app_data_dir() -> Path:
    root = Path(os.getenv("LOCALAPPDATA", Path.home())) / APP_NAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def default_output_dir(create: bool = True) -> Path:
    root = Path.home() / "Documents" / "Meeting Notes"
    if create:
        root.mkdir(parents=True, exist_ok=True)
    return root


def safe_name(value: str) -> str:
    value = re.sub(r'[<>:"/\\|?*]+', "-", value).strip(" .")
    return value[:100] or "Meeting"


@dataclass
class AudioSelection:
    microphone_id: str
    speaker_id: str


class Recorder(QObject):
    level = Signal(float, float)
    error = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._mic_chunks: list[np.ndarray] = []
        self._system_chunks: list[np.ndarray] = []
        self.cleanup_settings = CleanupSettings()
        self.original_folder: Path | None = None
        self.preserve_tracks = False

    @staticmethod
    def microphones():
        return list(sc.all_microphones(include_loopback=False))

    @staticmethod
    def speakers():
        return list(sc.all_speakers())

    def start(self, selection: AudioSelection) -> None:
        self._stop.clear()
        self._mic_chunks = []
        self._system_chunks = []
        self._live_cursor = 0
        microphones = {str(d.id): d for d in self.microphones()}
        speakers = {str(d.id): d for d in self.speakers()}
        microphone = microphones[selection.microphone_id]
        speaker = speakers[selection.speaker_id]
        loopback = sc.get_microphone(str(speaker.id), include_loopback=True)

        self._threads = [
            threading.Thread(
                target=self._capture,
                args=(microphone, self._mic_chunks, True),
                daemon=True,
            ),
            threading.Thread(
                target=self._capture,
                args=(loopback, self._system_chunks, False),
                daemon=True,
            ),
        ]
        for thread in self._threads:
            thread.start()

    def live_snapshot(self) -> tuple[np.ndarray, int] | None:
        # Capture always appends BLOCK_SIZE frames. Slice only the pending range,
        # never concatenate or copy the full meeting for each live update.
        available = max(len(self._mic_chunks), len(self._system_chunks)) * BLOCK_SIZE
        end = min(available, self._live_cursor + SAMPLE_RATE * LIVE_CHUNK_SECONDS)
        if end - self._live_cursor < SAMPLE_RATE * 4:
            return None
        start = max(0, self._live_cursor - SAMPLE_RATE)
        mixed = np.zeros(end - start, dtype=np.float32)
        for chunks in (self._mic_chunks, self._system_chunks):
            first = start // BLOCK_SIZE
            last = (end + BLOCK_SIZE - 1) // BLOCK_SIZE
            for index, block in enumerate(chunks[first:last], start=first):
                left = max(start, index * BLOCK_SIZE)
                right = min(end, index * BLOCK_SIZE + len(block))
                mixed[left - start:right - start] += block[left - index * BLOCK_SIZE:right - index * BLOCK_SIZE] * 0.68
        peak = float(np.max(np.abs(mixed))) if mixed.size else 0
        if peak > 0.98:
            mixed *= 0.98 / peak
        return mixed, end

    def commit_live_snapshot(self, end: int) -> None:
        self._live_cursor = end

    def _capture(self, device, chunks: list[np.ndarray], is_mic: bool) -> None:
        try:
            settings = self.cleanup_settings
            apply_cleanup = settings.enabled and (is_mic or settings.clean_others)
            cleaner = VoiceCleanup(settings) if apply_cleanup else None
            with ExitStack() as stack:
                recorder = stack.enter_context(device.recorder(samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE))
                original = None
                if settings.enabled and self.original_folder:
                    filename = "microphone-original.wav" if is_mic else "meeting-audio-original.wav"
                    original = stack.enter_context(sf.SoundFile(str(self.original_folder / filename), mode="w", samplerate=SAMPLE_RATE, channels=1, subtype="PCM_16"))
                while not self._stop.is_set():
                    block = recorder.record(numframes=BLOCK_SIZE)
                    if block.ndim == 2:
                        block = np.mean(block, axis=1)
                    block = np.asarray(block, dtype=np.float32)
                    rms = float(np.sqrt(np.mean(np.square(block))) if block.size else 0)
                    if original is not None:
                        original.write(block)
                    chunks.append(cleaner.process(block) if cleaner else block)
                    if is_mic:
                        self.level.emit(min(rms * 900, 100), -1)
                    else:
                        self.level.emit(-1, min(rms * 900, 100))
        except Exception as exc:
            self.error.emit(f"Could not record {device.name}: {exc}")
            self._stop.set()

    def stop(self, destination: Path) -> Path:
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=3)
        if not self._mic_chunks and not self._system_chunks:
            raise RuntimeError("No audio was captured.")

        mic = np.concatenate(self._mic_chunks) if self._mic_chunks else np.zeros(0, np.float32)
        system = (
            np.concatenate(self._system_chunks)
            if self._system_chunks
            else np.zeros(0, np.float32)
        )
        length = max(len(mic), len(system))
        mic = np.pad(mic, (0, length - len(mic)))
        system = np.pad(system, (0, length - len(system)))
        mixed = mic * 0.68 + system * 0.68
        peak = float(np.max(np.abs(mixed))) if mixed.size else 0
        if peak > 0.98:
            mixed *= 0.98 / peak
        sf.write(destination, mixed, SAMPLE_RATE, subtype="PCM_16")
        if self.preserve_tracks:
            sf.write(destination.with_name("microphone.wav"), mic, SAMPLE_RATE, subtype="PCM_16")
            sf.write(destination.with_name("meeting-audio.wav"), system, SAMPLE_RATE, subtype="PCM_16")
        return destination


class LiveTranscriber(QObject):
    text_ready = Signal(str)
    status = Signal(str)
    error = Signal(str)

    def __init__(self, model_name: str, cpu_threads: int = 4, prefer_gpu: bool = True):
        super().__init__()
        self.model_name = model_name
        self.cpu_threads = cpu_threads
        self.prefer_gpu = prefer_gpu
        self._ready = threading.Event()
        self._ready.set()
        self._queue: queue.Queue[np.ndarray | None] = queue.Queue(maxsize=1)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def submit(self, audio: np.ndarray) -> bool:
        if not self.can_accept():
            return False
        self._ready.clear()
        try:
            self._queue.put_nowait(audio)
            return True
        except queue.Full:
            self._ready.set()
            return False

    def can_accept(self) -> bool:
        return not self._stop.is_set() and self._ready.is_set()

    def is_running(self) -> bool:
        return self._thread.is_alive()

    def _load_cpu(self):
        return WhisperModel(self.model_name, device="cpu", compute_type="int8", cpu_threads=self.cpu_threads, num_workers=1)

    def stop(self) -> None:
        self._stop.set()
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass

    def _run(self) -> None:
        try:
            self.status.emit(f"Loading Whisper {self.model_name} for live transcription…")
            using_gpu = self.prefer_gpu
            if using_gpu:
                try:
                    model = WhisperModel(self.model_name, device="cuda", compute_type="float16", cpu_threads=self.cpu_threads, num_workers=1)
                except Exception:
                    using_gpu = False
                    self.status.emit("Starting CPU live transcription…")
                    model = self._load_cpu()
            else:
                model = self._load_cpu()
            self.status.emit("Live transcription is listening…")
            while not self._stop.is_set():
                audio = self._queue.get()
                if audio is None or self._stop.is_set():
                    break
                audio_16k = np.ascontiguousarray(audio[::3], dtype=np.float32)
                try:
                    text = self._transcribe_chunk(model, audio_16k)
                except Exception:
                    if not using_gpu or self._stop.is_set():
                        raise
                    # CUDA libraries can fail on inference, not just model loading.
                    # Retry this same chunk so the fallback does not lose speech.
                    using_gpu = False
                    self.status.emit("Graphics processing unavailable — switching live transcription to CPU…")
                    del model
                    model = self._load_cpu()
                    if self._stop.is_set():
                        break
                    text = self._transcribe_chunk(model, audio_16k)
                    self.status.emit("Live transcription is listening on CPU — updates may take longer.")
                if text and not self._stop.is_set():
                    self.text_ready.emit(text)
                self._ready.set()
        except Exception as exc:
            if not self._stop.is_set():
                self.error.emit(f"Live transcription paused: {exc}. Recording continues; a full transcript will be attempted when you stop.")
        finally:
            self._stop.set()

    @staticmethod
    def _transcribe_chunk(model, audio_16k: np.ndarray) -> str:
        segments, _ = model.transcribe(
            audio_16k,
            vad_filter=True,
            beam_size=1,
            condition_on_previous_text=False,
        )
        # Whisper may defer inference until the segments iterator is consumed.
        return " ".join(segment.text.strip() for segment in segments).strip()


class ProcessingWorker(QObject):
    progress = Signal(str)
    completed = Signal(str, str)
    failed = Signal(str)

    def __init__(self, audio_path: Path, whisper_model: str, ollama_model: str, prompt: str,
                 speaker_labels: bool = False, other_speakers: int = 2):
        super().__init__()
        self.audio_path = audio_path
        self.whisper_model = whisper_model
        self.ollama_model = ollama_model
        self.prompt = prompt
        self.speaker_labels = speaker_labels
        self.other_speakers = other_speakers

    @staticmethod
    def _segments(items) -> list[TranscriptSegment]:
        return [TranscriptSegment(float(item.start), float(item.end), item.text.strip()) for item in items if item.text.strip()]

    def _format_transcript(self, segments: list[TranscriptSegment]) -> str:
        if not self.speaker_labels:
            return " ".join(segment.text for segment in segments).strip()
        mic_path = self.audio_path.with_name("microphone.wav")
        others_path = self.audio_path.with_name("meeting-audio.wav")
        if not mic_path.exists() or not others_path.exists():
            return " ".join(segment.text for segment in segments).strip()
        microphone, mic_rate = sf.read(mic_path, dtype="float32", always_2d=False)
        meeting_audio, others_rate = sf.read(others_path, dtype="float32", always_2d=False)
        if mic_rate != others_rate:
            return " ".join(segment.text for segment in segments).strip()
        return label_transcript(
            segments,
            np.asarray(microphone).reshape(-1),
            np.asarray(meeting_audio).reshape(-1),
            mic_rate,
            self.other_speakers,
        )

    def run(self) -> None:
        try:
            self.progress.emit(f"Loading Whisper {self.whisper_model}…")
            try:
                model = WhisperModel(self.whisper_model, device="cuda", compute_type="float16")
                segments, _ = model.transcribe(
                    str(self.audio_path), vad_filter=True, beam_size=5
                )
                transcript = self._format_transcript(self._segments(segments))
            except Exception:
                self.progress.emit("Using CPU transcription…")
                model = WhisperModel(self.whisper_model, device="cpu", compute_type="int8")
                segments, _ = model.transcribe(
                    str(self.audio_path), vad_filter=True, beam_size=5
                )
                transcript = self._format_transcript(self._segments(segments))

            if not transcript:
                raise RuntimeError(
                    "No speech was detected. Check the microphone and system-audio meters before recording."
                )

            self.progress.emit(f"Generating notes with {self.ollama_model}…")
            recorded = datetime.fromtimestamp(self.audio_path.stat().st_mtime)
            user_content = (
                f"Recording date: {recorded:%Y-%m-%d %H:%M}\n\n"
                f"Transcript:\n{transcript}"
            )
            response = requests.post(
                "http://127.0.0.1:11434/api/chat",
                json={
                    "model": self.ollama_model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": self.prompt},
                        {"role": "user", "content": user_content},
                    ],
                    "options": {"temperature": 0.2},
                },
                timeout=900,
            )
            response.raise_for_status()
            notes = response.json()["message"]["content"].strip()
            self.completed.emit(transcript, notes)
        except Exception as exc:
            self.failed.emit(str(exc))


class ThemeToggle(QAbstractButton):
    """Compact, keyboard-accessible switch: checked means dark mode."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(54, 32)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName("Dark mode")
        self.setAccessibleDescription("Switch on for dark mode, off for light mode. Press Space to toggle.")
        self.setToolTip("Dark mode: on. Light mode: off. Your preference is remembered.")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QColor("#625dff" if self.isChecked() else "#35363e")
        if self.isDown():
            track = track.darker(115)
        if not self.isEnabled():
            painter.setOpacity(0.5)
        painter.setPen(QPen(QColor("#625dff" if self.isChecked() else "#55565f"), 1))
        painter.setBrush(track)
        painter.drawRoundedRect(QRectF(3, 4, 48, 24), 12, 12)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(QRectF(31 if self.isChecked() else 7, 8, 16, 16))
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(self.palette().color(QPalette.ColorRole.WindowText), 1, Qt.PenStyle.DashLine))
            painter.drawRoundedRect(QRectF(1, 1, 52, 30), 15, 15)


class NotesEditor(QPlainTextEdit):
    def sizeHint(self):
        return QSize(320, 80)

    def minimumSizeHint(self):
        return QSize(160, 80)


class MeetingScribeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MeetingScribe — Private Local Meeting Notes")
        self.resize(1000, 900)
        self.settings = QSettings("MeetingScribe", "MeetingScribe")
        apply_theme(QApplication.instance(), self.settings.value("theme", "light"))
        self.recorder = Recorder()
        self.recorder.level.connect(self.update_levels)
        self.recorder.error.connect(self.show_error)
        self.recording = False
        self.started_at = 0.0
        self.current_folder: Path | None = None
        self.current_audio: Path | None = None
        self.worker_thread: QThread | None = None
        self.live_transcriber: LiveTranscriber | None = None
        self.screen_recorder: ScreenRecorder | None = None
        self._update_checking = False
        self._update_downloading = False
        self._available_update = None
        self._ollama_process = None
        self.update_jobs = updater.UpdateJobs(self)
        self.update_jobs.checked.connect(self.update_checked)
        self.update_jobs.downloaded.connect(self.update_downloaded)
        self.update_jobs.progress.connect(self.update_progress)

        self._build_ui()
        self.refresh_devices()
        self.refresh_models()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_timer)
        self.live_timer = QTimer(self)
        self.live_timer.setInterval(8_000)
        self.live_timer.timeout.connect(self.request_live_transcription)

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("appRoot")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(26, 16, 26, 14)
        layout.setSpacing(9)

        header = QHBoxLayout()
        header.setSpacing(13)
        brand_icon = QLabel()
        brand_icon.setPixmap(
            QIcon(str(resource_path("assets/meetingscribe-icon.png"))).pixmap(58, 58)
        )
        brand_icon.setFixedSize(62, 62)
        brand_copy = QVBoxLayout()
        brand_copy.setSpacing(1)
        title = QLabel("MeetingScribe")
        title.setObjectName("brandTitle")
        subtitle = QLabel(
            "A little listening buddy for your big ideas. Private notes, made locally."
        )
        subtitle.setObjectName("brandSubtitle")
        subtitle.setWordWrap(True)
        brand_copy.addWidget(title)
        brand_copy.addWidget(subtitle)
        header.addWidget(brand_icon)
        header.addLayout(brand_copy, 1)
        privacy_badge = QLabel("✦  Your notes, your computer")
        privacy_badge.setObjectName("privacyBadge")
        preferences = QVBoxLayout()
        preferences.addWidget(privacy_badge)
        theme_row = QHBoxLayout()
        theme_row.addStretch()
        theme_label = QLabel("Dark mode")
        theme_label.setObjectName("fieldLabel")
        theme_row.addWidget(theme_label)
        self.theme_toggle = ThemeToggle()
        self.theme_toggle.setChecked(self.settings.value("theme", "light") == "dark")
        self.theme_toggle.toggled.connect(self.change_theme)
        theme_label.setBuddy(self.theme_toggle)
        theme_row.addWidget(self.theme_toggle)
        preferences.addLayout(theme_row)
        header.addLayout(preferences)
        layout.addLayout(header)

        setup_card = QFrame()
        setup_card.setObjectName("card")
        setup_card.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        setup_layout = QVBoxLayout(setup_card)
        setup_layout.setContentsMargins(16, 13, 16, 15)
        setup_layout.setSpacing(10)
        setup_title = QLabel("①  Let's get your audio ready")
        setup_title.setObjectName("sectionTitle")
        setup_hint = QLabel(
            "Your microphone captures you. Meeting audio output captures everyone you hear."
        )
        setup_hint.setObjectName("sectionHint")
        setup_hint.setWordWrap(True)
        setup_layout.addWidget(setup_title)
        setup_layout.addWidget(setup_hint)

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.mic_combo = QComboBox()
        self.speaker_combo = QComboBox()
        self.model_combo = QComboBox()
        self.whisper_combo = QComboBox()
        self.whisper_combo.addItems(["small", "medium", "large-v3"])
        self.whisper_combo.setCurrentText(self.settings.value("whisper", "small"))
        for combo in (
            self.mic_combo,
            self.speaker_combo,
            self.model_combo,
            self.whisper_combo,
        ):
            combo.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            )
            combo.setMinimumContentsLength(16)
            combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for label_text, control in (
            ("Your microphone", self.mic_combo),
            ("Meeting audio output", self.speaker_combo),
            ("Local AI model", self.model_combo),
            ("Transcription quality", self.whisper_combo),
        ):
            label = QLabel(label_text)
            label.setObjectName("fieldLabel")
            form.addRow(label, control)
        setup_layout.addLayout(form)

        audio_card = QFrame()
        audio_card.setObjectName("card")
        audio_card.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        audio_layout = QVBoxLayout(audio_card)
        audio_layout.setContentsMargins(16, 13, 16, 14)
        audio_layout.setSpacing(9)
        audio_title = QLabel("②  Sound check")
        audio_title.setObjectName("sectionTitle")
        meter_help = QLabel("The bars move once recording starts. Both should react during conversation.")
        meter_help.setObjectName("sectionHint")
        meter_help.setWordWrap(True)
        audio_heading = QHBoxLayout()
        audio_heading.addWidget(audio_title, 1)
        self.clarity_button = QPushButton("Voice clarity…")
        self.clarity_button.setObjectName("clarityButton")
        if self.cleanup_preferences().enabled:
            self.clarity_button.setText("Voice clarity: On")
        self.clarity_button.setToolTip("Optional cleanup inside MeetingScribe only. Does not change audio in other apps.")
        self.clarity_button.clicked.connect(self.edit_voice_clarity)
        audio_heading.addWidget(self.clarity_button)
        audio_layout.addLayout(audio_heading)
        audio_layout.addWidget(meter_help)
        meters = QHBoxLayout()
        meters.setSpacing(12)

        mic_box = QFrame()
        mic_box.setObjectName("meterPanel")
        mic_panel = QVBoxLayout(mic_box)
        mic_panel.setContentsMargins(12, 9, 12, 9)
        mic_label = QLabel("●  You · microphone")
        mic_label.setObjectName("fieldLabel")
        mic_panel.addWidget(mic_label)
        self.mic_meter = QProgressBar()
        self.mic_meter.setRange(0, 100)
        self.mic_meter.setTextVisible(False)
        self.mic_meter.setToolTip("Moves when your selected microphone hears you.")
        mic_panel.addWidget(self.mic_meter)
        self.mic_state = QLabel("Starts listening when recording begins")
        self.mic_state.setObjectName("meterState")
        self.mic_state.setWordWrap(True)
        mic_panel.addWidget(self.mic_state)
        meters.addWidget(mic_box, 1)

        system_box = QFrame()
        system_box.setObjectName("meterPanel")
        system_panel = QVBoxLayout(system_box)
        system_panel.setContentsMargins(12, 9, 12, 9)
        system_label = QLabel("●  Everyone else · audio")
        system_label.setObjectName("fieldLabel")
        system_panel.addWidget(system_label)
        self.system_meter = QProgressBar()
        self.system_meter.setRange(0, 100)
        self.system_meter.setTextVisible(False)
        self.system_meter.setToolTip(
            "Moves when sound is captured from the selected meeting audio output."
        )
        system_panel.addWidget(self.system_meter)
        self.system_state = QLabel("Starts listening when recording begins")
        self.system_state.setObjectName("meterState")
        self.system_state.setWordWrap(True)
        system_panel.addWidget(self.system_state)
        meters.addWidget(system_box, 1)
        audio_layout.addLayout(meters)

        consent_card = QFrame()
        consent_card.setObjectName("consentCard")
        consent_card.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        consent_layout = QVBoxLayout(consent_card)
        consent_layout.setContentsMargins(14, 10, 14, 11)
        consent_layout.setSpacing(6)
        consent_title = QLabel("Permission comes first")
        consent_title.setObjectName("consentTitle")
        consent_warning = QLabel("Recording rules vary. Inform everyone and get all required permission before you begin.")
        consent_warning.setWordWrap(True)
        self.consent_checkbox = QCheckBox("I have permission to record this meeting.")
        self.consent_checkbox.setToolTip(
            "This acknowledgment is required before Start Recording is enabled."
        )
        consent_layout.addWidget(consent_title)
        consent_layout.addWidget(consent_warning)
        consent_layout.addWidget(self.consent_checkbox)

        overview = QHBoxLayout()
        overview.setSpacing(12)
        overview.addWidget(setup_card, 1)
        readiness = QVBoxLayout()
        readiness.setSpacing(10)
        readiness.addWidget(audio_card)
        readiness.addWidget(consent_card)
        overview.addLayout(readiness, 1)
        layout.addLayout(overview)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        self.record_button = QPushButton("●  Start Recording")
        self.record_button.setObjectName("recordButton")
        self.record_button.setEnabled(False)
        self.record_button.clicked.connect(self.toggle_recording)
        self.consent_checkbox.toggled.connect(self.record_button.setEnabled)
        self.screen_toggle = QPushButton("▣  Screen record off")
        self.screen_toggle.setObjectName("screenToggle")
        self.screen_toggle.setCheckable(True)
        self.screen_toggle.setAccessibleName("Include screen recording")
        self.screen_toggle.setToolTip(
            "Include your selected screen in this meeting. Use Settings → Screen options to change the screen or quality."
        )
        self.screen_toggle.toggled.connect(self.toggle_screen_quick)
        self.screen_combo = QComboBox()
        self.screen_combo.setObjectName("screenPicker")
        self.screen_combo.setAccessibleName("Screen to record")
        self.screen_combo.setToolTip("Choose which screen MeetingScribe will record.")
        self.screen_combo.currentIndexChanged.connect(self.change_screen)
        self.refresh_screen_choices()
        self.duration = QLabel("00:00:00")
        self.duration.setObjectName("timer")
        self.duration.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.duration.setFont(QFont("Consolas", 18))
        controls.addWidget(self.record_button, 1)
        controls.addWidget(self.screen_toggle)
        controls.addWidget(self.screen_combo)
        controls.addWidget(self.duration)
        layout.addLayout(controls)

        self.status_label = QLabel("Ready — audio never leaves this computer.")
        self.status_label.setObjectName("statusPill")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        workspace = QSplitter(Qt.Orientation.Vertical)

        transcript_panel = QFrame()
        transcript_panel.setObjectName("workspaceCard")
        transcript_panel.setProperty("tone", "lavender")
        transcript_panel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        transcript_layout = QVBoxLayout(transcript_panel)
        transcript_layout.setContentsMargins(13, 10, 13, 13)
        transcript_label = QLabel("✦  Live transcript · we'll do the typing")
        transcript_label.setObjectName("fieldLabel")
        transcript_header = QHBoxLayout()
        transcript_header.addWidget(transcript_label, 1)
        self.live_mode_combo = QComboBox()
        self.live_mode_combo.setObjectName("liveMode")
        self.live_mode_combo.addItem("Eco — lowest load", "eco")
        self.live_mode_combo.addItem("Balanced — clearer preview", "balanced")
        self.live_mode_combo.addItem("Off — final transcript only", "off")
        saved_live_mode = self.live_mode_combo.findData(self.settings.value("live_mode", "eco"))
        self.live_mode_combo.setCurrentIndex(max(0, saved_live_mode))
        self.live_mode_combo.setAccessibleName("Live transcription resource use")
        self.live_mode_combo.setToolTip("Eco uses a smaller CPU model and updates about every 12 seconds when it can keep up. Balanced uses a larger preview model. Final transcription quality is unchanged. Choose before recording.")
        self.live_mode_combo.currentIndexChanged.connect(lambda: self.settings.setValue("live_mode", self.live_mode_combo.currentData()))
        transcript_header.addWidget(self.live_mode_combo)
        self.speaker_labels_combo = QComboBox()
        self.speaker_labels_combo.setAccessibleName("Final transcript speaker labels")
        self.speaker_labels_combo.setToolTip(
            "Adds Myself and Speaker labels to the final transcript after recording stops. The live preview remains unlabeled."
        )
        self.speaker_labels_combo.addItem("Final speakers: off", 0)
        for count in range(1, 5):
            self.speaker_labels_combo.addItem(
                f"Final: Myself + {count}", count
            )
        enabled, other_speakers = self.speaker_label_options()
        self.speaker_labels_combo.setCurrentIndex(
            self.speaker_labels_combo.findData(other_speakers if enabled else 0)
        )
        self.speaker_labels_combo.currentIndexChanged.connect(self.change_speaker_labels)
        transcript_header.addWidget(self.speaker_labels_combo)
        self.transcript_minimize_button = QPushButton("Minimize")
        self.transcript_minimize_button.setToolTip("Shrink the live transcript to make more room for your notes.")
        self.transcript_minimize_button.clicked.connect(lambda: self.resize_transcript("minimized"))
        transcript_header.addWidget(self.transcript_minimize_button)
        self.transcript_expand_button = QPushButton("Expand")
        self.transcript_expand_button.setToolTip("Expand the live transcript for easier reading.")
        self.transcript_expand_button.clicked.connect(lambda: self.resize_transcript("expanded"))
        transcript_header.addWidget(self.transcript_expand_button)
        transcript_layout.addLayout(transcript_header)
        transcript_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.live_transcript = NotesEditor()
        self.live_transcript.setReadOnly(True)
        self.live_transcript.setPlaceholderText(
            "Your conversation lands here in little batches. Start recording when everyone is ready."
        )
        transcript_layout.addWidget(self.live_transcript, 1)
        self.workspace = workspace
        self.transcript_view = "normal"
        self.transcript_normal_sizes = [250, 270]
        workspace.addWidget(transcript_panel)

        personal_panel = QFrame()
        personal_panel.setObjectName("workspaceCard")
        personal_panel.setProperty("tone", "peach")
        personal_panel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        personal_layout = QVBoxLayout(personal_panel)
        personal_layout.setContentsMargins(13, 10, 13, 13)
        personal_header = QHBoxLayout()
        personal_label = QLabel("✎  My notes · your space")
        personal_label.setObjectName("fieldLabel")
        personal_header.addWidget(personal_label)
        personal_header.addStretch()
        clear_personal = QPushButton("Clear My Notes")
        clear_personal.clicked.connect(self.clear_personal_notes)
        personal_header.addWidget(clear_personal)
        personal_layout.addLayout(personal_header)
        self.personal_notes = NotesEditor()
        self.personal_notes.setPlaceholderText("A bright idea? A question for later? Pop it here…")
        self.personal_notes.textChanged.connect(self.save_personal_notes)
        personal_layout.addWidget(self.personal_notes, 1)
        notes_splitter = QSplitter(Qt.Orientation.Horizontal)
        notes_splitter.addWidget(personal_panel)

        ai_panel = QFrame()
        ai_panel.setObjectName("workspaceCard")
        ai_panel.setProperty("tone", "mint")
        ai_panel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        ai_layout = QVBoxLayout(ai_panel)
        ai_layout.setContentsMargins(13, 10, 13, 13)
        ai_label = QLabel("✧  The wrap-up · after recording")
        ai_label.setObjectName("fieldLabel")
        ai_label.setWordWrap(True)
        ai_layout.addWidget(ai_label)
        ai_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.notes = NotesEditor()
        self.notes.setPlaceholderText("We'll gather the key points and next steps here after you stop. Give them a quick review before sharing.")
        self.notes.setFont(QFont("Segoe UI", 10))
        ai_layout.addWidget(self.notes, 1)
        notes_splitter.addWidget(ai_panel)
        notes_splitter.setSizes([470, 470])
        workspace.addWidget(notes_splitter)
        workspace.setCollapsible(0, True)
        workspace.setCollapsible(1, True)
        workspace.setSizes(self.transcript_normal_sizes)
        layout.addWidget(workspace, 1)

        bottom = QHBoxLayout()
        self.save_button = QPushButton("Save Notes")
        self.save_button.clicked.connect(self.save_notes)
        self.save_button.setEnabled(False)
        self.saved_meetings_button = QPushButton("Saved Meetings")
        self.saved_meetings_button.setObjectName("settingsButton")
        self.saved_meetings_button.setToolTip(
            f"Saved in: {default_output_dir(create=False)}\nOpen all dated meeting folders."
        )
        self.saved_meetings_menu = QMenu(self.saved_meetings_button)
        self.all_meetings_action = self.saved_meetings_menu.addAction("Open all saved meetings", self.open_saved_meetings)
        self.current_meeting_action = self.saved_meetings_menu.addAction("Open this meeting's folder", self.open_meeting_folder)
        self.current_meeting_action.setEnabled(False)
        self.saved_meetings_button.setMenu(self.saved_meetings_menu)
        bottom.addWidget(self.save_button)
        bottom.addWidget(self.saved_meetings_button)
        bottom.addStretch()
        self.settings_button = QPushButton("Settings")
        self.settings_button.setObjectName("settingsButton")
        self.settings_menu = QMenu(self.settings_button)
        self.screen_action = self.settings_menu.addAction("Screen options…", self.configure_screen_recording)
        self.speaker_action = self.settings_menu.addAction("Speaker labels…", self.configure_speaker_labels)
        self.settings_menu.addSeparator()
        self.settings_menu.addAction("Customize Summary…", self.edit_template)
        self.settings_menu.addAction("Refresh Devices", self.refresh_all)
        self.settings_menu.addSeparator()
        self.start_ollama_action = self.settings_menu.addAction("Start Ollama now", lambda: self.start_ollama(manual=True))
        self.auto_ollama_action = QAction("Start Ollama with MeetingScribe", self.settings_menu)
        self.auto_ollama_action.setCheckable(True)
        self.auto_ollama_action.setChecked(self.settings.value("start_ollama", True, type=bool))
        self.auto_ollama_action.setToolTip("Starts the local Ollama service when MeetingScribe opens. No models are downloaded.")
        self.auto_ollama_action.toggled.connect(lambda enabled: self.settings.setValue("start_ollama", enabled))
        self.settings_menu.addAction(self.auto_ollama_action)
        self.settings_menu.addSeparator()
        self.update_action = self.settings_menu.addAction("Check for updates", self.update_clicked)
        self.auto_update_action = QAction("Check for updates on startup", self.settings_menu)
        self.auto_update_action.setCheckable(True)
        self.auto_update_action.setChecked(self.settings.value("check_updates", True, type=bool))
        self.auto_update_action.setToolTip("Contact GitHub when the app opens. Meeting content is never sent.")
        self.auto_update_action.toggled.connect(lambda enabled: self.settings.setValue("check_updates", enabled))
        self.settings_menu.addAction(self.auto_update_action)
        self.settings_menu.addSeparator()
        version_label = self.settings_menu.addAction(f"MeetingScribe {APP_VERSION}")
        version_label.setEnabled(False)
        self.settings_menu.setToolTipsVisible(True)
        self.settings_button.setMenu(self.settings_menu)
        bottom.addWidget(self.settings_button)
        layout.addLayout(bottom)

        self.refresh_screen_recording_label()
        self.refresh_speaker_label()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(root)
        self.setCentralWidget(scroll)

    def update_busy(self):
        return bool(self.recording or self.record_button.property("processing")
                    or (self.worker_thread and self.worker_thread.isRunning())
                    or (self.live_transcriber and self.live_transcriber.is_running()))

    def screen_options(self):
        profile = self.settings.value("screen_profile", "efficient")
        if profile not in SCREEN_PROFILES:
            profile = "efficient"
        return ScreenOptions(
            enabled=self.settings.value("screen_enabled", False, type=bool),
            monitor=max(1, self.settings.value("screen_monitor", 1, type=int)),
            profile=profile,
        )

    def refresh_screen_choices(self):
        if not hasattr(self, "screen_combo"):
            return
        selected = self.settings.value("screen_monitor", 1, type=int)
        self.screen_combo.blockSignals(True)
        self.screen_combo.clear()
        try:
            monitors = available_monitors()
        except Exception:
            monitors = []
        for number, monitor in enumerate(monitors, 1):
            self.screen_combo.addItem(
                f"Screen {number} · {monitor['width']}×{monitor['height']}", number
            )
        if not monitors:
            self.screen_combo.addItem("No screen found", None)
        index = self.screen_combo.findData(selected)
        self.screen_combo.setCurrentIndex(index if index >= 0 else 0)
        self.screen_combo.blockSignals(False)
        self.screen_combo.setVisible(self.screen_options().enabled)

    def change_screen(self):
        monitor = self.screen_combo.currentData()
        if monitor is not None:
            self.settings.setValue("screen_monitor", monitor)

    def speaker_label_options(self):
        return (
            self.settings.value("speaker_labels/enabled", False, type=bool),
            max(1, min(4, self.settings.value("speaker_labels/others", 2, type=int))),
        )

    def change_speaker_labels(self):
        others = self.speaker_labels_combo.currentData()
        self.settings.setValue("speaker_labels/enabled", bool(others))
        if others:
            self.settings.setValue("speaker_labels/others", others)
            self.status_label.setText(
                "Speaker labels will appear in the final transcript after recording stops."
            )
        self.refresh_speaker_label()

    def resize_transcript(self, view):
        if view == self.transcript_view:
            view = "normal"
        if self.transcript_view == "normal":
            current = self.workspace.sizes()
            if all(current):
                self.transcript_normal_sizes = current
        if view == "expanded":
            self.workspace.setSizes([1000, 0])
        elif view == "minimized":
            self.workspace.setSizes([70, 1000])
        else:
            self.workspace.setSizes(self.transcript_normal_sizes)
        self.transcript_view = view
        self.transcript_expand_button.setText("Restore" if view == "expanded" else "Expand")
        self.transcript_minimize_button.setText("Restore" if view == "minimized" else "Minimize")

    def refresh_speaker_label(self):
        enabled, others = self.speaker_label_options()
        self.speaker_action.setText(
            f"Speaker labels: Myself + {others}…" if enabled else "Speaker labels: off…"
        )
        if hasattr(self, "speaker_labels_combo"):
            self.speaker_labels_combo.blockSignals(True)
            self.speaker_labels_combo.setCurrentIndex(
                self.speaker_labels_combo.findData(others if enabled else 0)
            )
            self.speaker_labels_combo.blockSignals(False)

    def configure_speaker_labels(self):
        if self.recording:
            QMessageBox.information(self, "Speaker labels", "Speaker label settings can be changed before the next recording.")
            return
        current_enabled, current_others = self.speaker_label_options()
        dialog = QDialog(self)
        dialog.setWindowTitle("Speaker labels")
        dialog.setMinimumWidth(540)
        body = QVBoxLayout(dialog)
        enabled = QCheckBox("Label who is speaking in the final transcript")
        enabled.setChecked(current_enabled)
        body.addWidget(enabled)
        hint = QLabel(
            "MeetingScribe can identify Myself from your microphone and group voices from meeting audio as Speaker 1, Speaker 2, and so on. "
            "The other-speaker labels are experimental and may be less accurate when people overlap, use similar voices, or share a room."
        )
        hint.setWordWrap(True)
        hint.setObjectName("sectionHint")
        body.addWidget(hint)
        form = QFormLayout()
        others = QSpinBox()
        others.setRange(1, 4)
        others.setValue(current_others)
        others.setSuffix(" other speaker" if current_others == 1 else " other speakers")
        others.valueChanged.connect(lambda value: others.setSuffix(" other speaker" if value == 1 else " other speakers"))
        others.setEnabled(enabled.isChecked())
        enabled.toggled.connect(others.setEnabled)
        form.addRow("Expected voices", others)
        body.addLayout(form)
        note = QLabel("Labels are added after you stop recording. Audio stays on this computer.")
        note.setObjectName("sectionHint")
        body.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        body.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.settings.setValue("speaker_labels/enabled", enabled.isChecked())
        self.settings.setValue("speaker_labels/others", others.value())
        self.refresh_speaker_label()

    def refresh_screen_recording_label(self):
        options = self.screen_options()
        if self.screen_recorder and self.screen_recorder.is_running():
            self.screen_action.setText("Stop screen recording")
        else:
            self.screen_action.setText("Screen options…")
        if hasattr(self, "screen_toggle"):
            self.screen_toggle.blockSignals(True)
            self.screen_toggle.setChecked(options.enabled)
            self.screen_toggle.setText("●  Screen record on" if options.enabled else "▣  Screen record off")
            self.screen_toggle.setToolTip(
                "Your selected screen will be saved with this meeting. Click to record audio only."
                if options.enabled else
                "Include your selected screen in this meeting. Use Settings → Screen options to change the screen or quality."
            )
            self.screen_toggle.blockSignals(False)
        if hasattr(self, "screen_combo"):
            self.screen_combo.setVisible(options.enabled)
            selected = self.screen_combo.findData(options.monitor)
            if selected >= 0:
                self.screen_combo.blockSignals(True)
                self.screen_combo.setCurrentIndex(selected)
                self.screen_combo.blockSignals(False)
        self.consent_checkbox.setText(
            "I have permission to record audio and the screen."
            if options.enabled else "I have permission to record this meeting."
        )

    def toggle_screen_quick(self, enabled):
        if enabled:
            try:
                monitors = available_monitors()
            except Exception:
                monitors = []
            if not monitors:
                self.settings.setValue("screen_enabled", False)
                self.refresh_screen_recording_label()
                QMessageBox.warning(self, "Screen recording", "No screen is available. Connect a display and try again.")
                return
            if self.screen_options().monitor > len(monitors):
                self.settings.setValue("screen_monitor", 1)
            self.refresh_screen_choices()
        self.settings.setValue("screen_enabled", bool(enabled))
        self.refresh_screen_recording_label()
        self.status_label.setText(
            "Screen will be included — audio and video stay on this computer."
            if enabled else "Ready — recording will include audio only."
        )

    def configure_screen_recording(self):
        if self.screen_recorder and self.screen_recorder.is_running():
            answer = QMessageBox.question(
                self, "Stop screen recording?",
                "Stop saving the screen now? Audio recording and transcription will continue.",
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.stop_screen_recording()
            return
        if self.recording:
            QMessageBox.information(self, "Screen recording", "Screen capture settings can be changed before the next recording.")
            return
        try:
            monitors = available_monitors()
        except Exception:
            monitors = []
        dialog = QDialog(self)
        dialog.setWindowTitle("Screen recording")
        dialog.setMinimumWidth(540)
        body = QVBoxLayout(dialog)
        enabled = QCheckBox("Record my screen with this meeting")
        enabled.setChecked(self.screen_options().enabled)
        body.addWidget(enabled)
        hint = QLabel("Saved locally as screen-recording.mp4. Screen capture can include notifications and sensitive information. Hide anything you do not want recorded.")
        hint.setWordWrap(True)
        hint.setObjectName("sectionHint")
        body.addWidget(hint)
        form = QFormLayout()
        monitor_combo = QComboBox()
        if monitors:
            for number, monitor in enumerate(monitors, 1):
                monitor_combo.addItem(f"Screen {number} · {monitor['width']} × {monitor['height']}", number)
        else:
            monitor_combo.addItem("No screen detected", None)
        selected = monitor_combo.findData(self.screen_options().monitor)
        monitor_combo.setCurrentIndex(max(0, selected))
        quality_combo = QComboBox()
        for key, (label, *_details) in SCREEN_PROFILES.items():
            quality_combo.addItem(label, key)
        quality_combo.setCurrentIndex(max(0, quality_combo.findData(self.screen_options().profile)))
        form.addRow("Screen", monitor_combo)
        form.addRow("Quality", quality_combo)
        body.addLayout(form)
        controls = (monitor_combo, quality_combo)
        enabled.toggled.connect(lambda checked: [control.setEnabled(checked) for control in controls])
        for control in controls:
            control.setEnabled(enabled.isChecked())
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        body.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if enabled.isChecked() and monitor_combo.currentData() is None:
            QMessageBox.warning(self, "Screen recording", "No screen is available. Connect a display and try again.")
            return
        self.settings.setValue("screen_enabled", enabled.isChecked())
        if monitor_combo.currentData() is not None:
            self.settings.setValue("screen_monitor", monitor_combo.currentData())
        self.settings.setValue("screen_profile", quality_combo.currentData())
        self.refresh_screen_choices()
        self.refresh_screen_recording_label()

    def start_screen_recording(self):
        options = self.screen_options()
        if not options.enabled or not self.current_folder:
            return False
        recorder = ScreenRecorder(self.current_folder / "screen-recording.mp4", options, self)
        recorder.error.connect(self.screen_recording_error)
        recorder.stopped.connect(self.screen_recording_stopped)
        try:
            recorder.start()
        except Exception as exc:
            self.screen_recording_error(f"Screen recording could not start: {exc}")
            return False
        self.screen_recorder = recorder
        self.refresh_screen_recording_label()
        return True

    def stop_screen_recording(self, wait=False):
        recorder = self.screen_recorder
        if recorder:
            recorder.stop(wait=wait)
        self.refresh_screen_recording_label()

    def screen_recording_error(self, message):
        self.screen_recorder = None
        self.refresh_screen_recording_label()
        self.set_screen_indicator(False)
        self.status_label.setText(message + " Audio recording continues.")

    def screen_recording_stopped(self, path):
        self.screen_recorder = None
        self.refresh_screen_recording_label()
        if self.recording:
            self.status_label.setText("Screen recording saved. Audio recording continues.")

    def set_screen_indicator(self, active):
        self.status_label.setProperty("screenRecording", bool(active))
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def startup_updates(self):
        self.restore_update_draft()
        if self.auto_ollama_action.isChecked():
            self.start_ollama(manual=False)
        if self.auto_update_action.isChecked():
            self.check_updates(manual=False)

    @staticmethod
    def ollama_executable():
        found = shutil.which("ollama")
        if found:
            return Path(found)
        candidates = []
        if sys.platform == "win32":
            local_app_data = os.environ.get("LOCALAPPDATA")
            program_files = os.environ.get("ProgramFiles")
            if local_app_data:
                candidates.append(Path(local_app_data) / "Programs" / "Ollama" / "ollama.exe")
            if program_files:
                candidates.append(Path(program_files) / "Ollama" / "ollama.exe")
        elif sys.platform == "darwin":
            candidates.extend((
                Path("/Applications/Ollama.app/Contents/Resources/ollama"),
                Path("/opt/homebrew/bin/ollama"),
                Path("/usr/local/bin/ollama"),
            ))
        return next((path for path in candidates if path.is_file()), None)

    @staticmethod
    def ollama_is_running(timeout=0.8):
        try:
            response = requests.get("http://127.0.0.1:11434/api/tags", timeout=timeout)
            return response.ok
        except requests.RequestException:
            return False

    def start_ollama(self, manual=False):
        if self.ollama_is_running():
            self.refresh_models()
            self.status_label.setText("Ollama is ready — your AI notes stay on this computer.")
            return True
        executable = self.ollama_executable()
        if not executable:
            if manual:
                QMessageBox.information(
                    self,
                    "Ollama is not installed",
                    "MeetingScribe could not find Ollama. Run the MeetingScribe installer again or install Ollama, then choose Start Ollama now.",
                )
            return False
        kwargs = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "stdin": subprocess.DEVNULL,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        try:
            self._ollama_process = subprocess.Popen([str(executable), "serve"], **kwargs)
        except OSError as exc:
            if manual:
                QMessageBox.warning(self, "Could not start Ollama", str(exc))
            return False
        self.status_label.setText("Starting Ollama in the background…")
        QTimer.singleShot(1200, lambda: self.finish_ollama_start(manual, 3))
        return True

    def finish_ollama_start(self, manual=False, attempts_left=0):
        if self.ollama_is_running():
            self.refresh_models()
            self.status_label.setText("Ollama is ready — your AI notes stay on this computer.")
            return
        if attempts_left > 0:
            QTimer.singleShot(1200, lambda: self.finish_ollama_start(manual, attempts_left - 1))
            return
        self.refresh_models()
        self.status_label.setText("Ollama did not start. Open Settings and choose Start Ollama now.")
        if manual:
            QMessageBox.warning(
                self,
                "Ollama did not start",
                "Open Ollama once from the Start menu, then return to MeetingScribe and try again.",
            )

    def update_clicked(self):
        if self._update_downloading:
            self.update_jobs.cancel.set()
            self.update_action.setText("Cancelling…")
        elif self._available_update:
            self.offer_update()
        else:
            self.check_updates(manual=True)

    def check_updates(self, manual=False):
        if self._update_checking or self._update_downloading:
            return
        self._update_checking = True
        self.update_action.setEnabled(False)
        self.update_action.setText("Checking…")
        self.update_jobs.check(APP_VERSION, manual)

    def update_checked(self, release, error, manual):
        self._update_checking = False
        self.update_action.setEnabled(True)
        self._available_update = release
        self.settings_button.setText("Settings · Update" if release else "Settings")
        self.update_action.setText("Update available" if release else "Check for updates")
        if error:
            if manual:
                QMessageBox.information(self, "Updates", error)
        elif release:
            # Never interrupt a meeting with a modal dialog. The button remains
            # available for later, without a second check or forced restart.
            if not self.update_busy():
                self.offer_update()
        elif manual:
            QMessageBox.information(self, "Updates", f"You're up to date ({APP_VERSION}).")

    def offer_update(self):
        if self.update_busy():
            QMessageBox.information(self, "Updates", "Finish recording and transcription before installing an update.")
            return
        if not self._available_update or self._update_downloading:
            return
        if sys.platform != "win32" or not getattr(sys, "frozen", False):
            QMessageBox.information(self, "Updates", "In-app installation is available in the installed Windows app. Source installations should update from GitHub.")
            return
        dialog = QMessageBox(self)
        dialog.setWindowTitle("A new MeetingScribe is ready")
        dialog.setTextFormat(Qt.TextFormat.PlainText)
        dialog.setText(f"Version {self._available_update.version} is available.\n\nDownload, verify, and restart to install. Your notes and settings will be kept. Windows may show a security warning because this beta is unsigned.")
        install = dialog.addButton("Install and restart", QMessageBox.ButtonRole.AcceptRole)
        later = dialog.addButton("Later", QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(later)
        dialog.exec()
        if dialog.clickedButton() != install or self.update_busy():
            return
        self._update_downloading = True
        self.settings_button.setText("Updating…")
        self.record_button.setEnabled(False)
        self.consent_checkbox.setEnabled(False)
        self.update_action.setText("Cancel download")
        self.update_jobs.download(self._available_update, app_data_dir() / "updates")

    def update_progress(self, percent):
        self.update_action.setText(f"Cancel download ({percent}%)")

    def update_downloaded(self, path, error):
        self._update_downloading = False
        self.update_action.setText("Update available")
        self.settings_button.setText("Settings · Update")
        self.consent_checkbox.setEnabled(True)
        self.record_button.setEnabled(self.consent_checkbox.isChecked() and not self.update_busy())
        if error or self.update_jobs.cancel.is_set():
            QMessageBox.information(self, "Update not installed", error or "Download cancelled.")
            return
        if self.update_busy():
            QMessageBox.information(self, "Updates", "Your meeting is still active. Install the update after it finishes.")
            return
        draft_saved = False
        try:
            updater.verify_file(path, self._available_update)
            self.save_update_draft()
            draft_saved = True
            self.launch_update(path)
        except Exception:
            QMessageBox.warning(self, "Update not installed", "The update could not start safely. Your app is still open. Try again later or use the website installer.")
            # Do not restore a stale snapshot over later edits after a failed launch.
            try:
                if draft_saved:
                    (app_data_dir() / "update-draft.json").unlink(missing_ok=True)
            except OSError:
                pass
            return
        self.close()

    def launch_update(self, path):
        if sys.platform != "win32" or not getattr(sys, "frozen", False):
            raise RuntimeError("Installed Windows app required")
        install_dir = str(Path(sys.executable).resolve().parent)
        subprocess.Popen([str(path), "/SILENT", "/NORESTART", "/NOCLOSEAPPLICATIONS",
                          "/NORESTARTAPPLICATIONS", "/UPDATEONLY=1", f"/UPDATEPID={os.getpid()}",
                          f"/DIR={install_dir}", f"/UPDATEFROM={install_dir}"], shell=False)

    def save_update_draft(self):
        # Keep pre-meeting text as well as edits to an existing meeting.
        self.save_notes()
        draft = {"folder": str(self.current_folder) if self.current_folder else None,
                 "personal": self.personal_notes.toPlainText(), "summary": self.notes.toPlainText(),
                 "transcript": self.live_transcript.toPlainText()}
        target = app_data_dir() / "update-draft.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(draft), encoding="utf-8")
        temporary.replace(target)
        self.settings.sync()
        if self.settings.status() != self.settings.Status.NoError:
            raise OSError("Settings could not be saved")

    def restore_update_draft(self):
        target = app_data_dir() / "update-draft.json"
        if not target.exists():
            return
        try:
            draft = json.loads(target.read_text(encoding="utf-8"))
            self.personal_notes.setPlainText(draft["personal"])
            self.notes.setPlainText(draft["summary"])
            self.live_transcript.setPlainText(draft["transcript"])
            folder = Path(draft["folder"]) if draft.get("folder") else None
            if folder and folder.is_dir():
                self.current_folder = folder
                self.save_button.setEnabled(True)
                self.current_meeting_action.setEnabled(True)
            target.unlink()
            self.status_label.setText("Welcome back — your notes were restored after the update.")
        except (OSError, ValueError, KeyError, TypeError):
            self.status_label.setText("Your update draft could not be restored; the recovery file has been kept.")

    def _set_record_button_state(self, state: str):
        labels = {
            "idle": "●  Start Recording",
            "recording": "■  Stop & Create Notes",
            "processing": "Creating your notes…",
        }
        self.record_button.setText(labels[state])
        self.record_button.setProperty("recording", state == "recording")
        self.record_button.setProperty("processing", state == "processing")
        self.record_button.style().unpolish(self.record_button)
        self.record_button.style().polish(self.record_button)

    def refresh_all(self):
        self.refresh_devices()
        self.refresh_models()
        self.refresh_screen_choices()

    def refresh_devices(self):
        prior_mic = self.settings.value("microphone_id", "")
        prior_speaker = self.settings.value("speaker_id", "")
        self.mic_combo.clear()
        self.speaker_combo.clear()
        for device in self.recorder.microphones():
            self.mic_combo.addItem(device.name, str(device.id))
        for device in self.recorder.speakers():
            self.speaker_combo.addItem(device.name, str(device.id))
        if prior_mic:
            self._select_data(self.mic_combo, prior_mic)
        else:
            physical_mic = next(
                (
                    d
                    for d in self.recorder.microphones()
                    if not any(word in d.name.lower() for word in ("voicemeeter", "virtual", "loopback"))
                ),
                None,
            )
            if physical_mic:
                self._select_data(self.mic_combo, str(physical_mic.id))
        if prior_speaker:
            self._select_data(self.speaker_combo, prior_speaker)
        else:
            try:
                self._select_data(self.speaker_combo, str(sc.default_speaker().id))
            except Exception:
                pass

    def refresh_models(self):
        selected = self.settings.value("ollama_model", "")
        self.model_combo.clear()
        try:
            response = requests.get("http://127.0.0.1:11434/api/tags", timeout=3)
            response.raise_for_status()
            models = [m["name"] for m in response.json().get("models", [])]
            self.model_combo.addItems(models)
            self._select_text(self.model_combo, selected)
            if not models:
                self.model_combo.addItem("Install a model with Ollama")
        except Exception:
            self.model_combo.addItem("Ollama is not running")

    @staticmethod
    def _select_data(combo: QComboBox, value: str):
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    @staticmethod
    def _select_text(combo: QComboBox, value: str):
        index = combo.findText(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def change_theme(self):
        theme = "dark" if self.theme_toggle.isChecked() else "light"
        self.settings.setValue("theme", theme)
        apply_theme(QApplication.instance(), theme)

    def cleanup_preferences(self):
        return CleanupSettings(
            noise_reduction=self.settings.value("cleanup/noise", False, type=bool),
            level_volume=self.settings.value("cleanup/level", False, type=bool),
            threshold_db=max(-65, min(-30, self.settings.value("cleanup/threshold", -50, type=int))),
            clean_others=self.settings.value("cleanup/others", False, type=bool),
        )

    def edit_voice_clarity(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Voice clarity — MeetingScribe only")
        dialog.setMinimumWidth(500)
        layout = QVBoxLayout(dialog)
        description = QLabel("Optional, lightweight cleanup for recordings and transcripts. It does not change what anyone hears in Teams or Discord.")
        description.setWordWrap(True)
        layout.addWidget(description)
        settings = self.cleanup_preferences()
        noise = QCheckBox("Reduce quiet background noise")
        noise.setChecked(settings.noise_reduction)
        noise.setToolTip("Softens low-level audio between speech. Does not isolate voices or remove noise over speech.")
        level = QCheckBox("Automatically level voice volume")
        level.setChecked(settings.level_volume)
        level.setToolTip("Gently adjusts volume, with amplification limited to 3×. Cannot restore clipped or missing speech.")
        others = QCheckBox("Also clean up meeting audio (other people)")
        others.setChecked(settings.clean_others)
        others.setToolTip("Leave off if Teams or Discord already processes other participants' audio.")
        for checkbox in (noise, level, others):
            layout.addWidget(checkbox)
        form = QFormLayout()
        threshold = QSpinBox()
        threshold.setRange(-65, -30)
        threshold.setSuffix(" dB")
        threshold.setValue(settings.threshold_db)
        threshold.setToolTip("Lower values preserve quieter voices. Higher values soften more background sound but can soften quiet speech too. Start at −50 dB.")
        form.addRow("Quiet-sound threshold", threshold)
        layout.addLayout(form)
        warning = QLabel("This is gentle volume-based cleanup, not AI voice isolation or echo cancellation. Turn both cleanup options off for unprocessed audio. When cleanup is on, original microphone and meeting-audio copies are saved too (uses more disk space).")
        warning.setWordWrap(True)
        layout.addWidget(warning)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            for name, value in (("noise", noise.isChecked()), ("level", level.isChecked()), ("others", others.isChecked()), ("threshold", threshold.value())):
                self.settings.setValue(f"cleanup/{name}", value)
            self.clarity_button.setText("Voice clarity: On" if self.cleanup_preferences().enabled else "Voice clarity…")

    def toggle_recording(self):
        if self.recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        if self._update_downloading:
            return
        if not self.consent_checkbox.isChecked():
            self.show_error(
                "Confirm that participants have been informed and that you have permission to record."
            )
            return
        if self.mic_combo.currentData() is None or self.speaker_combo.currentData() is None:
            self.show_error("Select both a microphone and an audio output.")
            return
        if self.model_combo.currentText().startswith(("Ollama is", "Install a")):
            self.show_error("Start Ollama and install a model before recording.")
            return

        stamp = datetime.now()
        self.current_folder = default_output_dir() / stamp.strftime("%Y-%m-%d_%H-%M-%S")
        self.current_folder.mkdir(parents=True, exist_ok=True)
        self.current_audio = self.current_folder / "recording.wav"
        self.save_personal_notes()
        selection = AudioSelection(
            str(self.mic_combo.currentData()), str(self.speaker_combo.currentData())
        )
        self.recorder.cleanup_settings = self.cleanup_preferences()
        self.recorder.original_folder = self.current_folder
        speaker_labels_enabled, other_speakers = self.speaker_label_options()
        self.recorder.preserve_tracks = speaker_labels_enabled
        (self.current_folder / "audio-settings.json").write_text(json.dumps(asdict(self.recorder.cleanup_settings), indent=2), encoding="utf-8")
        try:
            self.recorder.start(selection)
        except Exception as exc:
            self.show_error(str(exc))
            return

        if self.screen_options().enabled:
            (self.current_folder / "screen-settings.json").write_text(
                json.dumps(asdict(self.screen_options()), indent=2), encoding="utf-8"
            )
        screen_started = self.start_screen_recording()
        self.set_screen_indicator(screen_started)

        self.settings.setValue("microphone_id", selection.microphone_id)
        self.settings.setValue("speaker_id", selection.speaker_id)
        self.settings.setValue("ollama_model", self.model_combo.currentText())
        self.settings.setValue("whisper", self.whisper_combo.currentText())
        self.recording = True
        self.clarity_button.setEnabled(False)
        self.screen_toggle.setEnabled(False)
        self.last_mic_sound = self.last_system_sound = time.monotonic()
        self.consent_checkbox.setEnabled(False)
        self.mic_state.setText("Listening…")
        self.system_state.setText("Listening…")
        self.started_at = time.monotonic()
        self.timer.start(250)
        self.live_transcript.clear()
        live_mode = self.live_mode_combo.currentData()
        self.live_mode_combo.setEnabled(False)
        self.speaker_labels_combo.setEnabled(False)
        self.live_transcriber = None
        if live_mode != "off":
            preview_model, threads, prefer_gpu, interval = LIVE_PROFILES[live_mode]
            self.live_transcriber = LiveTranscriber(preview_model, cpu_threads=threads, prefer_gpu=prefer_gpu)
            self.live_transcriber.text_ready.connect(self.append_live_transcript)
            self.live_transcriber.status.connect(self.status_label.setText)
            self.live_transcriber.error.connect(self.status_label.setText)
            self.live_transcriber.start()
            self.live_timer.start(interval)
        else:
            self.live_transcript.setPlainText("Live preview is off to save resources. The full transcript will appear after you stop.")
        self._set_record_button_state("recording")
        self.status_label.setText(
            "● Recording audio + screen — everything stays on this computer."
            if screen_started else "Recording microphone and meeting audio…"
        )
        self.notes.clear()
        self.save_button.setEnabled(False)
        self.current_meeting_action.setEnabled(False)

    def stop_recording(self):
        self.timer.stop()
        self.live_timer.stop()
        if self.live_transcriber:
            self.live_transcriber.stop()
        self.stop_screen_recording(wait=True)
        self.set_screen_indicator(False)
        self.recording = False
        self.record_button.setEnabled(False)
        self._set_record_button_state("processing")
        try:
            self.recorder.stop(self.current_audio)
        except Exception as exc:
            self.processing_failed(str(exc))
            return
        self.finish_live_before_processing()

    def finish_live_before_processing(self):
        # Do not run two Whisper models concurrently at the recording boundary.
        # Poll asynchronously so the interface remains responsive.
        if self.live_transcriber and self.live_transcriber.is_running():
            self.status_label.setText("Finishing the live preview before final transcription…")
            QTimer.singleShot(150, self.finish_live_before_processing)
            return
        self.live_transcriber = None
        self.process_audio()

    def process_audio(self):
        prompt = self.settings.value("template", DEFAULT_PROMPT)
        self.worker_thread = QThread(self)
        worker = ProcessingWorker(
            self.current_audio,
            self.whisper_combo.currentText(),
            self.model_combo.currentText(),
            prompt,
            *self.speaker_label_options(),
        )
        worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(worker.run)
        worker.progress.connect(self.status_label.setText)
        worker.completed.connect(self.processing_completed)
        worker.failed.connect(self.processing_failed)
        worker.completed.connect(self.worker_thread.quit)
        worker.failed.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(worker.deleteLater)
        self.worker_thread.start()
        self._worker = worker

    def processing_completed(self, transcript: str, notes: str):
        self.clarity_button.setEnabled(True)
        self.screen_toggle.setEnabled(True)
        self.live_mode_combo.setEnabled(True)
        self.speaker_labels_combo.setEnabled(True)
        self.live_transcript.setPlainText(transcript)
        (self.current_folder / "transcript.txt").write_text(transcript, encoding="utf-8")
        self.save_personal_notes()
        combined_notes = self.combined_notes(transcript, notes)
        (self.current_folder / "notes.md").write_text(combined_notes, encoding="utf-8")
        metadata = {
            "created": datetime.now().isoformat(),
            "ollama_model": self.model_combo.currentText(),
            "whisper_model": self.whisper_combo.currentText(),
        }
        (self.current_folder / "meeting.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )
        self.notes.setPlainText(notes)
        self.status_label.setText("Complete — recording, transcript, and notes saved locally.")
        self._set_record_button_state("idle")
        self.consent_checkbox.setEnabled(True)
        self.consent_checkbox.setChecked(False)
        self.mic_state.setText("Starts listening when recording begins")
        self.system_state.setText("Starts listening when recording begins")
        self.save_button.setEnabled(True)
        self.current_meeting_action.setEnabled(True)

    def processing_failed(self, message: str):
        self.clarity_button.setEnabled(True)
        self.screen_toggle.setEnabled(True)
        self.live_mode_combo.setEnabled(True)
        self.speaker_labels_combo.setEnabled(True)
        self._set_record_button_state("idle")
        self.consent_checkbox.setEnabled(True)
        self.consent_checkbox.setChecked(False)
        self.mic_state.setText("Starts listening when recording begins")
        self.system_state.setText("Starts listening when recording begins")
        self.status_label.setText(f"Could not finish: {message}")
        self.show_error(message)

    def update_levels(self, mic: float, system: float):
        if mic >= 0:
            if mic >= 3:
                self.last_mic_sound = time.monotonic()
            self.mic_meter.setValue(int(mic))
            quiet_warning = self.recording and time.monotonic() - getattr(self, "last_mic_sound", time.monotonic()) > 10
            self.mic_state.setText("Sound detected ✓" if mic >= 3 else ("No recent sound — check your microphone if speaking." if quiet_warning else "Listening…"))
        if system >= 0:
            if system >= 3:
                self.last_system_sound = time.monotonic()
            self.system_meter.setValue(int(system))
            self.system_state.setText(
                "Sound detected ✓" if system >= 3 else ("No recent meeting audio — normal when others are silent." if self.recording and time.monotonic() - getattr(self, "last_system_sound", time.monotonic()) > 10 else "Listening…")
            )

    def request_live_transcription(self):
        if not self.recording or not self.live_transcriber or not self.live_transcriber.can_accept():
            return
        snapshot = self.recorder.live_snapshot()
        if not snapshot:
            return
        audio, end = snapshot
        if self.live_transcriber.submit(audio):
            self.recorder.commit_live_snapshot(end)

    def append_live_transcript(self, new_text: str):
        existing = self.live_transcript.toPlainText().strip()
        if not existing:
            merged = new_text.strip()
        else:
            existing_words = existing.split()
            new_words = new_text.split()
            overlap = 0
            limit = min(12, len(existing_words), len(new_words))
            for size in range(limit, 0, -1):
                left = [re.sub(r"\W+", "", w).lower() for w in existing_words[-size:]]
                right = [re.sub(r"\W+", "", w).lower() for w in new_words[:size]]
                if left == right:
                    overlap = size
                    break
            merged = " ".join(existing_words + new_words[overlap:])
        self.live_transcript.setPlainText(merged)
        scrollbar = self.live_transcript.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear_personal_notes(self):
        self.personal_notes.clear()

    def save_personal_notes(self):
        if self.current_folder:
            (self.current_folder / "my-notes.md").write_text(
                self.personal_notes.toPlainText(), encoding="utf-8"
            )

    @staticmethod
    def combined_notes(transcript: str, ai_notes: str) -> str:
        return (
            "# Transcript\n\n```text\n"
            + transcript.strip()
            + "\n```\n\n---\n\n"
            + ai_notes.strip()
            + "\n"
        )

    def update_timer(self):
        elapsed = int(time.monotonic() - self.started_at)
        self.duration.setText(
            f"{elapsed // 3600:02d}:{(elapsed % 3600) // 60:02d}:{elapsed % 60:02d}"
        )

    def save_notes(self):
        if not self.current_folder:
            return
        (self.current_folder / "notes.md").write_text(
            self.combined_notes(
                self.live_transcript.toPlainText(), self.notes.toPlainText()
            ),
            encoding="utf-8",
        )
        self.save_personal_notes()
        self.status_label.setText("Edited notes saved.")

    def open_meeting_folder(self):
        if self.current_folder:
            self._open_folder(self.current_folder)

    def open_saved_meetings(self):
        try:
            folder = default_output_dir()
        except OSError as exc:
            self.show_error(f"Could not access the saved meetings folder: {exc}")
            return
        self._open_folder(folder)

    def _open_folder(self, folder: Path):
        if not folder.is_dir():
            self.show_error(f"This folder is no longer available:\n\n{folder}")
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder.resolve()))):
            self.show_error(f"Could not open the folder. You can open it manually:\n\n{folder}")

    def edit_template(self):
        path = app_data_dir() / "note-template.txt"
        if not path.exists():
            path.write_text(self.settings.value("template", DEFAULT_PROMPT), encoding="utf-8")
        QMessageBox.information(
            self,
            "Edit Note Template",
            f"Edit this file, save it, then choose it below:\n\n{path}",
        )
        selected, _ = QFileDialog.getOpenFileName(
            self, "Choose note template", str(path), "Text files (*.txt);;All files (*)"
        )
        if selected:
            self.settings.setValue("template", Path(selected).read_text(encoding="utf-8"))
            self.status_label.setText("Custom note template loaded.")

    def show_error(self, message: str):
        QMessageBox.critical(self, "MeetingScribe", message)

    def confirm_force_close_processing(self) -> bool:
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle("Meeting still processing")
        dialog.setText(
            "MeetingScribe is still creating the transcript or summary.\n\n"
            "Force closing will stop that work. The audio recording and anything you typed will stay saved, "
            "but the unfinished transcript or summary will be lost."
        )
        keep_waiting = dialog.addButton("Keep waiting", QMessageBox.ButtonRole.RejectRole)
        force_close = dialog.addButton("Force close", QMessageBox.ButtonRole.DestructiveRole)
        dialog.setDefaultButton(keep_waiting)
        dialog.exec()
        return dialog.clickedButton() == force_close

    def force_close_processing(self):
        # QThread cannot safely be torn down mid-inference. Persist editable text,
        # then end the process immediately only after the explicit destructive choice.
        try:
            self.save_update_draft()
        except (OSError, ValueError):
            pass
        os._exit(0)

    def closeEvent(self, event):
        if self._update_downloading:
            self.update_jobs.cancel.set()
            QMessageBox.information(self, "Cancelling download", "The update download is cancelling. Please close the app again in a moment.")
            event.ignore()
            return
        if self.update_busy() and not self.recording:
            if self.confirm_force_close_processing():
                event.ignore()
                self.force_close_processing()
                return
            event.ignore()
            return
        if self.recording:
            answer = QMessageBox.question(
                self,
                "Recording in progress",
                "Stop recording and close MeetingScribe?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.stop_screen_recording(wait=True)
            self.recorder._stop.set()
        event.accept()


def main():
    if "--preload-whisper" in sys.argv:
        # Used by the all-in-one installer so the first meeting does not need
        # to wait for the transcription model download.
        WhisperModel("small", device="cpu", compute_type="int8")
        WhisperModel("tiny", device="cpu", compute_type="int8", cpu_threads=2)
        return

    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "MeetingScribe.MeetingScribe.CharacterTransparent"
            )
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("MeetingScribe")
    if sys.platform == "win32" and "--smoke-test" not in sys.argv:
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
        kernel.CreateMutexW.restype = wintypes.HANDLE
        app._instance_mutex = kernel.CreateMutexW(None, False, "Local\\MeetingScribe.UpdateSafety")
        if not app._instance_mutex or ctypes.get_last_error() == 183:
            QMessageBox.information(None, "MeetingScribe", "MeetingScribe is already open, or Windows could not reserve its update lock. Close any other copy and try again.")
            return 0
    icon_path = resource_path("assets/meetingscribe-icon.ico")
    if not icon_path.exists():
        icon_path = resource_path("assets/meetingscribe-icon.png")
    app_icon = QIcon(str(icon_path))
    app.setWindowIcon(app_icon)
    apply_theme(app)
    window = MeetingScribeWindow()
    window.setWindowIcon(app_icon)
    if "--smoke-test" in sys.argv:
        # Exercise frozen imports, the real platform UI, and bundled assets
        # without opening a window, recording audio, or downloading models.
        window.ensurePolished()
        app.processEvents()
        valid = not app_icon.isNull() and resource_path("assets/meetingscribe-icon.png").is_file()
        window.close()
        return 0 if valid else 1
    available = app.primaryScreen().availableGeometry()
    window.resize(min(1100, available.width() - 60), min(900, available.height() - 70))
    window.show()
    QTimer.singleShot(2500, window.startup_updates)
    sys.exit(app.exec())


if __name__ == "__main__":
    sys.exit(main())
