/* chat.js — message rendering, send, source panel */

const Chat = (() => {
  let sessionId = null;
  let sessionRegistered = false;

  // Track which "document slot" is active: 0 = IPCC HTML, 1..N = XML papers
  // docList is populated from window.SOURCE_DOCS set by index.html
  let currentDocIndex = 0;

  const conversationStore = {};

  // ── DOM refs ──────────────────────────────────────────────────────────────
  const messagesEl = () => document.getElementById("messages");
  const welcomeEl = () => document.getElementById("welcome-screen");
  const inputEl = () => document.getElementById("question-input");
  const sendBtnEl = () => document.getElementById("send-btn");
  const sourcePassageEl = () => document.getElementById("source-passage");
  const passageSectionEl = () => document.getElementById("passage-section");
  const passageTitleEl = () => document.getElementById("passage-title");
  const passageTextEl = () => document.getElementById("passage-text");
  const sourceIframeEl = () => document.getElementById("source-iframe");
  const docNavLabel = () => document.getElementById("doc-nav-label");
  const docNavPrev = () => document.getElementById("doc-nav-prev");
  const docNavNext = () => document.getElementById("doc-nav-next");

  // ── Document navigator ────────────────────────────────────────────────────
  function initDocNav() {
    const docs = window.SOURCE_DOCS || [];
    if (!docs.length) return;

    updateDocNav();

    docNavPrev()?.addEventListener("click", () => {
      currentDocIndex = (currentDocIndex - 1 + docs.length) % docs.length;
      updateDocNav();
      resetPassage();
    });

    docNavNext()?.addEventListener("click", () => {
      currentDocIndex = (currentDocIndex + 1) % docs.length;
      updateDocNav();
      resetPassage();
    });
  }

  function updateDocNav() {
    const docs = window.SOURCE_DOCS || [];
    const doc = docs[currentDocIndex];
    if (!doc) return;

    const label = docNavLabel();
    if (label) {
      label.innerHTML = `
        <span class="doc-nav-index">${currentDocIndex + 1} / ${docs.length}</span>
        <span class="doc-nav-title">${doc.label}</span>
      `;
    }

    const iframe = sourceIframeEl();
    if (iframe && doc.type === "html") {
      iframe.style.display = "";
      iframe.src = doc.url;
    } else if (iframe && doc.type === "xml") {
      // XML papers have no iframe — show the passage card with paper info
      iframe.style.display = "none";
      showPaperCard(doc);
    }
  }

  function showPaperCard(doc) {
    const passageEl = sourcePassageEl();
    passageEl.hidden = false;
    passageEl.classList.add("paper-info-card");

    passageSectionEl().textContent = "Research Article";
    passageTitleEl().textContent = doc.label;
    passageTextEl().innerHTML = doc.doi
      ? `<a href="https://doi.org/${doc.doi}" target="_blank" class="paper-doi-link">doi: ${doc.doi}</a>`
      : "Click a citation chip from this paper to view its source passage.";

    // Hide back button when showing the paper card (not a retrieved passage)
    const backBtn = document.getElementById("btn-passage-back");
    if (backBtn) backBtn.style.display = "none";
  }

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

      if (!conversationStore[sessionId]) conversationStore[sessionId] = [];
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

  // ── Restore a previous conversation ──────────────────────────────────────
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

      citations.forEach((c, i) => {
        const chip = document.createElement("button");
        chip.className = "cite-chip";
        // Show number + short label: [1] for IPCC sections, paper title for XML
        const isXml = !!c.pmcid || (c.source_type === "research_article");
        chip.innerHTML = isXml
          ? `<span class="cite-num">[${i + 1}]</span><span class="cite-label">${c.title || c.section}</span>`
          : `<span class="cite-num">[${i + 1}]</span><span class="cite-label">${c.section}</span>`;
        chip.dataset.sourceType = isXml ? "xml" : "html";
        chip.addEventListener("click", () => showPassage(c, isXml));
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
  function showPassage(citation, isXml) {
    const passageEl = sourcePassageEl();
    passageEl.hidden = false;
    passageEl.classList.remove("paper-info-card");

    const backBtn = document.getElementById("btn-passage-back");
    if (backBtn) backBtn.style.display = "";

    if (isXml) {
      // XML: show the passage text and paper metadata; no iframe involvement
      passageSectionEl().textContent = citation.title || citation.section;
      passageTitleEl().textContent = citation.document_title || "";

      let meta = "";
      if (citation.doi) meta += `<a href="https://doi.org/${citation.doi}" target="_blank" class="paper-doi-link">doi: ${citation.doi}</a>  `;
      if (citation.pmcid) meta += `<span class="paper-pmcid">PMC${citation.pmcid}</span>`;

      passageTextEl().innerHTML =
        (meta ? `<div class="passage-meta">${meta}</div>` : "") +
        `<div class="passage-prose">${escHtml(citation.text || "Source passage not available.")}</div>`;

      // Switch the doc navigator to the matching XML paper (if known)
      const docs = window.SOURCE_DOCS || [];
      const pmcid = citation.pmcid || "";
      const idx = docs.findIndex(d => d.pmcid === pmcid);
      if (idx !== -1 && idx !== currentDocIndex) {
        currentDocIndex = idx;
        updateDocNav();
      }

    } else {
      // HTML: show passage text and scroll the iframe to the anchor
      passageSectionEl().textContent = citation.section;
      passageTitleEl().textContent = citation.title
        ? `${citation.section} — ${citation.title}`
        : `Section ${citation.section}`;
      passageTextEl().innerHTML =
        `<div class="passage-prose">${escHtml(citation.text || "Source passage not available.")}</div>`;

      // Switch navigator back to IPCC (index 0) if needed
      if (currentDocIndex !== 0) {
        currentDocIndex = 0;
        updateDocNav();
      }

      const iframe = sourceIframeEl();
      if (iframe) scrollIframeToSection(iframe, citation.section);
    }
  }

  function scrollIframeToSection(iframe, sectionId) {
    try {
      if (iframe.contentDocument) {
        const anchor = iframe.contentDocument.getElementById(sectionId);
        if (anchor) anchor.scrollIntoView({ behavior: "smooth" });
      }
    } catch (e) { /* cross-origin: silently ignore */ }
  }

  function resetPassage() {
    const passageEl = sourcePassageEl();
    if (passageEl) {
      passageEl.hidden = true;
      passageEl.classList.remove("paper-info-card");
    }
    const backBtn = document.getElementById("btn-passage-back");
    if (backBtn) backBtn.style.display = "";
  }

  function escHtml(str) {
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  // ── Clear (new chat) ──────────────────────────────────────────────────────
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
    if (!msgs.length) return;
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

  // ── Init ──────────────────────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", initDocNav);

  return { send, clear, download, resetPassage, restore };
})();