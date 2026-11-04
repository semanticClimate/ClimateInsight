# ClimateInsight knowledge graph: how it works

**Author:** Anusha · **Checked:** 2026-11-04, against the code on `main` (commit `410730f`) and the indexed database
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

The whole graph is built **once, ahead of time**, by `backend/knowledge_graph.py`. Nobody asks a question during this.

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

**The one exception: a dashed connection.** *Social cost of carbon* never shares a passage with any other concept, so it would be left on its own. It appears in only one passage, in the paper `PMC10808424`. A fixed rule joins it to the concept that appears in that same paper and is mentioned in the most passages overall: *Climate change* (90 passages, 2 of them in that paper). It gets a low weight of 0.5 and is drawn dashed, so it's never confused with a real shared passage.

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

## 6. Example: the Bay of Bengal question

**Question:** *How have marine heatwaves in the Bay of Bengal affected food security in India's coastal fishing communities?*

- **Marine heatwave** is a node in 56 passages and **Food security** in 11, all 11 from the IPCC report.
- **They never occur in the same passage.** A plain text search, independent of the graph, agrees: 0 passages, even counting "MHW" and "food insecurity".
- They are in different clusters, and stayed separate in all 100 random seeds tested. They are two steps apart: 31 concepts are linked to both, for example *Climate change*, *Coral reef*, *Heat wave* and *Livelihood*.
- **The missing link is fisheries.** "Fisher…" appears in 31 passages: 17 with marine heatwaves and 3 with food (in)security. But fisheries is not in the term list, so it can't appear as a node.
- **Only 2 passages mention the Bay of Bengal**, so this corpus can't answer the question itself.

**What this means:** it shows a gap in *this corpus and term list*, not evidence of a gap in climate research. The papers were selected for ocean circulation, not food.

## 7. Limits (stated so they aren't discovered later)

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

## 8. Software and licences

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

## 9. How to check it yourself

- Whole graph as JSON: `GET /api/knowledge-graph` (nodes, links, clusters, counts).
- Every passage behind a concept: `GET /api/knowledge-graph/concept?id=Food%20security`
- The passages behind a link: `GET /api/knowledge-graph/link?a=Marine%20heatwave&b=Ocean%20heat%20content`
  - For two concepts that aren't linked, such as Marine heatwave and Food security, this returns "not linked".
- Tests: `pytest backend/tests`
