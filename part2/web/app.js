const exampleSelect = document.querySelector("#exampleSelect");
const themeToggle = document.querySelector("#themeToggle");
const requestForm = document.querySelector("#requestForm");
const urlInput = document.querySelector("#urlInput");
const focusInput = document.querySelector("#focusInput");
const maxWordsInput = document.querySelector("#maxWordsInput");
const processButton = document.querySelector("#processButton");
const errorMessage = document.querySelector("#errorMessage");

const pageTitle = document.querySelector("#pageTitle");
const summaryCount = document.querySelector("#summaryCount");
const sourceLink = document.querySelector("#sourceLink");
const summaryPoints = document.querySelector("#summaryPoints");
const statusTitle = document.querySelector("#statusTitle");
const statusBadge = document.querySelector("#statusBadge");
const httpValue = document.querySelector("#httpValue");
const downloadValue = document.querySelector("#downloadValue");
const cleanValue = document.querySelector("#cleanValue");
const chunkValue = document.querySelector("#chunkValue");
const guardrailValue = document.querySelector("#guardrailValue");
const providerValue = document.querySelector("#providerValue");
const providerNote = document.querySelector("#providerNote");
const chunksList = document.querySelector("#chunksList");
const componentsList = document.querySelector("#componentsList");

let examples = [];

function currentTheme() {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

function updateThemeToggle() {
  const nextTheme = currentTheme() === "dark" ? "light" : "dark";
  const label = `Switch to ${nextTheme} theme`;
  themeToggle.setAttribute("aria-label", label);
  themeToggle.title = label;
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem("web-summary-theme", theme);
  updateThemeToggle();
}

async function loadExamples() {
  const response = await fetch("/api/examples");
  const data = await response.json();
  examples = data.examples || [];

  examples.forEach((example, index) => {
    const option = document.createElement("option");
    option.value = String(index);
    option.textContent = `${example.case_id} - ${new URL(example.url).hostname}`;
    exampleSelect.appendChild(option);
  });
}

function applyExample(index) {
  const example = examples[index];
  if (!example) return;

  urlInput.value = example.url || "";
  focusInput.value = example.focus || "";
  maxWordsInput.value = example.max_summary_words ?? 120;
}

function getPayload() {
  return {
    case_id: "WEB-UI-001",
    url: urlInput.value.trim(),
    focus: focusInput.value.trim(),
    max_summary_words: Number.parseInt(maxWordsInput.value || "120", 10)
  };
}

async function processUrl(event) {
  event.preventDefault();
  errorMessage.textContent = "";
  setLoading(true);

  try {
    const response = await fetch("/api/process", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(getPayload())
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Processing failed");
    renderResult(data.result);
  } catch (error) {
    renderError(error.message);
  } finally {
    setLoading(false);
  }
}

function setLoading(isLoading) {
  processButton.disabled = isLoading;
  processButton.textContent = isLoading ? "Processing..." : "Scrape & summarize";
  if (isLoading) {
    statusTitle.textContent = "Processing";
    statusBadge.textContent = "working";
    statusBadge.className = "badge warn";
  }
}

function renderResult(result) {
  pageTitle.textContent = result.cleaning.title || "Untitled webpage";
  summaryCount.textContent =
    `${result.summary.word_count}/${result.summary.max_words} words`;

  sourceLink.href = result.fetch.final_url;
  sourceLink.textContent = result.fetch.final_url;
  sourceLink.target = "_blank";
  sourceLink.rel = "noreferrer";
  sourceLink.hidden = false;

  summaryPoints.innerHTML = "";
  summaryPoints.className = "summary-points";
  result.summary.points.forEach((point) => {
    const item = document.createElement("li");
    item.textContent = point;
    summaryPoints.appendChild(item);
  });

  statusTitle.textContent = "Summary ready";
  statusBadge.textContent = result.status;
  statusBadge.className = "badge ok";
  httpValue.textContent = `HTTP ${result.fetch.status_code}`;
  downloadValue.textContent = formatBytes(result.fetch.bytes_downloaded);
  cleanValue.textContent = `${result.cleaning.useful_words} words`;
  chunkValue.textContent = String(result.chunks.length);
  guardrailValue.textContent = formatStatus(result.summary.guardrail.status);
  providerValue.textContent = formatProvider(result.summary);
  providerNote.textContent = result.summary.fallback_reason || "";
  providerNote.hidden = !result.summary.fallback_reason;

  renderChunks(result.chunks);
  renderComponents(result.components);
}

function renderError(message) {
  errorMessage.textContent = message;
  statusTitle.textContent = "Could not summarize";
  statusBadge.textContent = "error";
  statusBadge.className = "badge warn";
}

function renderChunks(chunks) {
  chunksList.innerHTML = "";
  chunksList.className = "stack";
  chunks.forEach((chunk) => {
    const item = document.createElement("div");
    item.className = "proof-item";
    const strong = document.createElement("strong");
    strong.textContent = chunk.chunk_id;
    item.appendChild(strong);
    item.append(`${chunk.word_count} words`);
    chunksList.appendChild(item);
  });
}

function renderComponents(components) {
  componentsList.innerHTML = "";
  componentsList.className = "stack";
  components.forEach((component) => {
    const item = document.createElement("div");
    item.className = "proof-item";
    const strong = document.createElement("strong");
    strong.textContent = component;
    item.appendChild(strong);
    componentsList.appendChild(item);
  });
}

function formatStatus(status) {
  if (status === "passed") return "Passed";
  if (status === "blocked") return "Blocked";
  return status || "-";
}

function formatProvider(summary) {
  if (summary.provider === "deepseek") {
    return summary.model || "DeepSeek";
  }
  if (summary.provider === "gemini") {
    return summary.model || "Gemini";
  }
  if (summary.fallback_reason) return "Deterministic fallback";
  return "Deterministic";
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) return "-";
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

exampleSelect.addEventListener("change", () => {
  applyExample(Number.parseInt(exampleSelect.value, 10));
});
themeToggle.addEventListener("click", () => {
  setTheme(currentTheme() === "dark" ? "light" : "dark");
});
requestForm.addEventListener("submit", processUrl);

loadExamples().catch((error) => {
  errorMessage.textContent = error.message;
});
updateThemeToggle();
