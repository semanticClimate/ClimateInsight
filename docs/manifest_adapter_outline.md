# ClimateInsight — manifest ingest adapter (outline)

**Date:** 2026-07-16 (system date)  
**Status:** **P3 complete** — implemented 2026-07-16; 14/14 tests passing  
**Demo plan:** [semantic_corpus ocean heatwaves proposal](../../semantic_corpus/docs/demo/ocean_heatwaves_proposal.md) (sibling repo)

## Phase context

| Phase | Scope | Status |
|-------|--------|--------|
| **P3** | Manifest → chunks → Chroma (`--manifest`) | ✅ Done (this repo) |
| **P4** | Rehearsal + Cloudflare Quick Tunnel dry run | Next |
| **P2** | Encyclopedia glue (semantic_corpus + encyclopedia) | Still pending (parallel) |

**P3 done means:** adapter code + unit tests on the local filestore. It does **not** include ingesting the live ocean heatwaves export or a public tunnel demo — that is **P4**.

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

## Next (P4)

1. Mark papers `include` in the ocean heatwaves review table; re-export a non-empty `chatbot_manifest.json`.
2. Ingest that manifest into ClimateInsight ChromaDB.
3. Start backend + frontend; dry-run Cloudflare Quick Tunnels (`scripts/inject-tunnel.py`).
4. Optional in parallel: **P2** encyclopedia glue + sample under the corpus.
