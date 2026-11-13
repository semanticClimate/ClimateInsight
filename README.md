# ClimateInsight

ClimateInsight is an AI-powered chatbot that makes climate research easier to
explore through natural language conversations. Instead of searching through
lengthy reports and papers manually, users can ask questions in plain English,
read answers grounded in indexed scientific passages, and follow citations back
to their source material.

The application combines Retrieval-Augmented Generation (RAG), semantic search,
a locally hosted language model, an Encyclopedia of climate terms, and an
interactive knowledge graph. The chatbot explains the research, the Encyclopedia
provides definitions and descriptions, and the graph helps users explore how
concepts connect across the sources.

For a deeper explanation of the code, data, retrieval, and graph algorithms, see
the [architecture and developer guide](docs/ARCHITECTURE.md).

## How it works

ClimateInsight prepares two complementary resources: a searchable database of
scientific passages and an Encyclopedia vocabulary for identifying climate
concepts.

```text
IPCC report + research-paper XML
    |
    v
Parse sections -> overlapping chunks -> embeddings -> local ChromaDB
                                                          |
Question -> embedding -> retrieve 6 relevant passages <----+
                              |
                              +-> Ollama -> answer with source citations
                              |
                              +-> question focus on the concept graph
                                   + a separate cited explanation

IPCC report + official glossary HTML + approved paper XML
    |
    v
Extract terms -> add definitions and Wikipedia enrichment -> Encyclopedia
                                                               |
Indexed passages + Encyclopedia vocabulary ---------------------+
    |
    v
Match concepts -> find local co-occurrence evidence -> group and display graph
```

1. **Read and split the sources** (`backend/ingest/`). The IPCC reference HTML
   is read using its section structure and paragraph anchors. Research-paper JATS
   XML is read as sections such as abstract, introduction, methods, and results.
   Text is divided into chunks of about 400 words, with a 50-word overlap.
2. **Build the searchable index** (`backend/vectorstore/`). Each chunk is
   embedded using `all-MiniLM-L6-v2` and stored with its source metadata in a
   persistent local ChromaDB database. Questions use the same embedding model,
   allowing retrieval to match meaning rather than exact wording alone.
3. **Build the Encyclopedia** (`backend/encyclopedia/`). The configured IPCC
   report, official glossary HTML, and 12 approved PMC papers supply the terms.
   Extraction uses `txt2phrases` and the KBIR model. Official IPCC glossary
   definitions take priority; Wikipedia adds supplementary descriptions and
   identities. The generated vocabulary supports term matching and the viewer.
4. **Generate cited answers** (`backend/retrieval/` and `backend/llm/`). The
   six most similar passages are sent to the local Ollama model with instructions
   to answer from that evidence. Citations such as `[2.1]` for IPCC material and
   `[P1]` for papers are linked to the retrieved passages. Users can inspect the
   original text in the source panel.
5. **Construct the concept graph** (`backend/knowledge_graph/`). Encyclopedia
   concepts found in indexed passages become nodes. Concepts receive evidence
   links when they occur together within a sentence or a short overlapping text
   window. Link counts record how many passages contain that local evidence.
   NetworkX Louvain community detection groups related concepts, and weaker
   source-based bridges are displayed separately as dashed links.
6. **Show a question on the graph** (`backend/knowledge_graph/question.py`).
   The question and its retrieved passages identify a focus within the existing
   corpus graph. The local model generates a separate cited explanation. If
   Ollama is unavailable, the graph focus and source listing can still be shown.

Concept matching handles aliases, word boundaries, hyphen variations, capitalized
acronyms, and chemical formulas. This reduces false matches such as confusing the
word “no” with the chemical abbreviation `NO`.

The graph's structure comes from source text and graph algorithms. A connection
shows co-occurrence evidence or shared source membership; it does not establish
causation. Generated answers should also be checked against their cited passages.

## Local models and open-source tools

Retrieval and answer generation run locally with ChromaDB and Ollama. The project
does not require a hosted AI API key. Redis is optional: conversation history
falls back to memory when Redis is unavailable.

