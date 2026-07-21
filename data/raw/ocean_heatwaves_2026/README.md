# ocean_heatwaves_2026 ingest bundle

**Date:** 2026-07-17 (system date of generation)
**Source:** semantic_corpus `tests/fixtures/ocean_heatwaves_2026/`
**Review table:** `review/review_table.edited.json` (12 included papers)

## Ingest

```bash
cd backend
python -m ingest.ingest --manifest tests/fixtures/ocean_heatwaves_2026/chatbot_manifest.json
```

## Contents

- `chatbot_manifest.json` — 12 papers (`include` only)
- `12` XML full-text files
- `6` PDF files (optional; ingest uses XML first)
