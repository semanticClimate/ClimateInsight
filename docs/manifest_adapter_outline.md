# ClimateInsight — manifest ingest adapter (outline)

**Date:** 2026-07-17 (system date; updated after live ingest)  
**Status:** **P3 complete**; **P4 ingest complete** (314 chunks, 12 papers)  
**Demo plan:** [semantic_corpus ocean heatwaves proposal](../../semantic_corpus/docs/demo/ocean_heatwaves_proposal.md) (sibling repo)

## Phase context

| Phase | Scope | Status |
|-------|--------|--------|
| **P3** | Manifest → chunks → Chroma (`--manifest`) | ✅ Done (this repo) |
| **P4** | Rehearsal + Cloudflare Quick Tunnel dry run | **In progress** — live ingest ✅; RAG + tunnel pending |
| **P2** | Encyclopedia glue (semantic_corpus + encyclopedia) | Still pending (parallel) |

**P3 done means:** adapter code + unit tests on the local filestore.

**P4 progress (2026-07-17):** First live ingest of `ocean_heatwaves_2026` — 12 papers, 314 Chroma chunks via `tests/fixtures/ocean_heatwaves_2026/chatbot_manifest.json`. RAG smoke and Cloudflare tunnel still pending.

## Usage

```bash
source .venv/bin/activate
cd backend

# IPCC (default)
python -m ingest.ingest

# semantic_corpus manifest
python -m ingest.ingest --manifest /path/to/chatbot_manifest.json
```

## Tests

Run from `backend/` (so `ingest` imports resolve). Do not set `PYTHONPATH`.

```bash
source .venv/bin/activate
cd backend
pip install pytest   # if needed; not yet in requirements.txt
python -m pytest tests/ -v
```

## Package

`backend/ingest/manifest_ingest/` — `load_manifest`, `text_loader`, `jats_to_sections`, `build_from_manifest`

Also: `ingest.py --manifest`, extended `Chunk` / Chroma metadata for citations.

## Fixture bundle (ocean heatwaves)

`backend/tests/fixtures/ocean_heatwaves_2026/` — 12 XML, 6 PDF, `chatbot_manifest.json`, review table.

Session record: [semantic_corpus docs](../../semantic_corpus/docs/records/2026-07-17_ocean_heatwaves_ingest.md)

## Next (P4 remainder)

1. ~~Ingest manifest~~ ✅ — 314 chunks stored.
2. Smoke RAG — retrieval + Ollama; verify citations on marine heatwave questions.
3. Start backend + frontend; dry-run Cloudflare Quick Tunnels (`scripts/inject-tunnel.py`).
4. Optional in parallel: **P2** encyclopedia glue + sample under the corpus.
