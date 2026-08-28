const browser = chrome;

const form = document.getElementById("searchForm");
const input = document.getElementById("searchInput");
const results = document.getElementById("results");
const settingsButton = document.getElementById("settingsButton");
let token = 0;

function fallbackTheme() {
  return window.matchMedia?.("(prefers-color-scheme: dark)")?.matches ? "dark" : "light";
}

async function applyTheme() {
  let mode = "auto";
  try {
    const settings = await browser.storage.local.get({ themeMode: "auto" });
    mode = ["auto", "light", "dark"].includes(settings.themeMode) ? settings.themeMode : "auto";
  } catch (_) {}

  let theme = mode === "auto" ? fallbackTheme() : mode;
  if (mode === "auto") {
    try {
      const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
      if (tab?.id) {
        const response = await browser.tabs.sendMessage(tab.id, { type: "getPageTheme" });
        if (response?.theme === "dark" || response?.theme === "light") theme = response.theme;
      }
    } catch (_) {}
  }

  document.documentElement.dataset.theme = theme;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function formatCopyText(result) {
  if (!result?.ok || !result.entries?.length) return "";
  const lines = [];
  result.entries.forEach((entry, entryIndex) => {
    const head = [entry.headword || result.query, entry.partOfSpeech ? `(${entry.partOfSpeech})` : ""]
      .filter(Boolean)
      .join(" ");
    if (entryIndex > 0) lines.push("");
    lines.push(head);
    (entry.definitions || []).forEach((definition, index) => lines.push(`${index + 1}. ${definition}`));
  });
  if (result.synonyms?.length) lines.push("", `Synonyms: ${result.synonyms.join(", ")}`);
  if (result.antonyms?.length) lines.push(`Antonyms: ${result.antonyms.join(", ")}`);
  lines.push("", `Merriam-Webster: ${result.moreUrl}`);
  return lines.join("\n");
}

async function copyDefinition(button, result) {
  const text = formatCopyText(result);
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    const original = button.textContent;
    button.textContent = "Copied";
    setTimeout(() => { if (button.isConnected) button.textContent = original; }, 1300);
  } catch (_) {
    button.textContent = "Couldn't copy";
    setTimeout(() => { if (button.isConnected) button.textContent = "Copy"; }, 1300);
  }
}

async function lookup(word) {
  const query = String(word || "").trim();
  if (!query) return;
  input.value = query;
  results.replaceChildren(el("p", "muted", `Looking up “${query}”…`));
  const current = ++token;
  const response = await browser.runtime.sendMessage({ type: "lookup", word: query });
  if (current !== token) return;
  render(response);
}

function render(result) {
  results.replaceChildren();

  if (!result?.ok) {
    results.appendChild(el("div", "error", result?.error || "Something went wrong."));
    return;
  }

  if (!result.entries?.length) {
    if (result.suggestions?.length) {
      results.appendChild(el("p", "muted", `No exact entry for “${result.query}”. Did you mean:`));
      const grid = el("div", "suggestions");
      for (const suggestion of result.suggestions) {
        const button = el("button", "suggestion", suggestion);
        button.type = "button";
        button.addEventListener("click", () => lookup(suggestion));
        grid.appendChild(button);
      }
      results.appendChild(grid);
    } else {
      results.appendChild(el("p", "muted", `No Merriam-Webster entry was found for “${result.query}”.`));
    }
    return;
  }

  result.entries.forEach((entry, index) => {
    const section = el("section", "entry");
    if (index === 0) {
      const top = el("div", "result-top");
      const row = el("div", "word-row");
      row.appendChild(el("h2", "", entry.headword || result.query));
      if (entry.pronunciation) row.appendChild(el("span", "pron", `\\${entry.pronunciation}\\`));
      if (entry.audioUrl) {
        const audio = el("button", "audio", "🔊");
        audio.type = "button";
        audio.title = "Play pronunciation";
        audio.addEventListener("click", () => new Audio(entry.audioUrl).play().catch(() => {}));
        row.appendChild(audio);
      }
      const copy = el("button", "copy-button", "Copy");
      copy.type = "button";
      copy.title = "Copy definition";
      copy.addEventListener("click", () => copyDefinition(copy, result));
      top.append(row, copy);
      section.appendChild(top);
    }

    if (entry.partOfSpeech) section.appendChild(el("div", "pos", entry.partOfSpeech));
    const list = document.createElement("ol");
    for (const definition of entry.definitions || []) list.appendChild(el("li", "", definition));
    section.appendChild(list);
    results.appendChild(section);
  });

  if (result.synonyms?.length) {
    results.appendChild(el("div", "section-title", "Synonyms"));
    const chips = el("div", "chips");
    for (const word of result.synonyms) {
      const chip = el("button", "chip", word);
      chip.type = "button";
      chip.addEventListener("click", () => lookup(word));
      chips.appendChild(chip);
    }
    results.appendChild(chips);
  }

  if (result.antonyms?.length) {
    results.appendChild(el("div", "section-title", "Antonyms"));
    const chips = el("div", "chips");
    for (const word of result.antonyms) {
      const chip = el("button", "chip ant", word);
      chip.type = "button";
      chip.addEventListener("click", () => lookup(word));
      chips.appendChild(chip);
    }
    results.appendChild(chips);
  }

  const moreWrap = el("div", "more-wrap");
  const link = el("a", "more", "View full entry on Merriam-Webster →");
  link.href = result.moreUrl;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  moreWrap.appendChild(link);
  results.appendChild(moreWrap);
}

browser.storage.onChanged.addListener((changes, area) => {
  if (area === "local" && changes.themeMode) applyTheme();
});

form.addEventListener("submit", (event) => {
  event.preventDefault();
  lookup(input.value);
});

settingsButton.addEventListener("click", () => browser.runtime.openOptionsPage());

(async () => {
  await applyTheme();
  input.focus();
  try {
    const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) return;
    const selection = await browser.tabs.sendMessage(tab.id, { type: "getSelection" });
    if (selection?.word) lookup(selection.word);
  } catch (_) {}
})();
