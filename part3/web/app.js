const STORAGE_THREAD = "nimbus-policy-thread";
const STORAGE_THEME = "nimbus-policy-theme";

const state = {
  threadId: localStorage.getItem(STORAGE_THREAD) || crypto.randomUUID(),
  busy: false,
  maxMessageLength: 2000,
};

const elements = {
  form: document.querySelector("#chat-form"),
  input: document.querySelector("#message-input"),
  send: document.querySelector("#send-button"),
  messages: document.querySelector("#messages"),
  prompts: document.querySelector("#starter-prompts"),
  newThread: document.querySelector("#new-thread"),
  clearThread: document.querySelector("#clear-thread"),
  theme: document.querySelector("#theme-toggle"),
  connection: document.querySelector("#connection-status"),
  memory: document.querySelector("#memory-label"),
  provider: document.querySelector("#provider-value"),
  model: document.querySelector("#model-value"),
  turn: document.querySelector("#turn-value"),
  latency: document.querySelector("#latency-value"),
  evidence: document.querySelector("#evidence-list"),
  tools: document.querySelector("#tool-list"),
  traceStatus: document.querySelector("#trace-status"),
  threadId: document.querySelector("#thread-id"),
  count: document.querySelector("#character-count"),
  toast: document.querySelector("#toast"),
};

let toastTimer;

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderAnswer(value) {
  const escaped = escapeHtml(value);
  const paragraphs = escaped.split(/\n{2,}/).map((paragraph) => {
    const withCitations = paragraph.replace(
      /\[(P(\d+):S\d+)\]/g,
      '<a href="/document#page=$2" target="_blank">[$1]</a>',
    );
    return `<p>${withCitations.replaceAll("\n", "<br>")}</p>`;
  });
  return paragraphs.join("");
}

function addMessage(role, content) {
  const article = document.createElement("article");
  article.className = `message ${role}`;
  const label = role === "user" ? "You" : "Nimbus agent";
  article.innerHTML = `
    <div class="avatar" aria-hidden="true">${role === "user" ? "Y" : "N"}</div>
    <div class="message-content">
      <div class="message-meta">${label}</div>
      ${role === "assistant" ? renderAnswer(content) : `<p>${escapeHtml(content)}</p>`}
    </div>
  `;
  elements.messages.append(article);
  elements.messages.scrollTop = elements.messages.scrollHeight;
  return article;
}

function addTyping() {
  const article = document.createElement("article");
  article.className = "message assistant typing";
  article.id = "typing-indicator";
  article.innerHTML = `
    <div class="avatar" aria-hidden="true">N</div>
    <div class="message-content" aria-label="Agent is responding">
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
    </div>
  `;
  elements.messages.append(article);
  elements.messages.scrollTop = elements.messages.scrollHeight;
}

function removeTyping() {
  document.querySelector("#typing-indicator")?.remove();
}

function setBusy(busy) {
  state.busy = busy;
  elements.input.disabled = busy;
  elements.send.disabled = busy;
  elements.traceStatus.textContent = busy ? "Working" : "Ready";
  elements.traceStatus.className = `trace-status ${busy ? "working" : "idle"}`;
}

function updateTrace(response) {
  elements.provider.textContent = response.provider || "-";
  elements.model.textContent = response.model || "-";
  elements.turn.textContent = String(response.turn_count ?? 0);
  elements.latency.textContent = Number.isFinite(response.latency_ms)
    ? `${response.latency_ms} ms`
    : "-";
  elements.memory.textContent = response.remembered_name
    ? `Remembering ${response.remembered_name}`
    : "No saved name";

  if (response.retrieved_sections?.length) {
    elements.evidence.innerHTML = response.retrieved_sections.map((item) => `
      <div class="evidence-item">
        <a href="/document#page=${item.page_number}" target="_blank">
          [${escapeHtml(item.citation_id)}] ${escapeHtml(item.title)}
        </a>
        <span>Page ${item.page_number} / relevance ${Number(item.score).toFixed(2)}</span>
      </div>
    `).join("");
  } else {
    elements.evidence.className = "empty-state";
    elements.evidence.textContent = "No policy evidence was needed.";
  }

  if (response.tool_events?.length) {
    elements.tools.innerHTML = response.tool_events.map((item) => `
      <div class="tool-item">
        <strong>${escapeHtml(item.name)}</strong>
        <span>${escapeHtml(formatToolEvent(item))}</span>
      </div>
    `).join("");
  } else {
    elements.tools.className = "empty-state";
    elements.tools.textContent = "No tool used on this turn.";
  }
}

