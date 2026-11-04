<div align="center">

<img src="images/semantciClimatelogo.jpg" alt="semanticClimate logo" width="180">

# **Marine Heatwaves in the Bay of Bengal: Fisheries, Food Security and IPCC AR6**

**Authors:** Shweata Hedge, Renu Kumari, Larisa Beni, Neel Kumar, Aleena Harold Peter, Anusha Garg, Peter Murray-Rust, Simon Worthington

</div>

## **Abstract**

semanticClimate is a global online community of interns and volunteers creating Trustable semantic knowledge on climate Change. How do they explore a new subject - "El Nino in Latin America", "climate justice"...? They face complex language and acronyms ( ENSO, SST, Southern Oscillation, climate justice...) and many different tools.

We have created a powerful toolkit (AUKGET - Automatic Universal KnowledgeGraph Encyclopedia Toolkit - Python Apache2). A single automatic pipeline command (for any subject) will:

- query the recent scientific literature for a subject from OR load a corpus (e.g. UN-IPCC)
- create and clean a corpus (BAGIT)
- extract keyphrases (KBIR)
- build an encyclopedia based on Wikipedia entries for phrases
- find inter-entry relations through bibliography and Wikimedia proximity
- create and display a knowledgeGraph (corpus and encyclopedia tightly linked)
- remove false positives (visualising and analysing outlying clusters in the KG is particularly useful)

AUKGET is available as a colab script that can be used by highschool students or citizen groups or researchers. It is deliberately AI-free but the corpus is also usable as input to AI, e.g. an LLM RAG chatbot.

## **Workflow Diagram**

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

## **Examples**

### **Example Query and Cited Answer**

![Example query and cited answer with an embedded knowledge graph](images/query.png)

### **Knowledge Graph Visualization**

![Full knowledge graph visualization](images/kg.png)

## Sources

- **IPCC:** AR6 Synthesis Report (SYR), Longer Report, 2023, HTML version (https://www.ipcc.ch/report/ar6/syr/), stored as `data/raw/ipcc_reference.html`. Not the Working Group reports.
- **Papers:** 12 open-access papers from Europe PMC, full-text XML in `data/raw/ocean_heatwaves_2026/`. The query is recorded in `backend/tests/fixtures/ocean_heatwaves_2026/review/review_table.edited.json`:
  `("marine heatwave" OR "ocean heat wave" OR "ocean heatwave") AND ("ocean current" OR "ocean circulation" OR "Gulf Stream" OR "AMOC") AND (HAS_FT:Y)`
- **Term list:** `encyclopedia/climate-wiki.js`:
 Has 730 entries: 721 distinct terms (9 entries are repeated), mapped to 508 Wikipedia articles. **This is not the IPCC glossary.** The terms were chosen by hand.

## **Acknowledgements**

<div align="center">

<img src="images/semantciClimatelogo.jpg" alt="semanticClimate" width="125">&nbsp;&nbsp;
<img src="images/tib.png" alt="TIB – Leibniz Information Centre for Science and Technology" width="125">&nbsp;&nbsp;
<img src="images/nipgr.png" alt="National Institute of Plant Genome Research" width="85">&nbsp;&nbsp;
<img src="images/uc.png" alt="University of Cambridge" width="125">

</div>
