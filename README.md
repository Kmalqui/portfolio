# Katrina Malqui Portfolio

Practical desktop tools and reusable browser-extension templates for making repetitive work easier.

## Featured project — MeetingScribe

MeetingScribe records meetings with participant permission, creates a live transcript, and turns it into private local notes. It supports Windows and Mac, pause and cancellation, optional screen recording, speaker labels, and voice cleanup without a monthly subscription.

### Download

- [Windows installer](https://github.com/Kmalqui/portfolio/releases/download/meetingscribe-v0.4.1-beta/MeetingScribe-0.4.1-beta-One-Click-Windows-Setup.exe)
- [Mac — Apple Silicon](https://github.com/Kmalqui/portfolio/releases/download/meetingscribe-v0.4.1-beta/MeetingScribe-0.4.1-beta-macOS-Apple-Silicon.dmg)
- [Mac — Intel](https://github.com/Kmalqui/portfolio/releases/download/meetingscribe-v0.4.1-beta/MeetingScribe-0.4.1-beta-macOS-Intel.dmg)

[Setup, documentation, and source](tools/meetingscribe/) · [Open the latest release](https://github.com/Kmalqui/portfolio/releases/tag/meetingscribe-v0.4.1-beta)

The Mac download includes the official Ollama app. Its installer keeps any existing Ollama installation instead of replacing it. AI models are downloaded separately, and BlackHole remains a separate official install because it is a macOS system audio driver with separate licensing and setup requirements.

## Browser-extension library

These configurable templates are intended for sites and workflows you are authorized to automate. Review their host permissions, selectors, routes, field identifiers, and example values before use.

<details>
<summary><strong>Show the extension catalog</strong></summary>

| Template | What it demonstrates | Source | Download |
|---|---|---|---|
| Bulk Checkbox Enabler - Basic | Page through records and enable configured options | [Source](extensions/bulk-checkbox-enabler-basic/) | [ZIP](downloads/bulk-checkbox-enabler-basic.zip) |
| Bulk Checkbox Enabler - Pro | Resume, change-only saves, and CSV export | [Source](extensions/bulk-checkbox-enabler-pro/) | [ZIP](downloads/bulk-checkbox-enabler-pro.zip) |
| Bulk Contact Field Updater | Replace contact values or fill the first empty slot | [Source](extensions/bulk-contact-field-updater/) | [ZIP](downloads/bulk-contact-field-updater.zip) |
| Bulk Contact Replacer | Replace one configured contact with another across records | [Source](extensions/bulk-contact-replacer/) | [ZIP](downloads/bulk-contact-replacer.zip) |
| Bulk Email Field Cleaner | Clear a configured email field and log results | [Source](extensions/bulk-email-field-cleaner/) | [ZIP](downloads/bulk-email-field-cleaner.zip) |
| Bulk Related Contact Cleaner | Clear a related-contact field and disable a paired option | [Source](extensions/bulk-related-contact-cleaner/) | [ZIP](downloads/bulk-related-contact-cleaner.zip) |
| Firefox Quick Dictionary | Highlight, context-menu, and toolbar definitions with adaptive themes | [Source](extensions/firefox-quick-dictionary/) | [Firefox XPI](downloads/kats-dictionary.xpi) · [Source ZIP](downloads/firefox-quick-dictionary-v1.3.0.zip) |
| Chrome Quick Dictionary | Highlight, context-menu, and toolbar definitions with adaptive themes | [Source](extensions/chrome-quick-dictionary/) | [ZIP](downloads/chrome-quick-dictionary-v1.3.0.zip) |

</details>

<details>
<summary><strong>Browser-extension installation</strong></summary>

1. Download and extract the extension ZIP, or clone the repository.
2. Read that extension's README and configure its placeholder host, selectors, and values.
3. For Chrome, open `chrome://extensions`, enable Developer mode, and choose **Load unpacked**.
4. For Firefox Quick Dictionary, follow its Firefox-specific README.

</details>

## Safety and provenance

Test automation in a non-production environment first. The templates contain no intended production configuration or real sample data, but they can modify webpage data. MeetingScribe has its own MIT license in `tools/meetingscribe/LICENSE.txt`; no repository-wide license has been selected.

Last updated: 2026-10-09.
