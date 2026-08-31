# MeetingScribe for Windows

MeetingScribe records you and the other people in an online meeting, turns the recording into a transcript, and creates organized meeting notes. Everything is processed on your own computer.

You do not need Obsidian, ChatGPT, an OpenAI API key, or a paid subscription.

## New in 0.3.0 beta

- A cream-and-green interface with grouped setup cards and clear audio activity panels.
- A transcript across the top, with your personal notes and the organized summary side by side underneath. Drag the dividers to adjust their sizes.
- Distinct ready, recording, and processing button styles, plus scrolling on smaller screens.
- The ear-and-notepad icon on the installer, application, desktop shortcut, and Start-menu shortcut.

### Updating an existing installation

1. Finish any active meeting and close MeetingScribe.
2. Run the new 0.3.0 installer. Use the same installation folder as before.
3. Open MeetingScribe using the new desktop or Start-menu shortcut.

Your saved meetings and settings are kept. Existing models are reused, although setup still checks them and may need an internet connection.

If a pinned taskbar shortcut still shows the old icon, unpin it, open the updated app from Start, then pin that running app again. The new installer uses a separate icon file so newly created shortcuts do not depend on the old executable icon cache. You do not need to delete Windows icon-cache files.

## What MeetingScribe creates

After each meeting, MeetingScribe creates a folder containing:

- `recording.wav` — the complete audio recording.
- `transcript.txt` — everything Whisper could hear and transcribe.
- `my-notes.md` — anything you typed in the **My notes** section.
- `notes.md` — the final transcript at the top followed by organized AI meeting notes.
- `meeting.json` — basic technical details about how the notes were processed.

The generated notes normally include a title, summary, discussion points, decisions, action items, and the complete transcript.

## Before you install

MeetingScribe currently supports 64-bit Windows 10 and Windows 11.

You will need:

- A microphone and headphones, a headset, or speakers.
- An internet connection for the initial downloads.
- Approximately 5–15 GB of free disk space, depending on the models selected.
- At least 8 GB of memory. Sixteen GB or more is recommended.

After Ollama and the models are installed, meetings can be processed without sending the recording to an online AI service.

## Important: get permission before recording

Tell everyone that you intend to record and obtain any consent required by your workplace, school, meeting organizer, or local law. Recording laws differ by location. MeetingScribe cannot determine whether you have permission to record.

Do not use MeetingScribe for confidential, regulated, medical, legal, employment, or customer information unless you are authorized to store and process that information on your computer.

## Part 1 — Run the one-click installer

Open `MeetingScribe-0.3.0-beta-One-Click-Windows-Setup.exe` while connected to the internet and follow the setup screens. That single installer:

- Installs MeetingScribe.
- Downloads and installs Ollama from the official Ollama website if it is not already installed.
- Downloads the lightweight `qwen3:4b` model that writes the notes.
- Downloads the Whisper `small` model that transcribes recordings.
- Creates Start-menu and desktop shortcuts.

The model downloads are several gigabytes. Setup may take 10–60 minutes depending on the internet connection and computer. A download window may appear while the AI model is installed; leave it open until it closes by itself. The progress can appear paused for a while on slower connections.

After setup finishes, the program can record, transcribe, and create notes locally without a ChatGPT account, API key, or monthly subscription.

### If automatic setup fails

Run the same installer again while connected to the internet. It safely reuses components that have already downloaded. If it fails again, install Ollama manually from <https://ollama.com/download/windows>, open Windows Terminal, and run:

```text
ollama pull qwen3:4b
```

### If Windows SmartScreen appears

This community beta is not digitally signed, so Windows may display **Windows protected your PC** or **Unknown publisher**.

Only continue if you received the installer from someone you trust and its filename is exactly what you expected.

1. Select **More info**.
2. Confirm the app is the expected MeetingScribe installer.
3. Select **Run anyway**.

Do not bypass a warning for a differently named or unexpected file. Do not disable antivirus protection.

## Part 2 — Allow microphone access

1. Open **Windows Settings**.
2. Select **Privacy & security**.
3. Select **Microphone** under App permissions.
4. Turn on **Microphone access**.
5. Turn on **Let apps access your microphone** if it appears.
6. Turn on **Let desktop apps access your microphone**.
7. Close and reopen MeetingScribe after changing these settings.

## Part 3 — First-time MeetingScribe setup

Open MeetingScribe from the desktop shortcut or Start menu.

### Your microphone

Under **Your microphone**, select the physical microphone used by the meeting application. It may be called `Headset Microphone`, `Microphone Array`, `USB Microphone`, or named after a Logitech, Jabra, Poly, Dell, or other device.

Avoid inputs containing `virtual`, `loopback`, or `Voicemeeter` unless you deliberately use virtual audio software.

