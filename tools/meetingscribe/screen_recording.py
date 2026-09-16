"""Local, optional monitor capture for MeetingScribe."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path

import av
import mss
import numpy as np
from PySide6.QtCore import QObject, Signal


PROFILES = {
    "efficient": ("Efficient — 720p, 10 FPS", 10, 1280, 2_500_000),
    "standard": ("Standard — 1080p, 15 FPS", 15, 1920, 5_000_000),
    "high": ("High — native size, 30 FPS", 30, None, 12_000_000),
}


@dataclass(frozen=True)
class ScreenOptions:
    enabled: bool = False
    monitor: int = 1
    profile: str = "efficient"


def output_size(width: int, height: int, maximum_width: int | None):
    if maximum_width and width > maximum_width:
        scale = maximum_width / width
        width, height = maximum_width, round(height * scale)
    return max(2, width // 2 * 2), max(2, height // 2 * 2)


def available_monitors():
    with mss.mss() as capture:
        return [dict(item) for item in capture.monitors[1:]]


class ScreenRecorder(QObject):
    error = Signal(str)
    stopped = Signal(str)

    def __init__(self, output: Path, options: ScreenOptions, parent=None):
        super().__init__(parent)
        self.output = Path(output)
        self.options = options
        self._stop = threading.Event()
        self._thread = None
        self._error = ""

    def start(self):
        if self._thread and self._thread.is_alive():
            raise RuntimeError("Screen recording is already running")
        self._stop.clear()
        self._thread = threading.Thread(target=self._capture, daemon=True, name="MeetingScribe screen recorder")
        self._thread.start()

    def stop(self, wait=True):
        self._stop.set()
        if wait and self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=5)

    def is_running(self):
        return bool(self._thread and self._thread.is_alive())

    def _capture(self):
        container = None
        try:
            label, fps, max_width, bitrate = PROFILES[self.options.profile]
            with mss.mss() as capture:
                monitors = capture.monitors[1:]
                if not monitors or not 1 <= self.options.monitor <= len(monitors):
                    raise RuntimeError("The selected screen is no longer available.")
                monitor = monitors[self.options.monitor - 1]
                width, height = output_size(monitor["width"], monitor["height"], max_width)
                container = av.open(str(self.output), mode="w")
                stream = container.add_stream("mpeg4", rate=fps)
                stream.bit_rate = bitrate
                stream.width, stream.height, stream.pix_fmt = width, height, "yuv420p"
                interval = 1 / fps
                next_frame = time.perf_counter()
                while not self._stop.is_set():
                    shot = capture.grab(monitor)
                    frame = av.VideoFrame.from_ndarray(np.asarray(shot), format="bgra")
                    frame = frame.reformat(width=width, height=height, format="yuv420p")
                    for packet in stream.encode(frame):
                        container.mux(packet)
                    next_frame += interval
                    self._stop.wait(max(0, next_frame - time.perf_counter()))
                for packet in stream.encode():
                    container.mux(packet)
                container.close()
                container = None
            self.stopped.emit(str(self.output))
        except Exception as exc:
            self._error = str(exc)
            if container is not None:
                try:
                    container.close()
                except Exception:
                    pass
            self.output.unlink(missing_ok=True)
            self.error.emit(f"Screen recording stopped: {exc}")
