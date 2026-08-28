# Kat's Dictionary

Kat's Dictionary is a Firefox extension that looks up highlighted, right-clicked, or manually entered words through Merriam-Webster's Collegiate Dictionary and Collegiate Thesaurus APIs.

## Features

- Highlight a single word to show a compact definition card beside it.
- Right-click a word and choose **Define with Kat's Dictionary**.
- Search from the toolbar popup.
- Show pronunciations, audio, synonyms, antonyms, and spelling suggestions when available.
- Pin or copy a definition card.
- Press **Alt+Shift+D** to define the selection or open search.
- Choose an automatic page-aware color scheme, light mode, or dark mode.

## Get your Merriam-Webster API keys

This public repository and its downloads contain **no API keys or other credentials**. Each user needs their own keys. Never commit, post, or share your keys.

1. Visit [Merriam-Webster's Developer Center](https://dictionaryapi.com/) and create a free developer account.
2. Request a key for the **Collegiate Dictionary API**.
3. Request a separate key for the **Collegiate Thesaurus API**.
4. Keep both keys private.

## Add your keys in Firefox

1. Open Firefox and select the menu button.
2. Choose **Add-ons and themes**, then **Extensions**.
3. Find **Kat's Dictionary**, select the three-dot menu, and choose **Manage**.
4. Open the **Options** tab (shown as **Preferences** on some Firefox versions).
5. Paste the Dictionary API key into **Dictionary API key**.
6. Paste the Thesaurus API key into **Thesaurus API key**.
7. Select **Save settings**, then **Test Merriam-Webster**.
8. Refresh webpages that were already open before using highlight lookup.

The keys stay in Firefox's local extension storage. Do not add them to source files, ZIP/XPI packages, screenshots, issues, or commits.

## Install for local testing

1. Download and extract the source ZIP, or clone this repository.
2. In Firefox, open `about:debugging` and choose **This Firefox**.
3. Click **Load Temporary Add-on...** and select this folder's `manifest.json`.
4. Open the extension's Options page and enter your own API keys as described above.
5. Refresh any ordinary webpage that was already open, then highlight a word.

Firefox removes temporary add-ons after restart. A permanent public install would need to be signed through Mozilla Add-ons.

## Settings and privacy

API keys are saved in Firefox's local extension storage. Because a browser extension cannot securely conceal a key it uses directly, each user must supply their own and keep any configured copy private. The extension sends lookup words and the configured key only to the official Merriam-Webster API endpoints.

## Notes

Firefox does not allow extensions to run on protected pages such as `about:addons` or `about:debugging`. Test on a normal `http://` or `https://` webpage. Dictionary and thesaurus content is provided through Merriam-Webster's official APIs, with attribution displayed in the extension.

Version 1.3.0. Plain JavaScript, HTML, and CSS. No build step is required.
