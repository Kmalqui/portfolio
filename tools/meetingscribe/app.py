from __future__ import annotations

import json
import os
import queue
import re
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import requests
import soundcard as sc
import soundfile as sf
from faster_whisper import WhisperModel
from PySide6.QtCore import QObject, QSettings, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QDesktopServices, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QSpinBox,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)


APP_NAME = "MeetingScribe"
SAMPLE_RATE = 48_000
BLOCK_SIZE = 4_800
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


def default_output_dir() -> Path:
    root = Path.home() / "Documents" / "Meeting Notes"
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
        mic_chunks = list(self._mic_chunks)
        system_chunks = list(self._system_chunks)
        mic = np.concatenate(mic_chunks) if mic_chunks else np.zeros(0, np.float32)
        system = (
            np.concatenate(system_chunks) if system_chunks else np.zeros(0, np.float32)
        )
        end = max(len(mic), len(system))
        if end - self._live_cursor < SAMPLE_RATE * 4:
            return None
        start = max(0, self._live_cursor - SAMPLE_RATE)
        mic = np.pad(mic, (0, end - len(mic)))
        system = np.pad(system, (0, end - len(system)))
        mixed = mic[start:end] * 0.68 + system[start:end] * 0.68
        peak = float(np.max(np.abs(mixed))) if mixed.size else 0
        if peak > 0.98:
            mixed *= 0.98 / peak
        return mixed, end

    def commit_live_snapshot(self, end: int) -> None:
        self._live_cursor = end

    def _capture(self, device, chunks: list[np.ndarray], is_mic: bool) -> None:
        try:
            with device.recorder(samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE) as recorder:
                while not self._stop.is_set():
                    block = recorder.record(numframes=BLOCK_SIZE)
                    if block.ndim == 2:
                        block = np.mean(block, axis=1)
                    block = np.asarray(block, dtype=np.float32)
                    chunks.append(block)
                    rms = float(np.sqrt(np.mean(np.square(block))) if block.size else 0)
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
        return destination


class LiveTranscriber(QObject):
    text_ready = Signal(str)
    status = Signal(str)
    error = Signal(str)

    def __init__(self, model_name: str):
        super().__init__()
        self.model_name = model_name
        self._queue: queue.Queue[np.ndarray | None] = queue.Queue(maxsize=1)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def submit(self, audio: np.ndarray) -> bool:
        try:
            self._queue.put_nowait(audio)
            return True
        except queue.Full:
            return False

    def stop(self) -> None:
        self._stop.set()
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass

    def _run(self) -> None:
        try:
            self.status.emit(f"Loading Whisper {self.model_name} for live transcription…")
            try:
                model = WhisperModel(self.model_name, device="cuda", compute_type="float16")
            except Exception:
                model = WhisperModel(self.model_name, device="cpu", compute_type="int8")
            self.status.emit("Live transcription is listening…")
            while not self._stop.is_set():
                audio = self._queue.get()
                if audio is None or self._stop.is_set():
                    break
                audio_16k = np.ascontiguousarray(audio[::3], dtype=np.float32)
                segments, _ = model.transcribe(
                    audio_16k,
                    vad_filter=True,
                    beam_size=1,
                    condition_on_previous_text=False,
                )
                text = " ".join(segment.text.strip() for segment in segments).strip()
                if text:
                    self.text_ready.emit(text)
        except Exception as exc:
            self.error.emit(f"Live transcription paused: {exc}")


class ProcessingWorker(QObject):
    progress = Signal(str)
    completed = Signal(str, str)
    failed = Signal(str)

    def __init__(self, audio_path: Path, whisper_model: str, ollama_model: str, prompt: str):
        super().__init__()
        self.audio_path = audio_path
        self.whisper_model = whisper_model
        self.ollama_model = ollama_model
        self.prompt = prompt

    def run(self) -> None:
        try:
            self.progress.emit(f"Loading Whisper {self.whisper_model}…")
            try:
                model = WhisperModel(self.whisper_model, device="cuda", compute_type="float16")
                segments, _ = model.transcribe(
                    str(self.audio_path), vad_filter=True, beam_size=5
                )
                transcript = " ".join(s.text.strip() for s in segments).strip()
            except Exception:
                self.progress.emit("Using CPU transcription…")
                model = WhisperModel(self.whisper_model, device="cpu", compute_type="int8")
                segments, _ = model.transcribe(
                    str(self.audio_path), vad_filter=True, beam_size=5
                )
                transcript = " ".join(s.text.strip() for s in segments).strip()

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


class MeetingScribeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MeetingScribe — Private Local Meeting Notes")
        self.resize(1000, 900)
        self.settings = QSettings("MeetingScribe", "MeetingScribe")
        self.recorder = Recorder()
        self.recorder.level.connect(self.update_levels)
        self.recorder.error.connect(self.show_error)
        self.recording = False
        self.started_at = 0.0
        self.current_folder: Path | None = None
        self.current_audio: Path | None = None
        self.worker_thread: QThread | None = None
        self.live_transcriber: LiveTranscriber | None = None

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
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        title = QLabel("MeetingScribe")
        title.setFont(QFont("Segoe UI", 23, QFont.Weight.Bold))
        subtitle = QLabel(
            "With permission, record a meeting, transcribe locally, and create private AI notes."
        )
        subtitle.setStyleSheet("color: #707070")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        form = QFormLayout()
        self.mic_combo = QComboBox()
        self.speaker_combo = QComboBox()
        self.model_combo = QComboBox()
        self.whisper_combo = QComboBox()
        self.whisper_combo.addItems(["small", "medium", "large-v3"])
        self.whisper_combo.setCurrentText(self.settings.value("whisper", "small"))
        form.addRow("Your microphone", self.mic_combo)
        form.addRow("Meeting audio output", self.speaker_combo)
        form.addRow("Ollama model", self.model_combo)
        form.addRow("Transcription quality", self.whisper_combo)
        layout.addLayout(form)

        meter_help = QLabel(
            "Audio activity — after recording starts, these panels show what MeetingScribe can hear. "
            "Both should react while you and another participant are speaking."
        )
        meter_help.setWordWrap(True)
        meter_help.setStyleSheet("color: #a9a9a9")
        layout.addWidget(meter_help)

        meter_style = (
            "QProgressBar { min-height: 16px; border: 1px solid #666; border-radius: 5px; "
            "background: #303030; } "
            "QProgressBar::chunk { border-radius: 4px; background: #a8d84e; }"
        )
        meters = QHBoxLayout()

        mic_panel = QVBoxLayout()
        mic_panel.addWidget(QLabel("You — selected microphone"))
        self.mic_meter = QProgressBar()
        self.mic_meter.setRange(0, 100)
        self.mic_meter.setTextVisible(False)
        self.mic_meter.setStyleSheet(meter_style)
        self.mic_meter.setToolTip("Moves when your selected microphone hears you.")
        mic_panel.addWidget(self.mic_meter)
        self.mic_state = QLabel("Starts listening when recording begins")
        self.mic_state.setStyleSheet("color: #8f8f8f; font-size: 11px")
        mic_panel.addWidget(self.mic_state)
        meters.addLayout(mic_panel, 1)

        system_panel = QVBoxLayout()
        system_panel.addWidget(QLabel("Other people — selected meeting output"))
        self.system_meter = QProgressBar()
        self.system_meter.setRange(0, 100)
        self.system_meter.setTextVisible(False)
        self.system_meter.setStyleSheet(meter_style)
        self.system_meter.setToolTip(
            "Moves when sound is captured from the selected meeting audio output."
        )
        system_panel.addWidget(self.system_meter)
        self.system_state = QLabel("Starts listening when recording begins")
        self.system_state.setStyleSheet("color: #8f8f8f; font-size: 11px")
        system_panel.addWidget(self.system_state)
        meters.addLayout(system_panel, 1)
        layout.addLayout(meters)

        consent_warning = QLabel(
            "Recording laws and workplace rules vary. Record only after informing everyone "
            "and obtaining all permission required for this meeting."
        )
        consent_warning.setWordWrap(True)
        consent_warning.setStyleSheet(
            "padding: 9px; border: 1px solid #b8871b; background: #3a311f; color: #ffe5a3;"
        )
        layout.addWidget(consent_warning)

        self.consent_checkbox = QCheckBox(
            "I have informed the participants and have permission to record this meeting."
        )
        self.consent_checkbox.setToolTip(
            "This acknowledgment is required before Start Recording is enabled."
        )
        layout.addWidget(self.consent_checkbox)

        controls = QHBoxLayout()
        self.record_button = QPushButton("●  Start Recording")
        self.record_button.setMinimumHeight(46)
        self.record_button.setEnabled(False)
        self.record_button.clicked.connect(self.toggle_recording)
        self.consent_checkbox.toggled.connect(self.record_button.setEnabled)
        self.duration = QLabel("00:00:00")
        self.duration.setFont(QFont("Consolas", 18))
        self.open_folder_button = QPushButton("Open Meeting Folder")
        self.open_folder_button.clicked.connect(self.open_meeting_folder)
        self.open_folder_button.setEnabled(False)
        controls.addWidget(self.record_button, 1)
        controls.addWidget(self.duration)
        controls.addWidget(self.open_folder_button)
        layout.addLayout(controls)

        self.status_label = QLabel("Ready — audio never leaves this computer.")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        workspace = QSplitter(Qt.Orientation.Vertical)

        transcript_panel = QWidget()
        transcript_layout = QVBoxLayout(transcript_panel)
        transcript_layout.setContentsMargins(0, 0, 0, 0)
        transcript_layout.addWidget(QLabel("Live transcript — automatic, read-only"))
        self.live_transcript = QPlainTextEdit()
        self.live_transcript.setReadOnly(True)
        self.live_transcript.setPlaceholderText(
            "Near-real-time transcription will appear here shortly after recording starts."
        )
        transcript_layout.addWidget(self.live_transcript)
        workspace.addWidget(transcript_panel)

        personal_panel = QWidget()
        personal_layout = QVBoxLayout(personal_panel)
        personal_layout.setContentsMargins(0, 0, 0, 0)
        personal_header = QHBoxLayout()
        personal_header.addWidget(QLabel("My notes — type here during the meeting"))
        personal_header.addStretch()
        clear_personal = QPushButton("Clear My Notes")
        clear_personal.clicked.connect(self.clear_personal_notes)
        personal_header.addWidget(clear_personal)
        personal_layout.addLayout(personal_header)
        self.personal_notes = QPlainTextEdit()
        self.personal_notes.setPlaceholderText("Your own notes, questions, and reminders…")
        self.personal_notes.textChanged.connect(self.save_personal_notes)
        personal_layout.addWidget(self.personal_notes)
        workspace.addWidget(personal_panel)

        ai_panel = QWidget()
        ai_layout = QVBoxLayout(ai_panel)
        ai_layout.setContentsMargins(0, 0, 0, 0)
        ai_layout.addWidget(QLabel("AI meeting notes — created after recording stops"))
        self.notes = QPlainTextEdit()
        self.notes.setPlaceholderText("The organized summary will appear here.")
        self.notes.setFont(QFont("Segoe UI", 10))
        ai_layout.addWidget(self.notes)
        workspace.addWidget(ai_panel)
        workspace.setSizes([230, 160, 260])
        layout.addWidget(workspace, 1)

        bottom = QHBoxLayout()
        self.save_button = QPushButton("Save Edited Notes")
        self.save_button.clicked.connect(self.save_notes)
        self.save_button.setEnabled(False)
        self.template_button = QPushButton("Edit Note Template")
        self.template_button.clicked.connect(self.edit_template)
        refresh_button = QPushButton("Refresh Devices & Models")
        refresh_button.clicked.connect(self.refresh_all)
        bottom.addWidget(self.save_button)
        bottom.addWidget(self.template_button)
        bottom.addStretch()
        bottom.addWidget(refresh_button)
        layout.addLayout(bottom)

        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar())

    def refresh_all(self):
        self.refresh_devices()
        self.refresh_models()

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

    def toggle_recording(self):
        if self.recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
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
        try:
            self.recorder.start(selection)
        except Exception as exc:
            self.show_error(str(exc))
            return

        self.settings.setValue("microphone_id", selection.microphone_id)
        self.settings.setValue("speaker_id", selection.speaker_id)
        self.settings.setValue("ollama_model", self.model_combo.currentText())
        self.settings.setValue("whisper", self.whisper_combo.currentText())
        self.recording = True
        self.consent_checkbox.setEnabled(False)
        self.mic_state.setText("Listening…")
        self.system_state.setText("Listening…")
        self.started_at = time.monotonic()
        self.timer.start(250)
        self.live_transcript.clear()
        self.live_transcriber = LiveTranscriber(self.whisper_combo.currentText())
        self.live_transcriber.text_ready.connect(self.append_live_transcript)
        self.live_transcriber.status.connect(self.status_label.setText)
        self.live_transcriber.error.connect(self.status_label.setText)
        self.live_transcriber.start()
        self.live_timer.start()
        self.record_button.setText("■  Stop & Create Notes")
        self.status_label.setText("Recording microphone and meeting audio…")
        self.notes.clear()
        self.save_button.setEnabled(False)
        self.open_folder_button.setEnabled(False)

    def stop_recording(self):
        self.timer.stop()
        self.live_timer.stop()
        if self.live_transcriber:
            self.live_transcriber.stop()
        self.recording = False
        self.record_button.setEnabled(False)
        self.record_button.setText("Processing…")
        try:
            self.recorder.stop(self.current_audio)
        except Exception as exc:
            self.processing_failed(str(exc))
            return
        self.process_audio()

    def process_audio(self):
        prompt = self.settings.value("template", DEFAULT_PROMPT)
        self.worker_thread = QThread(self)
        worker = ProcessingWorker(
            self.current_audio,
            self.whisper_combo.currentText(),
            self.model_combo.currentText(),
            prompt,
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
        self.record_button.setText("●  Start Recording")
        self.consent_checkbox.setEnabled(True)
        self.consent_checkbox.setChecked(False)
        self.mic_state.setText("Starts listening when recording begins")
        self.system_state.setText("Starts listening when recording begins")
        self.save_button.setEnabled(True)
        self.open_folder_button.setEnabled(True)

    def processing_failed(self, message: str):
        self.record_button.setText("●  Start Recording")
        self.consent_checkbox.setEnabled(True)
        self.consent_checkbox.setChecked(False)
        self.mic_state.setText("Starts listening when recording begins")
        self.system_state.setText("Starts listening when recording begins")
        self.status_label.setText(f"Could not finish: {message}")
        self.show_error(message)

    def update_levels(self, mic: float, system: float):
        if mic >= 0:
            self.mic_meter.setValue(int(mic))
            self.mic_state.setText("Sound detected ✓" if mic >= 3 else "Listening…")
        if system >= 0:
            self.system_meter.setValue(int(system))
            self.system_state.setText(
                "Sound detected ✓" if system >= 3 else "Listening…"
            )

    def request_live_transcription(self):
        if not self.recording or not self.live_transcriber:
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
            QDesktopServices.openUrl(self.current_folder.as_uri())

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

    def closeEvent(self, event):
        if self.recording:
            answer = QMessageBox.question(
                self,
                "Recording in progress",
                "Stop recording and close MeetingScribe?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.recorder._stop.set()
        event.accept()


def main():
    if "--preload-whisper" in sys.argv:
        # Used by the all-in-one installer so the first meeting does not need
        # to wait for the transcription model download.
        WhisperModel("small", device="cpu", compute_type="int8")
        return

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(QIcon(str(resource_path("assets/meetingscribe-icon.png"))))
    app.setStyle("Fusion")
    window = MeetingScribeWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
