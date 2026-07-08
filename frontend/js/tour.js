/* tour.js — Guided onboarding tour
 * Triggered by the Help button in the topbar.
 * All steps are defined in the STEPS array below — add, remove, reorder freely.
 */

const Tour = (() => {

    // ── Step definitions ───────────────────────────────────────────────────────
    // selector : CSS selector for the element to spotlight
    // title    : tooltip heading
    // body     : tooltip explanation
    // position : preferred tooltip side — "top" | "bottom" | "left" | "right"
    //            (auto-flips if it would go off-screen)
    // before   : optional fn() called before this step activates (e.g. open sidebar)
    // watchChange : optional flag — if true, the tour listens for a "change"
    //               event on this step's element while it's active, and swaps
    //               the tooltip body to a confirmation message when it fires.
    //               Purely cosmetic — does not block "Next"/"Skip", and does
    //               not touch whatever handler already reacts to the change.
    const STEPS = [
        {
            selector: ".sidebar",
            title: "Sidebar",
            body: "Your conversation history and navigation live here. Collapse it any time with the hamburger button to give the chat more room.",
            position: "right",
            before: () => {
                const sb = document.getElementById("sidebar");
                if (sb && sb.classList.contains("collapsed")) window.sidebarController?.toggle();
            },
        },
        {
            selector: ".btn-new-chat",
            title: "New Conversation",
            body: "Start a fresh chat. Your previous conversations are listed below this button — click any to revisit them.",
            position: "right",
        },
        {
            selector: "#lang-select",
            title: "Language",
            body: "Switch the interface language. The chatbot will respond in the selected language. Try picking one now, or skip ahead — you can always change it later.",
            confirmBody: "Nice — language updated. You can change it again anytime from here.",
            position: "right",
            watchChange: true,
        },
        {
            selector: ".sidebar-actions",
            title: "Chat Actions",
            body: "Clear your current chat, download the full transcript as a text file, or open the server logs to inspect API requests.",
            position: "right",
        },
        {
            selector: ".chat-panel",
            title: "Suggested Questions",
            body: "Not sure where to start? Click any of these pre-written questions and the bot will answer instantly.",
            altBody: "Look at you — already a pro! These suggested questions are here if you ever need a nudge, but clearly you didn't.",
            position: "top",
        },
        {
            selector: ".input-bar",
            title: "Ask a Question",
            body: "Type your question here and press Enter (or click the send button). Use Shift+Enter to add a new line without sending.",
            altBody: "You've already cracked the code on this one. 🎉 Questions in, answers out — you're a natural. Nothing more to see here!",
            position: "top",
        },
        {
            selector: ".source-panel",
            title: "Source Panel",
            body: "The IPCC AR6 report is embedded here. When you click a citation chip in an answer, this panel scrolls to and highlights the relevant passage.",
            position: "left",
        },
    ];

    // ── State ──────────────────────────────────────────────────────────────────
    let current = 0;
    let active = false;
    let scrollLock = false;

    // Tracks a currently-attached "watchChange" listener so it can be cleanly
    // removed when the tour moves off that step (or ends).
    let watchCleanup = null;

    // ── DOM refs (created once) ────────────────────────────────────────────────
    let overlay, spotlight, tooltip, ttTitle, ttBody, ttStep, ttPrev, ttNext, ttSkip;

    // ── Build DOM ──────────────────────────────────────────────────────────────
    function build() {
        if (document.getElementById("tour-overlay")) return; // already built

        // Overlay — full-screen dim layer with a transparent cutout
        overlay = document.createElement("div");
        overlay.id = "tour-overlay";

        // Spotlight ring — absolutely positioned box that matches the target
        spotlight = document.createElement("div");
        spotlight.id = "tour-spotlight";
        overlay.appendChild(spotlight);

        // Tooltip card
        tooltip = document.createElement("div");
        tooltip.id = "tour-tooltip";
        tooltip.innerHTML = `
      <div class="tt-header">
        <span class="tt-step" id="tt-step"></span>
        <button class="tt-skip" id="tt-skip">Skip tour</button>
      </div>
      <div class="tt-title" id="tt-title"></div>
      <div class="tt-body"  id="tt-body"></div>
      <div class="tt-footer">
        <button class="tt-btn tt-prev" id="tt-prev">← Previous</button>
        <button class="tt-btn tt-next primary" id="tt-next">Next →</button>
      </div>
    `;
        overlay.appendChild(tooltip);

        document.body.appendChild(overlay);

        // Cache inner refs
        ttTitle = document.getElementById("tt-title");
        ttBody = document.getElementById("tt-body");
        ttStep = document.getElementById("tt-step");
        ttPrev = document.getElementById("tt-prev");
        ttNext = document.getElementById("tt-next");
        ttSkip = document.getElementById("tt-skip");

        ttPrev.addEventListener("click", prev);
        ttNext.addEventListener("click", next);
        ttSkip.addEventListener("click", end);

        // Click outside spotlight to advance
        overlay.addEventListener("click", (e) => {
            if (e.target === overlay) next();
        });

        // Keyboard nav
        document.addEventListener("keydown", onKey);
    }

    function onKey(e) {
        if (!active) return;
        if (e.key === "ArrowRight" || e.key === "Enter") next();
        if (e.key === "ArrowLeft") prev();
        if (e.key === "Escape") end();
    }

    // ── Start / End ────────────────────────────────────────────────────────────
    function start() {
        build();
        current = 0;
        active = true;
        overlay.classList.add("visible");
        goTo(current);
    }

    function end() {
        active = false;
        overlay.classList.remove("visible");
        tooltip.classList.remove("visible");
        spotlight.classList.remove("visible");
        document.removeEventListener("keydown", onKey);
        detachWatch();
        // Mark tour as seen
        try { localStorage.setItem("ipcc_tour_seen", "1"); } catch (_) { }
    }

    // ── Navigation ─────────────────────────────────────────────────────────────
    function next() {
        detachWatch();
        if (current < STEPS.length - 1) {
            current++;
            goTo(current);
        } else {
            end();
        }
    }

    function prev() {
        detachWatch();
        if (current > 0) {
            current--;
            goTo(current);
        }
    }

    // ── Go to step ─────────────────────────────────────────────────────────────
    function goTo(index) {
        const step = STEPS[index];
        if (!step) return;

        // Run any pre-step setup
        if (step.before) step.before();

        const el = document.querySelector(step.selector);
        if (!el) { next(); return; } // skip missing elements

        // Fade out tooltip while repositioning
        tooltip.classList.remove("visible");

        // Scroll element into view, then position
        scrollLock = true;
        el.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });

        // Give scroll time to settle before positioning
        setTimeout(() => {
            positionSpotlight(el);
            populateTooltip(step, index);
            positionTooltip(el, step.position || "bottom");

            if (step.watchChange) attachWatch(step, el);

            // Small delay so spotlight animates in first
            requestAnimationFrame(() => {
                spotlight.classList.add("visible");
                setTimeout(() => tooltip.classList.add("visible"), 100);
            });

            scrollLock = false;
        }, 350);
    }

    // ── Non-blocking "watch for change" nudge ────────────────────────────────
    // Listens for a native "change" event on the step's element while that
    // step is on screen. Purely cosmetic (swaps in a confirmation message) —
    // does not intercept, prevent, or replace whatever handler already exists
    // for that element elsewhere in the app.
    function attachWatch(step, el) {
        detachWatch(); // safety: never stack more than one listener

        const handler = () => {
            if (step.confirmBody) {
                ttBody.textContent = step.confirmBody;
            }
        };

        el.addEventListener("change", handler);
        watchCleanup = () => el.removeEventListener("change", handler);
    }

    function detachWatch() {
        if (watchCleanup) {
            watchCleanup();
            watchCleanup = null;
        }
    }

    // ── Spotlight ──────────────────────────────────────────────────────────────
    function positionSpotlight(el) {
        const PAD = 8;
        const rect = el.getBoundingClientRect();

        spotlight.style.top = `${rect.top - PAD}px`;
        spotlight.style.left = `${rect.left - PAD}px`;
        spotlight.style.width = `${rect.width + PAD * 2}px`;
        spotlight.style.height = `${rect.height + PAD * 2}px`;

        // Update the overlay clip-path to cut out the spotlight region
        const x1 = rect.left - PAD;
        const y1 = rect.top - PAD;
        const x2 = rect.right + PAD;
        const y2 = rect.bottom + PAD;

        overlay.style.setProperty("--cx1", `${x1}px`);
        overlay.style.setProperty("--cy1", `${y1}px`);
        overlay.style.setProperty("--cx2", `${x2}px`);
        overlay.style.setProperty("--cy2", `${y2}px`);
    }

    // ── Tooltip ────────────────────────────────────────────────────────────────
    // Returns true if the user has already sent at least one chat message.
    function _hasChat() {
        const msgs = document.querySelectorAll("#messages .msg.user");
        return msgs.length > 0;
    }

    function populateTooltip(step, index) {
        ttTitle.textContent = step.title;
        ttBody.textContent = (step.altBody && _hasChat()) ? step.altBody : step.body;
        ttStep.textContent = `${index + 1} of ${STEPS.length}`;

        ttPrev.style.visibility = index === 0 ? "hidden" : "visible";
        ttNext.textContent = index === STEPS.length - 1 ? "Finish ✓" : "Next →";
    }

    function positionTooltip(el, preferred) {
        const MARGIN = 16;
        const TT_W = 300;
        const TT_H = 180; // approximate
        const rect = el.getBoundingClientRect();
        const vw = window.innerWidth;
        const vh = window.innerHeight;

        // Work out which sides have enough room
        const room = {
            bottom: vh - rect.bottom > TT_H + MARGIN,
            top: rect.top > TT_H + MARGIN,
            right: vw - rect.right > TT_W + MARGIN,
            left: rect.left > TT_W + MARGIN,
        };

        // Fall back through preference → auto
        const order = [preferred, "bottom", "top", "right", "left"];
        const side = order.find(s => room[s]) || "bottom";

        let top, left;

        switch (side) {
            case "bottom":
                top = rect.bottom + MARGIN;
                left = Math.min(Math.max(rect.left + rect.width / 2 - TT_W / 2, MARGIN), vw - TT_W - MARGIN);
                break;
            case "top":
                top = rect.top - TT_H - MARGIN;
                left = Math.min(Math.max(rect.left + rect.width / 2 - TT_W / 2, MARGIN), vw - TT_W - MARGIN);
                break;
            case "right":
                top = Math.min(Math.max(rect.top + rect.height / 2 - TT_H / 2, MARGIN), vh - TT_H - MARGIN);
                left = rect.right + MARGIN;
                break;
            case "left":
                top = Math.min(Math.max(rect.top + rect.height / 2 - TT_H / 2, MARGIN), vh - TT_H - MARGIN);
                left = rect.left - TT_W - MARGIN;
                break;
        }

        tooltip.style.top = `${Math.max(MARGIN, top)}px`;
        tooltip.style.left = `${Math.max(MARGIN, left)}px`;
        tooltip.dataset.side = side;
    }

    // ── Auto-start for first-time visitors ────────────────────────────────────
    function maybeAutoStart() {
        // Disabled: Auto-start is now handled by about.js to show the About modal instead.
    }

    return { start, end, maybeAutoStart };
})();