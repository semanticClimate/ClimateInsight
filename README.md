# ClimateInsight

ClimateInsight helps you explore climate research through a chatbot, an
Encyclopedia of climate terms, and an interactive concept graph. Answers use
indexed IPCC and research-paper passages and include links to their evidence.
The answer model runs locally through Ollama.

For a detailed explanation of the code, retrieval, graph algorithms, and data
files, read the [architecture and developer guide](docs/ARCHITECTURE.md).

## What you need

- **Python 3.11, 64-bit** for the pinned project dependencies.
- **Git** to download the repositories.
- **Ollama** to run the local answer model.
- Internet access for the first model downloads and externally hosted viewer assets.

A separate Redis server is optional. The chatbot uses in-memory conversation
history when Redis is unavailable. You do not need Node.js or a frontend build.

## 1. Download the project

Run these commands in the folder where you keep your projects. The two
repositories should sit beside each other:

```bash
git clone https://github.com/semanticClimate/ClimateInsight.git
git clone https://github.com/semanticClimate/encyclopedia.git
cd ClimateInsight
```

```text
your-projects/
├── ClimateInsight/
└── encyclopedia/
```

If you use your own fork, replace the first repository URL with your fork's URL.
If the repositories are already present, keep them and enter `ClimateInsight`.
The Encyclopedia checkout must provide `encyclopedia/exchange.py`; its location
is configured as `../encyclopedia` in `config.toml`.
Use the matching integration checkout if that file is absent from the branch
you cloned; the [dependency details](docs/ARCHITECTURE.md#three-different-encyclopedia-locations)
explain what needs to be available.

## 2. Set up Python for your operating system

Choose the instructions for your system. Run them inside `ClimateInsight`.

### Windows: PowerShell

Install Python 3.11 from [python.org](https://www.python.org/downloads/) and Git
from [git-scm.com](https://git-scm.com/downloads), then open PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, you can run the environment's Python directly
instead. For example, use `.\.venv\Scripts\python.exe` wherever the remaining
instructions say `python`.

### macOS: Terminal

Install Python 3.11 and Git, then open Terminal. Use a Python installation that
matches your Mac's processor:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Linux: Terminal

Install Git and Python 3.11 with virtual-environment support using your
distribution's package manager, then open a terminal:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The activation commands follow Python's [virtual-environment documentation](https://docs.python.org/3.11/library/venv.html).
The runtime dependencies have been checked locally on Windows with Python 3.11;
macOS and Linux installations also depend on wheels being available for your
processor. If the pinned Torch version is unavailable, consult the
[PyTorch platform/version instructions](https://pytorch.org/get-started/previous-versions/)
before changing dependency versions.

## 3. Start Ollama and download the answer model

**Windows and macOS:** install and open Ollama from
[ollama.com/download](https://ollama.com/download).

**Linux:** use the [official Linux installation instructions](https://docs.ollama.com/linux):

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

In a terminal, download the model once:

```bash
ollama pull llama3.2:latest
```

Keep Ollama running while using the chatbot. If it is not already running as an
app or service, start it in a separate terminal with:

```bash
ollama serve
```

The [Ollama quickstart](https://docs.ollama.com/quickstart) describes the local
model workflow. This project does not require a hosted AI API key.

## 4. Build the searchable database

Return to the project terminal with `.venv` activated. Stay in the project root:

```bash
python -m backend.ingest.ingest
python -m backend.ingest.ingest --dir data/raw/ocean_heatwaves_2026
```

The first command adds the IPCC report. The second adds the research papers.
Both use the same database and preserve the other source's passages. The first
run downloads the embedding model, which can take a few minutes.

You only need to repeat ingestion when adding or changing scientific source
text, or when creating a fresh local database. Moving the Python modules into
their new folders does not require rebuilding an existing index.

## 5. Run the chatbot

From the project root:

```bash
python -m backend.app
```

Open **http://localhost:5001**. Keep this terminal and Ollama running.

- Ask a climate question and click a citation to inspect its source passage.
- Use the source navigator to read the IPCC report or a research paper.
- Open **http://localhost:5001/concept-graph** to explore concepts, groups, and
  the evidence behind their connections.

For later sessions, activate `.venv`, start Ollama if needed, and run
`python -m backend.app`. Restart the backend after code changes or ingestion.

## Where the files belong

| Folder/file | What belongs there |
| --- | --- |
| `backend/encyclopedia/` | Encyclopedia/glossary Python code |
| `backend/knowledge_graph/` | Graph generation, grouping, and question focus |
| `backend/ingest/` | Reading documents and splitting them into passages |
| `backend/vectorstore/` | Embeddings, Chroma indexing, and similarity search |
| `backend/retrieval/` and `backend/llm/` | Evidence preparation, prompts, answers, citations |
| `backend/api/` and `backend/core/` | Web routes, response formatting, paths, sessions |
| `frontend/` | Browser interface |
| `data/raw/ipcc_reference.html` | IPCC scientific source |
| `data/raw/IPCC_AR6_SYR_Glossary.html` | Approved glossary HTML used for Encyclopedia terms and definitions |
| `data/raw/ocean_heatwaves_2026/` | Matching paper XML/HTML and companion image folders |
| `encyclopedia_assets/` | Browser term viewer and generated Encyclopedia publications |
| `backend/generated_artifacts/` | Installed concept vocabulary |
| `backend/chroma_db/` | Local searchable database; kept out of Git |

`data/` holds the original scientific documents. `backend/encyclopedia/` holds
Python code; `encyclopedia_assets/` holds the files that code displays in the
browser. `backend/generated_artifacts/` holds the vocabulary built from those
documents. Put replacement papers in `data/raw/ocean_heatwaves_2026/`.

For a paper such as PMC10468509, keep `PMC10468509.xml` and
`PMC10468509.html` together in the paper folder. The XML feeds ingestion; the
HTML controls the reader's appearance. Keep any `PMC<number>_assets/` folder
beside its HTML. Older numeric HTML filenames are also supported.

## Encyclopedia rebuilds are separate

Normal use reads the generated vocabulary and glossary already stored in this
repository. You do not need to rerun phrase extraction to start the application.

The Encyclopedia extracts terms only from `data/raw/ipcc_reference.html`,
`data/raw/IPCC_AR6_SYR_Glossary.html`, and the 12 PMC XML files explicitly listed
in `config.toml`. Wikipedia supplies supplementary descriptions and identities;
official glossary definitions take priority. Wikipedia text is separate from
the scientific passages retrieved by the chatbot.

If you change the report, glossary HTML, or a listed PMC XML, rebuild the Encyclopedia in a
separate environment with `requirements-encyclopedia.txt`, using
`python -m backend.encyclopedia.build`. Do not install those build dependencies
over the chatbot environment: their Torch requirements differ. Full build and
maintenance instructions are in the [developer guide](docs/ARCHITECTURE.md#12-commands-and-maintenance).

The build writes `encyclopedia_assets/generated/source_manifest.json` with the
14 source filenames, their hashes, and selected term counts. This records exactly
which documents supplied terms. Unlisted files are not scanned. Successful
extraction and Wikipedia lookups are cached for subsequent builds.

To request fresh Wikipedia enrichment while reusing valid extraction results,
run `python -m backend.encyclopedia.build --enrich-existing` in the build environment.

For reporting: **The Encyclopedia extracts terms from the IPCC report, its
glossary HTML and 12 selected PMC papers, and uses Wikipedia for supplementary
descriptions and identities. Official glossary definitions take priority.**

## Common problems

| Symptom | What to check |
| --- | --- |
| Cannot connect to Ollama | Open Ollama or run `ollama serve` |
| Model is missing | Run `ollama pull llama3.2:latest` |
| ChromaDB is empty | Run the two ingestion commands above |
| Answer says evidence is insufficient | Check that the relevant sources were ingested; try a more focused question |
| Encyclopedia package is missing | Check the sibling checkout and `config.toml` repository path |
| Encyclopedia is stale | Rebuild after changing any of the 14 configured source documents |
| Paper figures are missing | Keep the companion assets folder beside the HTML |
| Python cannot find `backend` | Run module commands from the project root |
| Port 5001 is occupied | Set `PORT` in the shell before starting the backend |

Set variables in PowerShell with `$env:PORT = "8080"`, or in macOS/Linux shells
with `export PORT=8080`. Other useful settings are `OLLAMA_MODEL`,
`OLLAMA_BASE_URL`, and `OLLAMA_TIMEOUT`; their defaults are listed in the guide.

## Tests and optional sharing

With the chatbot environment active, run:

```bash
python -m pip install pytest httpx
python -m pytest backend/tests/ -v
```

To share a running local instance temporarily, install `cloudflared` and run
`python scripts/inject-tunnel.py` in another terminal. The link works while the
server and tunnel stay running. Stop the tunnel with Ctrl+C.

ClimateInsight is part of [semanticClimate](https://github.com/semanticClimate)
and is distributed under the [MIT license](LICENSE). Its dependencies, models,
and source documents retain their own licenses and attribution.
