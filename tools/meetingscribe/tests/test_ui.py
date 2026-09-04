"""UI regression checks; no microphone recording or AI model downloads."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QIcon, QPalette, QImage
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
        self.data_folder = Path(self.settings_folder.name) / "app-data"
        self.data_folder.mkdir()
        self.data_patch = patch.object(meetingscribe, "app_data_dir", return_value=self.data_folder)
        self.data_patch.start()
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
        # Mock workers in these tests must not trigger real shutdown dialogs.
        self.window.live_transcriber = None
        self.window.worker_thread = None
        self.window.recording = False
        self.window._update_downloading = False
        self.window._set_record_button_state("idle")
        self.window.close()
        self.window.deleteLater()
        self.qt.processEvents()
        self.settings_patch.stop()
        self.data_patch.stop()
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

    def test_update_startup_preference_and_manual_check(self):
        self.window.auto_update_action.setChecked(False)
        with patch.object(self.window, "restore_update_draft"), patch.object(self.window.update_jobs, "check") as check:
            self.window.startup_updates()
            check.assert_not_called()
            self.window.check_updates(manual=True)
            check.assert_called_once_with(meetingscribe.APP_VERSION, True)
        self.window.update_checked(None, "", False)
        self.assertTrue(self.window.update_action.isEnabled())

    def test_settings_menu_consolidates_footer_controls(self):
        labels = [action.text() for action in self.window.settings_menu.actions()]
        self.assertIn("Customize Summary…", labels)
        self.assertIn("Refresh Devices", labels)
        self.assertIn("Check for updates", labels)
        self.assertTrue(self.window.auto_update_action.isCheckable())
        self.assertIs(self.window.settings_button.menu(), self.window.settings_menu)
        self.assertFalse(any(child.metaObject().className() == "QStatusBar" for child in self.window.children()))
        self.window.auto_update_action.setChecked(False)
        self.assertFalse(self.test_settings.value("check_updates", True, type=bool))

    def test_update_offer_deferred_during_meeting(self):
        self.window.recording = True
        release = Mock(version="0.3.10-beta")
        with patch.object(self.window, "offer_update") as offer:
            self.window.update_checked(release, "", False)
            offer.assert_not_called()
            self.assertEqual(self.window.update_action.text(), "Update available")
            self.assertEqual(self.window.settings_button.text(), "Settings · Update")
        self.window.recording = False

    def test_processing_and_live_worker_block_updates(self):
        self.window._set_record_button_state("processing")
        self.assertTrue(self.window.update_busy())
        self.window._set_record_button_state("idle")
        self.window.live_transcriber = Mock()
        self.window.live_transcriber.is_running.return_value = True
        self.assertTrue(self.window.update_busy())
        self.window.live_transcriber = None

    def test_download_blocks_recording_and_failed_update_keeps_app_open(self):
        self.window._update_downloading = True
        with patch.object(self.window.recorder, "start") as start:
            self.window.start_recording()
            start.assert_not_called()
        with patch.object(meetingscribe.QMessageBox, "information"), patch.object(self.window, "close") as close:
            self.window.update_downloaded(None, "Failed safely")
            close.assert_not_called()
        self.assertFalse(self.window._update_downloading)

    def test_update_draft_preserves_pre_meeting_notes(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(meetingscribe, "app_data_dir", return_value=Path(folder)):
            self.window.personal_notes.setPlainText("Remember to ask about the plan.")
            self.window.notes.setPlainText("Edited summary")
            self.window.live_transcript.setPlainText("Transcript")
            self.window.save_update_draft()
            self.window.personal_notes.clear()
            self.window.notes.clear()
            self.window.restore_update_draft()
            self.assertEqual(self.window.personal_notes.toPlainText(), "Remember to ask about the plan.")
            self.assertEqual(self.window.notes.toPlainText(), "Edited summary")
            self.assertFalse((Path(folder) / "update-draft.json").exists())

    def test_update_reverifies_before_saving_or_launching(self):
        with patch.object(meetingscribe.updater, "verify_file", side_effect=ValueError("Mismatch")), patch.object(
                meetingscribe.QMessageBox, "warning"), patch.object(self.window, "launch_update") as launch:
            self.window.update_downloaded(Path("unused.exe"), "")
            launch.assert_not_called()

    def test_failed_launch_keeps_app_open(self):
        with patch.object(meetingscribe.updater, "verify_file"), patch.object(self.window, "save_update_draft"), patch.object(
                self.window, "launch_update", side_effect=OSError("Cannot launch")), patch.object(
                meetingscribe.QMessageBox, "warning"), patch.object(self.window, "close") as close:
            self.window.update_downloaded(Path("unused.exe"), "")
            close.assert_not_called()

    def test_verification_failure_does_not_delete_existing_recovery(self):
        draft = self.data_folder / "update-draft.json"
        draft.write_text("Keep this recovery copy", encoding="utf-8")
        with patch.object(meetingscribe.updater, "verify_file", side_effect=ValueError()), patch.object(meetingscribe.QMessageBox, "warning"):
            self.window.update_downloaded(Path("unused.exe"), "")
        self.assertEqual(draft.read_text(encoding="utf-8"), "Keep this recovery copy")

    def test_verified_update_saves_before_launch_and_close(self):
        order = []
        with patch.object(meetingscribe.updater, "verify_file", side_effect=lambda *args: order.append("verify")), patch.object(
                self.window, "save_update_draft", side_effect=lambda: order.append("save")), patch.object(
                self.window, "launch_update", side_effect=lambda path: order.append("launch")), patch.object(
                self.window, "close", side_effect=lambda: order.append("close")):
            self.window.update_downloaded(Path("unused.exe"), "")
        self.assertEqual(order, ["verify", "save", "launch", "close"])

    def test_installer_arguments_are_safe_and_do_not_force_close(self):
        with patch.object(meetingscribe.sys, "frozen", True, create=True), patch.object(meetingscribe.sys, "platform", "win32"), patch.object(
                meetingscribe.subprocess, "Popen") as launch:
            self.window.launch_update(Path("verified-update.exe"))
        args = launch.call_args.args[0]
        self.assertIn("/UPDATEONLY=1", args)
        self.assertIn("/NOCLOSEAPPLICATIONS", args)
        self.assertIn("/NORESTART", args)
        self.assertFalse(launch.call_args.kwargs["shell"])

    def test_character_background_is_transparent(self):
        image = QImage(str(meetingscribe.resource_path("assets/meetingscribe-icon.png")))
        self.assertTrue(image.hasAlphaChannel())
        for x, y in ((0, 0), (image.width()-1, 0), (0, image.height()-1), (image.width()-1, image.height()-1)):
            self.assertEqual(image.pixelColor(x, y).alpha(), 0)
        self.assertEqual(image.pixelColor(image.width()//2, image.height()//2).alpha(), 255)
        icon = QIcon(str(meetingscribe.resource_path("assets/meetingscribe-icon.ico")))
        for size in icon.availableSizes():
            self.assertEqual(icon.pixmap(size).toImage().pixelColor(0, 0).alpha(), 0)

    def test_saved_meetings_opens_before_recording(self):
        self.assertIs(self.window.saved_meetings_button.menu(), self.window.saved_meetings_menu)
        self.assertFalse(hasattr(self.window, "open_folder_button"))
        self.assertTrue(self.window.saved_meetings_button.isEnabled())
        self.assertFalse(self.window.current_meeting_action.isEnabled())
        self.assertIn(str(meetingscribe.default_output_dir(create=False)), self.window.saved_meetings_button.toolTip())
        with tempfile.TemporaryDirectory(prefix="meeting notes ") as folder:
            with patch.object(meetingscribe, "default_output_dir", return_value=Path(folder)), patch.object(
                meetingscribe.QDesktopServices, "openUrl", return_value=True
            ) as opened:
                self.window.all_meetings_action.trigger()
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
