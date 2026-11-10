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
| Reader for AR6 chapters fetched from amilib | `backend/ingest/ipcc_amilib_parser.py` |
| Reader for all other HTML, including `data/raw/ipcc_reference.html` | `backend/ingest/parser.py` (unchanged) |
| Fetch AR6 chapters from amilib | `scripts/fetch_ipcc_from_amilib.py` |
| Tests | `backend/tests/test_ipcc_amilib_parser.py`, `backend/tests/fixtures/ipcc_amilib/` |

## Existing behaviour is unchanged

`data/raw/ipcc_reference.html` (the SYR Longer Report the chatbot has
always used) is amilib's file: its 195 paragraph ids and texts match amilib's
`cleaned_content/syr/longer-report/html_with_ids.html`. It is still read by
`parser.py`, so the knowledge base is exactly as before. Building every
chunk from `data/raw` with this code and with `main` gives identical
results (118 chunks for the default IPCC ingest, 418 for `--dir data/raw`),
and `test_existing_ipcc_reference_still_uses_previous_reader` keeps it that
way.

## Adding AR6 chapters from amilib

```bash
python scripts/fetch_ipcc_from_amilib.py --list
python scripts/fetch_ipcc_from_amilib.py wg1/Chapter01 wg2/Chapter05
cd backend && python -m ingest.ingest --dir ../data/raw/ipcc
```

The script saves chapters in `data/raw/ipcc/` from a pinned amilib commit
and writes `SOURCES.json` (commit, path, checksum). HTML files next to a
`SOURCES.json` are read by `ipcc_amilib_parser.py`:

* one `Section` per amilib container, numbered from its heading;
* `html_id` is the first amilib paragraph id, which citations link to;
* `section_hierarchy` lists the enclosing headings;
* text is in the same form as `parser.py` produces (e.g. "CO 2"), so
  concept matching behaves the same;
* body paragraphs and list items amilib left without an id (such as the
  SYR's headline statements) are kept;
* reference lists, table of contents, figure captions, footnotes, author
  lists and the recommended citation are left out. The old reader would
  index WG reference lists (about 1,000 entries per chapter), which is why
  fetched chapters use this reader.

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
