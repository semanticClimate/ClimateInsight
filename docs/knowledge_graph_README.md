# ClimateInsight knowledge graph: how it works

**Author:** Anusha · **Checked:** 2026-11-04, against the code on `main` (commit `7356e5c`) and the indexed database
**Short version:** [anusha_knowledge_graph_summary.md](anusha_knowledge_graph_summary.md)

Every number below was counted twice: once with the project's own code, and once independently by reading the database and source files directly. Where the two differed, the reason is given.

---

## 1. In one paragraph

ClimateInsight is a chatbot that answers climate questions only from the IPCC report and 12 research papers, citing the passage behind each claim. From the same passages we build a **knowledge graph** that connects climate concepts that occur in the same passage. **No AI is used to build the graph.** It comes only from exact text matching and counting, so every link can be traced back to the passages behind it. The LLM only writes the chatbot's answers.

## 2. Sources

- **IPCC:** AR6 Synthesis Report (SYR), Longer Report, 2023, HTML version (https://www.ipcc.ch/report/ar6/syr/), stored as `data/raw/ipcc_reference.html`. Not the Working Group reports.
- **Papers:** 12 open-access papers from Europe PMC, full-text XML in `data/raw/ocean_heatwaves_2026/`. The query is recorded in `backend/tests/fixtures/ocean_heatwaves_2026/review/review_table.edited.json`:
  `("marine heatwave" OR "ocean heat wave" OR "ocean heatwave") AND ("ocean current" OR "ocean circulation" OR "Gulf Stream" OR "AMOC") AND (HAS_FT:Y)`
- **Term list:** `encyclopedia/climate-wiki.js`, made by Aleena Harold Peter for the chatbot's Wikipedia tooltips. It has 730 entries: 721 distinct terms (9 entries are repeated), mapped to 508 Wikipedia articles.
  - **This is not the IPCC glossary.** The terms were chosen by hand.

## 3. How the graph is built

1. **Passages.** The report and papers are split into passages of up to 400 words, with 50 words of overlap (`CHUNK_SIZE`/`OVERLAP` in `backend/ingest/ingest.py`). There are **418 passages: 118 from the IPCC report, 300 from the papers.**
2. **Find terms.** Every passage is searched for every term in the list by **exact text match (lexical)**, longest term first (`ConceptMatcher` in `backend/knowledge_graph.py`).
   - Matching ignores case, except for short acronyms such as `NO` (nitric oxide), which must be written in capitals so the word "no" doesn't match.
   - "CO 2", which comes from flattened HTML subscripts, is read as CO₂.
   - "Likelihood" (IPCC wording like "very likely") is excluded, leaving **507 concepts** that could be found.
3. **Nodes.** Each concept found becomes a node. **273 of the 507 concepts appear in the passages.**
   - The **identifier is the Wikipedia article title**, so synonyms merge into one node: "sea-level rise" and "sea level rise" both become *Sea level rise*.
4. **Links.** Two concepts are linked when they occur in the same passage.
   - Links are undirected, labelled "occurs in the same passage", and weighted by the number of shared passages.
   - **5,286 links.** One extra dashed link joins a concept that shares no passage with the rest, through a shared source section, so the graph is in one piece.
5. **Clusters (the colours).** Louvain community detection in **networkx**, run once over the whole graph using the link weights, with a fixed random seed (42).
   - This gives **5 clusters**, each named after its most-mentioned concept: Climate change (95 concepts), Marine heatwave (81), Greenhouse gas emissions (61), Electrification (26) and Paris Agreement (10).
   - The question and the LLM have no part in this.
6. **Display.** **vis-network** draws the graph in the browser and does no analysis.
   - Showing all 5,286 links would be unreadable, so 828 are drawn: the strongest chain connecting every concept, plus each concept's 3 strongest links.
   - All links are still used for the clusters.

**Graph type:** this is a co-occurrence graph, with one kind of node. It is the one-mode projection of a bipartite graph of passages and terms, where two terms are joined if they share a passage. (Neel's graph keeps both kinds of node: figures and glossary terms.)

## 4. What happens when someone asks a question

The question **does not create nodes or links.** It only chooses which part of the existing graph to highlight.

1. The question is turned into 384 numbers by the embedding model `all-MiniLM-L6-v2` (sentence-transformers).
2. ChromaDB finds the **6 passages** closest to it (cosine similarity). This semantic search is the same one the chatbot uses.
3. Up to **15 concepts** from the question and those 6 passages are highlighted, with every link between them.
   - The concept named in the question becomes the large central node.
4. The LLM writes a short explanation using only those 6 passages, citing them as `[2.1]` (an IPCC section) or `[P1]` (a paper passage). Any citation that doesn't match a retrieved passage is removed.

**LLM:** Llama 3.2, `llama3.2:latest`, 3.2B parameters, Q4_K_M, Ollama ID `a80c4f17acd5`, run locally through Ollama, temperature 0.2.

## 5. Example: the Bay of Bengal question

**Question:** *How have marine heatwaves in the Bay of Bengal affected food security in India's coastal fishing communities?*

- **Marine heatwave** is a node in 56 passages and **Food security** in 11, all 11 from the IPCC report.
- **They never occur in the same passage.** A plain text search, independent of the graph, agrees: 0 passages, even counting "MHW" and "food insecurity".
- They are in different clusters, and stayed separate in all 100 random seeds tested. They are two steps apart: 31 concepts are linked to both, for example *Climate change*, *Coral reef*, *Heat wave* and *Livelihood*.
- **The missing link is fisheries.** "Fisher…" appears in 31 passages: 17 with marine heatwaves and 3 with food (in)security. But fisheries is not in the term list, so it can't appear as a node.
- **Only 2 passages mention the Bay of Bengal**, so this corpus can't answer the question itself.

**What this means:** it shows a gap in *this corpus and term list*, not evidence of a gap in climate research. The papers were selected for ocean circulation, not food.

## 6. Limits (stated so they aren't discovered later)

- **Links mean "discussed together", not "causes".** There are no relation types.
- **Exact matching misses variants not in the term list:**
  - 92 passages use only the abbreviation "MHW", and these are not counted under Marine heatwave.
  - One Bay of Bengal passage writes "marine heat wave" with a space and is also missed.
  - Plurals only match when listed: "marine heatwaves" is in the list, "floods" is not.
- **Common concepts dominate.** Climate change is in 90 passages with 216 links. Weights are raw counts, not adjusted for how common a term is.
- **70 of the 273 concepts appear in only one passage,** so their links rest on a single piece of text.
- **The number of clusters depends on the random seed.** Across 100 seeds: 4 clusters 50 times, 5 clusters 40 times, 6 clusters 7 times, 3 clusters 3 times. Agreement with seed 42 (adjusted Rand index) was between 0.56 and 1.00, median 0.74. "5 clusters" is the seed-42 result, not a fixed property.
- **Search only reads the start of most passages.** The embedding model reads at most 256 tokens, and 312 of the 418 passages are longer (median 504 tokens), so the end of those passages is not used when searching.
- **Citation checking removes invented citations, but doesn't prove a passage supports the claim.** Answers have not been systematically evaluated.
- **The corpus is unbalanced:** 300 passages from papers, 118 from the IPCC report. Renu suggested making the chatbot IPCC-only. That has not been done.

## 7. Software and licences

| Part | Tool | Licence |
|---|---|---|
| Graph and clusters | networkx 3.2.1 | BSD |
| Graph display | vis-network 9.1.9 (loaded from the jsDelivr CDN) | Apache-2.0 / MIT |
| Embeddings | sentence-transformers 2.7.0, `all-MiniLM-L6-v2` | Apache-2.0 |
| Vector database | ChromaDB 0.4.24 | Apache-2.0 |
| LLM runtime / model | Ollama / Llama 3.2 | MIT / Llama 3.2 Community Licence (open weights, not open source) |
| Web server | FastAPI 0.111.0, uvicorn 0.30.1 | MIT / BSD-3 |
| HTML parsing | Beautiful Soup 4.12.3 | MIT |

- **ClimateInsight's own licence is unclear and needs fixing.** The `LICENSE` file, which GitHub reads, is **Apache-2.0**. But `config.toml` and the README's licence table say **MIT**. The team should choose one.
- **It is not fully offline.** Search and the LLM run locally. The pages load vis-network and Google Fonts from the internet, and IPCC figures are fetched from ipcc.ch.

## 8. How to check it yourself

- Whole graph as JSON: `GET /api/knowledge-graph` (nodes, links, clusters, counts).
- Every passage behind a concept: `GET /api/knowledge-graph/concept?id=Food%20security`
- The passages behind a link: `GET /api/knowledge-graph/link?a=Marine%20heatwave&b=Ocean%20heat%20content`
  - For two concepts that aren't linked, such as Marine heatwave and Food security, this returns "not linked".
- Tests: `pytest backend/tests`