### Meeting audio output

Under **Meeting audio output**, select the device through which you hear other participants. It must match the **Speaker** or **Output** selected inside Teams, Zoom, Meet, Webex, Discord, or the other meeting application.

If you change headphones or speakers during a meeting, stop the recording, select the new output, and start a new recording.

### Local AI model (Ollama)

Select `qwen3:4b`, which the one-click installer downloads automatically.

If the list says **Ollama is not running**:

1. Open Ollama from the Start menu.
2. Wait ten seconds.
3. Return to MeetingScribe and select **Refresh Devices**.

If it says **Install a model with Ollama**, follow the model-installation instructions in Part 1.

### Transcription quality

| Setting | Best for | Tradeoff |
|---|---|---|
| `small` | Most computers and first-time setup | Fastest and smallest download |
| `medium` | Better accuracy on a capable computer | Slower and uses more memory |
| `large-v3` | Highest available accuracy | Largest and slowest without a strong GPU |

Start with `small`. The first meeting processed with a particular Whisper model downloads that model. This can take several minutes. Keep MeetingScribe open and connected to the internet during that first download.

MeetingScribe provides near-real-time transcription in short chunks while recording. It is not instant word-by-word captioning. The delay depends on the computer and selected Whisper model. Use `small` for the fastest live transcription; `medium` and `large-v3` may fall behind on computers without a capable graphics card. After recording stops, MeetingScribe transcribes the complete recording again to create the final transcript.

## Part 5 — Test audio before a real meeting

Always make a short test first.

1. Select the headset or speakers you will use.
2. Play a video containing clear speech.
3. In MeetingScribe, select the same device under **Meeting audio output**.
4. Confirm that everyone has been informed and you have permission to record.
5. Select the permission checkbox in MeetingScribe.
6. Select **Start Recording**.
7. Speak while the video plays.
8. Check both audio panels while recording:
   - **You (microphone)** should move when you speak.
   - **Other people (meeting audio)** should move when the video or another participant speaks.
9. Record for 15–30 seconds.
10. Select **Stop & Create Notes**.
11. Wait for transcription and note generation.
12. Select **Open Meeting Folder**.
13. Play `recording.wav` and confirm both voices are audible.
14. Check `transcript.txt` and `notes.md`.

Do not record an important meeting unless both meters move during the test.

## Part 6 — Record a meeting

1. Open Ollama if it is not already running.
2. Open MeetingScribe.
3. Join the meeting.
4. Confirm the meeting application's microphone and speaker match MeetingScribe.
5. Tell participants that recording is about to begin and obtain consent.
6. Select the permission checkbox. MeetingScribe will not enable recording until you acknowledge that participants have been informed and permission has been obtained.
7. Select **Start Recording**.
8. Confirm both audio panels respond when people speak.
9. Leave MeetingScribe open; you may minimize it.
10. Do not let the computer sleep.
11. At the end, select **Stop & Create Notes**.
12. Wait while MeetingScribe transcribes and generates notes.
13. Review the draft carefully. AI can misunderstand names, technical terms, decisions, owners, and deadlines.
14. Edit the notes if needed and select **Save Notes**.

During the meeting:

- **Live transcript** fills automatically in short chunks and cannot be edited.
- **My notes** remains editable for your own questions, reminders, and observations.
- **AI meeting notes** appears after processing finishes.
- Use **Clear My Notes** before starting a different meeting if you do not want to carry over text from the previous one.

## Where files are saved

MeetingScribe saves meetings under:

```text
Documents\Meeting Notes
```

Each meeting receives a date-and-time folder, such as:

```text
Documents\Meeting Notes\2026-08-28_14-30-00
```

Audio files can be large. A one-hour WAV recording may require hundreds of megabytes. Review the folder periodically according to your storage and retention requirements.

Deleting a meeting folder removes its recording, transcript, notes, and metadata unless another backup exists.

## Open and share Markdown notes

`notes.md` and `my-notes.md` are ordinary text in Markdown format. They can be opened with Notepad, Visual Studio Code, Obsidian, Typora, and many other applications. After reviewing them, you can copy the text into Word, Google Docs, email, Teams, Slack, or another approved destination.

## Customize the note format

1. Select **Customize Summary**.
2. MeetingScribe shows its template-file location.
3. Edit and save the instructions.
4. Select the saved template when asked.

Useful instructions might request risks and blockers, separate customer questions, an email draft, or approved department headings. The model can follow templates imperfectly, so review every result.

## Troubleshooting

### The Mic meter does not move

- Select the correct physical microphone.
- Check the microphone's hardware mute button.
- Check **Windows Settings → Privacy & security → Microphone**.
- Close other audio tools that may control the device.
- Reopen MeetingScribe after connecting a new headset.
- Select **Refresh Devices**.

