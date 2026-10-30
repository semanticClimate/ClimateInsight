/* concept_graph.js
 * Inline knowledge-graph panel for the ClimateInsight main chat UI.
 *
 * What it does:
 *  - Adds a "Knowledge graph" button after every assistant answer
 *  - Clicking it opens an inline panel below the message showing the
 *    encyclopedia concepts the question touches and how they are linked
 *    in the IPCC / paper passages, plus a cited explanation (Ollama, local)
 *  - "Full page" opens /concept-graph, the corpus-wide knowledge graph,
 *    with the same concepts highlighted
 *
 * Dependencies (already on the page): api.js  (Api.conceptGraph)
 * Open-source renderer: vis-network 9.1.9 (Apache-2.0 / MIT) via jsDelivr
 */

const ConceptGraph = (() => {
  // ── vis-network loader (https://github.com/visjs/vis-network) ─────────────
  const VIS_URL = "https://cdn.jsdelivr.net/npm/vis-network@9.1.9/standalone/umd/vis-network.min.js";
  const PALETTE = ["#16A34A", "#2563EB", "#D97706", "#9333EA", "#DC2626",
                   "#0891B2", "#65A30D", "#DB2777", "#4B5563", "#B45309"];
  let _visLoading = null;

  function ensureVis() {
    if (window.vis && window.vis.Network) return Promise.resolve(true);
    if (!_visLoading) {
      _visLoading = new Promise(resolve => {
        const s = document.createElement("script");
        s.src = VIS_URL;
        s.onload = () => resolve(true);
        s.onerror = () => { _visLoading = null; resolve(false); };
        document.head.appendChild(s);
      });
    }
    return _visLoading;
  }

  // ── Render the question's concept subgraph into a container ───────────────
  // main: the asked-about concept(s) — pinned at the centre as the hub,
  //       with a dark ring, glow, big label and thick links in its colour
  async function renderSubgraph(subgraph, container, main = []) {
    const nodes = subgraph?.nodes || [];
    if (!nodes.length) {
      container.textContent = "No encyclopedia concepts were found for this question.";
      return;
    }
    const ok = await ensureVis();
    if (!ok) {
      // Text fallback: list the concepts and their links
      container.textContent = "Concepts: " + nodes.map(n => n.label).join(", ");
      return;
    }
    const hubs = new Set(main);
    const colorOf = id => PALETTE[(nodes.find(n => n.id === id)?.group || 0) % PALETTE.length];
    const maxCount = Math.max(...nodes.map(n => n.count));
    const maxW = Math.max(1, ...subgraph.edges.map(e => e.weight));
    const data = {
      nodes: new vis.DataSet(nodes.map((n, i) => {
        const color = PALETTE[n.group % PALETTE.length];
        const hub = hubs.has(n.id);
        // Pin a single hub at the centre so the others arrange around it
        const pinned = hub && hubs.size === 1;
        const node = {
          id: n.id, label: n.label, title: `${n.label} — ${n.count} passages`,
          value: n.count,
          color: { background: color, border: color },
        };
        if (hub) {
          Object.assign(node, {
            value: maxCount * 1.8,
            borderWidth: 4,
            color: { background: color, border: "#111827" },
            shadow: { enabled: true, color, size: 24, x: 0, y: 0 },
            font: { size: 22, color: "#111827", strokeWidth: 5, strokeColor: "#ffffff" },
            scaling: { label: { enabled: false } },
          });
        }
        if (pinned) Object.assign(node, { x: 0, y: 0, fixed: true });
        return node;
      })),
      edges: new vis.DataSet(subgraph.edges.map(e => {
        const hubEdge = hubs.has(e.from) || hubs.has(e.to);
        const passages = `${e.weight} passage${e.weight === 1 ? "" : "s"}`;
        const edge = {
          from: e.from, to: e.to, dashes: e.kind === "source",
          value: e.weight,
          title: `${e.from} and ${e.to}: mentioned together in ${passages}`,
        };
        if (hubEdge) {
          edge.value = maxW * 1.5;   // hub links are the thickest
          edge.color = { color: colorOf(hubs.has(e.from) ? e.from : e.to), opacity: 1 };
          edge.label = e.kind === "source" ? "same section" : passages;
        }
        return edge;
      })),
    };
    const network = new vis.Network(container, data, {
      nodes: {
        shape: "dot",
        scaling: { min: 6, max: 26, label: { enabled: false } },   // every node labelled
        font: { face: "Jost, sans-serif", size: 13, color: "#1F2937", strokeWidth: 4, strokeColor: "#ffffff" },
      },
      edges: {
        color: { color: "#B6C2BC" }, scaling: { min: 0.5, max: 5, label: { enabled: false } }, smooth: false,
        font: { face: "Jost, sans-serif", size: 11, color: "#374151", strokeWidth: 4, strokeColor: "#ffffff", align: "middle" },
      },
      physics: {
        solver: "forceAtlas2Based",
        forceAtlas2Based: { gravitationalConstant: -90, springLength: 120, avoidOverlap: 0.8 },
        stabilization: { iterations: 250 },
      },
      interaction: { hover: true, zoomView: false },
    });
    network.once("stabilizationIterationsDone", () => {
      network.setOptions({ physics: false });
      network.fit();
    });

    // Clicking a concept or a line opens its sources on the full graph page
    const base = API_BASE.replace(/\/api$/, "");
    network.on("click", p => {
      const id = p.nodes[0] || (p.edges[0] && network.body.data.edges.get(p.edges[0]).from);
      if (id) window.open(`${base}/concept-graph?concept=${encodeURIComponent(id)}`, "_blank");
    });
  }

  // ── Build the inline concept-graph panel ──────────────────────────────────
  function buildPanel(question, messageEl) {
    // Don't add a second panel if one already exists on this message
    if (messageEl.querySelector(".cg-panel")) return;

    const panel = document.createElement("div");
    panel.className = "cg-panel";
    panel.style.cssText = `
      margin-top: 10px;
      border: 1.5px solid var(--panel-border);
      border-radius: var(--radius);
      background: var(--panel-bg);
      overflow: hidden;
      animation: cgFadeIn .25s ease;
    `;

    // Tab bar
    panel.innerHTML = `
      <div class="cg-tabs" style="
        display:flex; align-items:center;
        border-bottom:1.5px solid var(--panel-border);
        padding: 0 12px; gap:12px; background:var(--panel-header-bg);">
        <button class="cg-tab cg-tab-active" data-tab="graph"
          style="padding:8px 0;font-size:.75rem;font-weight:600;border:none;
                 background:none;cursor:pointer;color:var(--green);font-family:inherit;
                 border-bottom:2.5px solid var(--green);margin-bottom:-1.5px;">
          Graph
        </button>
        <button class="cg-tab" data-tab="explain"
          style="padding:8px 0;font-size:.75rem;font-weight:500;border:none;
                 background:none;cursor:pointer;color:var(--text-muted);font-family:inherit;
                 border-bottom:2.5px solid transparent;margin-bottom:-1.5px;">
          Explanation
        </button>
        <div style="margin-left:auto;display:flex;align-items:center;gap:4px;padding:4px 0;">
          <button class="cg-open-btn" title="Open this question on the full knowledge graph"
            style="font-size:.72rem;padding:4px 10px;border-radius:6px;
                   border:1.5px solid var(--panel-border);background:var(--bg);
                   color:var(--text);cursor:pointer;font-family:inherit;font-weight:600;">
            Open full graph
          </button>
          <button class="cg-close-btn" title="Close this panel"
            style="font-size:.72rem;padding:4px 10px;border-radius:6px;
                   border:1.5px solid var(--panel-border);background:var(--bg);
                   color:var(--text-muted);cursor:pointer;font-family:inherit;">Close</button>
        </div>
      </div>

      <div class="cg-loading" style="
        display:flex;align-items:center;gap:8px;
        padding:20px 16px;color:var(--text-muted);font-size:.8rem;">
        Finding the concepts for this question and writing an explanation. This can take up to a minute.
      </div>

      <div class="cg-panel-graph" style="display:none;padding:12px;">
        <div style="overflow-x:auto;border:1.5px solid var(--panel-border);
                    border-radius:var(--radius-sm);background:var(--bg);padding:12px;">
          <div class="cg-graph-out" style="height:300px"></div>
          <p style="font-size:.72rem;color:var(--text-muted);margin-top:6px">
            The largest circle is the main topic. Click any concept to read its sources on the full graph.
          </p>
        </div>
      </div>

      <div class="cg-panel-explain" style="display:none;padding:12px;">
        <p class="cg-explain-text"
           style="font-size:.82rem;color:var(--text);line-height:1.65;"></p>
      </div>
    `;

    // Wire up tabs
    const tabs = panel.querySelectorAll(".cg-tab");
    tabs.forEach(tab => {
      tab.addEventListener("click", () => {
        tabs.forEach(t => {
          t.style.color = "var(--text-muted)";
          t.style.borderBottomColor = "transparent";
          t.style.fontWeight = "500";
        });
        tab.style.color = "var(--green)";
        tab.style.borderBottomColor = "var(--green)";
        tab.style.fontWeight = "600";
        panel.querySelector(".cg-panel-graph").style.display =
          tab.dataset.tab === "graph" ? "block" : "none";
        panel.querySelector(".cg-panel-explain").style.display =
          tab.dataset.tab === "explain" ? "block" : "none";
      });
    });

    // Close button
    panel.querySelector(".cg-close-btn").addEventListener("click", () => {
      panel.style.animation = "cgFadeOut .2s ease forwards";
      setTimeout(() => panel.remove(), 200);
    });

    // Full page button
    panel.querySelector(".cg-open-btn").addEventListener("click", () => {
      const url = `${API_BASE.replace(/\/api$/, "")}/concept-graph?q=${encodeURIComponent(question)}`;
      window.open(url, "_blank");
    });

    messageEl.appendChild(panel);
    return panel;
  }

  // ── Populate a panel with data ────────────────────────────────────────────
  async function populatePanel(panel, data) {
    panel.querySelector(".cg-loading").style.display = "none";
    panel.querySelector(".cg-panel-graph").style.display = "block";


    // Explanation
    const explainEl = panel.querySelector(".cg-explain-text");
    explainEl.textContent = data.explanation;

    // Sources the map was built from (IPCC sections / papers)
    if (data.sources && data.sources.length) {
      const list = document.createElement("ul");
      list.className = "cg-sources";
      list.style.cssText = "margin:8px 0 0 16px;font-size:.72rem;line-height:1.5;color:var(--text-muted)";
      data.sources.forEach(s => {
        const li = document.createElement("li");
        li.textContent = `[${s.ref}] ${s.label}`;
        list.appendChild(li);
      });
      explainEl.after(list);
    }

    // Knowledge subgraph for this question
    await renderSubgraph(data.subgraph, panel.querySelector(".cg-graph-out"), data.main || []);
  }

  // ── Show error in panel ───────────────────────────────────────────────────
  function showPanelError(panel, msg) {
    const loading = panel.querySelector(".cg-loading");
    loading.innerHTML = "";
    const span = document.createElement("span");
    span.style.color = "#b91c1c";
    span.textContent = "Error: " + msg;
    loading.appendChild(span);
  }

  // ── Public: attach a "Knowledge graph" button to an assistant message ────
  function attachButton(messageEl, question) {
    // Avoid duplicate buttons
    if (messageEl.querySelector(".cg-trigger-btn")) return;

    const btn = document.createElement("button");
    btn.className = "cg-trigger-btn";
    btn.textContent = "Knowledge graph";
    btn.title = "Show this answer's concepts in the knowledge graph";
    btn.style.cssText = `
      margin-top: 8px;
      display: inline-flex; align-items: center; gap: 4px;
      font-size: .72rem; padding: 4px 12px;
      border-radius: 20px;
      border: 1.5px solid var(--panel-border);
      background: var(--bg);
      color: var(--green);
      font-weight: 600;
      cursor: pointer;
      font-family: inherit;
      transition: background .15s, border-color .15s;
    `;
    btn.onmouseenter = () => {
      btn.style.background = "var(--green-light)";
      btn.style.borderColor = "var(--green-mid)";
    };
    btn.onmouseleave = () => {
      btn.style.background = "var(--bg)";
      btn.style.borderColor = "var(--panel-border)";
    };

    btn.addEventListener("click", async () => {
      btn.disabled = true;
      btn.textContent = "Working…";

      const panel = buildPanel(question, messageEl);
      if (!panel) { btn.disabled = false; btn.textContent = "Knowledge graph"; return; }

      try {
        const data = await Api.conceptGraph(question);
        await populatePanel(panel, data);
      } catch (e) {
        showPanelError(panel, e.message || "Failed to generate concept map");
      }

      btn.textContent = "Knowledge graph";
      btn.disabled = false;
    });

    // Add button after the citations row (or after text if no citations)
    const citationsRow = messageEl.querySelector(".msg-citations");
    if (citationsRow) {
      citationsRow.after(btn);
    } else {
      messageEl.querySelector(".msg-text")?.after(btn);
    }
  }

  // ── Topbar button ─────────────────────────────────────────────────────────
  function addTopbarButton() {
    const topbarIcons = document.querySelector(".topbar-icons");
    if (!topbarIcons) return;

    const btn = document.createElement("button");
    btn.className = "topbar-icon-btn";
    btn.title = "Knowledge Graph";
    btn.innerHTML = `
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
           stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="5"  cy="12" r="2"/>
        <circle cx="19" cy="5"  r="2"/>
        <circle cx="19" cy="19" r="2"/>
        <line x1="7"  y1="11" x2="17" y2="6"/>
        <line x1="7"  y1="13" x2="17" y2="18"/>
        <circle cx="12" cy="12" r="2"/>
        <line x1="7" y1="12" x2="10" y2="12"/>
        <line x1="14" y1="12" x2="17" y2="6"/>
        <line x1="14" y1="12" x2="17" y2="18"/>
      </svg>`;

    btn.addEventListener("click", () => {
      // Get the last user question if there is one
      const lastUserMsg = [...document.querySelectorAll(".msg.user .msg-text")].at(-1);
      const q = lastUserMsg ? encodeURIComponent(lastUserMsg.textContent.trim()) : "";
      const base = API_BASE.replace(/\/api$/, "");
      window.open(`${base}/concept-graph${q ? "?q=" + q : ""}`, "_blank");
    });

    // Insert before the existing first icon
    topbarIcons.insertBefore(btn, topbarIcons.firstChild);
  }

  // ── Init ──────────────────────────────────────────────────────────────────
  function init() {
    // Inject required keyframe animations
    if (!document.getElementById("cg-styles")) {
      const style = document.createElement("style");
      style.id = "cg-styles";
      style.textContent = `
        @keyframes cgFadeIn  { from { opacity:0; transform:translateY(6px) } to { opacity:1; transform:none } }
        @keyframes cgFadeOut { from { opacity:1 } to { opacity:0; transform:translateY(4px) } }
        @keyframes cgSpin    { to { transform: rotate(360deg) } }
      `;
      document.head.appendChild(style);
    }

    // Add topbar button once DOM is ready
    addTopbarButton();

    // Observe the messages container so we attach a button to every new
    // assistant message as it's added to the DOM.
    const messagesEl = document.getElementById("messages");
    if (!messagesEl) return;

    const observer = new MutationObserver((mutations) => {
      mutations.forEach(({ addedNodes }) => {
        addedNodes.forEach(node => {
          if (!(node instanceof Element)) return;
          if (!node.classList.contains("msg") || !node.classList.contains("assistant")) return;

          // Find the question that prompted this answer (the previous user msg)
          const allMsgs = [...messagesEl.querySelectorAll(".msg")];
          const myIdx   = allMsgs.indexOf(node);
          const prevUser = allMsgs.slice(0, myIdx).reverse().find(m => m.classList.contains("user"));
          const question = prevUser?.querySelector(".msg-text")?.textContent?.trim() || "";

          if (question) attachButton(node, question);
        });
      });
    });

    observer.observe(messagesEl, { childList: true });
  }

  return { init, attachButton };
})();

// Auto-init when DOM is ready
document.addEventListener("DOMContentLoaded", () => ConceptGraph.init());
