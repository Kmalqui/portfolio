const DEFAULT_SETTINGS = {
  dictionaryKey: "",
  thesaurusKey: "",
  autoLookup: true,
  showSynonyms: true,
  themeMode: "auto"
};

async function seedDefaults() {
  const current = await browser.storage.local.get(Object.keys(DEFAULT_SETTINGS));
  const missing = {};
  for (const [key, value] of Object.entries(DEFAULT_SETTINGS)) {
    if (current[key] === undefined || current[key] === null || current[key] === "") {
      missing[key] = value;
    }
  }
  if (Object.keys(missing).length) {
    await browser.storage.local.set(missing);
  }
}

function ensureContextMenu() {
  try {
    browser.menus.create({
      id: "mw-define-word",
      title: "Define with Merriam-Webster",
      contexts: ["page", "selection"]
    }, () => {
      // Ignore duplicate-ID errors when Firefox restores a persisted menu.
      void browser.runtime.lastError;
    });
  } catch (_) {}
}

browser.runtime.onInstalled.addListener(async () => {
  await seedDefaults();
  ensureContextMenu();
});

browser.runtime.onStartup.addListener(async () => {
  await seedDefaults();
  ensureContextMenu();
});

// Also seed during temporary/debug loads, where onInstalled behavior can vary.
seedDefaults().catch(console.error);
// Firefox may not fire onInstalled the same way for temporary/debug loads.
// Register once at background startup as well. Duplicate-ID errors are harmless.
ensureContextMenu();

browser.menus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "mw-define-word" || !tab?.id) return;

  await sendPanelMessage(tab.id, {
    type: "openContextPanel",
    selectionText: info.selectionText || ""
  });
});

browser.runtime.onMessage.addListener((message) => {
  if (!message || message.type !== "lookup") return undefined;
  return lookupWord(message.word);
});

function normalizeWord(value) {
  return String(value || "")
    .trim()
    .replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, "")
    .slice(0, 80);
}

