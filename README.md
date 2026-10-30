# ClimateInsight

ClimateInsight is an AI-powered chatbot designed to make information from the Intergovernmental Panel on Climate Change (IPCC) more accessible through natural language conversations. Instead of manually searching through lengthy reports, users can ask questions in plain English and receive context-aware responses grounded in the indexed IPCC reference material, with every claim linked back to the section it came from. A **knowledge graph** connects every climate concept found in the sources, and any answer can be shown on it.

The project was developed to demonstrate how Retrieval-Augmented Generation (RAG), semantic search, and locally hosted Large Language Models (LLMs) can be combined to create an interpretable, privacy-friendly question-answering system. Rather than relying on cloud-hosted AI services, ClimateInsight performs retrieval and inference locally using Ollama and ChromaDB, making it suitable for experimentation, education, and offline development.

---

# 🌍 How It Works

```text
IPCC AR6 HTML report ─┐
Research papers (XML) ┴─► parse into sections ─► split into chunks ─► embed ─► ChromaDB
                                                                                  │
Question ─► embed ─► retrieve the 6 most similar chunks ◄─────────────────────────┘
                              │
                              ├─► Chat:       local LLM answers using ONLY those chunks,
                              │               citing them as [2.1] (IPCC) or [P1] (paper)
                              │
                              └─► Knowledge graph: highlight the question's concepts on
                                                   the corpus-wide concept graph + cited explanation

Encyclopedia terms (encyclopedia/climate-wiki.js) ─► find concepts in every chunk ─► link concepts
                                                     that share a passage ─► clusters (networkx)
```

1. **Ingest** (`backend/ingest/`): the IPCC HTML report is split into its numbered sections (1, 2.1, 2.1.1 …); research-paper JATS XML is split into abstract / introduction / results … Each section is cut into overlapping ~400-word chunks.
2. **Index** (`backend/vectorstore/`): chunks are embedded with `all-MiniLM-L6-v2` and stored in a local ChromaDB database.
3. **Answer** (`backend/retrieval/`): the question is embedded, the closest chunks are retrieved, and the local Ollama model answers from them only. Citations are mapped back to the exact passage, and clicking one scrolls the IPCC report to that section.
4. **Knowledge graph** (`backend/knowledge_graph.py`): every concept from the climate term list in `encyclopedia/climate-wiki.js` (term → Wikipedia article) found in the indexed passages becomes a node; two concepts are linked when they occur in the same passage, weighted by how often. Clusters come from Louvain community detection. This step is deliberately AI-free, so every link can be traced to its passages. Concepts that never share a passage with the rest are joined through their source section (dashed link), so the whole graph is connected.
5. **Question view** (`backend/concept_graph.py`): a question highlights the concepts in its retrieved passages, shows every link between them, and the local model writes a cited explanation. If Ollama is not running, the graph still works and the sources are listed instead.

False positives are filtered before linking: short acronyms such as `NO` or `CO` only count when written in capitals (not the words "no"/"co"), flattened chemical formulas like "CO 2" are read as CO₂, and IPCC likelihood language ("very likely") is not treated as a topic.

---

# 🔓 Fully Open Source

Every component runs locally. No hosted AI service or API key is used.