### The Others meter does not move

- Confirm audio is playing.
- Confirm MeetingScribe uses the output through which you hear the meeting.
- Confirm the meeting application's speaker/output matches it.
- With Bluetooth headphones, prefer the normal stereo/headphones output over a hands-free output.
- Reopen MeetingScribe after changing devices.

### I can hear myself but not other participants

The wrong meeting-audio output was selected. Choose the device through which you hear the meeting and make another test.

### I can hear participants but not myself

Select the physical microphone used by the meeting app. Check its mute button and Windows permissions.

### The recording is silent

Return to the test procedure and verify both meters move. Restart MeetingScribe after changing devices or permissions.

### Ollama is not running

Open Ollama from Start, wait ten seconds, and select **Refresh Devices**. Restart Windows if necessary.

### No Ollama models appear

Run the installer again, or use the manual recovery command in Part 1. The download must finish before the model appears.

### The first transcription appears stuck

The Whisper model may still be downloading. Keep MeetingScribe open and connected. Larger models take longer. Try `small` on a computer with limited memory.

### Processing is extremely slow

- Use Whisper `small`.
- Use `qwen3:4b` or `qwen3:8b`.
- Close games and other demanding applications.
- Connect laptops to power.
- Ensure enough disk space is free.

### Names or technical terms are incorrect

Whisper can mishear names, acronyms, products, and specialized terms. Correct notes before sharing. Try Whisper `medium` on a capable computer.

### No speech was detected

Play `recording.wav`. Check both meters, microphone permissions, and output selection before retrying.

### Antivirus or Windows warns about the app

The beta is unsigned. Verify the source and filename. Do not disable antivirus software or run an unexpected file.

### MeetingScribe closes unexpectedly

Reopen it and make a short test. Confirm sufficient memory and disk space. If it repeats, record what happened immediately before the crash and give that information to the beta maintainer.

## Privacy and network use

- Audio is recorded locally.
- Whisper transcribes locally.
- Ollama generates notes locally.
- Meeting data is not intentionally uploaded to ChatGPT or an OpenAI API.

The internet is used to download MeetingScribe, Ollama, and models. Other software—including Windows, meeting apps, security software, and backup or synchronization tools—is outside MeetingScribe's control.

If Documents is synchronized with OneDrive or another service, Meeting Notes may also be uploaded by that service. Check organizational storage rules before recording sensitive meetings.

## Updating MeetingScribe

1. Finish and save any current meeting.
2. Close MeetingScribe.
3. Run the newer trusted installer in the default location.
4. Reopen MeetingScribe and make a short audio test.

Updates should not remove `Documents\Meeting Notes`, but important files should still be backed up normally.

## Updating an Ollama model

Open Windows Terminal and run the same pull command again, for example:

```text
ollama pull qwen3:8b
```

Restart MeetingScribe and select **Refresh Devices**.

## Uninstalling MeetingScribe

1. Close MeetingScribe.
2. Open **Windows Settings → Apps → Installed apps**.
3. Find **MeetingScribe** and select **Uninstall**.

Uninstalling does not delete `Documents\Meeting Notes`.

## Uninstalling Ollama

Only remove Ollama if no other local applications use it. Open **Windows Settings → Apps → Installed apps**, find **Ollama**, and choose **Uninstall**. Model data may remain afterward; consult current Ollama documentation if you want to remove it too.

## Sharing notes safely

Before sharing generated notes:

1. Verify the transcript and summary.
2. Correct names, dates, deadlines, decisions, and owners.
3. Remove private or irrelevant conversation.
4. Confirm recipients are authorized.
5. Use an approved sharing method.

AI-generated notes are a draft, not an authoritative record.

## Beta limitations

- This is an unsigned community beta.
- Windows is supported first; a macOS build is not included.
- Speaker identification is not guaranteed.
- Transcriptions and summaries can contain errors.
- MeetingScribe does not join meetings automatically.
- It does not notify participants that recording is active.
- It does not provide enterprise retention, legal hold, or administrative controls.

## License

MeetingScribe is distributed under the MIT License. See `LICENSE.txt`.

## For developers: interface checks

With the dependencies in `requirements.txt` installed, run this from the MeetingScribe source folder:

```text
python -m unittest discover -s tests -v
```

The checks exercise consent gating, recording-button states, the audio meters, separate transcript and personal-note fields, small-window scrolling, and the multi-size icon. They do not record audio, download models, or replace a real meeting test.

After building with PyInstaller, `MeetingScribe.exe --smoke-test` checks startup and bundled icons without opening the recorder window. A zero exit code means the startup check passed.
