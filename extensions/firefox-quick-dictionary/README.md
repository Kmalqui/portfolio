# Firefox Quick Dictionary

Firefox Quick Dictionary is a Firefox WebExtension that looks up highlighted, right-clicked, or manually entered words through Merriam-Webster's Collegiate Dictionary and Collegiate Thesaurus APIs.

## Features

- Highlight a single word to show a compact definition card beside it.
- Right-click a word and choose **Define with Merriam-Webster**.
- Search from the toolbar popup.
- Show pronunciations, audio, synonyms, antonyms, and spelling suggestions when available.
- Pin or copy a definition card.
- Press **Alt+Shift+D** to define the selection or open search.
- Choose an automatic page-aware color scheme, light mode, or dark mode.

## Requirements

Create your own Merriam-Webster developer keys for the Collegiate Dictionary API and, optionally, the Collegiate Thesaurus API. No API keys or other credentials are included in this repository or ZIP.

## Install for local testing

1. Download and extract the ZIP, or clone this repository.
2. In Firefox, open `about:debugging` and choose **This Firefox**.
3. Click **Load Temporary Add-on...** and select this folder's `manifest.json`.
4. Open the extension's Settings page and enter your own API keys.
5. Refresh any ordinary webpage that was already open, then highlight a word.

Firefox removes temporary add-ons after restart. A permanent public install would need to be signed through Mozilla Add-ons.

## Settings and privacy

API keys are saved in Firefox's local extension storage. Because a browser extension cannot securely conceal a key it uses directly, each user must supply their own and should keep any configured copy private. The extension sends lookup words and the configured key only to the official Merriam-Webster API endpoints.

## Notes

Firefox does not allow extensions to run on protected pages such as `about:addons` or `about:debugging`. Test on a normal `http://` or `https://` webpage. Dictionary and thesaurus content is provided through Merriam-Webster's official APIs, with attribution displayed in the extension.

Version 1.3.0. Plain JavaScript, HTML, and CSS. No build step is required.
