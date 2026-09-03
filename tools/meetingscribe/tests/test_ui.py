"""UI regression checks; no microphone recording or AI model downloads."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPalette
from PySide6.QtWidgets import QApplication

import app as meetingscribe


class InterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])
        meetingscribe.apply_theme(cls.qt)

    def setUp(self):
        with patch.object(meetingscribe.MeetingScribeWindow, "refresh_devices"), patch.object(
            meetingscribe.MeetingScribeWindow, "refresh_models"
        ):
            self.window = meetingscribe.MeetingScribeWindow()
        self.window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        self.window.show()
        self.qt.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.qt.processEvents()

    def test_consent_required_and_button_states(self):
        self.assertFalse(self.window.record_button.isEnabled())
        with patch.object(self.window, "show_error") as error, patch.object(
            self.window.recorder, "start"
        ) as record:
            self.window.start_recording()
            error.assert_called_once()
            record.assert_not_called()
        self.window.consent_checkbox.setChecked(True)
        self.assertTrue(self.window.record_button.isEnabled())
        self.window._set_record_button_state("recording")
        self.assertTrue(self.window.record_button.property("recording"))
        self.window._set_record_button_state("processing")
        self.assertTrue(self.window.record_button.property("processing"))
        self.window._set_record_button_state("idle")
        self.assertFalse(self.window.record_button.property("recording"))
        self.assertFalse(self.window.record_button.property("processing"))

    def test_editors_fit_and_small_window_scrolls(self):
        self.assertEqual(self.window.centralWidget().verticalScrollBar().maximum(), 0)
        for editor in (
            self.window.live_transcript, self.window.personal_notes, self.window.notes
        ):
            self.assertLess(editor.geometry().bottom(), editor.parentWidget().height())
        self.window.resize(960, 700)
        self.qt.processEvents()
        self.assertEqual(self.window.centralWidget().horizontalScrollBar().maximum(), 0)
        self.assertGreater(self.window.centralWidget().verticalScrollBar().maximum(), 0)

    def test_transcript_and_personal_notes_remain_separate(self):
        self.window.personal_notes.setPlainText("Ask about the timeline.")
        self.window.append_live_transcript("We will review the timeline")
        self.window.append_live_transcript("the timeline tomorrow.")
        self.assertEqual(self.window.live_transcript.toPlainText(), "We will review the timeline tomorrow.")
        self.assertEqual(self.window.personal_notes.toPlainText(), "Ask about the timeline.")
        self.assertTrue(self.window.live_transcript.isReadOnly())
        with tempfile.TemporaryDirectory(prefix="meetingscribe-test-") as folder:
            self.window.current_folder = Path(folder)
            self.window.save_personal_notes()
            self.assertEqual((Path(folder) / "my-notes.md").read_text(encoding="utf-8"), "Ask about the timeline.")
            self.window.current_folder = None

    def test_audio_meters_and_light_palette(self):
        self.window.update_levels(25, 40)
        self.assertEqual(self.window.mic_meter.value(), 25)
        self.assertEqual(self.window.system_meter.value(), 40)
        self.assertIn("Sound detected", self.window.system_state.text())
        self.assertEqual(self.qt.palette().color(QPalette.ColorRole.WindowText).name(), "#173329")

    def test_icon_has_multiple_sizes(self):
        icon = QIcon(str(meetingscribe.resource_path("assets/meetingscribe-icon.ico")))
        self.assertFalse(icon.isNull())
        self.assertGreaterEqual(len(icon.availableSizes()), 4)

    def test_saved_meetings_opens_before_recording(self):
        self.assertTrue(self.window.saved_meetings_button.isEnabled())
        self.assertFalse(self.window.open_folder_button.isEnabled())
        self.assertIn(str(meetingscribe.default_output_dir(create=False)), self.window.save_location_label.text())
        with tempfile.TemporaryDirectory(prefix="meeting notes ") as folder:
            with patch.object(meetingscribe, "default_output_dir", return_value=Path(folder)), patch.object(
                meetingscribe.QDesktopServices, "openUrl", return_value=True
            ) as opened:
                self.window.saved_meetings_button.click()
                opened.assert_called_once()
                self.assertTrue(opened.call_args.args[0].isLocalFile())
                self.assertEqual(Path(opened.call_args.args[0].toLocalFile()), Path(folder).resolve())

    def test_current_folder_is_distinct_from_all_meetings(self):
        with tempfile.TemporaryDirectory(prefix="meetingscribe-test-") as folder:
            self.window.current_folder = Path(folder)
            with patch.object(meetingscribe.QDesktopServices, "openUrl", return_value=True) as opened:
                self.window.open_meeting_folder()
                self.assertEqual(Path(opened.call_args.args[0].toLocalFile()), Path(folder).resolve())
            self.window.current_folder = None

    def test_folder_errors_are_visible(self):
        with patch.object(meetingscribe, "default_output_dir", side_effect=PermissionError("Access denied")), patch.object(
            self.window, "show_error"
        ) as error:
            self.window.open_saved_meetings()
            error.assert_called_once()
        with tempfile.TemporaryDirectory(prefix="meetingscribe-test-") as folder:
            with patch.object(meetingscribe.QDesktopServices, "openUrl", return_value=False), patch.object(
                self.window, "show_error"
            ) as error:
                self.window._open_folder(Path(folder))
                error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
