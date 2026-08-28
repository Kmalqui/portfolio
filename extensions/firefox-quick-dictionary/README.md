# Firefox Quick Dictionary

Firefox Quick Dictionary is a Firefox extension that looks up highlighted, right-clicked, or manually entered words through Merriam-Webster's Collegiate Dictionary and Collegiate Thesaurus APIs.

## Features

- Highlight a single word to show a compact definition card beside it.
- Right-click a word and choose **Define with Firefox Quick Dictionary**.
- Search from the toolbar popup.
- Show pronunciations, audio, synonyms, antonyms, and spelling suggestions when available.
- Pin or copy a definition card.
- Press **Alt+Shift+D** to define the selection or open search.
- Choose an automatic page-aware color scheme, light mode, or dark mode.

## Get your Merriam-Webster API keys

The public repository and downloadable XPI ship with **blank API-key fields**. Each user must provide their own keys. Never commit, post, or share an API key.

1. Visit [Merriam-Webster's Developer Center](https://dictionaryapi.com/) and select the option to create a developer account.
2. Complete the account form and verify your account if prompted. If the form asks for your role or occupation, select **Software Developer**.
3. Sign in and request a key for the **Collegiate Dictionary API**. This is the Dictionary API key used for definitions.
4. Request a second, separate key for the **Collegiate Thesaurus API**. This is the Thesaurus API key used for synonyms and antonyms.
5. Open your Merriam-Webster account dashboard and locate the list of registered API keys or products.
6. Identify and safely copy both values: the key listed for the Collegiate Dictionary API and the key listed for the Collegiate Thesaurus API. Keep the dashboard open while you configure Firefox, or store the keys temporarily in a private password manager.

## Add your keys in Firefox

1. Open Firefox and select the menu button.
2. Choose **Add-ons and themes**, then **Extensions**.
3. Find **Firefox Quick Dictionary**, select the three-dot menu, and choose **Manage**.
4. Open **Firefox Quick Dictionary Settings** by selecting the **Options** tab. Firefox may label this tab **Preferences** on some versions.
5. Paste the Collegiate Dictionary API value from your Merriam-Webster dashboard into the **Dictionary key** field.
6. Paste the Collegiate Thesaurus API value into the **Thesaurus key** field.
7. Select **Save settings**. You can then select **Test Merriam-Webster** to confirm the keys work.
8. Refresh any webpages that were already open before using highlighted-word or right-click lookup.

The keys stay in Firefox's local extension storage. Do not add them to source files, ZIP/XPI packages, screenshots, issues, or commits. If you fork this repository, keep all API keys and other secrets out of source control; forks should retain the blank-key defaults.

## Use the Chrome version

A separate [Chrome Quick Dictionary](../chrome-quick-dictionary/) package is included in this repository.

1. Download and extract `chrome-quick-dictionary-v1.3.0.zip`.
2. Open `chrome://extensions` in Chrome and turn on **Developer mode**.
3. Select **Load unpacked**, then choose the extracted `chrome-quick-dictionary` folder.
4. Find **Chrome Quick Dictionary**, select **Details**, and open **Extension options**.
5. Paste your Dictionary and Thesaurus keys into their matching fields, select **Save settings**, and refresh any webpages that were already open.

See the [Chrome README](../chrome-quick-dictionary/README.md) for the complete Chrome installation, API-key, shortcut, privacy, and testing instructions.

## Install for local testing

1. Download and extract the source ZIP, or clone this repository.
2. In Firefox, open `about:debugging` and choose **This Firefox**.
3. Click **Load Temporary Add-on...** and select this folder's `manifest.json`.
4. Open **Firefox Quick Dictionary Settings/Options** and enter your own API keys as described above.
5. Refresh any ordinary webpage that was already open, then highlight a word.

Firefox removes temporary add-ons after restart. A permanent public install would need to be signed through Mozilla Add-ons.

## Settings and privacy

API keys are saved in Firefox's local extension storage. Because a browser extension cannot securely conceal a key it uses directly, each user must supply their own and keep any configured copy private. The extension sends lookup words and the configured key only to the official Merriam-Webster API endpoints.

## Notes

Firefox does not allow extensions to run on protected pages such as `about:addons` or `about:debugging`. Test on a normal `http://` or `https://` webpage. Dictionary and thesaurus content is provided through Merriam-Webster's official APIs, with attribution displayed in the extension.

Version 1.3.0. Plain JavaScript, HTML, and CSS. No build step is required.