| Part | Tool | Licence |
|---|---|---|
| LLM runtime | [Ollama](https://github.com/ollama/ollama) | MIT |
| Default model | Llama 3.2 (`llama3.2:latest`) — any Ollama model can be used | Llama 3.2 Community Licence (open weights) |
| Embeddings | [sentence-transformers](https://github.com/UKPLab/sentence-transformers) `all-MiniLM-L6-v2` | Apache-2.0 |
| Vector database | [ChromaDB](https://github.com/chroma-core/chroma) | Apache-2.0 |
| Backend | [Flask](https://github.com/pallets/flask) | BSD-3 |
| Graph analysis | [networkx](https://github.com/networkx/networkx) | BSD-3 |
| Graph renderer | [vis-network](https://github.com/visjs/vis-network) | Apache-2.0 / MIT |
| Font | Jost | SIL Open Font Licence |
| Encyclopedia tooltips | Wikipedia | CC BY-SA |
| Tunnel (optional) | [cloudflared](https://github.com/cloudflare/cloudflared) | Apache-2.0 |
| ClimateInsight itself | this repository | MIT |

> If you need a fully open-*source* model licence (rather than open weights), use an Apache-2.0 model such as Mistral: `ollama pull mistral` and set `OLLAMA_MODEL=mistral`.

---

# ⚙️ Setup & Installation

## Prerequisites

- Python **3.10 or later**
- Git
- Ollama
- (Optional) Cloudflared, if you plan to share the application externally

## 1. Clone the Repository

```bash
git clone https://github.com/semanticClimate/ClimateInsight.git
cd ClimateInsight
```

## 2. Create and Activate a Virtual Environment

A virtual environment keeps this project's Python packages isolated from the rest of your computer.

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Your prompt should now start with `(.venv)`.

## 3. Install Project Dependencies

```bash
pip install -r requirements.txt
```

## 4. Install Ollama and Download the Model

Download Ollama from https://ollama.com/, then start it and pull the model (once):

```bash
ollama serve
ollama pull llama3.2:latest
```

Keep `ollama serve` running while using the chatbot. (On macOS the Ollama app starts the server for you.)

## 5. Prepare the Data

Place the IPCC HTML reference document at:

```text
data/raw/ipcc_reference.html
```

Optional: put research papers (JATS `.xml`, e.g. from Europe PMC) in a folder such as `data/raw/ocean_heatwaves_2026/`. If a folder holds both `PMC123.xml` and a rendered `123.html` of the same paper, only the XML is ingested.

## 6. Build the Vector Database

Run the ingestion from the `backend` directory:

```bash
cd backend
python -m ingest.ingest                                    # IPCC report
python -m ingest.ingest --dir ../data/raw/ocean_heatwaves_2026   # optional: papers
```

Re-running is safe: unchanged chunks are skipped, and chunks from a re-ingested file that no longer exist are removed.

> **Note:** The first ingestion downloads the embedding model (`all-MiniLM-L6-v2`). This may take a few minutes.

---

# 🚀 Running the Application

The Flask backend serves both the API and the web interface, so there is only one server to start.

```bash
cd backend
python app.py
```

Open http://localhost:5001 in your browser.

- **Chat**: ask a question; click a citation chip to see the source passage.
- **Knowledge graph**: click **Knowledge graph** under any answer, or open http://localhost:5001/concept-graph to explore the whole graph: ask a question to highlight its concepts, click a concept for its Wikipedia link, connections and sources, filter by cluster, or download the graph as JSON.

> Port 5000 is used by AirPlay Receiver on macOS, so ClimateInsight uses **5001**. Change it with `PORT=8080 python app.py`.

## Configuration (environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `5001` | Backend port |
| `OLLAMA_MODEL` | `llama3.2:latest` | Model used for chat and mind maps |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server |
| `OLLAMA_TIMEOUT` | `120` | Seconds to wait for the model |
| `REDIS_URL` | `redis://localhost:6379/0` | Optional session store (falls back to memory) |
| `FLASK_DEBUG` | `0` | Set to `1` for the Flask debugger (binds to 127.0.0.1 only) |

---

# 🌐 Sharing the App (Cloudflare Tunnel)

To share the chatbot with others or use it from another device without deploying a server:

1. Install `cloudflared` and make sure it is on your `PATH`.
2. Start the app as above (`python app.py`).
3. From the project root, run:

```bash
python scripts/inject-tunnel.py
```

The script creates a temporary public URL for the app and prints it. Anyone with the link can use the app while the script runs. Press `Ctrl + C` to close the tunnel.

> Never run the tunnel with `FLASK_DEBUG=1`: the debugger allows anyone with the link to run code on your computer.
