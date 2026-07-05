# ClimateInsight: IPCC Chatbot

> [!WARNING]
> **Development Version**: This is currently a work-in-progress development build. It is not intended or configured for production environments.

> [!IMPORTANT]
> **External / Remote Access**: To access the chatbot remotely or share it outside the local environment, you must use **Cloudflare Tunnels**. The application includes scripts to manage this connection automatically.

---

## 📂 Revamped Project Structure

Here is an overview of the restructured codebase designed for scalability, modularity, and clean separation of concerns:

```
ClimateInsight/
├── backend/                        # Backend Application Layer
│   ├── app.py                      # Flask Server (Endpoints, CORS, Proxying)
│   ├── config.py                   # Configuration Loader (Parses config.toml)
│   ├── db.py                       # Legacy ChromaDB wrapper
│   ├── llm.py                      # Legacy Ollama caller
│   ├── sessions.py                 # Legacy Session Manager (in-memory)
│   │
│   ├── ingest/                     # Ingestion Pipeline
│   │   ├── __init__.py
│   │   ├── ingest.py               # Ingestion script entry point
│   │   ├── parser.py               # HTML document parser (Extracts headings, sections)
│   │   ├── chunker.py              # Paragraph chunker & text splitter
│   │   ├── pipeline.py             # Pipeline orchestrator
│   │   └── models.py               # Ingest data models (e.g., Chunk, Document)
│   │
│   ├── vectorstore/                # Vector Database Client & Indexing
│   │   ├── __init__.py
│   │   ├── chroma_client.py        # Client initializer
│   │   ├── embedder.py             # Text embedding generator (Ollama or local HuggingFace)
│   │   ├── indexer.py              # Inserts and registers document chunks in ChromaDB
│   │   └── retriever.py            # Queries ChromaDB for top-K matching chunks
│   │
│   ├── retrieval/                  # Retrieval-Augmented Generation (RAG) Flow
│   │   ├── __init__.py
│   │   ├── pipeline.py             # RAG main coordinator (retrieval -> prompt -> generation)
│   │   ├── context_builder.py      # Format retrieved chunks for the prompt context
│   │   ├── prompt_builder.py       # Combines chat history, context, and user query
│   │   └── citation_parser.py      # Parses citations and builds mappings back to source report
│   │
│   ├── services/                   # Application Business Logic
│   │   ├── __init__.py
│   │   ├── chat_service.py         # Manages multi-turn conversation logic
│   │   ├── greeting_service.py     # Provides greeting messages based on user context
│   │   ├── session_service.py      # Handles chat history memory & session states
│   │   └── response_formatter.py   # Sanitizes and structures response outputs
│   │
│   └── llm/                        # Language Model Interfacing
│       ├── __init__.py
│       ├── client.py               # Ollama connection handler
│       ├── prompt_templates.py     # Centralized system and user prompt definitions
│       └── translation.py          # Multilingual utilities (Translation to/from English)
│
├── frontend/                       # Frontend Web UI (Vanilla HTML/CSS/JS)
│   ├── index.html                  # Main chatbot application screen
│   ├── ipcc_logo.png               # Brand logo
│   ├── css/                        # Styling sheets (Modular CSS)
│   │   ├── layout.css              # Grid system, page layouts
│   │   └── report.css              # Report iframe viewing layout
│   ├── js/                         # JavaScript Modules
│   │   ├── api.js                  # Centralized client for backend endpoints
│   │   ├── chat.js                 # Chat input/output UI interactions
│   │   ├── main.js                 # Main script loader and orchestrator
│   │   ├── sidebar.js              # Collapsible panels and navigation
│   │   └── tour.js                 # Onboarding/Intro guide
│   └── images/                     # Graphic resources and icons
│
├── data/                           # Data Assets
│   ├── raw/                        # Place raw IPCC documents here (e.g., ipcc_reference.html)
│   ├── images/                     # Extracted figures and tables from reports
│   └── extract_fig.py              # Script to extract figures/tables from sources
│
├── scripts/                        # Operational Scripts
│   ├── inject-tunnel.py            # Automatically spins up and configures Cloudflare tunnels
│   └── tunnel-url.txt              # Tracks the current active tunnel URL
│
├── requirements.txt                # Python environment requirements
└── LICENSE                         # Repository license info
```

---

## ⚙️ Setup & Installation

### 1. Install Dependencies
Ensure you have Python 3.10+ installed. In the project root folder (or virtual environment):
```powershell
pip install -r requirements.txt
```

### 2. Set Up the Local LLM (Ollama)
The chatbot relies on a locally hosted Ollama server for inference:
1. Download and install [Ollama](https://ollama.com/).
2. Run the Ollama server:
   ```powershell
   ollama serve
   ```
3. Pull the required model:
   ```powershell
   ollama pull llama3.2:latest
   ```

### 3. Ingest IPCC Reference Data
Ensure your target HTML document is placed at `data/raw/ipcc_reference.html`. Run the ingestion pipeline from the `backend/` directory to parse, chunk, embed, and index it into ChromaDB:
```powershell
cd backend
python -m ingest.ingest
```
*Note: The first ingestion will automatically download the local embedding model (`all-MiniLM-L6-v2`), which might take a couple of minutes.*

---

## 🚀 Running the Application

There are two ways to run the project during development:

### Option A: Local Development (Localhost)
If you only need to run the application locally on your machine:
1. **Start the Flask Backend**:
   ```powershell
   cd backend
   python app.py
   ```
   *The API will be available at `http://localhost:5000`.*
2. **Start the Frontend Server**:
   You can serve the `frontend/` directory using Python's built-in HTTP server:
   ```powershell
   cd frontend
   python -m http.server 3000
   ```
   *Open your browser and navigate to `http://localhost:3000`.*

### Option B: Development with External Access (Cloudflare Tunnels)
To share or test the application externally, the project features a Cloudflare Quick Tunnel utility. This is the **only supported method** for external access during development.

1. Install the `cloudflared` CLI on your machine (ensure it's in your system `PATH`).
2. Run the Flask backend and serve the frontend locally:
   - Backend on `localhost:5000`
   - Frontend on `localhost:3000`
3. Run the tunnel injection script from the project root:
   ```powershell
   python scripts/inject-tunnel.py
   ```
4. This script will:
   - Request temporary public URLs from Cloudflare for both port `3000` (frontend) and `5000` (backend).
   - Automatically patch `frontend/js/api.js` with the active backend tunnel URL.
   - Output both URLs to the terminal.
5. **Paste the generated backend URL** into `scripts/tunnel-url.txt`.
6. **Open the frontend URL** in your browser to access the chatbot interface.
7. When finished, press `Ctrl+C` in the script terminal to gracefully shut down the tunnels and automatically restore `api.js` settings back to `localhost`.

---

## 🛠️ API Reference

- `GET  /api/health` — Returns backend health status
- `POST /api/chat` — Sends a user message, retrieves context, queries Ollama, and returns the response with source citations
- `DELETE /api/session/<session_id>` — Clears active conversation memory for the given session
