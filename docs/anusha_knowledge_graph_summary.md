# ClimateInsight knowledge graph: one-page summary

**Author:** Anusha  · **Date:** 2026-11-04 · **Branch:** `anusha/knowledge-graph`, commit `069d61f`

**What I am trying to do:** Build a knowledge graph of the climate concepts in the ClimateInsight chatbot's source texts, so that every chatbot answer can be checked against the passages it came from.

**Source:**
- **IPCC:** IPCC AR6 Synthesis Report (SYR), Longer Report, 2023, HTML version (https://www.ipcc.ch/report/ar6/syr/), stored as `data/raw/ipcc_reference.html`.
- **EPMC query:** `("marine heatwave" OR "ocean heat wave" OR "ocean heatwave") AND ("ocean current" OR "ocean circulation" OR "Gulf Stream" OR "AMOC") AND (HAS_FT:Y)`, which gave 12 open-access papers.

**Technical plan:** Split the texts into ~400-word chunks (50-word overlap) and embed them with sentence-transformers `all-MiniLM-L6-v2` into ChromaDB. Find terms from `encyclopedia/climate-wiki.js` in each chunk with Python regex, link terms that share a chunk with networkx, cluster with Louvain (seed 42) and draw with vis-network. Answers come from Ollama `llama3.2:latest` (3.2B, Q4_K_M), served by Flask.

**My repository/corpus:**
- Code: https://github.com/semanticClimate/ClimateInsight/tree/anusha/knowledge-graph
- Papers: `data/raw/ocean_heatwaves_2026/` (12 Europe PMC XML full texts)
- IPCC report: `data/raw/ipcc_reference.html`

**What I did:** I started from Aleena Harold Peter's RAG chatbot and term list. I added a corpus-wide concept graph (`backend/knowledge_graph.py`), a page where a question is shown on the graph (`backend/concept_graph.py`, `frontend/concept_graph.html`) and tests (`backend/tests/test_knowledge_graph.py`). I also moved the chatbot to a fully local stack (Ollama only, no hosted API) and fixed citation collisions, duplicate ingest, unstable chunk IDs and false term matches (e.g. "no" being read as NO, nitric oxide).

**What results I got:** 418 passages (118 IPCC, 300 papers) → 507 Wikipedia-linked concepts in the term list → **273 found in the passages**, with **5,286 links** and **5 clusters**. The clusters are Climate change (95 concepts), Marine heatwave (81), Greenhouse gas emissions (61), Electrification (26) and Paris Agreement (10). One extra dashed link through a shared source section makes the graph fully connected. For the test question *"How have marine heatwaves in the Bay of Bengal affected food security in India's coastal fishing communities?"*, **Marine heatwave** (159 passages) and **Food security** (13 passages) **never occur in the same passage**.

**What the results mean:** The missing bridge is *fisheries*. It appears in 31 passages, 17 of them with marine heatwave, but it is not in the term list, so the graph cannot show the link. This is a gap in our corpus and term list, not evidence of a gap in climate research. The papers were chosen for ocean circulation, not food, and only 2 passages mention the Bay of Bengal. Links mean "discussed together", not "causes".

**Where knowledge graphs are involved:** Nodes are encyclopedia terms (identified by their Wikipedia article). Links mean two terms occur in the same passage, weighted by the number of shared passages. The graph is built without any AI, so every link can be traced to its source text. The LLM only writes the answer and adds no nodes or links.

```mermaid
flowchart LR
  A[IPCC AR6 SYR HTML<br/>+ 12 EPMC papers] --> B[418 chunks<br/>~400 words]
  B --> C[Find terms from<br/>climate-wiki.js]
  C --> D[Link terms in the<br/>same chunk<br/>networkx]
  D --> E[Louvain clusters<br/>273 nodes, 5 clusters]
  E --> F[vis-network graph]
  Q[Question] --> R[6 closest chunks<br/>ChromaDB]
  R --> F
  R --> L[Cited answer<br/>Llama 3.2 via Ollama]
```

Example from the graph: `Marine heatwave` and `Food security` sit in different clusters with no direct link. `Fisheries` would join them but is missing from the term list.