| Component | Tool | Role |
| --- | --- | --- |
| Language-model runtime | Ollama | Runs the local answer model |
| Default answer model | Llama 3.2, `llama3.2:latest` | Generates chat answers and graph explanations |
| Embeddings | Sentence Transformers, `all-MiniLM-L6-v2` | Represents passages and questions for semantic search |
| Vector database | ChromaDB | Stores and retrieves scientific passages |
| Backend | FastAPI and Uvicorn | Serves the API, source documents, and browser interface |
| Document parsing | Beautiful Soup and lxml | Reads HTML and research-paper XML |
| Term extraction | txt2phrases and KBIR | Extracts candidate Encyclopedia terms |
| Encyclopedia integration | semanticClimate Encyclopedia and amilib | Supports extraction and term-entry generation |
| Graph analysis | NetworkX | Matches relationships and detects communities |
| Graph display | vis-network | Renders the interactive graph in the browser |
| Frontend | HTML, CSS, and JavaScript | Provides chat, source navigation, and term viewing |
| Session storage | Redis, with an in-memory fallback | Retains conversation history |
| Optional sharing | cloudflared | Exposes a running local app through a temporary URL |

The default language model is distributed under its own model license.
Dependencies, models, Wikipedia content, and scientific documents retain their
respective licenses and attribution.

Internet access is needed for initial model downloads and uncached Wikipedia
enrichment. Some browser libraries, fonts, remote figures, and fallback Wikipedia
summaries also use external services, so the full interface is not completely
self-contained offline.

## Setup and installation

### Prerequisites

- **Python 3.11, 64-bit** and **Git**.
- **Ollama**, installed and running before you start the setup below. ClimateInsight
  uses it to answer questions locally; no hosted AI API key is needed.
- Internet access for the initial model and Python package downloads.
- Optional: **Redis** for persistent conversation history and **cloudflared** for
  temporary sharing.

