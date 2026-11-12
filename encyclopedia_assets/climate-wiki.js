/**
 * Generated IPCC Encyclopedia viewer (served through /climate-wiki-js)
 * ───────────────
 * Drop this script into any HTML page to get:
 *  • Hover tooltip  — preferred IPCC or Wikipedia definition
 *  • Click          — source glossary entry or Wikipedia article
 *
 * Usage:
 *   <script src="climate-wiki.js"></script>
 *
 * Works on the original ipcc_reference.html without modifying it —
 * just add this one <script> tag before </body>.
 */

(function () {
  "use strict";

  /* ── 1. TERM → WIKIPEDIA ARTICLE MAP ─────────────────────────────── */
  // Vocabulary is generated from the report and the IPCC SYR glossary.
  // The former hand-written map is preserved in climate-wiki.legacy.js.
  if (window.__CI_ENCYCLOPEDIA_VIEWER__) return;
  window.__CI_ENCYCLOPEDIA_VIEWER__ = true;
  /* ENCYCLOPEDIA_DATA */
  function encyclopediaTitle(key) {
    const entry = ENCYCLOPEDIA_CONCEPTS[key];
    if (!entry || !entry.wikipedia_url) return key;
    return decodeURIComponent(new URL(entry.wikipedia_url).pathname.slice(6)).replace(/_/g, " ");
  }


  /* ── 2. INJECT CSS ────────────────────────────────────────────────── */
  const CSS = `
    .cw-term {
      color: #1B4F9B;
      text-decoration: underline dotted #1B4F9B;
      cursor: pointer;
      border-radius: 2px;
      font-weight: bold;
      transition: background 0.15s;
    }
    .cw-term:hover {
      background: #e8f5ee;
      text-decoration: underline solid #1B4F9B;
    }

    /* Tooltip */
    #cw-tooltip {
      display: none;
      position: fixed;
      z-index: 99997;
      background: #fff;
      border: 1px solid #c8e6d5;
      border-left: 4px solid #1B4F9B;
      border-radius: 7px;
      padding: 10px 14px;
      max-width: 320px;
      font-size: 13px;
      line-height: 1.55;
      color: #1a1a1a;
      box-shadow: 0 4px 18px rgba(0,0,0,0.13);
      pointer-events: none;
      font-family: system-ui, sans-serif;
    }
    #cw-tooltip .cw-tt-title {
      font-weight: 700;
      font-size: 13.5px;
      color: #1B4F9B;
      margin-bottom: 5px;
    }
    #cw-tooltip .cw-tt-body {
      color: #333;
    }
    #cw-tooltip .cw-tt-loading {
      color: #999;
      font-style: italic;
    }
    #cw-tooltip .cw-tt-hint {
      margin-top: 7px;
      font-size: 11px;
      color: #888;
    }

    /* Modal overlay */
    #cw-overlay {
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.52);
      z-index: 99998;
      align-items: center;
      justify-content: center;
      font-family: system-ui, sans-serif;
    }
    #cw-overlay.cw-open { display: flex; }

    /* Modal box */
    #cw-modal {
      background: #fff;
      border-radius: 12px;
      width: min(1000px, 95vw);
      height: 96vh;
      max-height: 96vh;
      display: flex;
      flex-direction: column;
      box-shadow: 0 10px 50px rgba(0,0,0,0.28);
      overflow: hidden;
    }
    #cw-modal-header {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 14px 18px;
      background: #1B4F9B;
      color: #fff;
      flex-shrink: 0;
    }
    #cw-modal-header svg {
      flex-shrink: 0;
      opacity: 0.85;
    }
    #cw-modal-title {
      flex: 1;
      margin: 0;
      font-size: 17px;
      font-weight: 600;
      letter-spacing: 0.01em;
    }
    #cw-modal-close {
      background: rgba(255,255,255,0.15);
      border: none;
      color: #fff;
      font-size: 18px;
      cursor: pointer;
      border-radius: 6px;
      width: 32px;
      height: 32px;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: background 0.15s;
    }
    #cw-modal-close:hover { background: rgba(255,255,255,0.28); }

    #cw-modal-iframe-wrap {
      flex: 1;
      overflow: hidden;
      position: relative;
    }
    #cw-modal-loading {
      position: absolute;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      background: #f9fafb;
      font-size: 14px;
      color: #888;
      gap: 10px;
    }
    #cw-modal-iframe {
      width: 100%;
      height: 100%;
      border: none;
      display: block;
    }

    #cw-modal-footer {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 9px 18px;
      border-top: 1px solid #eee;
      flex-shrink: 0;
      font-size: 12px;
      color: #999;
    }
    #cw-modal-footer a {
      color: #1B4F9B;
      text-decoration: none;
      font-weight: 500;
    }
    #cw-modal-footer a:hover { text-decoration: underline; }

    /* Loading spinner */
    @keyframes cw-spin { to { transform: rotate(360deg); } }
    .cw-spinner {
      width: 20px; height: 20px;
      border: 2px solid #ddd;
      border-top-color: #1B4F9B;
      border-radius: 50%;
      animation: cw-spin 0.7s linear infinite;
    }
  `;

  const styleEl = document.createElement("style");
  styleEl.textContent = CSS;
  document.head.appendChild(styleEl);


  /* ── 3. BUILD DOM ─────────────────────────────────────────────────── */

  // Tooltip
  const tooltip = document.createElement("div");
  tooltip.id = "cw-tooltip";
  tooltip.innerHTML = `
    <div class="cw-tt-title"></div>
    <div class="cw-tt-body cw-tt-loading">Loading…</div>
    <div class="cw-tt-hint">Click to open full article</div>
  `;
  document.body.appendChild(tooltip);

  // Modal
  const overlay = document.createElement("div");
  overlay.id = "cw-overlay";
  overlay.innerHTML = `
    <div id="cw-modal">
      <div id="cw-modal-header">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>
        </svg>
        <h2 id="cw-modal-title">Wikipedia</h2>
        <button id="cw-modal-close" title="Close (Esc)">✕</button>
      </div>
      <div id="cw-modal-iframe-wrap">
        <div id="cw-modal-loading">
          <div class="cw-spinner"></div> Loading Wikipedia…
        </div>
        <iframe id="cw-modal-iframe" src="" sandbox="allow-same-origin allow-scripts allow-popups allow-forms"></iframe>
      </div>
      <div id="cw-modal-footer">
        <span>Source: <strong>Wikipedia</strong></span>
        <a id="cw-modal-ext" href="#" target="_blank" rel="noopener">Open in Wikipedia ↗</a>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);

  /* ── 4. MODAL LOGIC ───────────────────────────────────────────────── */
  const iframe = overlay.querySelector("#cw-modal-iframe");
  const loadingDiv = overlay.querySelector("#cw-modal-loading");

  function openModal(wikiTitle, displayText) {
    const entry = ENCYCLOPEDIA_CONCEPTS[wikiTitle];
    if (entry && entry.definition_source) {
      const url = "/ipcc-glossary#" + encodeURIComponent(entry.definition_source.html_id);
      window.open(url, "_blank", "noopener"); return;
    }
    if (!entry || !entry.wikipedia_url) {
      window.open("/ipcc-encyclopedia", "_blank", "noopener"); return;
    }
    wikiTitle = encyclopediaTitle(wikiTitle);
    // If we are in the iframe, send message to parent window
    if (window !== window.parent) {
      window.parent.postMessage({ type: "OPEN_WIKI_MODAL", wikiTitle, displayText }, "*");
      return;
    }

    const mobileUrl = `https://en.m.wikipedia.org/wiki/${encodeURIComponent(wikiTitle)}`;
    const desktopUrl = `https://en.wikipedia.org/wiki/${encodeURIComponent(wikiTitle)}`;
    overlay.querySelector("#cw-modal-title").textContent = displayText;
    overlay.querySelector("#cw-modal-ext").href = desktopUrl;
    loadingDiv.style.display = "flex";
    iframe.src = "";
    iframe.onload = () => { loadingDiv.style.display = "none"; };
    iframe.src = mobileUrl;
    overlay.classList.add("cw-open");
  }

  // Listen for modal requests from child iframe
  window.addEventListener("message", (e) => {
    if (e.data && e.data.type === "OPEN_WIKI_MODAL") {
      openModal(e.data.wikiTitle, e.data.displayText);
    }
  });

  function closeModal() {
    overlay.classList.remove("cw-open");
    iframe.src = "";
    loadingDiv.style.display = "flex";
  }

  overlay.querySelector("#cw-modal-close").addEventListener("click", closeModal);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) closeModal(); });

  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

  /* ── 5. WIKIPEDIA SUMMARY API + CACHE ────────────────────────────── */
  const summaryCache = {};

  function fetchSummary(wikiTitle, cb) {
    const imported = ENCYCLOPEDIA_CONCEPTS[wikiTitle];
    if (imported && imported.description) {
      cb(imported.description.split(/(?<=[.!?])\s+/)[0] || imported.description); return;
    }
    if (!imported || !imported.wikipedia_url) {
      cb("Extracted from an IPCC source; no definition is available."); return;
    }
    wikiTitle = encyclopediaTitle(wikiTitle);
    if (summaryCache[wikiTitle]) { cb(summaryCache[wikiTitle]); return; }
    fetch(`https://en.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(wikiTitle)}`)
      .then((r) => r.json())
      .then((d) => {
        const plain = d.extract || "";
        const first = plain.split(/(?<=[.!?])\s+/)[0] || plain || "No definition found.";
        summaryCache[wikiTitle] = first;
        cb(first);
      })
      .catch(() => {
        summaryCache[wikiTitle] = "Could not load definition.";
        cb(summaryCache[wikiTitle]);
      });
  }

  /* ── 6. TOOLTIP POSITIONING ──────────────────────────────────────── */
  function positionTooltip(e) {
    const pad = 12;
    const tw = tooltip.offsetWidth || 320;
    const th = tooltip.offsetHeight || 80;

    let minX = pad;
    let maxX = window.innerWidth - pad;
    let minY = pad;
    let maxY = window.innerHeight - pad;

    try {
      const panel = window.parent.document.querySelector('.source-panel');
      if (panel && window.frameElement) {
        const panelRect = panel.getBoundingClientRect();
        const iframeRect = window.frameElement.getBoundingClientRect();

        // Convert panel bounds to iframe's coordinate system
        const limitLeft = panelRect.left - iframeRect.left;
        const limitRight = panelRect.right - iframeRect.left;
        const limitTop = panelRect.top - iframeRect.top;
        const limitBottom = panelRect.bottom - iframeRect.top;

        // Ensure boundaries are constrained within the iframe's visible viewport
        minX = Math.max(0, limitLeft) + pad;
        maxX = Math.min(window.innerWidth, limitRight) - pad;
        minY = Math.max(0, limitTop) + pad;
        maxY = Math.min(window.innerHeight, limitBottom) - pad;
      }
    } catch (err) {
      // Fallback to window dimensions if cross-origin blocked or missing
    }

    // Try placing to the right of the cursor
    let x = e.clientX + 16;
    if (x + tw > maxX) {
      x = e.clientX - tw - 8;
    }

    // Try placing below the cursor
    let y = e.clientY + 16;
    if (y + th > maxY) {
      y = e.clientY - th - 8;
    }

    // Final clamp to ensure the tooltip is entirely within bounds
    if (x < minX) x = minX;
    if (x + tw > maxX) x = maxX - tw;
    if (y < minY) y = minY;
    if (y + th > maxY) y = maxY - th;

    tooltip.style.left = x + "px";
    tooltip.style.top = y + "px";
  }

  /* ── 7. TEXT NODE WALKER + TERM INJECTION ────────────────────────── */
  // Sort terms longest-first to prevent partial matches
  const sortedTerms = Object.keys(WIKI_MAP).sort((a, b) => b.length - a.length);
  const pattern = new RegExp(
    "\\b(" + sortedTerms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|") + ")\\b",
    "gi"
  );

  // Short keys are mostly acronyms / chemical formulas ("no" → NO, "co" → CO).
  // Matched case-insensitively they hit ordinary words ("no", "No"), so they
  // only count when written as an acronym: all capitals or at least two
  // (NO, CO₂, NDCs) — except these real words / units.
  // Keep in sync with backend/knowledge_graph.py.
  const LOWERCASE_OK = new Set(["coal", "oil", "firn", "buoy", "ppm", "ppb", "2°c", "2 c"]);
  const ACRONYMS = new Set(["afolu", "beccs", "hcfcs", "llghg", "nmvoc", "slcps"]);
  function requiresCapital(key) {
    return ACRONYMS.has(key) || (key.length <= 4 && !LOWERCASE_OK.has(key));
  }
  function looksLikeAcronym(matched) {
    const letters = matched.replace(/[^A-Za-z]/g, "");
    const capitals = letters.replace(/[^A-Z]/g, "").length;
    return capitals >= 2 || (letters.length > 0 && capitals === letters.length);
  }
  // Text that follows a match, even across tags: the report's InDesign HTML
  // puts the "2" of CO₂ in the next <span>, not in a <sub>.
  function followingText(textNode, endIndex) {
    const rest = textNode.nodeValue.slice(endIndex);
    if (rest) return rest;
    let node = textNode;
    while (node && !node.nextSibling) node = node.parentNode;
    return node && node.nextSibling ? node.nextSibling.textContent || "" : "";
  }

  // Tags we skip entirely (don't touch their text content)
  const SKIP_TAGS = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "TEXTAREA", "CODE", "PRE", "A", "BUTTON", "INPUT", "SELECT"]);

  function wrapTermsInNode(textNode) {
    const text = textNode.nodeValue;
    if (!pattern.test(text)) return;       // fast exit
    pattern.lastIndex = 0;

    const frag = document.createDocumentFragment();
    let last = 0, m;
    pattern.lastIndex = 0;

    while ((m = pattern.exec(text)) !== null) {
      if (m.index > last) {
        frag.appendChild(document.createTextNode(text.slice(last, m.index)));
      }
      const matched = m[0];
      const key = matched.toLowerCase();
      // "CO" directly followed by a subscript digit is CO₂, not carbon monoxide
      const beforeSubscript =
        key.length <= 3 && /^\s?[2-6₂-₆]/.test(followingText(textNode, m.index + matched.length));
      const falsePositive =
        (requiresCapital(key) && !looksLikeAcronym(matched)) || beforeSubscript;
      const wikiTitle = falsePositive ? null : WIKI_MAP[key];
      if (!wikiTitle) {
        frag.appendChild(document.createTextNode(matched));
      } else {
        const a = document.createElement("a");
        a.className = "cw-term";
        a.href = "#";
        a.textContent = matched;
        a.dataset.wiki = wikiTitle;
        a.dataset.entryId = (ENCYCLOPEDIA_CONCEPTS[wikiTitle] || {}).wikidata_id || wikiTitle;
        a.dataset.display = matched;

        a.addEventListener("mouseenter", (e) => {
          const entry = ENCYCLOPEDIA_CONCEPTS[wikiTitle];
          tooltip.querySelector(".cw-tt-hint").textContent = entry && entry.definition_source
            ? "IPCC glossary · Click to read the full definition"
            : "Wikipedia · Click to open the article";
          tooltip.querySelector(".cw-tt-title").textContent = matched;
          tooltip.querySelector(".cw-tt-body").textContent = "Loading…";
          tooltip.querySelector(".cw-tt-body").className = "cw-tt-body cw-tt-loading";
          tooltip.style.display = "block";
          positionTooltip(e);
          fetchSummary(wikiTitle, (text) => {
            tooltip.querySelector(".cw-tt-body").textContent = text;
            tooltip.querySelector(".cw-tt-body").className = "cw-tt-body";
          });
        });
        a.addEventListener("mousemove", positionTooltip);
        a.addEventListener("mouseleave", () => { tooltip.style.display = "none"; });
        a.addEventListener("click", (e) => {
          e.preventDefault();
          tooltip.style.display = "none";
          openModal(wikiTitle, matched);
        });

        frag.appendChild(a);
      }
      last = m.index + m[0].length;
    }

    if (last < text.length) {
      frag.appendChild(document.createTextNode(text.slice(last)));
    }

    textNode.parentNode.replaceChild(frag, textNode);
  }

  function walkNode(node) {
    if (node.nodeType === Node.TEXT_NODE) {
      wrapTermsInNode(node);
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    if (SKIP_TAGS.has(node.tagName)) return;
    if (node.getAttribute("role") === "ami_encyclopedia") return;
    if (node.classList && node.classList.contains("cw-term")) return;

    // Collect children first (walking live NodeList while modifying it is unsafe)
    const children = Array.from(node.childNodes);
    children.forEach(walkNode);
  }

  /* ── 8. RUN ───────────────────────────────────────────────────────── */
  function run() {
    // Only scan and highlight terms if we are inside the IPCC iframe
    if (window !== window.parent) {
      walkNode(document.body);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
})();
