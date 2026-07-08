/* about.js — Logic for opening, closing, keyboard handling (Esc), outside-click detection, and auto-start for the About modal. */

document.addEventListener("DOMContentLoaded", () => {
  const aboutBtn = document.getElementById("btn-about");
  const aboutModal = document.getElementById("about-modal");
  const closeAboutBtn = document.getElementById("btn-close-about");
  const closeAboutFooterBtn = document.getElementById("btn-close-about-footer");

  if (!aboutModal) return;

  function openAbout() {
    aboutModal.hidden = false;
  }

  function closeAbout() {
    aboutModal.hidden = true;
  }

  // ── Open Modal ───────────────────────────────────────────────────────────
  if (aboutBtn) {
    aboutBtn.addEventListener("click", openAbout);
  }

  // ── Close Modal ──────────────────────────────────────────────────────────
  if (closeAboutBtn) {
    closeAboutBtn.addEventListener("click", closeAbout);
  }

  if (closeAboutFooterBtn) {
    closeAboutFooterBtn.addEventListener("click", closeAbout);
  }

  // Close when clicking outside the modal card
  aboutModal.addEventListener("click", (e) => {
    if (e.target === aboutModal) {
      closeAbout();
    }
  });

  // Close when pressing the Esc key
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !aboutModal.hidden) {
      closeAbout();
    }
  });

  // ── Auto-start for first-time visitors ───────────────────────────────────
  try {
    if (!localStorage.getItem("climate_about_seen")) {
      setTimeout(openAbout, 800);
      localStorage.setItem("climate_about_seen", "1");
    }
  } catch (_) {}
});
