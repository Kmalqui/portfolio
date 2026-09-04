"""Offline update safety tests; never install software or contact GitHub."""
import hashlib
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock

import updater


def release_data(version="0.3.10-beta", content=b"test installer"):
    name = f"MeetingScribe-{version}-One-Click-Windows-Setup.exe"
    return {"tag_name": f"meetingscribe-v{version}", "draft": False,
            "prerelease": "beta" in version, "assets": [{"name": name,
            "browser_download_url": f"https://github.com/Kmalqui/portfolio/releases/download/meetingscribe-v{version}/{name}",
            "size": len(content), "digest": "sha256:" + hashlib.sha256(content).hexdigest()}]}


class Response:
    def __init__(self, status=200, data=None, chunks=(), headers=None):
        self.status_code, self.data, self.chunks = status, data, chunks
        self.headers = headers or {}
    def __enter__(self): return self
    def __exit__(self, *args): self.close()
    def close(self): pass
    def json(self): return self.data
    def iter_content(self, size): return iter(self.chunks)


class UpdateTests(unittest.TestCase):
    def test_numeric_versions_and_beta_to_stable(self):
        self.assertGreater(updater.version_key("0.3.10-beta"), updater.version_key("0.3.9-beta"))
        self.assertGreater(updater.version_key("0.3.9"), updater.version_key("0.3.9-beta"))

    def test_newer_beta_selected_and_old_versions_ignored(self):
        data = [release_data("0.3.8-beta"), release_data(), release_data("0.3.9-beta")]
        self.assertEqual(updater.select_release(data, "0.3.9-beta").version, "0.3.10-beta")
        self.assertIsNone(updater.select_release(data, "0.3.10-beta"))

    def test_stable_does_not_opt_into_beta(self):
        self.assertIsNone(updater.select_release([release_data()], "0.3.9"))

    def test_drafts_other_projects_and_bad_versions_ignored(self):
        for change in ({"draft": True}, {"tag_name": "other-v99.0.0"}, {"tag_name": "meetingscribe-vbad"}):
            data = release_data()
            data.update(change)
            self.assertIsNone(updater.select_release([data], "0.3.9-beta"))

    def test_missing_digest_wrong_host_name_and_size_rejected(self):
        for field, value in (("digest", None), ("browser_download_url", "https://example.com/setup.exe"),
                             ("name", "wrong.exe"), ("size", 0), ("size", updater.MAX_SIZE + 1)):
            data = release_data()
            data["assets"][0][field] = value
            self.assertIsNone(updater.select_release([data], "0.3.9-beta"))

    def test_paginated_check(self):
        get = Mock(side_effect=[Response(data=[{"tag_name": "other"}] * 100), Response(data=[release_data()])])
        self.assertEqual(updater.check_release("0.3.9-beta", get).version, "0.3.10-beta")
        self.assertEqual(get.call_count, 2)

    def test_api_rate_limit_and_invalid_json(self):
        for response in (Response(403), Response(data={"error": "bad"})):
            with self.assertRaises((RuntimeError, ValueError)):
                updater.check_release("0.3.9-beta", Mock(return_value=response))

    def test_download_verifies_and_follows_trusted_redirect(self):
        content = b"test installer"
        release = updater.select_release([release_data(content=content)], "0.3.9-beta")
        get = Mock(side_effect=[Response(302, headers={"Location": "https://release-assets.githubusercontent.com/test"}), Response(chunks=[content])])
        with tempfile.TemporaryDirectory() as folder:
            path = updater.download_release(release, folder, threading.Event(), get=get)
            self.assertEqual(path.read_bytes(), content)
            updater.verify_file(path, release)

    def test_corrupt_truncated_oversize_cancelled_downloads_removed(self):
        release = updater.select_release([release_data()], "0.3.9-beta")
        for content, cancelled in ((b"bad", False), (b"x" * 14, False), (b"x" * 100, False), (b"test installer", True)):
            with tempfile.TemporaryDirectory() as folder:
                event = threading.Event()
                if cancelled: event.set()
                with self.assertRaises((RuntimeError, ValueError)):
                    updater.download_release(release, folder, event, get=Mock(return_value=Response(chunks=[content])))
                self.assertEqual(list(Path(folder).iterdir()), [])

    def test_untrusted_redirect_and_credentials_rejected(self):
        for url in ("http://github.com/test", "https://evil.example/setup", "https://github.com.evil.example/setup",
                    "https://user:pass@github.com/setup", "https://github.com:444/setup"):
            with self.assertRaises(ValueError): updater.validate_download_url(url)
        release = updater.select_release([release_data()], "0.3.9-beta")
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                updater.download_release(release, folder, threading.Event(), get=Mock(return_value=Response(302, headers={"Location": "https://evil.example/setup"})))
            self.assertEqual(list(Path(folder).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