**Windows and macOS:** install and open Ollama from
[ollama.com/download](https://ollama.com/download). **Linux:** follow the
[official Linux installation instructions](https://docs.ollama.com/linux).
Then, in PowerShell on Windows or Terminal on macOS/Linux, download the answer
model once:

```text
ollama pull llama3.2:latest
```

Keep Ollama running while you use ClimateInsight. The Windows/macOS app normally
starts the Ollama service for you. On Linux, or if the service is not already
running, start it in a separate terminal with `ollama serve`.

The frontend is served by the Python backend. No Node.js installation or frontend
build is required.

### Setup

Follow these steps in order. Run commands from a terminal in the folder where
you keep your projects.

#### 1. Download ClimateInsight

```shell
git clone https://github.com/semanticClimate/ClimateInsight.git
cd ClimateInsight
```

If you use a fork, replace the repository URL with your fork's URL. Run all
remaining commands from the **ClimateInsight project folder**.

The Encyclopedia helper files are already included; you only need to download
ClimateInsight.

#### 2. Set up the Encyclopedia environment

The Encyclopedia uses different Python packages from the chatbot, so it has its
own environment. Create and activate it, install its packages, and build the
Encyclopedia before switching to the chatbot environment.

**Windows — PowerShell:**

```powershell
py -3.11 -m venv .venv-encyclopedia
.\.venv-encyclopedia\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-encyclopedia.txt
python -m backend.encyclopedia.build --enrich-existing
deactivate
```

**macOS or Linux — Terminal:**

```bash
python3.11 -m venv .venv-encyclopedia
. .venv-encyclopedia/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-encyclopedia.txt
python -m backend.encyclopedia.build --enrich-existing
deactivate
```

If PowerShell blocks activation, skip `Activate.ps1` and `deactivate`, and use
`.\.venv-encyclopedia\Scripts\python.exe` instead of `python` for this step's
install and build commands.

This creates the Encyclopedia terms and definitions used by the app. It can take
a while the first time; later builds reuse cached work. The `deactivate` command
returns you to your regular terminal before you set up the chatbot environment.

#### 3. Set up the chatbot environment

Create and activate the chatbot environment, then install its packages. Keep
this environment active for ingestion and app startup.

**Windows — PowerShell:**

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

**macOS or Linux — Terminal:**

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Your terminal prompt should now show `(.venv)`. If PowerShell blocks activation,
run `.\.venv\Scripts\python.exe` instead of `python` in the commands below.
On Linux, install your distribution's Python virtual-environment support if
creating an environment fails.

#### 4. Prepare the searchable climate sources

The IPCC report, glossary, and research papers are already included in the
project. With `(.venv)` active, run these commands from the project folder:

```shell
python -m backend.ingest.ingest
python -m backend.ingest.ingest --dir data/raw/ocean_heatwaves_2026
```

The first command prepares the IPCC report; the second prepares the research
papers. The first run downloads an embedding model and may take a few minutes.

#### 5. Start ClimateInsight

With `(.venv)` still active, start the app from the project folder:

**Windows — PowerShell:**

```powershell
python .\backend\app.py
```

**macOS or Linux — Terminal:**

```bash
python backend/app.py
```

The FastAPI backend serves both the API and the web interface, so only one
application server is needed. Open **http://localhost:5001**.

- **Chat:** ask a climate question and click a citation to inspect its passage.
- **Source reader:** navigate the IPCC report and research papers, including
  their available figures.
- **Encyclopedia:** open **http://localhost:5001/ipcc-encyclopedia** to browse
  term entries, definitions, and source examples.
- **Concept graph:** open **http://localhost:5001/concept-graph** to explore
  communities, concepts, connections, and supporting evidence. A question can
  focus the graph on relevant concepts.

The graph is constructed automatically on its first request from the indexed
passages and Encyclopedia vocabulary. There is no separate graph build command.

Keep the application terminal and Ollama running. For later sessions, open
Ollama and activate `.venv` from the project folder. In PowerShell, run
`.\.venv\Scripts\Activate.ps1`; on macOS or Linux, run
`source .venv/bin/activate`. Then start the app with `python .\backend\app.py`
on Windows or `python backend/app.py` on macOS or Linux. Repeat ingestion and
the Encyclopedia build when updating their sources, then restart the app.

Run only one backend on port 5001. If startup reports `[Errno 10048]` or an
occupied port, check whether **http://localhost:5001** already opens. To restart
the backend, press **Ctrl+C** in its existing terminal, then run the startup
command again. A Redis-unavailable message followed by an in-memory fallback is
expected when optional Redis is not running.

**http://localhost:5001/api/health** checks whether the backend responds; testing
chat, citations, the Encyclopedia, and the graph also checks the dependencies
those features need.

## Configuration

`config.toml` contains project metadata and Encyclopedia settings, including
the source list and extraction limits. The answer model and server settings are
read from environment variables.

| Variable | Default | Purpose |
| --- | --- | --- |
| `PORT` | `5001` | Application port |
| `HOST` | `0.0.0.0` outside development mode | Server bind address |
| `DEV` | `0` | Set to `1` for development reload on `127.0.0.1` |
| `OLLAMA_MODEL` | `llama3.2:latest` | Model used for chat and graph explanations |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server |
| `OLLAMA_TIMEOUT` | `120` | Seconds to wait for a model response |
| `REDIS_URL` | `redis://localhost:6379/0` | Optional persistent session store |
| `SESSION_TTL_SECONDS` | `86400` | Redis session expiry in seconds |

For example, to change the application port before starting the backend:

**PowerShell:**

```powershell
$env:PORT = "8080"
python -m backend.app
```

**macOS or Linux:**

```bash
export PORT=8080
python -m backend.app
```

To use another Ollama model, download it with `ollama pull <model-name>`, set
`OLLAMA_MODEL` to the same name, and restart the backend.

## Project structure

```text
ClimateInsight/
├── backend/
│   ├── app.py                  # Application entry point
│   ├── api/                    # HTTP routes and response formatting
│   ├── core/                   # Shared paths and conversation sessions
│   ├── ingest/                 # HTML/XML parsing and passage chunking
│   ├── vectorstore/            # Embeddings, indexing, and similarity search
│   ├── retrieval/              # Evidence preparation, prompts, and citations
│   ├── llm/                    # Ollama client and prompt templates
│   ├── encyclopedia/           # Term extraction, glossary, and viewer integration
│   ├── knowledge_graph/        # Graph construction, grouping, and question focus
│   ├── generated_artifacts/    # Generated concept vocabulary
│   ├── chroma_db/              # Local vector database; excluded from Git
│   └── tests/                  # Backend tests
├── frontend/                   # HTML, CSS, and browser JavaScript
├── encyclopedia/               # Bundled Encyclopedia helpers; no second clone
├── data/raw/                   # Scientific source documents and paper assets
├── encyclopedia_assets/        # Browser term viewer and generated publications
├── docs/                       # Architecture and maintenance documentation
├── scripts/                    # Utilities, including temporary sharing
├── config.toml                 # Project metadata and Encyclopedia configuration
├── requirements.txt            # Chatbot runtime dependencies
└── requirements-encyclopedia.txt # Separate Encyclopedia build dependencies
```

Scientific originals belong in `data/raw/`; Python integration code belongs in
`backend/encyclopedia/`; generated browser publications belong in
`encyclopedia_assets/`. The vocabulary and Chroma database have separate roles
and locations.

## Updating the sources

Stop the backend before updating its index or generated Encyclopedia outputs.

| Change | What to rerun |
| --- | --- |
| IPCC report text | IPCC ingestion, then the Encyclopedia build |
| An approved paper's XML | Paper-directory ingestion, then the Encyclopedia build |
| Official glossary HTML | Encyclopedia build |
| A new paper | Paper-directory ingestion; also list its XML in `config.toml` and rebuild to include its terms |
| Paper display HTML or images only, with matching XML unchanged | Refresh the browser |
| Encyclopedia extraction settings | Encyclopedia build |

Use `.venv` for ingestion and `.venv-encyclopedia` for building. Restart the
backend afterward so the graph and vocabulary caches reflect the update.
Removing a source requires explicit index cleanup or a fresh database followed
by ingestion of the remaining sources.

To refresh Wikipedia enrichment while reusing valid extraction caches, add
`--enrich-existing` to the Encyclopedia build command using the build
environment's Python.

Keep source changes and their generated vocabulary/publications together when
sharing the repository. Keep virtual environments, local model caches, and
`backend/chroma_db/` out of Git.

## Common problems

| Symptom | What to check |
| --- | --- |
| Cannot connect to Ollama | Open the Ollama app or run `ollama serve` |
| Answer model is missing | Run `ollama pull llama3.2:latest`, or pull the model named in `OLLAMA_MODEL` |
| ChromaDB is empty | Run both ingestion commands in step 4 |
| Ingestion reports skipped files | Review the warnings and check the affected HTML/XML |
| Evidence is insufficient | Check that the relevant sources were ingested and try a more focused question |
| Encyclopedia is missing or stale | Rerun the build command in step 2 after updating approved source documents |
| Encyclopedia integration cannot be loaded | Use the bundled `encyclopedia/` folder and `repository = "."`; remove a stale `CLIMATEINSIGHT_ENCYCLOPEDIA_REPO` override if set |
| Concept graph is empty or unavailable | Check ingestion and the Encyclopedia build, then restart the backend |
| Paper figures are missing | Keep the companion assets folder beside the paper HTML |
| Python cannot find `backend` | Run module commands from the project root |
| Port 5001 is occupied | Set `PORT` before starting the application |

## Sharing the application

To share a running local instance temporarily:

1. Install `cloudflared` and make sure it is on your `PATH`.
2. Start ClimateInsight as described in step 5.
3. Open another terminal in the project folder and activate `.venv`:

   **Windows — PowerShell:**

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

   **macOS or Linux — Terminal:**

   ```bash
   source .venv/bin/activate
   ```

4. In that terminal, run:

   ```shell
   python scripts/inject-tunnel.py
   ```

The script prints a temporary public URL. Anyone with the link can use the app
while the backend and tunnel remain running. If you changed `PORT`, use the same
value in the tunnel terminal. Press **Ctrl+C** to stop sharing.

## Development and tests

With the chatbot environment active:

```shell
python -m pip install pytest httpx
python -m pytest backend/tests/ -v
```

The [developer guide](docs/ARCHITECTURE.md) covers ingestion formats, citations,
Encyclopedia provenance, graph evidence, API routes, configuration, and maintenance
in greater detail.

ClimateInsight is part of [semanticClimate](https://github.com/semanticClimate).
See [LICENSE](LICENSE) for the repository's license terms. Dependencies, models,
and source documents retain their own licenses and attribution.
