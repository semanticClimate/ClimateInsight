# How ClimateInsight reads IPCC AR6

semanticClimate's [amilib](https://github.com/semanticClimate/amilib)
already cleans IPCC web pages: it removes the site's navigation, nests each
section in a `div.hN-container` and gives every body paragraph a stable id
such as `2.1.1_p3`. It publishes the result as `html_with_ids.html` for 49
AR6 chapters (SYR Longer Report and WG I, II, III chapters) under
`test/resources/ipcc/cleaned_content/<report>/<chapter>/`.

ClimateInsight builds on that instead of cleaning IPCC pages itself.

## Where the code is

| What | File |
|---|---|
| Chooses the reader for each `.html` file | `backend/ingest/loader_registry.py` (`parse_html_document`) |
| Reader for IPCC AR6 chapters in amilib's format, including `data/raw/ipcc_reference.html` | `backend/ingest/ipcc_amilib_parser.py` |
| Reader for other HTML (not IPCC) | `backend/ingest/parser.py` |
| Fetch AR6 chapters from amilib | `scripts/fetch_ipcc_from_amilib.py` |
| Serve a fetched chapter in the browser | `GET /ipcc-reference?doc=<file>` in `backend/app.py` |
| Tests | `backend/tests/test_ipcc_amilib_parser.py`, `backend/tests/fixtures/ipcc_amilib/`, `backend/tests/test_knowledge_graph_sources.py` |

ClimateInsight has no IPCC cleaning rules of its own. Any HTML file in
amilib's IPCC format is read by `ipcc_amilib_parser.py`.

## What the reader does

* one `Section` per amilib container, numbered from its heading (the SYR
  has two containers with id `2.2.3`; the heading numbers are right);
* `html_id` is the first amilib paragraph id, which citations link to;
* `section_hierarchy` lists the enclosing headings;
* text is in the same form as the generic reader produces (e.g. "CO 2"),
  so concept matching behaves the same;
* body paragraphs and list items amilib left without an id (such as the
  SYR's headline statements and risk lists) are kept;
* reference lists, table of contents, figure captions, footnotes, author
  lists and the recommended citation are left out.

## Effect on the existing SYR index

`data/raw/ipcc_reference.html` is amilib's file (its 195 paragraph ids and
texts match amilib's `cleaned_content/syr/longer-report/html_with_ids.html`).
Reading it through amilib's structure instead of the earlier
ClimateInsight-specific parser, measured against `main`:

* 115 IPCC passages instead of 118; the 300 research-paper passages are
  identical;
* every amilib paragraph is kept; what drops out is the author list, the
  recommended citation, figure captions and footnotes;
* section titles are complete (the earlier parser cut titles at a line
  break, e.g. "Current Mitigation and Adaptation Actions and Policies are");
* every section now has a citation anchor (6 had none);
* knowledge graph: 270 concepts instead of 273 (3 appeared only in figure
  captions) and 5,218 links instead of 5,286.

Re-ingest after updating: `cd backend && python -m ingest.ingest`.

## Adding AR6 chapters from amilib

```bash
python scripts/fetch_ipcc_from_amilib.py --list
python scripts/fetch_ipcc_from_amilib.py wg1/Chapter01 wg2/Chapter05
cd backend && python -m ingest.ingest --dir ../data/raw
```

The script saves chapters in `data/raw/ipcc/` from a pinned amilib commit
and writes `SOURCES.json` (commit, path, checksum). The old reader would
index WG reference lists (about 1,000 entries per chapter); the amilib
reader skips them.

## When the IPCC documents (or amilib) change

1. Get the chapter re-cleaned in amilib (fix or extend amilib, not this repo).
2. Rerun the fetch script with `--ref <new amilib commit>`.
3. Run the tests: `cd backend && python -m pytest`. The fixture pins the
   amilib format the reader relies on, and the SYR tests check that every
   amilib paragraph is still indexed.
4. If amilib's format changed, update `ipcc_amilib_parser.py` only, then
   re-ingest.

## Known gaps to raise with amilib

* amilib's IPCC classes live in its `test/` folder (`test/ipcc_classes.py`),
  so they are not in the installed `amilib` package. ClimateInsight
  therefore uses amilib's output files rather than importing its code.
* In the WG I and WG II chapters checked, Executive Summary paragraphs have
  no ids.
* Two SYR sections share the container id `2.2.3`, so their paragraph ids
  collide. The reader numbers sections from headings to avoid mixing them.
* The SYR page `<title>` says "Summary for Policymakers"; the reader uses
  the chapter heading.
