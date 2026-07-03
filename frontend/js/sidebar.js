/* sidebar.js — collapsible sidebar + conversation list */

const Sidebar = (() => {
  let collapsed = false;
  let conversations = [];   // [{ id, label }]

  function toggle() {
    collapsed = !collapsed;
    document.getElementById("sidebar").classList.toggle("collapsed", collapsed);
  }

  function addConversation(question) {
    const label = question.length > 36 ? question.slice(0, 36) + "…" : question;
    const id = Date.now();
    conversations.unshift({ id, label });

    const list = document.getElementById("conversation-list");
    const emptyEl = list.querySelector(".empty-convos");
    if (emptyEl) emptyEl.remove();

    // Deactivate others
    list.querySelectorAll(".convo-item").forEach(el => el.classList.remove("active"));

    const btn = document.createElement("button");
    btn.className = "convo-item active";
    btn.textContent = label;
    btn.title = question;
    btn.addEventListener("click", () => {
      list.querySelectorAll(".convo-item").forEach(el => el.classList.remove("active"));
      btn.classList.add("active");
    });

    list.prepend(btn);
  }

  return { toggle, addConversation };
})();