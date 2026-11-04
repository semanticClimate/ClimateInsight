# ClimateInsight knowledge graph: how it works

**Author:** Anusha · **Checked:** 2026-11-04, against the code on `main` (commit `9b34de1`) and the indexed database
**Short version:** [anusha_knowledge_graph_summary.md](anusha_knowledge_graph_summary.md)

Every number below was counted twice: once with the project's own code, and once independently by reading the database and source files directly. Where the two differed, the reason is given.

---

## 1. In one paragraph

ClimateInsight is a chatbot that answers climate questions only from the IPCC report and 12 research papers, citing the passage behind each claim. From the same passages we build a **knowledge graph** of climate concepts: two concepts are connected when they appear in the same passage. **No LLM and no trained AI model creates any part of the graph.**
- The nodes come from exact text matching against a fixed term list.
- The connections come from counting shared passages.
- The colours come from a clustering algorithm (Louvain).

So every node and every connection can be traced back to the passages behind it, and checked by hand.

## 2. Is AI used? Part by part

| Part | What creates it | Is an AI model involved? |
|---|---|---|
| The term list (which words *can* become nodes) | Made by hand by Aleena Harold Peter, who describes it as hand-coded words and their synonyms | No model is used in the code. Whether any AI tool helped choose the words is not recorded. |
| **Which nodes exist** | Exact text match of the term list in the 418 passages | **No** |
| Node names and identifiers | The Wikipedia article title written in the term list | **No** |
| **Connections (links) and their weights** | Counting how many passages two concepts share | **No** |
| Clusters (the colours) | The Louvain algorithm in networkx, a fixed procedure (not a trained model) | **No** |
| Cluster names | Our code picks each cluster's most-mentioned concept | **No** |
| Which part of the graph is highlighted for a question | The embedding model `all-MiniLM-L6-v2` finds the 6 closest passages | **Yes.** But it only *selects* existing nodes; it never adds or changes a node or connection. |
| The written answer and explanation | Llama 3.2 | **Yes.** Its output never changes the graph. |

**In the terms Peter uses:**
- Finding terms is **supervised**: it uses a fixed dictionary of terms decided in advance.
- Clustering is **unsupervised**: Louvain finds groups without being told any topics.

## 3. Sources

