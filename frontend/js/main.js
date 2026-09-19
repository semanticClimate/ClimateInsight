/* main.js — app init: wires up DOM events to Chat/Sidebar/Api */

document.addEventListener("DOMContentLoaded", async () => {
  // ── i18n: init first so all translated strings are ready ─────────────────
  await I18n.init();

  // Restore language from session (survives page refresh within same tab)
  const savedLang = sessionStorage.getItem("ci_lang") || "en";
  const langSelect = document.getElementById("lang-select");
  if (langSelect && savedLang !== "en") {
    langSelect.value = savedLang;
  }
  I18n.setLang(savedLang);

  const sendBtn = document.getElementById("send-btn");
  const input = document.getElementById("question-input");
  const newChatBtn = document.getElementById("btn-new-chat");
  const toggleSidebarBtn = document.getElementById("btn-toggle-sidebar");
  const clearChatBtn = document.getElementById("btn-clear-chat");
  const downloadChatBtn = document.getElementById("btn-download-chat");
  const resetHighlightBtn = document.getElementById("btn-reset-highlight");
  const passageBackBtn = document.getElementById("btn-passage-back");
  const statusDot = document.getElementById("status-dot");
  const statusLabel = document.getElementById("status-label");

  // ── Send message ──────────────────────────────────────────────────────────
  if (sendBtn) sendBtn.addEventListener("click", () => Chat.send());

  if (input) {
    // Enter to send, Shift+Enter for newline
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        Chat.send();
      }
    });

    // Auto-resize textarea
    input.addEventListener("input", () => {
      input.style.height = "auto";
      input.style.height = `${input.scrollHeight}px`;
    });
  }

  // ── Suggested question buttons ────────────────────────────────────────────
  document.querySelectorAll(".sq-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const q = btn.dataset.q;
      if (q) Chat.send(q);
    });
  });

  // ── New conversation ──────────────────────────────────────────────────────
  if (newChatBtn) {
    newChatBtn.addEventListener("click", () => {
      Chat.clear();
      showToast(I18n.t("toast_new_chat"));
    });
  }

  // ── Sidebar toggle ────────────────────────────────────────────────────────
  if (toggleSidebarBtn) {
    toggleSidebarBtn.addEventListener("click", () => {
      if (window.sidebarController) window.sidebarController.toggle();
    });
  }

  // ── Clear / download chat ────────────────────────────────────────────────
  if (clearChatBtn) {
    clearChatBtn.addEventListener("click", () => {
      Chat.clear();
      showToast(I18n.t("toast_clear_chat"));
    });
  }
  if (downloadChatBtn) {
    downloadChatBtn.addEventListener("click", () => {
      Chat.download();
      showToast(I18n.t("toast_download"));
    });
  }

  // ── Source panel reset ────────────────────────────────────────────────────
  if (resetHighlightBtn) resetHighlightBtn.addEventListener("click", () => Chat.resetPassage());
  if (passageBackBtn) passageBackBtn.addEventListener("click", () => Chat.resetPassage());

  // ── Toast Notification Helper ─────────────────────────────────────────────
  const toast = document.getElementById("toast-notification");
  function showToast(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add("show");
    setTimeout(() => {
      toast.classList.remove("show");
    }, 2500);
  }

  // ── Language Dropdown Selector ────────────────────────────────────────────
  if (langSelect) {
    langSelect.addEventListener("change", () => {
      const code = langSelect.value;
      I18n.setLang(code);
      const langName = I18n.getLangName(code);
      showToast(I18n.t("toast_lang_changed", { lang: langName }));
    });
  }

  // ── Server Logs Modal ─────────────────────────────────────────────────────
  const logsModal = document.getElementById("logs-modal");
  const logsConsole = document.getElementById("logs-console");
  const closeLogsBtn = document.getElementById("btn-close-logs");
  const serverLogsBtn = document.getElementById("btn-server-logs");

  function renderLogs() {
    if (!logsConsole) return;
    const logs = Api.getLogs();
    if (logs.length === 0) {
      logsConsole.innerHTML = '<div style="color: #64748B;">No requests logged yet. Waiting for interaction...</div>';
      return;
    }
    logsConsole.innerHTML = logs.map(log => {
      const statusClass = typeof log.status === 'number' ? `status-200` : 'status-failed';
      return `
        <div class="log-line" style="margin-bottom: 6px;">
          <span class="log-time" style="color: #64748B; font-size: 0.75rem;">[${log.timestamp}]</span>
          <span class="log-method" style="color: #38BDF8; font-weight: 600; font-size: 0.75rem; margin-right: 4px;">${log.method}</span>
          <span class="log-url" style="color: #E2E8F0; font-size: 0.75rem; margin-right: 8px;">${log.url}</span>
          <span class="log-status ${statusClass}" style="font-size: 0.7rem; padding: 2px 6px; border-radius: 4px;">${log.status}</span>
        </div>
      `;
    }).join('');
  }

  if (serverLogsBtn) {
    serverLogsBtn.addEventListener("click", () => {
      renderLogs();
      if (logsModal) logsModal.hidden = false;
    });
  }

  if (closeLogsBtn) {
    closeLogsBtn.addEventListener("click", () => {
      if (logsModal) logsModal.hidden = true;
    });
  }

  if (logsModal) {
    logsModal.addEventListener("click", (e) => {
      if (e.target === logsModal) {
        logsModal.hidden = true;
      }
    });
  }

  document.addEventListener("api-log-updated", () => {
    if (logsModal && !logsModal.hidden) {
      renderLogs();
    }
  });

  // ── Help button → launch tour ─────────────────────────────────────────────
  const helpBtn = document.getElementById("btn-help");
  if (helpBtn) {
    helpBtn.addEventListener("click", () => Tour.start());
  }

  // Auto-start for first-time visitors
  Tour.maybeAutoStart();

  // ── Backend health check ──────────────────────────────────────────────────
  Api.health()
    .then(() => {
      if (statusDot) statusDot.classList.add("ok");
      if (statusLabel) statusLabel.textContent = I18n.t("status_ready");
    })
    .catch(() => {
      if (statusDot) statusDot.classList.remove("ok");
      if (statusLabel) statusLabel.textContent = I18n.t("status_offline");
    });
});