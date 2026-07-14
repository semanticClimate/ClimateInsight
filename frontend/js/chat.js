/* chat.js — message rendering, send, source panel */

const Chat = (() => {
  let sessionId = null;
  let sessionRegistered = false;
  let iframeLoaded = false; // ← tracks whether we've set the iframe src yet

  // In-memory store: sessionId -> array of { role, text, citations }
  const conversationStore = {};

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

      if (!conversationStore[sessionId]) {
        conversationStore[sessionId] = [];
      }

      conversationStore[sessionId].push({ role: "user", text: question, citations: [] });
      conversationStore[sessionId].push({ role: "assistant", text: data.answer, citations: data.citations || [] });

      typing.remove();
      appendMessage("assistant", data.answer, data.citations || []);

      if (!sessionRegistered) {
        window.sidebarController?.addConversation(question, sessionId);
        sessionRegistered = true;
      }

    } catch (err) {
      typing.remove();
      appendError(err.message || "Could not reach the backend.");
    }

    sendBtnEl().disabled = false;
    inputEl().focus();
  }

  // ── Restore a previous conversation from the sidebar ──────────────────────
  function restore(storedSessionId) {
    const messages = conversationStore[storedSessionId];
    if (!messages) return;

    sessionId = storedSessionId;
    sessionRegistered = true;

    messagesEl().innerHTML = "";
    resetPassage();

    const welcome = welcomeEl();
    if (welcome) welcome.style.display = "none";

    messages.forEach(m => appendMessage(m.role, m.text, m.citations));
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
  function showPassage(citation) {
    const passageEl = sourcePassageEl();
    passageEl.hidden = false;

    passageSectionEl().textContent = citation.section;

    passageTitleEl().textContent = citation.title
      ? `${citation.section} — ${citation.title}`
      : `Section ${citation.section}`;

    passageTextEl().textContent = citation.text
      ? citation.text
      : "Source passage not available for this citation.";

    // ── Lazy-load the IPCC reference iframe on first citation click ──────────
    // The iframe src is intentionally left empty on page load to avoid fetching
    // 855KB of HTML before the user needs it. We set it here, once, then scroll.
    const iframe = sourceIframeEl();
    if (!iframe) return;

    if (!iframeLoaded) {
      const referenceUrl = window.IPCC_REFERENCE_URL;
      if (referenceUrl) {
        iframe.src = referenceUrl;
        iframeLoaded = true;

        // Wait for the iframe to load before trying to scroll to the anchor
        iframe.addEventListener("load", () => scrollIframeToSection(iframe, citation.section), { once: true });
        return; // scroll will happen in the load handler above
      }
    }

    scrollIframeToSection(iframe, citation.section);
  }

  function scrollIframeToSection(iframe, sectionId) {
    try {
      if (iframe.contentWindow) {
        const anchor = iframe.contentDocument
          ? iframe.contentDocument.getElementById(sectionId)
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

  // ── Clear (new chat) ───────────────────────────────────────────────────────
  async function clear() {
    await Api.clearSession(sessionId);
    sessionId = null;
    sessionRegistered = false;
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

  return { send, clear, download, resetPassage, restore };
})();