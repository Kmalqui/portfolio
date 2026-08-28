const autoLookup = document.getElementById("autoLookup");
const showSynonyms = document.getElementById("showSynonyms");
const themeMode = document.getElementById("themeMode");
const dictionaryKey = document.getElementById("dictionaryKey");
const thesaurusKey = document.getElementById("thesaurusKey");
const saveButton = document.getElementById("saveButton");
const testButton = document.getElementById("testButton");
const status = document.getElementById("status");
const shortcutButton = document.getElementById("shortcutButton");
const shortcutText = document.getElementById("shortcutText");

async function load() {
  const settings = await browser.storage.local.get({
    autoLookup: true,
    showSynonyms: true,
    themeMode: "auto",
    dictionaryKey: "",
    thesaurusKey: ""
  });
  autoLookup.checked = settings.autoLookup !== false;
  showSynonyms.checked = settings.showSynonyms !== false;
  themeMode.value = ["auto", "light", "dark"].includes(settings.themeMode) ? settings.themeMode : "auto";
  dictionaryKey.value = settings.dictionaryKey || "";
  thesaurusKey.value = settings.thesaurusKey || "";
  try {
    const commands = await browser.commands.getAll();
    const command = commands.find((item) => item.name === "open-quick-dictionary");
    shortcutText.textContent = command?.shortcut || "Not assigned";
  } catch (_) {}
}

async function save(showMessage = true) {
  await browser.storage.local.set({
    autoLookup: autoLookup.checked,
    showSynonyms: showSynonyms.checked,
    themeMode: themeMode.value,
    dictionaryKey: dictionaryKey.value.trim(),
    thesaurusKey: thesaurusKey.value.trim()
  });
  if (showMessage) {
    status.textContent = "Saved.";
    setTimeout(() => { status.textContent = ""; }, 1800);
  }
}

saveButton.addEventListener("click", () => save(true));

shortcutButton.addEventListener("click", () => browser.commands.openShortcutSettings());

testButton.addEventListener("click", async () => {
  await save(false);
  status.textContent = "Testing…";
  const result = await browser.runtime.sendMessage({ type: "lookup", word: "example" });
  status.textContent = result?.ok && result.entries?.length
    ? "Connected to Merriam-Webster successfully."
    : (result?.error || "The API did not return a definition.");
});

document.querySelectorAll(".reveal").forEach((button) => {
  button.addEventListener("click", () => {
    const input = document.getElementById(button.dataset.target);
    const showing = input.type === "text";
    input.type = showing ? "password" : "text";
    button.textContent = showing ? "Show" : "Hide";
  });
});

load();
