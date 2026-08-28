# Chrome Quick Dictionary

Chrome Quick Dictionary looks up highlighted, right-clicked, or manually entered words through Merriam-Webster's Collegiate Dictionary and Collegiate Thesaurus APIs. It is the Chrome version of the Firefox Quick Dictionary project.

## Features

- Highlight a single word to show a compact definition card beside it.
- Right-click a word and choose **Define with Chrome Quick Dictionary**.
- Search from the toolbar popup.
- Show pronunciations, audio, synonyms, antonyms, and spelling suggestions when available.
- Pin or copy a definition card.
- Press **Alt+Shift+D** to define the selection or open search.
- Choose an automatic page-aware color scheme, light mode, or dark mode.

## Get your Merriam-Webster API keys

The public repository and downloadable ZIP ship with **blank API-key fields**. Each user must provide their own keys. Never commit, post, or share an API key.

1. Visit [Merriam-Webster's Developer Center](https://dictionaryapi.com/) and create a developer account.
2. If the account form asks for your role or occupation, select **Software Developer**.
3. Request a key for the **Collegiate Dictionary API**.
4. Request a separate key for the **Collegiate Thesaurus API**.
5. Open your Merriam-Webster account dashboard and locate both registered API keys.
6. Keep the dashboard open while configuring Chrome, or temporarily store the values in a private password manager.

## Install in Chrome

1. Download and extract `chrome-quick-dictionary-v1.3.0.zip`, or clone this repository.
2. In Chrome, open `chrome://extensions`.
3. Turn on **Developer mode** in the upper-right corner.
4. Select **Load unpacked**.
5. Choose the extracted `chrome-quick-dictionary` folder. Select the folder itself, not an individual file inside it.
6. Find **Chrome Quick Dictionary** on the Extensions page and optionally pin it from Chrome's Extensions menu.

Chrome may show a reminder that Developer mode extensions are installed. A permanent public Chrome Web Store installation would require publishing the extension through the Chrome Web Store.

## Add your keys in Chrome

1. Open `chrome://extensions` and find **Chrome Quick Dictionary**.
2. Select **Details**, then select **Extension options**.
3. Paste the Collegiate Dictionary API value into the **Dictionary key** field.
4. Paste the Collegiate Thesaurus API value into the **Thesaurus key** field.
5. Select **Save settings**, then select **Test Merriam-Webster** to confirm the keys work.
6. Refresh any webpages that were already open before using highlighted-word or right-click lookup.

The keys stay in Chrome's local extension storage. Do not add them to source files, ZIP packages, screenshots, issues, or commits. If you fork this repository, keep all API keys and other secrets out of source control; forks should retain the blank-key defaults.

## Keyboard shortcut

Open `chrome://extensions/shortcuts` to view or change the **Alt+Shift+D** shortcut.

## Settings and privacy

Because a browser extension cannot securely conceal a key it uses directly, each user must supply their own and keep configured copies private. The extension sends lookup words and the configured key only to the official Merriam-Webster API endpoints.

## Notes

Chrome does not allow extensions to run on protected browser pages such as `chrome://extensions`. Test on a normal `http://` or `https://` webpage. Dictionary and thesaurus content is provided through Merriam-Webster's official APIs, with attribution displayed in the extension.

Version 1.3.0. Chrome Manifest V3. Plain JavaScript, HTML, and CSS. No build step is required.
