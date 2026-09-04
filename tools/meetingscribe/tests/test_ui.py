"""UI regression checks; no microphone recording or AI model downloads."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QIcon, QPalette
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

import app as meetingscribe


class InterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])
        meetingscribe.apply_theme(cls.qt)

    def setUp(self):
        self.settings_folder = tempfile.TemporaryDirectory(prefix="meetingscribe-settings-")
        self.test_settings = QSettings(str(Path(self.settings_folder.name) / "settings.ini"), QSettings.Format.IniFormat)
        self.settings_patch = patch.object(meetingscribe, "QSettings", return_value=self.test_settings)
        self.settings_patch.start()
        with patch.object(meetingscribe.MeetingScribeWindow, "refresh_devices"), patch.object(
            meetingscribe.MeetingScribeWindow, "refresh_models"
        ):
            self.window = meetingscribe.MeetingScribeWindow()
        self.window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        self.window.show()
        self.qt.processEvents()

    def test_theme_switches_immediately_and_is_restored(self):
        self.window.personal_notes.setPlainText("Keep this note.")
        self.window.theme_toggle.click()
        self.qt.processEvents()
        self.assertEqual(self.test_settings.value("theme"), "dark")
        self.assertEqual(self.qt.palette().color(QPalette.ColorRole.Window).name(), "#211d30")
        self.assertEqual(self.window.personal_notes.toPlainText(), "Keep this note.")
        with patch.object(meetingscribe.MeetingScribeWindow, "refresh_devices"), patch.object(
            meetingscribe.MeetingScribeWindow, "refresh_models"
        ):
            reopened = meetingscribe.MeetingScribeWindow()
        self.assertTrue(reopened.theme_toggle.isChecked())
        reopened.close()
        reopened.deleteLater()
        QTest.keyClick(self.window.theme_toggle, Qt.Key.Key_Space)
        self.assertFalse(self.window.theme_toggle.isChecked())
        self.assertEqual(self.test_settings.value("theme"), "light")
        self.assertEqual(self.qt.palette().color(QPalette.ColorRole.Window).name(), "#fff8f2")

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.qt.processEvents()
        self.settings_patch.stop()
        self.test_settings.sync()
        self.settings_folder.cleanup()

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

    def test_live_mode_defaults_to_eco_and_off_skips_worker(self):
        self.assertEqual(self.window.live_mode_combo.currentData(), "eco")
        self.window.mic_combo.addItem("Microphone", "mic")
        self.window.speaker_combo.addItem("Speakers", "speaker")
        self.window.model_combo.addItem("test-model")
        self.window.consent_checkbox.setChecked(True)
        for mode in ("eco", "off"):
            self.window.live_mode_combo.setCurrentIndex(self.window.live_mode_combo.findData(mode))
            with patch.object(meetingscribe, "default_output_dir", return_value=Path(self.settings_folder.name)), patch.object(
                self.window.recorder, "start"
            ), patch.object(meetingscribe, "LiveTranscriber") as factory:
                self.window.start_recording()
                if mode == "eco":
                    factory.assert_called_once_with("tiny", cpu_threads=2, prefer_gpu=False)
                    self.assertEqual(self.window.live_timer.interval(), 12000)
                else:
                    factory.assert_not_called()
                    self.assertIn("off", self.window.live_transcript.toPlainText())
                self.assertFalse(self.window.live_mode_combo.isEnabled())
            self.window.timer.stop()
            self.window.live_timer.stop()
            self.window.recording = False
        self.window.current_folder = None

    def test_busy_live_worker_skips_audio_copy(self):
        self.window.recording = True
        self.window.live_transcriber = Mock()
        self.window.live_transcriber.can_accept.return_value = False
        with patch.object(self.window.recorder, "live_snapshot") as snapshot:
            self.window.request_live_transcription()
            snapshot.assert_not_called()
        self.window.recording = False

    def test_final_processing_waits_for_live_worker(self):
        self.window.live_transcriber = Mock()
        self.window.live_transcriber.is_running.return_value = True
        with patch.object(meetingscribe.QTimer, "singleShot") as later, patch.object(self.window, "process_audio") as process:
            self.window.finish_live_before_processing()
            process.assert_not_called()
            later.assert_called_once()
            self.window.live_transcriber.is_running.return_value = False
            self.window.finish_live_before_processing()
            process.assert_called_once()
            self.assertIsNone(self.window.live_transcriber)

    def test_editors_fit_and_small_window_scrolls(self):
        # Use explicit large/small viewports, independent of CI font metrics.
        self.window.resize(1100, 1000)
        self.qt.processEvents()
        self.assertEqual(self.window.centralWidget().verticalScrollBar().maximum(), 0)
        for editor in (
            self.window.live_transcript, self.window.personal_notes, self.window.notes
        ):
            self.assertLess(editor.geometry().bottom(), editor.parentWidget().height())
        self.window.resize(1100, 700)
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
        self.assertEqual(self.qt.palette().color(QPalette.ColorRole.WindowText).name(), "#34264d")

    def test_clarity_dialog_save_cancel_and_persistence(self):
        def save_dialog(dialog):
            boxes = dialog.findChildren(meetingscribe.QCheckBox)
            boxes[0].setChecked(True)
            boxes[1].setChecked(True)
            return meetingscribe.QDialog.DialogCode.Accepted
        with patch.object(meetingscribe.QDialog, "exec", save_dialog):
            self.window.edit_voice_clarity()
        self.assertTrue(self.window.cleanup_preferences().enabled)
        self.assertFalse(self.window.cleanup_preferences().clean_others)
        self.assertEqual(self.window.clarity_button.text(), "Voice clarity: On")
        with patch.object(meetingscribe.QDialog, "exec", return_value=meetingscribe.QDialog.DialogCode.Rejected):
            self.window.edit_voice_clarity()
        self.assertTrue(self.window.cleanup_preferences().noise_reduction)

    def test_quiet_input_notice_does_not_stop_recording(self):
        self.window.recording = True
        self.window.last_mic_sound = self.window.last_system_sound = 0
        self.window.update_levels(0, 0)
        self.assertIn("No recent", self.window.mic_state.text())
        self.assertTrue(self.window.recording)
        self.window.update_levels(25, 25)
        self.assertIn("Sound detected", self.window.mic_state.text())
        self.window.recording = False

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
