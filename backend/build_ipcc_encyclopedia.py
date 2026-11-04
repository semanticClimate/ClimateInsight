"""Build ClimateInsight's vocabulary from its IPCC report, without ingestion.

Run from the project root: python backend/build_ipcc_encyclopedia.py
This explicit build loads txt2phrases and retrieves Wikipedia pages. Serving the
report and constructing the existing NetworkX graph only read its outputs.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import sys
from pathlib import Path
import tempfile
from urllib.parse import unquote, urlparse

from lxml import html

from encyclopedia_importer import build_normalized_vocabulary, merge_manual_and_imported
from encyclopedia_service import ROOT, exchange_module, source_path, tomllib


def _plain(markup):
    return " ".join(html.fromstring(markup).text_content().split()) if markup else None


def export_records(entries, source_file):
    """Keep unresolved model terms; use actual resolved Wikipedia titles as IDs."""
    exchange = exchange_module()
    records = []
    for entry in entries:
        term = str(entry.get("term") or "").strip()
        if not term:
            continue
        url = exchange.wikipedia_url(entry.get("wikipedia_url"))
        title = unquote(urlparse(url).path[len("/wiki/"):]).replace("_", " ") if url else term
        note = entry.get("content_note") or ""
        # A disambiguation/missing-article notice is not a definition.
        if note:
            url, title = None, term
        records.append({
            "canonical_name": title,
            "synonyms": sorted({term, str(entry.get("search_term") or term)} - {title}),
            "description": _plain(entry.get("description_html")) if not note else None,
            "wikidata_id": entry.get("wikidata_id") or None if not note else None,
            "wikipedia_url": url,
            "source_file": source_file,
        })
    return records


def build(source=None, *, top_n=500, max_terms=300, min_count=2, add_wikipedia=True):
    exchange = exchange_module()
    from ipcc_encyclopedia_pipeline import build_report_encyclopedia
    from knowledge_graph import ConceptMatcher

    source = Path(source or source_path()).resolve(strict=True)
    original = source.read_bytes()
    source_hash = hashlib.sha256(original).hexdigest()
    try:
        source_file = source.relative_to(ROOT).as_posix()
    except ValueError:
        source_file = source.as_posix()
    output = ROOT / "encyclopedia/generated"
    output.parent.mkdir(parents=True, exist_ok=True)
    # A failed extraction/enrichment leaves the currently installed build intact.
    with tempfile.TemporaryDirectory(prefix="ipcc-build-", dir=output.parent) as scratch:
        scratch = Path(scratch)
        encyclopedia, paths = build_report_encyclopedia(
            source, scratch, top_n=top_n, max_terms=max_terms,
            min_count=min_count, add_wikipedia=add_wikipedia,
        )
        records = export_records(encyclopedia.entries, source_file)
        portable = scratch / "entries.html"
        portable.write_text(exchange.render_entries(records), encoding="utf-8")
        artifact, _ = build_normalized_vocabulary(portable, scratch)
        for record in artifact["concepts"]:
            record["source_file"] = source_file
        if not artifact["concepts"]:
            raise ValueError("No Encyclopedia entries were produced; previous build retained")
        aliases, metadata, conflicts = merge_manual_and_imported({}, artifact["concepts"])
        matcher = ConceptMatcher(aliases)
        contexts = exchange.report_contexts(original.decode("utf-8"), matcher.find)
        glossary = exchange.render_entries(artifact["concepts"], contexts,
                                          title="IPCC AR6 SYR Longer Report Encyclopedia")
        document = ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
                    '<title>IPCC Encyclopedia</title></head><body>' + glossary + '</body></html>')
        artifact["provenance"] = {
            "source_file": source_file, "source_sha256": source_hash,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "extractor": "txt2phrases", "extractor_version": version("txt2phrases"),
            "model": "ml6team/keyphrase-extraction-kbir-inspec",
            "top_n": top_n, "max_terms": max_terms, "min_count": min_count,
            "wikipedia_requested": add_wikipedia,
            "selected_keyphrases": len(encyclopedia.entries),
            "unresolved_entries": sum(not r.get("wikipedia_url") for r in records),
            "vocabulary_conflicts": conflicts,
        }
        if hashlib.sha256(source.read_bytes()).hexdigest() != source_hash:
            raise ValueError("The source report changed during extraction; previous build retained")
        output.mkdir(parents=True, exist_ok=True)
        (output / "wordlist.csv").write_bytes(paths["wordlist"].read_bytes())
        (output / "ipcc_reference.txt").write_bytes(paths["text"].read_bytes())
        (output / "ipcc_encyclopedia.html").write_text(document, encoding="utf-8")
        manifest = {"provenance": artifact["provenance"], "summary": artifact["summary"]}
        (output / "build.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        target = ROOT / "backend/data/generated/encyclopedia_concepts.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        ready = target.with_suffix(".json.tmp")
        ready.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        ready.replace(target)
    print(json.dumps(manifest, indent=2))
    return artifact


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    config = tomllib.loads((ROOT / "config.toml").read_text(encoding="utf-8")).get("encyclopedia", {})
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=source_path())
    parser.add_argument("--top-n", type=int, default=config.get("top_n", 500))
    parser.add_argument("--max-terms", type=int, default=config.get("max_terms", 300))
    parser.add_argument("--min-count", type=int, default=config.get("min_count", 2))
    parser.add_argument("--no-wikipedia", action="store_true", help="Offline entry generation; descriptions remain missing")
    args = parser.parse_args()
    build(args.source, top_n=args.top_n, max_terms=args.max_terms,
          min_count=args.min_count, add_wikipedia=not args.no_wikipedia)


if __name__ == "__main__":
    main()
