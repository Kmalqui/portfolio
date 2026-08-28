const browser = chrome;

(() => {
  if (window.__MW_QUICK_DICTIONARY_LOADED__) return;
  window.__MW_QUICK_DICTIONARY_LOADED__ = true;

  const HOST_ID = "__mw_quick_dictionary_host__";
  const PANEL_WIDTH = 360;
  let panelHost = null;
  let panelPinned = false;
  let lastContextWord = "";
  let lastContextPoint = { x: 24, y: 24 };
  let autoLookupEnabled = true;
  let themeMode = "auto";
  let lastPanelPoint = { x: 24, y: 24 };
  let lookupToken = 0;

  browser.storage.local.get({ autoLookup: true, themeMode: "auto" }).then((settings) => {
    autoLookupEnabled = settings.autoLookup !== false;
    themeMode = ["auto", "light", "dark"].includes(settings.themeMode) ? settings.themeMode : "auto";
  }).catch(() => {});

  browser.storage.onChanged.addListener((changes, area) => {
    if (area !== "local") return;
    if (changes.autoLookup) {
      autoLookupEnabled = changes.autoLookup.newValue !== false;
    }
    if (changes.themeMode) {
      themeMode = ["auto", "light", "dark"].includes(changes.themeMode.newValue)
        ? changes.themeMode.newValue
        : "auto";
      const panel = panelHost?.shadowRoot?.querySelector(".panel");
      if (panel) panel.dataset.theme = resolveTheme(lastPanelPoint);
    }
  });

  function cleanCandidate(value) {
    return String(value || "")
      .trim()
      .replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, "")
      .slice(0, 80);
  }

  function isSingleWord(value) {
    const word = cleanCandidate(value);
    return Boolean(word) && /^[\p{L}\p{N}][\p{L}\p{M}\p{N}'’\-]*$/u.test(word);
  }

  function getSelectedWord() {
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed) return "";
    const text = selection.toString();
    return isSingleWord(text) ? cleanCandidate(text) : "";
  }

  function getSelectionRect() {
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed || selection.rangeCount === 0) return null;
    const rect = selection.getRangeAt(0).getBoundingClientRect();
    if (!rect || (!rect.width && !rect.height)) return null;
    return rect;
  }

  function isWordChar(char) {
    return Boolean(char) && /[\p{L}\p{M}\p{N}'’\-]/u.test(char);
  }

  function getWordAtPoint(x, y) {
    let node = null;
    let offset = 0;

    try {
      if (document.caretPositionFromPoint) {
        const position = document.caretPositionFromPoint(x, y);
        if (position) {
          node = position.offsetNode;
          offset = position.offset;
        }
      } else if (document.caretRangeFromPoint) {
        const range = document.caretRangeFromPoint(x, y);
        if (range) {
          node = range.startContainer;
          offset = range.startOffset;
        }
      }
    } catch (_) {}

    if (!node || node.nodeType !== Node.TEXT_NODE) return "";
    const text = node.textContent || "";
    if (!text) return "";

    let cursor = Math.min(Math.max(offset, 0), text.length - 1);
    if (!isWordChar(text[cursor]) && cursor > 0 && isWordChar(text[cursor - 1])) cursor -= 1;
    if (!isWordChar(text[cursor])) return "";

    let start = cursor;
    let end = cursor + 1;
    while (start > 0 && isWordChar(text[start - 1])) start -= 1;
    while (end < text.length && isWordChar(text[end])) end += 1;
    return cleanCandidate(text.slice(start, end));
  }


  function parseColor(value) {
    const match = String(value || "").match(/rgba?\(\s*(\d+(?:\.\d+)?)\s*[, ]\s*(\d+(?:\.\d+)?)\s*[, ]\s*(\d+(?:\.\d+)?)(?:\s*[,/]\s*(\d*\.?\d+))?\s*\)/i);
    if (!match) return null;
    return {
      r: Math.min(255, Number(match[1])),
      g: Math.min(255, Number(match[2])),
      b: Math.min(255, Number(match[3])),
      a: match[4] === undefined ? 1 : Number(match[4])
    };
  }

  function relativeLuminance({ r, g, b }) {
    const channels = [r, g, b].map((value) => {
      const normalized = value / 255;
      return normalized <= 0.04045
        ? normalized / 12.92
        : Math.pow((normalized + 0.055) / 1.055, 2.4);
    });
    return (0.2126 * channels[0]) + (0.7152 * channels[1]) + (0.0722 * channels[2]);
  }

  function detectedPageTheme(point = { x: window.innerWidth / 2, y: window.innerHeight / 2 }) {
    const x = Math.min(Math.max(Number(point?.x) || window.innerWidth / 2, 0), Math.max(0, window.innerWidth - 1));
    const y = Math.min(Math.max(Number(point?.y) || window.innerHeight / 2, 0), Math.max(0, window.innerHeight - 1));

    let element = null;
    try { element = document.elementFromPoint(x, y); } catch (_) {}

    const seen = new Set();
    const candidates = [];
    for (let current = element; current && current.nodeType === Node.ELEMENT_NODE; current = current.parentElement) {
      if (!seen.has(current)) {
        seen.add(current);
        candidates.push(current);
      }
    }
    for (const fallback of [document.body, document.documentElement]) {
      if (fallback && !seen.has(fallback)) {
        seen.add(fallback);
        candidates.push(fallback);
      }
    }

    for (const candidate of candidates) {
      try {
        const style = getComputedStyle(candidate);
        const color = parseColor(style.backgroundColor);
        if (color && color.a >= 0.35) {
          return relativeLuminance(color) < 0.32 ? "dark" : "light";
        }
      } catch (_) {}
    }

    try {
      const scheme = getComputedStyle(document.documentElement).colorScheme || "";
      if (/^dark(?:\s|$)/i.test(scheme)) return "dark";
      if (/^light(?:\s|$)/i.test(scheme)) return "light";
    } catch (_) {}

    return window.matchMedia?.("(prefers-color-scheme: dark)")?.matches ? "dark" : "light";
  }

  function resolveTheme(point) {
    if (themeMode === "light" || themeMode === "dark") return themeMode;
    return detectedPageTheme(point);
  }

  function removePanel() {
    if (panelHost) panelHost.remove();
    panelHost = null;
    panelPinned = false;
  }

  function createElement(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
  }

  function positionPanel(host, point) {
    const margin = 12;
    const maxX = Math.max(margin, window.innerWidth - PANEL_WIDTH - margin);
    const x = Math.min(Math.max(point.x, margin), maxX);
    const estimatedHeight = Math.min(470, window.innerHeight - 24);
    const belowY = point.y + 10;
    const y = belowY + estimatedHeight <= window.innerHeight
      ? belowY
      : Math.max(margin, point.y - estimatedHeight - 10);

    host.style.left = `${x}px`;
    host.style.top = `${y}px`;
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
      (entry.definitions || []).forEach((definition, index) => {
        lines.push(`${index + 1}. ${definition}`);
      });
    });
    if (result.synonyms?.length) lines.push("", `Synonyms: ${result.synonyms.join(", ")}`);
    if (result.antonyms?.length) lines.push(`Antonyms: ${result.antonyms.join(", ")}`);
    lines.push("", `Merriam-Webster: ${result.moreUrl}`);
    return lines.join("\n");
  }

  async function copyText(text) {
    if (!text) return false;
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
        return true;
      }
    } catch (_) {}

    try {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.setAttribute("readonly", "");
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      textarea.style.pointerEvents = "none";
      document.documentElement.appendChild(textarea);
      textarea.select();
      const ok = document.execCommand("copy");
      textarea.remove();
      return ok;
    } catch (_) {
      return false;
    }
  }

  function buildPanel(point, initialWord = "", focusSearch = false) {
    removePanel();
    lastPanelPoint = { x: Number(point?.x) || 24, y: Number(point?.y) || 24 };

    const host = document.createElement("div");
    host.id = HOST_ID;
    host.style.all = "initial";
    host.style.position = "fixed";
    host.style.zIndex = "2147483647";
    host.style.width = `${PANEL_WIDTH}px`;
    host.style.maxWidth = "calc(100vw - 24px)";
    host.style.fontFamily = "Inter, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
    document.documentElement.appendChild(host);
    panelHost = host;

    const shadow = host.attachShadow({ mode: "open" });
    const style = document.createElement("style");
    style.textContent = `
      :host { all: initial; }
      * { box-sizing: border-box; }
      .panel {
        width: ${PANEL_WIDTH}px; max-width: calc(100vw - 24px);
        max-height: min(560px, calc(100vh - 24px)); overflow: hidden;
        border: 1px solid rgba(15, 23, 42, .14); border-radius: 14px;
        background: #fff; color: #172033;
        box-shadow: 0 16px 46px rgba(0,0,0,.22), 0 2px 10px rgba(0,0,0,.09);
        font: 13px/1.42 Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }
      .header { display:flex; align-items:center; gap:8px; padding:9px 10px; border-bottom:1px solid #e8ebef; }
      .logo { width:34px; height:34px; flex:0 0 34px; }
      .brand { min-width:0; flex:1; }
      .brand-title { font-size:12px; line-height:1.2; font-weight:750; color:#004990; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
      .brand-sub { margin-top:1px; font-size:9.5px; color:#667085; }
      .header-actions { display:flex; align-items:center; gap:4px; }
      .tool {
        height:28px; border:1px solid #dde2e8; border-radius:8px; padding:0 8px;
        background:#fff; color:#475467; font:650 11px/1 inherit; cursor:pointer;
      }
      .tool:hover { background:#f5f7f9; color:#1f2937; }
      .tool.active { border-color:#97bde0; background:#edf6fd; color:#004990; }
      .close { width:28px; padding:0; font-size:20px; font-weight:400; line-height:26px; }
      .search { display:flex; gap:6px; padding:8px 10px; border-bottom:1px solid #eef0f3; }
      .input {
        flex:1; min-width:0; height:34px; border:1px solid #cbd2da; border-radius:9px;
        padding:0 10px; background:#fff; color:#111827; font:inherit; outline:none;
      }
      .input:focus { border-color:#004990; box-shadow:0 0 0 2px rgba(0,73,144,.11); }
      .button { height:34px; border:0; border-radius:9px; padding:0 11px; background:#004990; color:#fff; font:650 12px/1 inherit; cursor:pointer; }
      .body { padding:10px; max-height:430px; overflow:auto; }
      .status { padding:10px 1px; color:#667085; }
      .result-top { display:flex; align-items:flex-start; gap:7px; margin-bottom:7px; }
      .word-block { min-width:0; flex:1; }
      .word-line { display:flex; align-items:center; flex-wrap:wrap; gap:6px; }
      .word { margin:0; font-family:Georgia, 'Times New Roman', serif; font-size:23px; line-height:1.12; color:#101828; }
      .pron { font-size:11.5px; color:#667085; }
      .audio { width:27px; height:27px; border:1px solid #d9dee5; border-radius:50%; background:#fff; color:#004990; cursor:pointer; font-size:13px; }
      .copy { flex:0 0 auto; }
      .entry + .entry { margin-top:11px; padding-top:10px; border-top:1px solid #eef0f3; }
      .pos { margin-bottom:4px; font-size:11px; font-weight:750; font-style:italic; color:#d71920; }
      ol { margin:0; padding-left:20px; }
      li { margin:3px 0; color:#27364b; }
      .section-title { margin:11px 0 6px; font-size:10px; font-weight:800; text-transform:uppercase; letter-spacing:.05em; color:#667085; }
      .chips { display:flex; flex-wrap:wrap; gap:5px; }
      .chip { border:1px solid #d7dee6; border-radius:999px; padding:3px 7px; background:#f8fafc; color:#004990; font:650 11px/1.3 inherit; cursor:pointer; }
      .chip:hover { background:#eef5fb; }
      .ant { color:#9f1239; }
      .empty { color:#667085; padding:7px 0; }
      .suggestions { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:5px; }
      .suggestion { text-align:left; border:1px solid #d9dee5; background:#fff; border-radius:8px; padding:6px 8px; color:#004990; cursor:pointer; font:650 11px/1.3 inherit; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
      .footer { margin-top:11px; padding-top:8px; border-top:1px solid #eef0f3; }
      .more { color:#004990; text-decoration:none; font-weight:700; font-size:11px; }
      .more:hover { text-decoration:underline; }
      .error { color:#9f1239; background:#fff1f2; border:1px solid #fecdd3; border-radius:9px; padding:9px; }
      .panel[data-theme="dark"] { background:#15191f; color:#f4f6f8; border-color:#343b45; box-shadow:0 18px 55px rgba(0,0,0,.5); color-scheme:dark; }
      .panel[data-theme="dark"] .header,.panel[data-theme="dark"] .search,.panel[data-theme="dark"] .entry + .entry,.panel[data-theme="dark"] .footer { border-color:#2c333d; }
      .panel[data-theme="dark"] .brand-title { color:#6fb2ee; }
      .panel[data-theme="dark"] .brand-sub,.panel[data-theme="dark"] .status,.panel[data-theme="dark"] .pron,.panel[data-theme="dark"] .section-title,.panel[data-theme="dark"] .empty { color:#a8b1bd; }
      .panel[data-theme="dark"] .tool,.panel[data-theme="dark"] .audio { background:#20262d; border-color:#414b57; color:#c8d1db; }
      .panel[data-theme="dark"] .tool:hover { background:#27303a; color:#fff; }
      .panel[data-theme="dark"] .tool.active { background:#18344c; border-color:#365d7d; color:#8fc4f2; }
      .panel[data-theme="dark"] .input { background:#20262d; color:#f8fafc; border-color:#4a5562; }
      .panel[data-theme="dark"] .word { color:#f8fafc; }
      .panel[data-theme="dark"] li { color:#dde3ea; }
      .panel[data-theme="dark"] .chip,.panel[data-theme="dark"] .suggestion { background:#20262d; border-color:#414b57; color:#8fc4f2; }
      .panel[data-theme="dark"] .chip:hover { background:#27333f; }
      .panel[data-theme="dark"] .more { color:#8fc4f2; }
      .panel[data-theme="dark"] .error { color:#fecdd3; background:#3a1820; border-color:#6b2636; }
    `;
    shadow.appendChild(style);

    const panel = createElement("div", "panel");
    panel.dataset.theme = resolveTheme(lastPanelPoint);
    const header = createElement("div", "header");
    const logo = document.createElement("img");
    logo.className = "logo";
    logo.src = "https://dictionaryapi.com/images/info/branding-guidelines/MWLogo_LightBG_120x120_2x.png";
    logo.alt = "Merriam-Webster";

    const brand = createElement("div", "brand");
    brand.appendChild(createElement("div", "brand-title", "Merriam-Webster's Collegiate® Dictionary"));
    brand.appendChild(createElement("div", "brand-sub", "Definitions powered by Merriam-Webster Inc."));

    const headerActions = createElement("div", "header-actions");
    const pin = createElement("button", "tool", "Pin");
    pin.type = "button";
    pin.title = "Keep this definition open";
    pin.addEventListener("click", () => {
      panelPinned = !panelPinned;
      pin.classList.toggle("active", panelPinned);
      pin.textContent = panelPinned ? "Pinned" : "Pin";
      pin.title = panelPinned ? "Unpin this definition" : "Keep this definition open";
    });

    const close = createElement("button", "tool close", "×");
    close.type = "button";
    close.title = "Close";
    close.addEventListener("click", removePanel);
    headerActions.append(pin, close);
    header.append(logo, brand, headerActions);

    const form = createElement("form", "search");
    const input = createElement("input", "input");
    input.type = "text";
    input.placeholder = "Search for a word…";
    input.autocomplete = "off";
    input.spellcheck = false;
    input.value = initialWord;
    const button = createElement("button", "button", "Define");
    button.type = "submit";
    form.append(input, button);

    const body = createElement("div", "body");
    body.appendChild(createElement("div", "status", initialWord ? "Looking up…" : "Type a word above to search Merriam-Webster."));

    panel.append(header, form, body);
    shadow.appendChild(panel);
    positionPanel(host, point);

    async function doLookup(word) {
      const query = cleanCandidate(word);
      if (!query) {
        body.replaceChildren(createElement("div", "status", "Type a word above to search Merriam-Webster."));
        input.focus();
        return;
      }

      input.value = query;
      body.replaceChildren(createElement("div", "status", `Looking up “${query}”…`));
      const myToken = ++lookupToken;

      let result;
      try {
        result = await browser.runtime.sendMessage({ type: "lookup", word: query });
      } catch (_) {
        result = { ok: false, error: "The dictionary lookup couldn't start on this page." };
      }
      if (myToken !== lookupToken || !panelHost) return;
      renderResult(body, result, doLookup);
      requestAnimationFrame(() => positionPanel(host, point));
    }

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      doLookup(input.value);
    });

    if (initialWord) doLookup(initialWord);
    if (focusSearch || !initialWord) setTimeout(() => { input.focus(); input.select(); }, 0);

    return { doLookup };
  }

  function renderResult(container, result, onWordClick) {
    container.replaceChildren();

    if (!result?.ok) {
      container.appendChild(createElement("div", "error", result?.error || "Something went wrong."));
      return;
    }

    if (!result.entries?.length) {
      if (result.suggestions?.length) {
        container.appendChild(createElement("div", "empty", `No exact entry for “${result.query}”. Did you mean:`));
        const grid = createElement("div", "suggestions");
        for (const suggestion of result.suggestions) {
          const btn = createElement("button", "suggestion", suggestion);
          btn.type = "button";
          btn.addEventListener("click", () => onWordClick(suggestion));
          grid.appendChild(btn);
        }
        container.appendChild(grid);
      } else {
        container.appendChild(createElement("div", "empty", `No Merriam-Webster entry was found for “${result.query}”.`));
      }
      return;
    }

    const copyPayload = formatCopyText(result);

    result.entries.forEach((entry, index) => {
      const wrapper = createElement("section", "entry");
      if (index === 0) {
        const resultTop = createElement("div", "result-top");
        const wordBlock = createElement("div", "word-block");
        const wordLine = createElement("div", "word-line");
        wordLine.appendChild(createElement("h2", "word", entry.headword || result.query));
        if (entry.pronunciation) wordLine.appendChild(createElement("span", "pron", `\\${entry.pronunciation}\\`));
        if (entry.audioUrl) {
          const audio = createElement("button", "audio", "🔊");
          audio.type = "button";
          audio.title = "Play pronunciation";
          audio.addEventListener("click", () => new Audio(entry.audioUrl).play().catch(() => {}));
          wordLine.appendChild(audio);
        }
        wordBlock.appendChild(wordLine);

        const copy = createElement("button", "tool copy", "Copy");
        copy.type = "button";
        copy.title = "Copy definition";
        copy.addEventListener("click", async () => {
          const ok = await copyText(copyPayload);
          const original = copy.textContent;
          copy.textContent = ok ? "Copied" : "Couldn't copy";
          setTimeout(() => { if (copy.isConnected) copy.textContent = original; }, 1300);
        });
        resultTop.append(wordBlock, copy);
        wrapper.appendChild(resultTop);
      }

      if (entry.partOfSpeech) wrapper.appendChild(createElement("div", "pos", entry.partOfSpeech));
      const list = document.createElement("ol");
      for (const definition of entry.definitions || []) list.appendChild(createElement("li", "", definition));
      wrapper.appendChild(list);
      container.appendChild(wrapper);
    });

    if (result.synonyms?.length) {
      container.appendChild(createElement("div", "section-title", "Synonyms"));
      const chips = createElement("div", "chips");
      for (const word of result.synonyms) {
        const chip = createElement("button", "chip", word);
        chip.type = "button";
        chip.addEventListener("click", () => onWordClick(word));
        chips.appendChild(chip);
      }
      container.appendChild(chips);
    }

    if (result.antonyms?.length) {
      container.appendChild(createElement("div", "section-title", "Antonyms"));
      const chips = createElement("div", "chips");
      for (const word of result.antonyms) {
        const chip = createElement("button", "chip ant", word);
        chip.type = "button";
        chip.addEventListener("click", () => onWordClick(word));
        chips.appendChild(chip);
      }
      container.appendChild(chips);
    }

    const footer = createElement("div", "footer");
    const more = createElement("a", "more", "View full entry on Merriam-Webster →");
    more.href = result.moreUrl;
    more.target = "_blank";
    more.rel = "noopener noreferrer";
    footer.appendChild(more);
    container.appendChild(footer);
  }

  document.addEventListener("contextmenu", (event) => {
    lastContextPoint = { x: event.clientX, y: event.clientY };
    lastContextWord = getSelectedWord() || getWordAtPoint(event.clientX, event.clientY);
  }, true);

  document.addEventListener("mouseup", (event) => {
    if (event.button !== 0 || !autoLookupEnabled || panelPinned) return;
    if (panelHost && (event.target === panelHost || panelHost.contains(event.target))) return;

    setTimeout(() => {
      const word = getSelectedWord();
      const rect = getSelectionRect();
      if (!word || !rect || panelPinned) return;
      buildPanel({
        x: Math.min(rect.left, window.innerWidth - 24),
        y: Math.min(rect.bottom, window.innerHeight - 24)
      }, word);
    }, 40);
  }, true);

  document.addEventListener("mousedown", (event) => {
    if (!panelHost || panelPinned) return;
    if (event.target === panelHost || panelHost.contains(event.target)) return;
    removePanel();
  }, true);

  window.addEventListener("scroll", () => { if (!panelPinned) removePanel(); }, { passive: true });
  window.addEventListener("resize", () => { if (!panelPinned) removePanel(); }, { passive: true });

  browser.runtime.onMessage.addListener((message) => {
    if (!message) return undefined;

    if (message.type === "openContextPanel") {
      const selectionWord = isSingleWord(message.selectionText) ? cleanCandidate(message.selectionText) : "";
      const word = selectionWord || lastContextWord;
      buildPanel(lastContextPoint, word, !word);
      return Promise.resolve({ ok: true, word });
    }

    if (message.type === "openShortcutPanel") {
      const word = getSelectedWord();
      const rect = getSelectionRect();
      const point = rect
        ? { x: Math.min(rect.left, window.innerWidth - 24), y: Math.min(rect.bottom, window.innerHeight - 24) }
        : { x: Math.max(12, Math.round((window.innerWidth - PANEL_WIDTH) / 2)), y: 72 };
      buildPanel(point, word, !word);
      return Promise.resolve({ ok: true, word });
    }

    if (message.type === "getSelection") {
      return Promise.resolve({ word: getSelectedWord() });
    }

    if (message.type === "getPageTheme") {
      const rect = getSelectionRect();
      const point = rect
        ? { x: rect.left + (rect.width / 2), y: rect.top + (rect.height / 2) }
        : { x: window.innerWidth / 2, y: window.innerHeight / 2 };
      return Promise.resolve({ theme: resolveTheme(point) });
    }

    return undefined;
  });
})();
