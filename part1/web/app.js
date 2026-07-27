const exampleSelect = document.querySelector("#exampleSelect");
const customerName = document.querySelector("#customerName");
const contactCount = document.querySelector("#contactCount");
const subject = document.querySelector("#subject");
const body = document.querySelector("#body");
const processButton = document.querySelector("#processButton");
const themeToggle = document.querySelector("#themeToggle");
const errorMessage = document.querySelector("#errorMessage");
const chatMessages = document.querySelector("#chatMessages");

const statusTitle = document.querySelector("#statusTitle");
const statusBadge = document.querySelector("#statusBadge");
const criticalValue = document.querySelector("#criticalValue");
const categoryValue = document.querySelector("#categoryValue");
const routerNote = document.querySelector("#routerNote");
const subagentValue = document.querySelector("#subagentValue");
const guardrailValue = document.querySelector("#guardrailValue");
const writerValue = document.querySelector("#writerValue");
const writerNote = document.querySelector("#writerNote");
const evidenceList = document.querySelector("#evidenceList");
const skillsList = document.querySelector("#skillsList");

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

function setTheme(theme, persist = true) {
  document.documentElement.dataset.theme = theme;
  if (persist) {
    localStorage.setItem("support-agent-theme", theme);
  }
  updateThemeToggle();
}

async function loadExamples() {
  const response = await fetch("/api/examples");
  const data = await response.json();
  examples = data.examples || [];

  examples.forEach((example, index) => {
    const option = document.createElement("option");
    option.value = String(index);
    option.textContent = `${example.case_id} - ${example.subject}`;
    exampleSelect.appendChild(option);
  });
}

function applyExample(index) {
  const example = examples[index];
  if (!example) return;

  customerName.value = example.customer_name || "";
  contactCount.value = example.contact_count_last_7_days ?? 0;
  subject.value = example.subject || "";
  body.value = example.body || "";
}

function getPayload() {
  return {
    case_id: "WEB-CASE-001",
    customer_id: "WEB-CUSTOMER",
    customer_name: customerName.value.trim() || "Customer",
    customer_email: "customer@example.com",
    subject: subject.value.trim(),
    body: body.value.trim(),
    contact_count_last_7_days: Number.parseInt(contactCount.value || "0", 10),
    received_at: new Date().toISOString(),
    metadata: {}
  };
}

async function processEmail() {
  const payload = getPayload();
  errorMessage.textContent = "";
  appendMessage("user", "Customer Email", formatUserEmail(payload));
  processButton.disabled = true;
  processButton.textContent = "Sending...";

  try {
    const response = await fetch("/api/process", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Processing failed");
    renderResult(data.result);
  } catch (error) {
    errorMessage.textContent = error.message;
    appendMessage("assistant", "Support Agent", `I could not process that email. ${error.message}`);
  } finally {
    processButton.disabled = false;
    processButton.textContent = "Send";
  }
}

function renderResult(result) {
  const needsReview = result.status === "human_review";
  const reply = result.handoff_ticket
    ? `Human review required.\n\n${result.handoff_ticket.summary}`
    : result.final_draft?.reply || "-";

  appendMessage("assistant", "Support Agent", reply);

  statusTitle.textContent = titleForStatus(result.status);
  statusBadge.textContent = result.status;
  statusBadge.className = `badge ${needsReview ? "warn" : "ok"}`;

  criticalValue.textContent = formatCriticalGate(result);
  categoryValue.textContent = result.classification?.primary_category || "-";
  routerNote.textContent = formatRouter(result.classification);
  subagentValue.textContent = result.route?.selected_subagent || result.skill_plan?.selected_subagent || "-";
  guardrailValue.textContent = formatRefundGuardrailStatus(result.guardrail?.status);
  writerValue.textContent = formatWriter(result.final_draft);
  writerNote.textContent = result.final_draft?.fallback_reason || "";
  writerNote.hidden = !result.final_draft?.fallback_reason;

  renderEvidence(result.search_result?.passages || result.final_draft?.evidence || []);
  renderSkills(result.skill_plan?.skills || []);
}

function appendMessage(role, name, text) {
  const article = document.createElement("article");
  article.className = `message ${role}`;

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "user" ? "U" : "A";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  const strong = document.createElement("strong");
  strong.textContent = name;
  bubble.appendChild(strong);

  String(text).split("\n\n").forEach((paragraph) => {
    const p = document.createElement("p");
    p.textContent = paragraph;
    bubble.appendChild(p);
  });

  article.appendChild(avatar);
  article.appendChild(bubble);
  chatMessages.appendChild(article);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function formatUserEmail(payload) {
  return `Subject: ${payload.subject}\n\n${payload.body}`;
}

function titleForStatus(status) {
  if (status === "human_review") return "Human review required";
  if (status === "drafted") return "Draft ready";
  return "Processed";
}

function formatRefundGuardrailStatus(status) {
  if (status === "passed") return "Applied";
  if (status === "blocked") return "Blocked";
  if (status === "not_applicable") return "Not applied";
  return "-";
}

function formatCriticalGate(result) {
  return result.critical_check?.is_critical ? "Yes" : "No";
}

function formatRouter(classification) {
  if (!classification) return "";
  if (classification.provider === "deepseek") {
    return "DeepSeek Router Agent";
  }
  if (classification.fallback_reason) {
    return "Keyword fallback";
  }
  return "Keyword classifier";
}

function formatWriter(draft) {
  if (!draft) return "Not used";
  if (draft.provider === "deepseek") {
    return draft.model || "DeepSeek";
  }
  if (draft.provider === "human_review") return "Human review template";
  if (draft.fallback_reason) return "Deterministic fallback";
  return "Deterministic";
}

function renderEvidence(passages) {
  evidenceList.innerHTML = "";
  if (!passages.length) {
    evidenceList.textContent = "No customer-facing evidence used.";
    evidenceList.className = "stack muted";
    return;
  }
  evidenceList.className = "stack";
  passages.forEach((passage) => {
    const item = document.createElement("div");
    item.className = "item";
    item.innerHTML = `<strong>Page ${passage.page_number} - ${escapeHtml(passage.section)}</strong>${escapeHtml(trimText(passage.text, 230))}`;
    evidenceList.appendChild(item);
  });
}

function renderSkills(skills) {
  skillsList.innerHTML = "";
  if (!skills.length) {
    skillsList.textContent = "No skills selected.";
    skillsList.className = "stack muted";
    return;
  }
  skillsList.className = "stack";
  skills.forEach((skill) => {
    const item = document.createElement("div");
    item.className = "item";
    item.innerHTML = `<strong>${escapeHtml(skill.name)}</strong>${escapeHtml(skill.purpose)}`;
    skillsList.appendChild(item);
  });
}

function trimText(text, maxLength) {
  if (!text || text.length <= maxLength) return text || "";
  return `${text.slice(0, maxLength - 3).trim()}...`;
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

exampleSelect.addEventListener("change", () => applyExample(Number.parseInt(exampleSelect.value, 10)));
processButton.addEventListener("click", processEmail);
themeToggle.addEventListener("click", () => {
  setTheme(currentTheme() === "dark" ? "light" : "dark");
});

body.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    processEmail();
  }
});

loadExamples().catch((error) => {
  errorMessage.textContent = error.message;
});

updateThemeToggle();
