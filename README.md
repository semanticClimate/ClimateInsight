# PaperInsight — 12-Paper Europe PMC RAG Chatbot

A clean-room rebuild of the original ClimateInsight chatbot, scoped **only to the 12 Europe PMC/JATS XML research papers** in `corpus/`.

The design deliberately separates three concerns that were mixed in the older bot:

1. **Ingestion** turns each JATS XML paper into stable, section-aware chunks.
2. **Retrieval** selects evidence from the 12-paper corpus using dense + lexical hybrid search.
3. **Citation rendering** maps short model citation handles (`C1`, `C2`, …) back to the exact retrieved chunk. The frontend never guesses whether a citation came from HTML or XML.

## Why this version is safer

- No IPCC HTML is indexed.
- Every chunk keeps its PMCID, DOI, article title, section path, and chunk index.
- The model sees only short citation handles (`C1`, `C2`, …), not fragile long section names.
- Backend validation drops citation handles that were not present in the retrieved evidence.
- Citation chips are built from the validated evidence objects, so a chip always opens the exact passage that was retrieved.
- Hybrid retrieval helps both scientific terminology (`marine heatwave`, `MHW`) and semantic paraphrases.
- An evaluation script is included so retrieval quality can be measured before trusting the chatbot.

## Stack

- Python 3.11+
- FastAPI
- ChromaDB
- Sentence Transformers (`all-MiniLM-L6-v2` by default)
- scikit-learn TF-IDF for lexical retrieval
- Local Ollama (`llama3.2` by default)
- Vanilla HTML/CSS/JS frontend

## 1. Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Install Ollama separately, then:

```bash
ollama pull llama3.2
```

## 2. Ingest the 12 papers

```bash
python -m backend.ingest.build_index
```

This creates `backend/chroma_db/` and a lexical index cache under `backend/index_cache/`.

## 3. Start the chatbot

```bash
uvicorn backend.app:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

## 4. Test retrieval before using the LLM

```bash
python -m backend.retrieval.evaluate
```

The evaluation set is in `tests/golden_questions.json`. Add real questions you care about and expected PMCIDs. Do not judge the bot only by whether the final answer sounds good; check whether the correct paper is retrieved in the top-k first.

## Citation pipeline

For a question, the backend does:

```text
question
  ↓
hybrid retrieval
  ↓
validated evidence: E1, E2, E3...
  ↓
LLM prompt with C1 → E1, C2 → E2...
  ↓
answer containing [C1] / [C2]
  ↓
validate citation handles
  ↓
API returns exact evidence objects
  ↓
frontend renders citation chips
```

The chip does **not** reconstruct a citation from a section title. It uses the exact evidence object returned by retrieval.

## Adding more papers later

Keep the architecture paper-scoped. Add XML files and regenerate the index. Do not reintroduce IPCC HTML into this collection. If you eventually need both IPCC and research papers, create separate corpus namespaces and perform an explicit corpus-level router before retrieval.
