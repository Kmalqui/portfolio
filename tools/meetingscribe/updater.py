"""Opt-in installation of verified releases from the project's public repository."""
from __future__ import annotations

import hashlib
import re
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests
from PySide6.QtCore import QObject, Signal

REPOSITORY = "Kmalqui/portfolio"
API = f"https://api.github.com/repos/{REPOSITORY}/releases"
MAX_SIZE = 250 * 1024 * 1024


def version_key(value):
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:-beta(?:\.(\d+))?)?", value)
    if not match:
        raise ValueError("Unsupported version")
    major, minor, patch, beta = match.groups()
    return (int(major), int(minor), int(patch), int("-beta" not in value), int(beta or 0))


@dataclass(frozen=True)
class Release:
    version: str
    url: str
    digest: str
    size: int
    name: str


def select_release(releases, current):
    candidates = []
    for release in releases:
        tag = release.get("tag_name", "")
        if release.get("draft") or not tag.startswith("meetingscribe-v"):
            continue
        version = tag.removeprefix("meetingscribe-v")
        try:
            if version_key(version) <= version_key(current):
                continue
        except (TypeError, ValueError):
            continue
        # Stable installations do not silently opt into beta releases.
        if "-beta" not in current and (release.get("prerelease") or "-beta" in version):
            continue
        name = f"MeetingScribe-{version}-One-Click-Windows-Setup.exe"
        expected_url = f"https://github.com/{REPOSITORY}/releases/download/{tag}/{name}"
        for asset in release.get("assets", []):
            digest = asset.get("digest") or ""
            size = asset.get("size", 0)
            if (asset.get("name") == name and asset.get("browser_download_url") == expected_url
                    and re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
                    and isinstance(size, int) and 0 < size <= MAX_SIZE):
                candidates.append(Release(version, expected_url, digest[7:], size, name))
    return max(candidates, key=lambda r: version_key(r.version), default=None)


def check_release(current, get=requests.get):
    releases = []
    # The repository also contains other projects; include beta releases and
    # filter our own tags instead of using GitHub's stable-only latest endpoint.
    for page in range(1, 4):
        with get(API, params={"per_page": 100, "page": page}, timeout=(5, 10),
                 headers={"Accept": "application/vnd.github+json"}, allow_redirects=False) as response:
            if response.status_code != 200:
                raise RuntimeError("GitHub is unavailable or its request limit was reached.")
            batch = response.json()
        if not isinstance(batch, list):
            raise ValueError("Unexpected release response")
        releases.extend(batch)
        if len(batch) < 100:
            break
    return select_release(releases, current)


def validate_download_url(url):
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.hostname not in
            {"github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"}
            or parsed.username or parsed.password or parsed.port not in (None, 443)):
        raise ValueError("Untrusted download address")


def verify_file(path, release):
    digest = hashlib.sha256()
    size = 0
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    if size != release.size or digest.hexdigest() != release.digest:
        raise ValueError("The update did not pass its integrity check. Please download it again.")


def download_release(release, cache, cancel, progress=lambda percent: None, get=requests.get):
    # Do not execute arbitrary URLs supplied by a caller, even on an allowed host.
    expected = f"https://github.com/{REPOSITORY}/releases/download/meetingscribe-v{release.version}/{release.name}"
    if release.url != expected or release.name != f"MeetingScribe-{release.version}-One-Click-Windows-Setup.exe":
        raise ValueError("Unexpected installer address")
    Path(cache).mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix="update-", dir=cache))
    target = folder / release.name
    response = None
    try:
        url = release.url
        for _ in range(6):
            validate_download_url(url)
            response = get(url, stream=True, timeout=(10, 20), allow_redirects=False)
            if response.status_code not in (301, 302, 303, 307, 308):
                break
            url = response.headers.get("Location", "")
            response.close()
        if response.status_code != 200:
            raise RuntimeError("The installer could not be downloaded.")
        received = 0
        started = time.monotonic()
        with target.open("xb") as output:
            for chunk in response.iter_content(1024 * 1024):
                if cancel.is_set():
                    raise RuntimeError("Download cancelled.")
                if time.monotonic() - started > 600:
                    raise RuntimeError("Download timed out. Please try again.")
                received += len(chunk)
                if received > min(release.size, MAX_SIZE):
                    raise ValueError("Unexpected installer size")
                output.write(chunk)
                progress(int(received * 100 / release.size))
        verify_file(target, release)
        return target
    except Exception:
        target.unlink(missing_ok=True)
        folder.rmdir()
        raise
    finally:
        if response is not None:
            response.close()


class UpdateJobs(QObject):
    checked = Signal(object, str, bool)
    downloaded = Signal(object, str)
    progress = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cancel = threading.Event()

    def check(self, current, manual):
        def work():
            try:
                self.checked.emit(check_release(current), "", manual)
            except Exception:
                self.checked.emit(None, "Could not check for updates. Check your internet connection and try again later.", manual)
        threading.Thread(target=work, daemon=True).start()

    def download(self, release, cache):
        self.cancel.clear()
        def work():
            try:
                path = download_release(release, cache, self.cancel, self.progress.emit)
                self.downloaded.emit(path, "")
            except Exception:
                self.downloaded.emit(None, "Download cancelled or verification failed. Your current app is unchanged; you can try again later.")
        threading.Thread(target=work, daemon=True).start()