function formatToolEvent(event) {
  const args = Object.entries(event.arguments || {})
    .map(([key, value]) => `${key}: ${value}`)
    .join(", ");
  return `${event.status}${args ? ` / ${args}` : ""}`;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  let payload;
  try {
    payload = await response.json();
  } catch {
    payload = {};
  }
  if (!response.ok) {
    throw new Error(payload.error || `Request failed (${response.status}).`);
  }
  return payload;
}

async function sendMessage(message) {
  if (state.busy) return;
  const normalized = message.trim();
  if (!normalized) return;

  elements.prompts?.remove();
  addMessage("user", normalized);
  elements.input.value = "";
  resizeInput();
  updateCount();
  addTyping();
  setBusy(true);

  try {
    const response = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        thread_id: state.threadId,
        message: normalized,
      }),
    });
    removeTyping();
    addMessage("assistant", response.answer);
    updateTrace(response);
  } catch (error) {
    removeTyping();
    elements.traceStatus.textContent = "Error";
    elements.traceStatus.className = "trace-status error";
    addMessage("assistant", `I could not complete that request. ${error.message}`);
    showToast(error.message);
  } finally {
    setBusy(false);
    elements.input.focus();
  }
}

async function loadApp() {
  localStorage.setItem(STORAGE_THREAD, state.threadId);
  elements.threadId.textContent = state.threadId;
  applyTheme(localStorage.getItem(STORAGE_THEME) || "light");

  try {
    const [config, conversation] = await Promise.all([
      api("/api/config"),
      api(`/api/conversations/${encodeURIComponent(state.threadId)}`),
    ]);
    state.maxMessageLength = config.max_message_length || 2000;
    elements.input.maxLength = state.maxMessageLength;
    elements.provider.textContent = config.provider;
    elements.model.textContent = config.model;
    elements.connection.className = "status-indicator online";
    elements.connection.lastChild.textContent = " Online";
    restoreConversation(conversation);
  } catch (error) {
    elements.connection.className = "status-indicator offline";
    elements.connection.lastChild.textContent = " Offline";
    showToast(error.message);
  }
  updateCount();
}

function restoreConversation(conversation) {
  if (!conversation.messages?.length) return;
  elements.prompts?.remove();
  elements.messages.innerHTML = "";
  conversation.messages.forEach((message) => {
    addMessage(message.role, message.content);
  });
  elements.turn.textContent = String(conversation.turn_count || 0);
  elements.memory.textContent = conversation.remembered_name
    ? `Remembering ${conversation.remembered_name}`
    : "No saved name";
}

async function clearConversation() {
  if (state.busy) return;
  try {
    await api(`/api/conversations/${encodeURIComponent(state.threadId)}`, {
      method: "DELETE",
    });
    window.location.reload();
  } catch (error) {
    showToast(error.message);
  }
}

function newConversation() {
  if (state.busy) return;
  state.threadId = crypto.randomUUID();
  localStorage.setItem(STORAGE_THREAD, state.threadId);
  window.location.reload();
}

function resizeInput() {
  elements.input.style.height = "auto";
  elements.input.style.height = `${Math.min(elements.input.scrollHeight, 120)}px`;
}

function updateCount() {
  elements.count.textContent =
    `${elements.input.value.length} / ${state.maxMessageLength}`;
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  elements.theme.firstElementChild.textContent = theme === "dark" ? "\u263e" : "\u263c";
}

function toggleTheme() {
  const next = document.documentElement.dataset.theme === "dark"
    ? "light"
    : "dark";
  localStorage.setItem(STORAGE_THEME, next);
  applyTheme(next);
}

function showToast(message) {
  window.clearTimeout(toastTimer);
  elements.toast.textContent = message;
  elements.toast.classList.add("visible");
  toastTimer = window.setTimeout(() => {
    elements.toast.classList.remove("visible");
  }, 3500);
}

function switchPanel(panelName) {
  document.querySelectorAll("[data-panel-name]").forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.panelName === panelName);
  });
  document.querySelectorAll(".mobile-tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.panel === panelName);
  });
}

elements.form.addEventListener("submit", (event) => {
  event.preventDefault();
  sendMessage(elements.input.value);
});

elements.input.addEventListener("input", () => {
  resizeInput();
  updateCount();
});

elements.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    elements.form.requestSubmit();
  }
});

elements.prompts?.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (button) sendMessage(button.textContent);
});

elements.newThread.addEventListener("click", newConversation);
elements.clearThread.addEventListener("click", clearConversation);
elements.theme.addEventListener("click", toggleTheme);
document.querySelectorAll(".mobile-tab").forEach((button) => {
  button.addEventListener("click", () => switchPanel(button.dataset.panel));
});

loadApp();
