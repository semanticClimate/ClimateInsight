/**
 * climate-wiki.js
 * ───────────────
 * Drop this script into any HTML page to get:
 *  • Hover tooltip  — first sentence from Wikipedia
 *  • Click modal    — full Wikipedia article in an iframe
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
    const WIKI_MAP = {
        "greenhouse gas emissions": "Greenhouse gas emissions",
        "greenhouse gases": "Greenhouse gas",
        "greenhouse gas": "Greenhouse gas",
        "carbon dioxide removal": "Carbon dioxide removal",
        "bioenergy with carbon capture and storage": "Bioenergy with carbon capture and storage",
        "atlantic meridional overturning circulation": "Atlantic meridional overturning circulation",
        "integrated assessment model": "Integrated assessment modelling",
        "ecosystem-based adaptation": "Ecosystem-based adaptation",
        "nationally determined contribution": "Nationally determined contribution",
        "equilibrium climate sensitivity": "Climate sensitivity",
        "transient climate response": "Climate sensitivity",
        "nature-based solutions": "Nature-based solutions",
        "climate-smart agriculture": "Climate-smart agriculture",
        "sustainable development": "Sustainable development",
        "climate change": "Climate change",
        "global warming": "Global warming",
        "global surface temperature": "Global surface temperature",
        "global mean temperature": "Global mean surface temperature",
        "sea level rise": "Sea level rise",
        "sea-level rise": "Sea level rise",
        "paris agreement": "Paris Agreement",
        "loss and damage": "Loss and damage (climate change)",
        "radiative forcing": "Radiative forcing",
        "carbon budget": "Carbon budget",
        "carbon pricing": "Carbon price",
        "carbon capture": "Carbon capture and storage",
        "carbon sequestration": "Carbon sequestration",
        "carbon footprint": "Carbon footprint",
        "carbon tax": "Carbon tax",
        "carbon offset": "Carbon offset",
        "carbon cycle": "Carbon cycle",
        "carbon sink": "Carbon sink",
        "net zero": "Net zero emissions",
        "net-zero": "Net zero emissions",
        "net negative": "Negative emissions",
        "just transition": "Just transition",
        "energy transition": "Energy transition",
        "energy efficiency": "Energy efficiency",
        "climate resilience": "Climate resilience",
        "adaptive capacity": "Adaptive capacity",
        "maladaptation": "Maladaptation",
        "tipping point": "Tipping points in the climate system",
        "tipping points": "Tipping points in the climate system",
        "climate risk": "Climate risk",
        "climate action": "Climate change mitigation",
        "climate finance": "Climate finance",
        "climate system": "Climate system",
        "climate model": "Climate model",
        "climate governance": "Climate governance",
        "climate justice": "Climate justice",
        "food security": "Food security",
        "energy security": "Energy security",
        "stranded assets": "Stranded asset",
        "green economy": "Green economy",
        "ocean acidification": "Ocean acidification",
        "ocean warming": "Ocean heat content",
        "permafrost": "Permafrost",
        "glacier retreat": "Retreat of glaciers since 1850",
        "ice sheet": "Ice sheet",
        "coral bleaching": "Coral bleaching",
        "biodiversity loss": "Biodiversity loss",
        "extreme weather": "Extreme weather",
        "tropical cyclone": "Tropical cyclone",
        "storm surge": "Storm surge",
        "compound events": "Compound event",
        "urban heat island": "Urban heat island",
        "early warning system": "Early warning system",
        "managed retreat": "Managed retreat",
        "afforestation": "Afforestation",
        "reforestation": "Reforestation",
        "deforestation": "Deforestation",
        "electrification": "Electrification",
        "decarbonization": "Low-carbon economy",
        "decarbonisation": "Low-carbon economy",
        "renewable energy": "Renewable energy",
        "solar energy": "Solar energy",
        "wind energy": "Wind power",
        "green hydrogen": "Green hydrogen",
        "emissions trading": "Emissions trading",
        "cap and trade": "Emissions trading",
        "carbon market": "Carbon emission trading",
        "warming level": "Global warming",
        "overshoot": "Overshoot (climate)",
        "attribution": "Attribution of recent climate change",
        "sensitivity": "Climate sensitivity",
        "feedback": "Climate change feedback",
        "forcing": "Radiative forcing",
        "aerosols": "Aerosol",
        "aerosol": "Aerosol",
        "albedo": "Albedo",
        "precipitation": "Precipitation",
        "drought": "Drought",
        "wildfire": "Wildfire",
        "flood": "Flood",
        "heatwave": "Heat wave",
        "heat wave": "Heat wave",
        "adaptation": "Climate change adaptation",
        "mitigation": "Climate change mitigation",
        "emissions": "Greenhouse gas emissions",
        "resilience": "Climate resilience",
        "vulnerability": "Vulnerability (climate change)",
        "likelihood": "Likelihood",
        "uncertainty": "Uncertainty quantification",
        "equity": "Climate justice",
        "ipcc": "Intergovernmental Panel on Climate Change",
        "unfccc": "United Nations Framework Convention on Climate Change",
        "beccs": "Bioenergy with carbon capture and storage",
        "cdr": "Carbon dioxide removal",
        "ssp": "Shared Socioeconomic Pathways",
        "rcp": "Representative Concentration Pathway",
        "iam": "Integrated assessment modelling",
        "cop": "United Nations Climate Change conference",
        "dac": "Direct air capture",
        "methane": "Methane",
        "bioenergy": "Bioenergy",
        "hydrogen": "Hydrogen",
        // ── NEW TERMS TO ADD ─────────────────────────────────────────────

        // Acronyms & organisations
        "ndc": "Nationally determined contribution",
        "ndcs": "Nationally determined contribution",
        "unfccc": "United Nations Framework Convention on Climate Change",
        "kyoto protocol": "Kyoto Protocol",
        "kyoto": "Kyoto Protocol",
        "sdg": "Sustainable Development Goals",
        "sdgs": "Sustainable Development Goals",
        "sustainable development goals": "Sustainable Development Goals",
        "sids": "Small Island Developing States",
        "small island developing states": "Small Island Developing States",
        "least developed countries": "Least developed countries",
        "ldcs": "Least Developed Countries",
        "warsaw international mechanism": "Warsaw International Mechanism for Loss and Damage",
        "sendai framework": "Sendai Framework",
        "montreal protocol": "Montreal Protocol",
        "wim": "Warsaw International Mechanism for Loss and Damage",
        "afolu": "Agriculture, forestry and other land use",
        "co2-ffi": "Fossil fuel combustion",
        "co2-lulucf": "Land use, land-use change and forestry",
        "lulucf": "Land use, land-use change and forestry",
        "gwp": "Global warming potential",
        "gwp100": "Global warming potential",
        "f-gases": "Fluorinated gases",
        "fluorinated gases": "Fluorinated gases",
        "hfcs": "Hydrofluorocarbon",
        "pfcs": "Perfluorocarbon",
        "n2o": "Nitrous oxide",
        "nitrous oxide": "Nitrous oxide",
        "tropospheric ozone": "Tropospheric ozone",
        "stratospheric ozone": "Ozone layer",
        "ozone depletion": "Ozone depletion",
        "ch4": "Methane",

        // Climate science terms
        "emissions gap": "Emissions gap",
        "implementation gap": "Emissions gap",
        "carbon intensity": "Carbon intensity",
        "energy intensity": "Energy intensity",
        "hard limits": "Limits to adaptation",
        "soft limits": "Limits to adaptation",
        "adaptation limits": "Limits to adaptation",
        "transformational adaptation": "Climate change adaptation",
        "incremental adaptation": "Climate change adaptation",
        "adaptation gap": "Limits to adaptation",
        "slow-onset events": "Slow onset event",
        "compound flooding": "Compound event",
        "fire weather": "Wildfire",
        "marine heatwave": "Marine heatwave",
        "marine heatwaves": "Marine heatwave",
        "heavy precipitation": "Precipitation",
        "cold wave": "Cold wave",
        "cold waves": "Cold wave",
        "cryosphere": "Cryosphere",
        "biosphere": "Biosphere",
        "land degradation": "Land degradation",
        "desertification": "Desertification",
        "coastal wetlands": "Wetland",
        "peatlands": "Peat",
        "mangroves": "Mangrove",
        "agroforestry": "Agroforestry",
        "agroecological": "Agroecology",
        "soil organic carbon": "Soil carbon",
        "evapotranspiration": "Evapotranspiration",
        "water scarcity": "Water scarcity",
        "water security": "Water security",
        "vector-borne diseases": "Vector-borne disease",
        "zoonoses": "Zoonosis",
        "zoonosis": "Zoonosis",
        "displacement": "Climate refugee",
        "climate migration": "Climate refugee",
        "climate hazard": "Climate risk",
        "climate hazards": "Climate risk",
        "climate pledges": "Nationally determined contribution",
        "overshoot pathways": "Overshoot (climate)",

        // Energy & tech
        "photovoltaic": "Photovoltaics",
        "solar pv": "Photovoltaics",
        "pv": "Photovoltaics",
        "lithium-ion batteries": "Lithium-ion battery",
        "battery storage": "Battery storage",
        "electric vehicles": "Electric vehicle",
        "electric vehicle": "Electric vehicle",
        "evs": "Electric vehicle",
        "internal combustion engine": "Internal combustion engine",
        "levelised cost of energy": "Levelized cost of energy",
        "lcoe": "Levelized cost of energy",
        "fuel switching": "Fuel switching",
        "energy demand": "Energy demand",
        "demand side management": "Demand-side management",
        "direct air capture": "Direct air capture",
        "carbon removal": "Carbon dioxide removal",
        "co2 removals": "Carbon dioxide removal",

        // Policy & finance
        "green bonds": "Green bond",
        "green bond": "Green bond",
        "climate litigation": "Climate litigation",
        "carbon taxes": "Carbon tax",
        "concessional": "Concessional loan",
        "public-private partnerships": "Public–private partnership",
        "climate services": "Climate services",
        "anticipatory financing": "Anticipatory action",
        "disaster risk management": "Disaster risk reduction",
        "disaster risk reduction": "Disaster risk reduction",
        "climate literacy": "Climate literacy",
        "rights-based": "Rights-based approach",
        "just-transition": "Just transition",
        "social safety nets": "Social safety net",
        "social safety net": "Social safety net",
        "indigenous peoples": "Indigenous peoples",

        // Ecosystems
        "ecosystem services": "Ecosystem services",
        "biodiversity": "Biodiversity",
        "species loss": "Biodiversity loss",
        "habitat": "Habitat",
        "wetland": "Wetland",
        "wetlands": "Wetland",
        "coral reef": "Coral reef",
        "coral reefs": "Coral reef",
        "arctic sea ice": "Arctic sea ice",
        "snow cover": "Snow cover",
        "greenland ice sheet": "Greenland ice sheet",
        "land use change": "Land use, land-use change and forestry",
        "land-use change": "Land use, land-use change and forestry",
        "sustainable land management": "Sustainable land management",
        "urban green infrastructure": "Green infrastructure",
        "blue infrastructure": "Blue-green infrastructure",
        "urban greening": "Green infrastructure",
    };

    /* ── 2. INJECT CSS ────────────────────────────────────────────────── */
    const CSS = `
    .cw-term {
      color: #1a6b3c;
      text-decoration: underline dotted #1a6b3c;
      cursor: pointer;
      border-radius: 2px;
      transition: background 0.15s;
    }
    .cw-term:hover {
      background: #e8f5ee;
      text-decoration: underline solid #1a6b3c;
    }

    /* Tooltip */
    #cw-tooltip {
      display: none;
      position: fixed;
      z-index: 99997;
      background: #fff;
      border: 1px solid #c8e6d5;
      border-left: 4px solid #1a6b3c;
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
      color: #1a6b3c;
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
      width: min(800px, 93vw);
      height: 95vh;
      max-height: 95vh;
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
      background: #1a6b3c;
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
      color: #1a6b3c;
      text-decoration: none;
      font-weight: 500;
    }
    #cw-modal-footer a:hover { text-decoration: underline; }

    /* Loading spinner */
    @keyframes cw-spin { to { transform: rotate(360deg); } }
    .cw-spinner {
      width: 20px; height: 20px;
      border: 2px solid #ddd;
      border-top-color: #1a6b3c;
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
    const iframe = document.getElementById("cw-modal-iframe");
    const loadingDiv = document.getElementById("cw-modal-loading");

    function openModal(wikiTitle, displayText) {
        const mobileUrl = `https://en.m.wikipedia.org/wiki/${encodeURIComponent(wikiTitle)}`;
        const desktopUrl = `https://en.wikipedia.org/wiki/${encodeURIComponent(wikiTitle)}`;
        document.getElementById("cw-modal-title").textContent = displayText;
        document.getElementById("cw-modal-ext").href = desktopUrl;
        loadingDiv.style.display = "flex";
        iframe.src = "";
        iframe.onload = () => { loadingDiv.style.display = "none"; };
        iframe.src = mobileUrl;
        overlay.classList.add("cw-open");
    }

    function closeModal() {
        overlay.classList.remove("cw-open");
        iframe.src = "";
        loadingDiv.style.display = "flex";
    }

    document.getElementById("cw-modal-close").addEventListener("click", closeModal);
    overlay.addEventListener("click", (e) => { if (e.target === overlay) closeModal(); });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

    /* ── 5. WIKIPEDIA SUMMARY API + CACHE ────────────────────────────── */
    const summaryCache = {};

    function fetchSummary(wikiTitle, cb) {
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
        let x = e.clientX + 16;
        let y = e.clientY + 16;
        if (x + tw > window.innerWidth - pad) x = e.clientX - tw - 8;
        if (y + th > window.innerHeight - pad) y = e.clientY - th - 8;
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
            const wikiTitle = WIKI_MAP[key];
            if (!wikiTitle) {
                frag.appendChild(document.createTextNode(matched));
            } else {
                const a = document.createElement("a");
                a.className = "cw-term";
                a.href = "#";
                a.textContent = matched;
                a.dataset.wiki = wikiTitle;
                a.dataset.display = matched;

                a.addEventListener("mouseenter", (e) => {
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
        if (node.classList && node.classList.contains("cw-term")) return;

        // Collect children first (walking live NodeList while modifying it is unsafe)
        const children = Array.from(node.childNodes);
        children.forEach(walkNode);
    }

    /* ── 8. RUN ───────────────────────────────────────────────────────── */
    function run() {
        walkNode(document.body);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", run);
    } else {
        run();
    }
})();
