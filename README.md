# ClimateInsight

ClimateInsight is an AI-powered chatbot designed to make information from the Intergovernmental Panel on Climate Change (IPCC) more accessible through natural language conversations. Instead of manually searching through lengthy reports, users can ask questions in plain English and receive context-aware responses grounded in the indexed IPCC reference material.

The project was developed to demonstrate how Retrieval-Augmented Generation (RAG), semantic search, and locally hosted Large Language Models (LLMs) can be combined to create an interpretable, privacy-friendly question-answering system. Rather than relying on cloud-hosted AI services, ClimateInsight performs retrieval and inference locally using Ollama and ChromaDB, making it suitable for experimentation, education, and offline development.

---

# ⚙️ Setup & Installation

## Prerequisites

Before starting, ensure you have the following installed:

- Python **3.10 or later**
- Git
- Ollama
- (Optional) Cloudflared, if you plan to expose the application externally

---

## 1. Clone the Repository

Clone the repository to your local machine.

```bash
git clone https://github.com/semanticClimate/ClimateInsight.git
```

---

## 2. Navigate into the Project

```bash
cd ClimateInsight
```

Replace `ClimateInsight` with the repository name if different.

---

## 3. Create a Python Virtual Environment

Creating a virtual environment keeps this project's Python packages isolated from packages installed globally on your computer. This prevents dependency conflicts between different Python projects and makes the project easier to reproduce across different machines.

The virtual environment is created inside a folder named `.venv`.

### Windows (PowerShell)

```powershell
python -m venv .venv
```

### macOS / Linux

```bash
python3 -m venv .venv
```

---

## 4. Activate the Virtual Environment

After creating the virtual environment, activate it before installing any dependencies.

When activated, all Python packages installed using `pip` will be placed inside `.venv` rather than your global Python installation.

### Windows (PowerShell)

```powershell
.\.venv\Scripts\Activate.ps1
```

### macOS / Linux

```bash
source .venv/bin/activate
```

Once activated, your terminal should display something similar to:

```text
(.venv)
```

at the beginning of the command prompt.

---

## 5. Install Project Dependencies

Once the virtual environment is active, install all required Python libraries.

These dependencies include:

- Flask
- ChromaDB
- Sentence Transformers
- LangChain components
- Ollama integration
- Other libraries required by the chatbot

### Windows (PowerShell)

```powershell
pip install -r requirements.txt
```

### macOS / Linux

```bash
pip install -r requirements.txt
```

Installing packages while the virtual environment is active ensures that they are stored inside `.venv` instead of your system-wide Python installation.

---

## 6. Install and Configure Ollama

ClimateInsight uses a locally hosted Large Language Model (LLM) through Ollama for response generation.

### Download Ollama

Download and install Ollama from:

https://ollama.com/

---

### Start the Ollama Server

#### Windows (PowerShell)

```powershell
ollama serve
```

#### macOS / Linux

```bash
ollama serve
```

Keep this terminal running while using the chatbot.

---

### Download the Required Model

ClimateInsight expects the `llama3.2` model.

#### Windows (PowerShell)

```powershell
ollama pull llama3.2:latest
```

#### macOS / Linux

```bash
ollama pull llama3.2:latest
```

This only needs to be done once.

---

## 7. Prepare the IPCC Reference Data

Place the IPCC HTML reference document at:

```text
data/raw/ipcc_reference.html
```

This document serves as the chatbot's knowledge base.

---

## 8. Build the Vector Database

ClimateInsight uses a Retrieval-Augmented Generation (RAG) pipeline.

During ingestion, the project will:

- Parse the IPCC document
- Clean the extracted text
- Split the document into semantic chunks
- Generate embeddings
- Store the embeddings inside ChromaDB

Run the ingestion pipeline from the `backend` directory.

### Windows (PowerShell)

```powershell
cd backend
python -m ingest.ingest
```

### macOS /Linux

```bash
cd backend
python3 -m ingest.ingest
```

> **Note:** During the first ingestion, the embedding model (`all-MiniLM-L6-v2`) will automatically be downloaded. This may take several minutes depending on your internet connection.

---

# 🚀 Running the Application

There are two supported ways to run ClimateInsight during development.

---

# Option A — Local Development (Localhost)

Use this option if you only need to access the chatbot from your own computer.

---

## 1. Start the Backend

Open a terminal.

### Windows (PowerShell)

```powershell
cd backend
python app.py
```

### macOS / Linux

```bash
cd backend
python3 app.py
```

The backend will run at:

```text
http://localhost:5000
```

---

## 2. Configure the Frontend

Before starting the frontend, create a file named:

```text
frontend/tunnel-base.txt
```

The file should contain exactly:

```text
https://localhost:5000
```

The frontend reads this file to determine which backend endpoint it should communicate with.

For local development, this should point to the localhost backend.

---

## 3. Start the Frontend

Open a second terminal.

### Windows (PowerShell)

```powershell
cd frontend
python -m http.server 3000
```

### macOS / Linux

```bash
cd frontend
python3 -m http.server 3000
```

Open your browser and visit:

```text
http://localhost:3000
```

---

# Option B — External Development (Cloudflare Tunnel)

If you want to share the chatbot with others or access it from another device without deploying it to a server, ClimateInsight includes support for Cloudflare Quick Tunnels.

This is the recommended method for external development and testing.

---

## 1. Install Cloudflared

Install the Cloudflare CLI and ensure it is available from your system `PATH`.

---

## 2. Start the Backend

Run the backend as described in Option A.

---

## 3. Start the Frontend

Run the frontend as described in Option A.

---

## 4. Launch the Tunnel Utility

From the project root:

### Windows (PowerShell)

```powershell
python scripts/inject-tunnel.py
```

### macOS / Linux

```bash
python3 scripts/inject-tunnel.py
```

---

## 5. What the Script Does

The tunnel utility automatically:

- Creates temporary Cloudflare Quick Tunnels
- Generates a public URL for the frontend
- Generates a public URL for the backend
- Updates the frontend configuration with the active backend tunnel
- Displays both URLs in the terminal

No manual editing of configuration files is required.

---

## 6. Open the Application

Open the generated frontend URL in your browser.

The frontend will automatically communicate with the backend through the generated Cloudflare tunnel.

---

## 7. Closing the Tunnels

When finished, press:

```text
Ctrl + C
```

The tunnel utility will:

- Close both Cloudflare tunnels
- Restore the frontend configuration back to localhost
- Clean up temporary configuration changes
