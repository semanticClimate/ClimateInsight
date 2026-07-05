## ⚙️ Setup & Installation

### 1. Create and Activate a Virtual Environment

It is recommended to use a Python virtual environment to isolate project dependencies.

**Windows (PowerShell)**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

### 2. Install Dependencies

Ensure you have **Python 3.10+** installed.

**Windows (PowerShell)**

```powershell
pip install -r requirements.txt
```

**macOS / Linux**

```bash
pip install -r requirements.txt
```

---

### 3. Set Up the Local LLM (Ollama)

The chatbot relies on a locally hosted Ollama server for inference.

1. Download and install **Ollama** from https://ollama.com/.
2. Start the Ollama server.

**Windows (PowerShell)**

```powershell
ollama serve
```

**macOS / Linux**

```bash
ollama serve
```

3. Pull the required model.

**Windows (PowerShell)**

```powershell
ollama pull llama3.2:latest
```

**macOS / Linux**

```bash
ollama pull llama3.2:latest
```

---

### 4. Ingest IPCC Reference Data

Ensure your target HTML document is placed at:

```text
data/raw/ipcc_reference.html
```

Run the ingestion pipeline from the `backend/` directory to parse, chunk, embed, and index the document into ChromaDB.

**Windows (PowerShell)**

```powershell
cd backend
python -m ingest.ingest
```

**macOS / Linux**

```bash
cd backend
python3 -m ingest.ingest
```

> **Note:** During the first ingestion, the embedding model (`all-MiniLM-L6-v2`) will be downloaded automatically. This may take a few minutes.

---

# 🚀 Running the Application

There are two ways to run the project during development.

# Option A: Local Development (Localhost)

If you only need to run the application locally on your machine:

### 1. Start the Flask Backend

**Windows (PowerShell)**

```powershell
cd backend
python app.py
```

**macOS / Linux**

```bash
cd backend
python3 app.py
```

The backend API will be be available at:

```
http://localhost:5000
```

---

### 2. Start the Frontend Server

Serve the `frontend/` directory using Python's built-in HTTP server.

**Windows (PowerShell)**

```powershell
cd frontend
python -m http.server 3000
```

**macOS / Linux**

```bash
cd frontend
python3 -m http.server 3000
```

Open your browser and navigate to:

```
http://localhost:3000
```

Before using the application locally, create a file named `tunnel-base.txt` directly inside the `frontend/` directory (alongside `index.html`) with the following contents:

```text
https://localhost:5000
```

This file tells the frontend to communicate with the locally running backend instead of using a Cloudflare Tunnel.

---

### 2. Start the Frontend Server

Serve the `frontend/` directory using Python's built-in HTTP server.

**Windows (PowerShell)**

```powershell
cd frontend
python -m http.server 3000
```

**macOS / Linux**

```bash
cd frontend
python3 -m http.server 3000
```

Open your browser and navigate to:

```
http://localhost:3000
```

---

## Option B: Development with External Access (Cloudflare Tunnels)

To share or test the application externally, the project includes a Cloudflare Quick Tunnel utility. This is the **only supported method** for external access during development.

1. Install the `cloudflared` CLI and ensure it is available in your system `PATH`.

2. Start both services locally:
   - Backend on `localhost:5000`
   - Frontend on `localhost:3000`

3. Run the tunnel injection script from the project root.

**Windows (PowerShell)**

```powershell
python scripts/inject-tunnel.py
```

**macOS / Linux**

```bash
python3 scripts/inject-tunnel.py
```

4. The script will automatically:
   - Request temporary public URLs from Cloudflare for ports `3000` and `5000`.
   - Patch `frontend/js/api.js` with the active backend tunnel URL.
   - Display both public URLs in the terminal.

5. Open the generated **frontend URL** in your browser.

6. When finished, press **Ctrl+C** to gracefully terminate the tunnels. The script will automatically restore `frontend/js/api.js` to use `localhost`.