- **IPCC:** AR6 Synthesis Report (SYR), Longer Report, 2023, HTML version (https://www.ipcc.ch/report/ar6/syr/), stored as `data/raw/ipcc_reference.html`. Not the Working Group reports.
- **Papers:** 12 open-access papers from Europe PMC, full-text XML in `data/raw/ocean_heatwaves_2026/`. The query is recorded in `backend/tests/fixtures/ocean_heatwaves_2026/review/review_table.edited.json`:
  `("marine heatwave" OR "ocean heat wave" OR "ocean heatwave") AND ("ocean current" OR "ocean circulation" OR "Gulf Stream" OR "AMOC") AND (HAS_FT:Y)`
- **Term list:** `encyclopedia/climate-wiki.js`, made by Aleena Harold Peter for the chatbot's Wikipedia tooltips.
  - It has 730 entries: 721 distinct terms (9 entries are repeated), mapped to 508 Wikipedia articles.
  - **This is not the IPCC glossary.** The terms were chosen by hand.

## 4. How the graph is built, step by step

The whole graph is built **once, ahead of time**, by `backend/knowledge_graph.py`. Nobody asks a question during this. Section 6 gives the same steps with the exact code.

A **real example** runs through every step: passage 301, from IPCC SYR section 1 (Introduction). It contains the sentence:

> "It considers long-term characteristics, impacts, risks and costs in adaptation and mitigation pathways in the context of sustainable development."

### Step 1: Cut the texts into passages

The IPCC report and the 12 papers are cut into passages of up to 400 words, each overlapping the next by 50 words (`CHUNK_SIZE` and `OVERLAP` in `backend/ingest/ingest.py`). This gives **418 passages: 118 from the IPCC report and 300 from the papers.**

A passage is the unit for everything that follows. "Appearing together" means appearing in the same passage, not the same sentence.

### Step 2: The term list says which words to look for

Each line of `encyclopedia/climate-wiki.js` maps a word or phrase to a Wikipedia article. For example:

```
"adaptation":              "Climate change adaptation",
"mitigation":              "Climate change mitigation",
"sustainable development": "Sustainable development",
"sea level rise":          "Sea level rise",
"sea-level rise":          "Sea level rise",
```

Several spellings can point to the same article. They then count as **one concept**: "sea level rise" and "sea-level rise" are both the concept *Sea level rise*.

One concept is left out on purpose: *Likelihood*, which is IPCC wording such as "very likely". It appears almost everywhere and would connect everything to everything. Without it, **507 concepts** can be found.

### Step 3: Search every passage for every term

The code (`ConceptMatcher`) reads each passage and looks for every term **letter for letter**. This is called a *lexical* match.

- **Longer terms win.** "carbon dioxide removal" is matched as one term, not as "carbon dioxide" plus "removal".
- **Capital letters are ignored**, except for short terms of 4 letters or fewer, which must be written in capitals. So `NO` matches *Nitric oxide* but the word "no" doesn't, and `COP` matches but "cop" doesn't. A few real short words are allowed in lower case, such as "coal" and "oil".
- **"CO 2" is read as CO₂.** Turning the HTML into plain text splits chemical formulas like "CO<sub>2</sub>", so they are joined back first.
- **Anything not in the list is not found.** "floods" doesn't match *Flood*, because only "flood" is in the list. "MHW" doesn't match *Marine heatwave*.

**Example:** in passage 301, "adaptation", "mitigation" and "sustainable development" are matched. Across the whole passage, **11 concepts** are found:

> Biodiversity, Climate change, Climate change adaptation, Climate change mitigation, Intergovernmental Panel on Climate Change, Kyoto Protocol, Nationally determined contribution, Paris Agreement, Sustainable development, United Nations, United Nations Framework Convention on Climate Change.

A concept mentioned several times in one passage still counts **once** for that passage.

### Step 4: Each concept found becomes a node

A concept becomes a node if it is found in **at least one** passage. **273 of the 507 concepts** are found, so the graph has 273 nodes.

- **Identifier and label:** the Wikipedia article title from the term list (e.g. *Climate change adaptation*).
- **What each node stores:**
  - how many passages mention it (e.g. *Climate change adaptation*: 64)
  - which source sections and papers those passages come from
  - its strongest connections

### Step 5: Connect concepts that share a passage

For **each passage**, the code connects **every pair** of concepts found in it, and adds 1 to that pair's count.

**Example:** passage 301 has 11 concepts, which makes 55 pairs (11 × 10 ÷ 2). Each of those 55 pairs gets +1 from this passage, including *Climate change adaptation – Climate change mitigation*.

The same is done for all 418 passages, and the counts add up. *Climate change adaptation* and *Climate change mitigation* end up sharing **39 passages**, so their connection has **weight 39**.

**What a connection means:**
- **Label:** "occurs in the same passage".
- **Weight:** the number of passages the two concepts share.
- **No direction, no meaning beyond that.** It does *not* say one concept causes, increases or reduces the other.
- **Every connection can be checked.** The passages behind it are listed at `/api/knowledge-graph/link?a=…&b=…`.

This gives **5,286 connections**.

**The one exception: a dashed connection.** *Social cost of carbon* is the only concept that never shares a passage with another concept, so it would float on its own. To keep the graph in one piece, a fixed rule links it to *Climate change*: of all the concepts in the same paper, it is the one mentioned most across all sources. This link is drawn dashed and given a low weight (0.5), so it's never mistaken for a real shared passage.

### Step 6: Find clusters (the colours)

The **Louvain algorithm** (in networkx) looks for groups of concepts that are connected to each other more strongly than to the rest of the graph:
1. Every concept starts in its own group.
2. Concepts are moved, one at a time, into a neighbour's group whenever that makes the groups more tightly connected inside.
3. Each group is then treated as a single node, and step 2 is repeated, until nothing improves.

What it uses and doesn't use:
- **It only uses the connections and their weights.** It never reads the text, the question or anything from an AI model.
- **It returns unnamed groups.** Louvain does not name them. Our code names each group after its most-mentioned concept.
- **It uses a fixed random seed (42),** because the result depends on the order concepts are visited. With seed 42 there are **5 clusters**: Climate change (95 concepts), Marine heatwave (81), Greenhouse gas emissions (61), Electrification (26) and Paris Agreement (10). Other seeds give 3 to 6 clusters (see Limits).

**Example:** *Climate change adaptation* and *Climate change mitigation* are both in the *Climate change* cluster.

### Step 7: Draw it

**vis-network** draws the graph in the browser. It does no analysis.

Drawing all 5,286 connections would be unreadable, so 828 are drawn:
- the strongest chain that keeps every concept connected, plus
- each concept's 3 strongest connections.

All 5,286 are still used for the clusters.

**Graph type:** a co-occurrence graph with one kind of node. It is the *one-mode projection* of a bipartite graph of passages and terms: two terms are joined when they share a passage. Neel's graph keeps both kinds of node, figures and glossary terms.

## 5. What happens when someone asks a question

**A question does not create nodes or connections.** It only chooses which part of the existing graph to highlight. This is the only place an AI model touches the graph view.

1. **Find passages (AI: embedding model).** The question is turned into 384 numbers by `all-MiniLM-L6-v2` (sentence-transformers). ChromaDB finds the **6 passages** with the closest numbers (cosine similarity). This is the same search the chatbot uses.
2. **Pick concepts (no AI).** Using the same exact matching as Step 3, the code finds concepts in the question and in those 6 passages, and keeps up to **15**:
   - up to 3 concepts named in the question come first
   - the rest are ranked by how often they appear in the 6 passages, with mentions in closer-matching passages counting more
3. **Show them (no AI).** Those concepts are highlighted together with every connection that already exists between them. The concept named in the question is the large central node.
4. **Write the explanation (AI: LLM).** Llama 3.2 writes a short explanation using only those 6 passages, citing them as `[2.1]` (an IPCC section) or `[P1]` (a paper passage). Any citation that doesn't match a retrieved passage is removed. **Nothing the LLM writes is added to the graph.**

**LLM:** Llama 3.2, `llama3.2:latest`, 3.2B parameters, Q4_K_M, Ollama ID `a80c4f17acd5`, run locally through Ollama, temperature 0.2.

## 6. The technical process, in code order

This section is for anyone who wants to check or rebuild the system. It names the file, function and setting behind each step. Everything is in Python on the backend and JavaScript in the browser.

### A. Ingest: from documents to stored passages

This runs once, when the data is loaded (`backend/ingest/ingest.py`).

1. **Parse the IPCC report.** `parse_html()` in `backend/ingest/parser.py` reads `ipcc_reference.html` with Beautiful Soup (`html.parser`). It walks the `h1`–`h4`, `p` and `li` tags to split the report into its numbered sections (1, 2.1, 2.1.1 …).
2. **Parse the papers.** `backend/ingest/manifest_ingest/jats_to_sections.py` reads each paper's JATS XML with Beautiful Soup (`xml` parser) and takes its top-level `<sec>` sections (introduction, results …).
3. **Cut into passages.** `chunk_records()` in `backend/ingest/chunker.py` splits each section's text on whitespace into words.
   - A section of 400 words or fewer stays as one passage.
   - A longer section is cut with a sliding window of 400 words, moving 350 words each time, so neighbouring passages share 50 words.
4. **Give each passage a stable ID.** The format is `<paper ID or file name>__<section>__<first 12 characters of the SHA-1 hash of the text>`, e.g. `ipcc_reference__2.1.1__b317abe6aa57`. The same text always gets the same ID, so re-loading data doesn't create duplicates.
5. **Embed and store.** `backend/vectorstore/indexer.py` turns passages into vectors in batches of 64:
   - `embed()` in `backend/vectorstore/embedder.py` uses sentence-transformers `all-MiniLM-L6-v2` with `normalize_embeddings=True`, giving 384 numbers per passage.
   - The vectors, texts and metadata (section, title, paper ID, DOI) are added to a ChromaDB collection called `ipcc`, saved in `backend/chroma_db/`, which searches by cosine distance (`hnsw:space: cosine`).

### B. Build the graph: from passages to nodes, connections and clusters

All of this is in `backend/knowledge_graph.py`, function `_build()`. It uses no model.

1. **Load the passages.** `get_collection().get(include=["documents", "metadatas"])` reads all 418 passages and their metadata from ChromaDB. The stored vectors are not used here.
2. **Load the term list.** `load_encyclopedia()` reads `encyclopedia/climate-wiki.js` as text and pulls out every `"term": "Wikipedia title"` line inside `WIKI_MAP`, using the regular expression `^\s*"([^"]+)"\s*:\s*"([^"]+)"`. Terms are lower-cased into a Python dictionary {term → title}.
3. **Build one search pattern.** `ConceptMatcher` sorts all terms **longest first** and joins them into a single regular expression: `(?<![\w-])(term1|term2|…)(?![\w-])`, with `re.IGNORECASE`.
   - The `(?<![\w-])` and `(?![\w-])` parts mean a term must not be part of a longer word or hyphenated word. So "co" does not match inside "co-benefits".
   - Because longer terms come first in the pattern, "carbon dioxide removal" wins over "carbon dioxide".
4. **Clean the text first.** `_normalise()` re-joins chemical formulas that HTML extraction split apart, using two regular expressions: "N 2 O" → "N2O", and "CO 2", "CH 4", "SO 2" etc. → "CO2", "CH4", "SO2".
5. **Filter false matches.** For each match:
   - `_requires_capital()` marks short terms: 4 letters or fewer, except real words such as "coal", "oil", "ppm", plus a few longer acronyms such as "BECCS".
   - These only count if `_looks_like_acronym()` is true: at least two capital letters, or all letters capitals.
   - So `NO` and `COP` count, but "no" and "cop" don't.
6. **Record what each passage contains.** For each passage the code takes the **set** of concepts found, so repeats count once, and updates Python `Counter`s:
   - passages per concept (`concept_chunks`)
   - passages per concept per source section or paper (`concept_sources`)
   - the list of passage numbers for each concept (`concept_passages`), used later to show the evidence
7. **Count pairs.** `itertools.combinations(concepts, 2)` lists every pair of concepts in that passage, and `pair_weights[(a, b)] += 1` adds one to each.
8. **Make the graph.** A `networkx.Graph` (undirected):
   - `add_nodes_from()` adds every concept found
   - `add_edge(a, b, weight=w, kind="passage")` adds every counted pair
9. **Join any isolated parts.** `_bridge_components()` uses `nx.connected_components()` to find concepts cut off from the main graph. For each, it picks the main-graph concept that appears in the same source section or paper and is mentioned in the most passages overall, and adds `add_edge(..., weight=0.5, kind="source")`. In this data there is exactly one: *Social cost of carbon* → *Climate change*.
10. **Find clusters.** `nx.community.louvain_communities(G, weight="weight", seed=42)`, with networkx's defaults `resolution=1` and `threshold=1e-07`. Clusters are sorted by total passages, and each is labelled with its member that is mentioned in the most passages.
11. **Choose connections to draw.** The union of:
    - `nx.maximum_spanning_edges(G)` (Kruskal's algorithm): the strongest set of connections that keeps every concept connected
    - each concept's 3 strongest connections (`TOP_K = 3`)

    This gives 828 of the 5,286.
12. **Produce JSON.** Each node has:
    - `id` (the Wikipedia title), `count` (passages), `group` (cluster), `degree` (number of connections)
    - `kinds` (IPCC and/or paper)
    - its 10 strongest `neighbors`
    - its 8 most frequent `sources`

    Each connection has `from`, `to`, `weight` and `kind`. The graph also carries `groups` (clusters) and `stats` (totals).
13. **Cache.** `_state()` builds the graph once and keeps it in memory, behind a `threading.Lock`. It rebuilds only when the number of stored passages or the modification time of `climate-wiki.js` changes.

### C. Answer a question on the graph

This is `generate_concept_graph()` in `backend/concept_graph.py`. Questions longer than 1,000 characters are refused.

1. **Retrieve passages (embedding model).** `query_chunks(question, top_k=6)` in `backend/vectorstore/retriever.py` embeds the question with the same model and asks ChromaDB for the 6 nearest passages. Each gets a similarity `score = 1 − cosine distance`.
2. **Give each passage a citation key.** `assign_citation_keys()` gives IPCC passages their section number (e.g. `2.1`) and paper passages `P1`, `P2` … in retrieval order.
3. **Score concepts.** `focus_concepts()`, using the same `ConceptMatcher` as the graph:
   - each mention in the **question** adds 10 points
   - each mention in a **passage** adds that passage's similarity score (at least 0.1)
   - the top 15 concepts that exist in the graph are kept (`MAX_FOCUS = 15`)
4. **Pick the centre.** `main_concepts()` takes up to 3 concepts named in the question (`MAX_MAIN = 3`), most-mentioned in the corpus first. If the question names none, it takes the top-scoring concept. These go first in the list.
5. **Cut out the subgraph.** `subgraph()` uses `G.subgraph(concepts)` to return those concepts and every existing connection between them. Nothing new is added.
6. **Write the explanation (LLM).** `ask_llm()` in `backend/llm/client.py` sends one prompt to Ollama's local HTTP API (`POST http://localhost:11434/api/generate`, no streaming, 120-second timeout):
   - model `llama3.2:latest`, temperature 0.2, at most 500 tokens
   - the prompt holds the instructions, the question and the 6 passages, each labelled with its citation key. The passages are its only source text, and it is told to cite every claim.
7. **Check citations.** `strip_ghost_citations()` deletes any `[key]` in the answer that isn't one of the 6 retrieved keys. `extract_citations()` attaches the passage text to each remaining one.
8. **If Ollama is down,** the explanation becomes a list of the retrieved sources, and the graph part is returned unchanged.

### D. Show it in the browser

- **API routes** (FastAPI, `backend/app.py`):
  - `GET /api/knowledge-graph`: the whole graph as JSON
  - `GET /api/knowledge-graph/concept?id=…` and `GET /api/knowledge-graph/link?a=…&b=…`: the evidence. Up to 40 passages, each cut to the sentence(s) naming the concept(s), with any very long sentence shortened to 420 characters and the terms marked for highlighting.
  - `POST /api/concept-graph`: a question, as in C above
- **Drawing:** `frontend/concept_graph.html` and `frontend/js/concept_graph.js` put the JSON into vis-network `DataSet`s.
  - The layout uses the `forceAtlas2Based` physics solver: connected nodes pull together and others push apart.
  - On the full-graph page, physics is switched off after 300 stabilisation steps, so the picture stops moving.

## 7. Example: the Bay of Bengal question

**Question:** *How have marine heatwaves in the Bay of Bengal affected food security in India's coastal fishing communities?*

- **Marine heatwave** is a node in 56 passages and **Food security** in 11, all 11 from the IPCC report.
- **They never occur in the same passage.** A plain text search, independent of the graph, agrees: 0 passages, even counting "MHW" and "food insecurity".
- They are in different clusters, and stayed separate in all 100 random seeds tested. They are two steps apart: 31 concepts are linked to both, for example *Climate change*, *Coral reef*, *Heat wave* and *Livelihood*.
- **The missing link is fisheries.** "Fisher…" appears in 31 passages: 17 with marine heatwaves and 3 with food (in)security. But fisheries is not in the term list, so it can't appear as a node.
- **Only 2 passages mention the Bay of Bengal**, so this corpus can't answer the question itself.

**What this means:** it shows a gap in *this corpus and term list*, not evidence of a gap in climate research. The papers were selected for ocean circulation, not food.

## 8. Limits (stated so they aren't discovered later)

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

## 9. Software and licences

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

## 10. How to check it yourself

- Whole graph as JSON: `GET /api/knowledge-graph` (nodes, links, clusters, counts).
- Every passage behind a concept: `GET /api/knowledge-graph/concept?id=Food%20security`
- The passages behind a link: `GET /api/knowledge-graph/link?a=Marine%20heatwave&b=Ocean%20heat%20content`
  - For two concepts that aren't linked, such as Marine heatwave and Food security, this returns "not linked".
- Tests: `pytest backend/tests`
