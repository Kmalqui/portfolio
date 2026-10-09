"""Regression checks for the guided Mac installer source and release workflow."""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT.parents[1] / ".github" / "workflows" / "build-meetingscribe-macos.yml"


class MacPackagingTests(unittest.TestCase):
    def test_installer_keeps_common_existing_ollama_installations(self):
        source = (ROOT / "macos" / "Install MeetingScribe.applescript").read_text(
            encoding="utf-8"
        )
        self.assertIn("/Applications/Ollama.app", source)
        self.assertIn('"Applications/Ollama.app"', source)
        self.assertIn("/opt/homebrew/bin/ollama", source)
        self.assertIn("/usr/local/bin/ollama", source)
        self.assertIn("if not ollamaWasPresent then", source)
        self.assertIn("Your existing Ollama installation was kept.", source)

    def test_workflow_pins_and_verifies_the_ollama_download(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertRegex(workflow, r"OLLAMA_VERSION: v\d+\.\d+\.\d+")
        self.assertRegex(workflow, r"OLLAMA_SHA256: [0-9a-f]{64}")
        self.assertIn("shasum -a 256 --check", workflow)
        self.assertIn("codesign --verify --deep --strict vendor/Ollama.app", workflow)
        self.assertIn("OLLAMA-LICENSE.txt", workflow)
        self.assertIn("THIRD-PARTY-NOTICES.txt", workflow)

    def test_package_and_app_versions_match(self):
        app_source = (ROOT / "app.py").read_text(encoding="utf-8")
        workflow = WORKFLOW.read_text(encoding="utf-8")
        version = re.search(r'APP_VERSION = "([^"]+)"', app_source).group(1)
        self.assertIn(f"MeetingScribe-{version}-macOS-", workflow)
        installer = (ROOT / "installer.iss").read_text(encoding="utf-8")
        self.assertIn(f'#define MyAppVersion "{version}"', installer)
        self.assertIn(f"MeetingScribe-{version}-One-Click-Windows-Setup", installer)
        bundle_version = version.removesuffix("-beta")
        spec = (ROOT / "MeetingScribe.spec").read_text(encoding="utf-8")
        self.assertIn(f"'CFBundleShortVersionString': '{bundle_version}'", spec)
        self.assertIn(f"'CFBundleVersion': '{bundle_version}'", spec)


if __name__ == "__main__":
    unittest.main()