function cleanMarkup(text) {
  if (!text) return "";
  return String(text)
    .replace(/\{bc\}/g, ": ")
    .replace(/\{ldquo\}|\{rdquo\}/g, '"')
    .replace(/\{lsquo\}|\{rsquo\}/g, "'")
    .replace(/\{it\}|\{\/it\}|\{b\}|\{\/b\}|\{sc\}|\{\/sc\}/g, "")
    .replace(/\{inf\}|\{\/inf\}|\{sup\}|\{\/sup\}/g, "")
    .replace(/\{[^}]+\}/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function unique(items) {
  return [...new Set(items.filter(Boolean))];
}

function makeAudioUrl(audio) {
  if (!audio) return "";
  let subdirectory;
  if (audio.startsWith("bix")) subdirectory = "bix";
  else if (audio.startsWith("gg")) subdirectory = "gg";
  else if (/^[^A-Za-z]/.test(audio)) subdirectory = "number";
  else subdirectory = audio[0].toLowerCase();

  return `https://media.merriam-webster.com/audio/prons/en/us/mp3/${subdirectory}/${audio}.mp3`;
}

function parseDictionary(data) {
  if (!Array.isArray(data) || data.length === 0) {
    return { entries: [], suggestions: [] };
  }

  if (typeof data[0] === "string") {
    return {
      entries: [],
      suggestions: data.filter((item) => typeof item === "string").slice(0, 10)
    };
  }

  const entries = [];
  const seen = new Set();

  for (const item of data) {
    if (!item || typeof item !== "object" || !Array.isArray(item.shortdef)) continue;

    const headword = cleanMarkup(item.hwi?.hw || item.meta?.id || "")
      .replace(/\*/g, "·")
      .replace(/:\d+$/, "");
    const partOfSpeech = cleanMarkup(item.fl || "");
    const pronunciation = cleanMarkup(item.hwi?.prs?.[0]?.mw || "");
    const audioName = item.hwi?.prs?.find((p) => p?.sound?.audio)?.sound?.audio || "";
    const definitions = item.shortdef.map(cleanMarkup).filter(Boolean).slice(0, 4);

    if (!headword || definitions.length === 0) continue;

    const signature = `${headword}|${partOfSpeech}|${definitions[0]}`;
    if (seen.has(signature)) continue;
    seen.add(signature);

    entries.push({
      headword,
      partOfSpeech,
      pronunciation,
      audioUrl: makeAudioUrl(audioName),
      definitions
    });

    if (entries.length >= 4) break;
  }

  return { entries, suggestions: [] };
}

function parseThesaurus(data) {
  if (!Array.isArray(data) || !data.length || typeof data[0] === "string") {
    return { synonyms: [], antonyms: [] };
  }

  const synonyms = [];
  const antonyms = [];

  for (const item of data) {
    const synGroups = item?.meta?.syns || [];
    const antGroups = item?.meta?.ants || [];
    for (const group of synGroups) {
      if (Array.isArray(group)) synonyms.push(...group);
    }
    for (const group of antGroups) {
      if (Array.isArray(group)) antonyms.push(...group);
    }
  }

  return {
    synonyms: unique(synonyms.map(cleanMarkup)).slice(0, 12),
    antonyms: unique(antonyms.map(cleanMarkup)).slice(0, 8)
  };
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Merriam-Webster API returned HTTP ${response.status}`);
  }
  return response.json();
}

async function lookupWord(rawWord) {
  const word = normalizeWord(rawWord);
  if (!word) {
    return { ok: false, error: "Enter a word to look up." };
  }

  const settings = await browser.storage.local.get(DEFAULT_SETTINGS);
  const dictionaryKey = String(settings.dictionaryKey || "").trim();
  const thesaurusKey = String(settings.thesaurusKey || "").trim();

  if (!dictionaryKey) {
    return {
      ok: false,
      error: "Dictionary API key is missing. Open the extension settings and add it."
    };
  }

  try {
    const encoded = encodeURIComponent(word);
    const dictionaryUrl = `https://www.dictionaryapi.com/api/v3/references/collegiate/json/${encoded}?key=${encodeURIComponent(dictionaryKey)}`;

    const dictionaryPromise = fetchJson(dictionaryUrl);
    const thesaurusPromise = settings.showSynonyms && thesaurusKey
      ? fetchJson(`https://www.dictionaryapi.com/api/v3/references/thesaurus/json/${encoded}?key=${encodeURIComponent(thesaurusKey)}`).catch(() => [])
      : Promise.resolve([]);

    const [dictionaryData, thesaurusData] = await Promise.all([
      dictionaryPromise,
      thesaurusPromise
    ]);

    const dictionary = parseDictionary(dictionaryData);
    const thesaurus = parseThesaurus(thesaurusData);

    return {
      ok: true,
      query: word,
      entries: dictionary.entries,
      suggestions: dictionary.suggestions,
      synonyms: thesaurus.synonyms,
      antonyms: thesaurus.antonyms,
      moreUrl: `https://www.merriam-webster.com/dictionary/${encodeURIComponent(word)}`
    };
  } catch (error) {
    console.error(error);
    return {
      ok: false,
      error: "I couldn't reach Merriam-Webster. Check your connection or API key and try again."
    };
  }
}

async function sendPanelMessage(tabId, message) {
  try {
    await browser.tabs.sendMessage(tabId, message);
    return true;
  } catch (_) {}

  try {
    await browser.scripting.executeScript({
      target: { tabId },
      files: ["content.js"]
    });
    await browser.tabs.sendMessage(tabId, message);
    return true;
  } catch (error) {
    console.warn("Quick Dictionary cannot run on this page:", error);
    return false;
  }
}

browser.commands.onCommand.addListener(async (command) => {
  if (command !== "open-quick-dictionary") return;
  try {
    const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) return;
    await sendPanelMessage(tab.id, { type: "openShortcutPanel" });
  } catch (error) {
    console.warn("Quick Dictionary shortcut failed:", error);
  }
});
