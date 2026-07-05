/* chat.js — message rendering, send, source panel */

const Chat = (() => {
  let sessionId = null;

  // ── DOM refs ──────────────────────────────────────────────────────────────
  const messagesEl = () => document.getElementById("messages");
  const welcomeEl = () => document.getElementById("welcome-screen");
  const inputEl = () => document.getElementById("question-input");
  const sendBtnEl = () => document.getElementById("send-btn");
  const sourceDefaultEl = () => document.getElementById("source-default");
  const sourcePassageEl = () => document.getElementById("source-passage");
  const passageSectionEl = () => document.getElementById("passage-section");
  const passageTitleEl = () => document.getElementById("passage-title");
  const passageTextEl = () => document.getElementById("passage-text");
  const sourceIframeEl = () => document.getElementById("source-iframe");

  // ── Send a message ────────────────────────────────────────────────────────
  async function send(question) {
    question = (question || inputEl().value).trim();
    if (!question) return;

    const welcome = welcomeEl();
    if (welcome) welcome.style.display = "none";
    inputEl().value = "";
    inputEl().style.height = "auto";

    appendMessage("user", question);
    const typing = showTyping();
    sendBtnEl().disabled = true;

    try {
      const data = await Api.chat(question, sessionId);
      sessionId = data.session_id;
      typing.remove();
      appendMessage("assistant", data.answer, data.citations || []);
      window.sidebarController?.addConversation(question);
    } catch (err) {
      typing.remove();
      appendError(err.message || "Could not reach the backend.");
    }

    sendBtnEl().disabled = false;
    inputEl().focus();
  }

  // ── DOM builders ──────────────────────────────────────────────────────────
  function appendMessage(role, text, citations = []) {
    const el = document.createElement("div");
    el.className = `msg ${role}`;

    const textEl = document.createElement("div");
    textEl.className = "msg-text";
    textEl.textContent = text;
    el.appendChild(textEl);

    if (citations.length > 0) {
      const row = document.createElement("div");
      row.className = "msg-citations";

      citations.forEach(c => {
        const chip = document.createElement("button");
        chip.className = "cite-chip";
        chip.textContent = c.section;

        // Each chip carries the verbatim chunk text from the backend.
        // showPassage() no longer touches the LLM answer at all.
        chip.addEventListener("click", () => showPassage(c));
        row.appendChild(chip);
      });

      el.appendChild(row);
    }

    messagesEl().appendChild(el);
    messagesEl().scrollTop = messagesEl().scrollHeight;
  }

  function appendError(msg) {
    const el = document.createElement("div");
    el.className = "msg error";
    el.textContent = `⚠ ${msg}`;
    messagesEl().appendChild(el);
    messagesEl().scrollTop = messagesEl().scrollHeight;
  }

  function showTyping() {
    const el = document.createElement("div");
    el.className = "typing-indicator";
    el.innerHTML = "<span></span><span></span><span></span>";
    messagesEl().appendChild(el);
    messagesEl().scrollTop = messagesEl().scrollHeight;
    return el;
  }

  // ── Source panel ──────────────────────────────────────────────────────────
  /**
   * Show the verbatim chunk that the LLM cited.
   * @param {Object} citation  - { section, title, text } from the API
   */
  function showPassage(citation) {
    const passageEl = sourcePassageEl();
    passageEl.hidden = false;

    passageSectionEl().textContent = citation.section;

    // Show the section title if we have one, otherwise fall back gracefully
    passageTitleEl().textContent = citation.title
      ? `${citation.section} — ${citation.title}`
      : `Section ${citation.section}`;

    // Display the exact chunk text retrieved from the vector store.
    // If for some reason it's missing, say so honestly rather than
    // showing a sentence extracted from the LLM's paraphrase.
    passageTextEl().textContent = citation.text
      ? citation.text
      : "Source passage not available for this citation.";

    // Try to scroll the iframe to the relevant anchor if available
    try {
      const iframe = sourceIframeEl();
      if (iframe && iframe.contentWindow) {
        const anchor = iframe.contentDocument
          ? iframe.contentDocument.getElementById(citation.section)
          : null;
        if (anchor) anchor.scrollIntoView({ behavior: "smooth" });
      }
    } catch (e) { /* cross-origin: silently ignore */ }
  }

  function resetPassage() {
    const passageEl = sourcePassageEl();
    if (passageEl) passageEl.hidden = true;
    const def = sourceDefaultEl();
    if (def) def.hidden = true;
  }

  // ── Clear ─────────────────────────────────────────────────────────────────
  async function clear() {
    await Api.clearSession(sessionId);
    sessionId = null;
    messagesEl().innerHTML = "";
    resetPassage();

    const welcome = welcomeEl();
    if (welcome) welcome.style.display = "";
  }

  // ── Download ──────────────────────────────────────────────────────────────
  function download() {
    const msgs = [...messagesEl().querySelectorAll(".msg")];
    if (msgs.length === 0) return;

    const lines = msgs.map(m => {
      const role = m.classList.contains("user") ? "User" : "Assistant";
      return `${role}: ${m.querySelector(".msg-text")?.textContent || m.textContent}`;
    });

    const blob = new Blob([lines.join("\n\n")], { type: "text/plain" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "ipcc-chat.txt";
    a.click();
  }

  return { send, clear, download, resetPassage };
})();
