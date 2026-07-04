# IPCC Chatbot — Clean Build

## What's in here

```
backend/
  app.py        ← Flask server (run this)
  ingest.py     ← load IPCC data into ChromaDB (run once)
  db.py         ← ChromaDB wrapper
  llm.py        ← Ollama caller
  sessions.py   ← in-memory conversation history
  requirements.txt

frontend/
  index.html    ← open this in your browser (no build step needed)
```

## Setup (do this once)

### 1. Install dependencies
```powershell
cd backend
pip install -r requirements.txt
```

### 2. Ingest the IPCC data into ChromaDB
Make sure `data/raw/ipcc_reference.html` exists next to the `backend/` folder, then:
```powershell
python -m ingest.ingest
```
This takes a few minutes the first time (downloading the embedding model).
After that it's instant — ChromaDB caches everything.

### 3. Start Ollama
```powershell
ollama serve
```
Make sure you have the model: `ollama pull llama3.2:latest`

### 4. Start the Flask server
```powershell
python app.py
```

### 5. Open the frontend
Just open `frontend/index.html` in your browser. That's it.

## How it works

1. You type a question
2. Frontend sends it to `POST /api/chat`
3. Flask embeds your question and searches ChromaDB for the 5 most relevant IPCC passages
4. Those passages + your question are sent to Ollama as a prompt
5. Ollama's answer comes back with citations
6. Frontend displays it

## API endpoints

- `GET  /api/health`              — check the server is up
- `POST /api/chat`                — ask a question
- `DELETE /api/session/<id>`      — clear conversation history

## Adding features later

- **Persistent sessions** → swap `sessions.py` for Redis
- **Better retrieval** → add re-ranking in `db.py`
- **Different LLM** → swap `llm.py` for OpenAI/Anthropic
- **React frontend** → the API doesn't change, just replace `index.html`
