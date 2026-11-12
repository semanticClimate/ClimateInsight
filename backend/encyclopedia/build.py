"""Build from the configured report, glossary HTML and approved PMC papers.

Run from the project root: python -m backend.encyclopedia.build
This explicit build loads txt2phrases and retains Wikipedia enrichment. Serving the
report and constructing the existing NetworkX graph only read its outputs.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import csv
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import sys
from pathlib import Path
import tempfile
from urllib.parse import unquote, urlparse

from lxml import html

from backend.encyclopedia.importer import build_normalized_vocabulary, merge_manual_and_imported
from backend.encyclopedia.service import ROOT, exchange_module, source_path, tomllib
from backend.encyclopedia.glossary import enrich_artifact, render_entries
from backend.encyclopedia.concepts import refine_concepts


def refine_artifact(artifact, source_file, report_html, glossary_html=None):
    sources = [(source_file, report_html)]
    if glossary_html:
        sources.append((artifact["provenance"]["glossary"]["source_file"], glossary_html))
    artifact = deepcopy(artifact)
    artifact["concepts"], audit = refine_concepts(artifact["concepts"], sources)
    artifact["provenance"]["concept_cleanup"] = {
        "version": audit["version"], "input_concepts": audit["input_concepts"],
        "output_concepts": audit["output_concepts"], "excluded_terms": len(audit["removed"]),
        "merged_groups": len(audit["merged"]), "source_abbreviations": len(audit["source_abbreviations"]),
    }
    artifact["summary"].update({
        "unique_concepts_exported": len(artifact["concepts"]),
        "concepts_with_descriptions": sum(bool(c.get("description")) for c in artifact["concepts"]),
        "concepts_with_synonyms": sum(bool(c.get("synonyms")) for c in artifact["concepts"]),
        "concepts_with_wikidata_ids": sum(bool(c.get("wikidata_id")) for c in artifact["concepts"]),
        "concepts_with_ipcc_definitions": sum(bool(c.get("definition_source")) for c in artifact["concepts"]),
    })
    return artifact, audit


def refine_existing():
    """Reprocess installed extraction outputs, without model or Wikipedia calls."""
    from backend.encyclopedia.service import source_concepts, glossary_html_path
    from backend.knowledge_graph.engine import ConceptMatcher

    target = ROOT / "backend/generated_artifacts/encyclopedia_concepts.json"
    source_concepts(target)  # validate installed report/glossary checksums first
    output = ROOT / "encyclopedia_assets/generated"
    raw_path = output / "extracted_concepts.json"
    installed = json.loads(target.read_text(encoding="utf-8"))
    raw = json.loads(raw_path.read_text(encoding="utf-8")) if raw_path.is_file() else installed
    for field in ("source_sha256", "wordlist_sha256"):
        if raw["provenance"].get(field) != installed["provenance"].get(field):
            raise ValueError("The extraction snapshot is stale; rebuild the report first")
    if raw["provenance"].get("glossary") != installed["provenance"].get("glossary"):
        raise ValueError("The glossary extraction snapshot is stale; rebuild it first")
    report = source_path().read_text(encoding="utf-8")
    glossary = glossary_html_path().read_text(encoding="utf-8") if raw["provenance"].get("glossary") else None
    artifact, audit = refine_artifact(raw, raw["provenance"]["source_file"], report, glossary)
    aliases, _, conflicts = merge_manual_and_imported({}, artifact["concepts"])
    artifact["provenance"]["vocabulary_conflicts"] = conflicts
    artifact["provenance"]["refined_at"] = datetime.now(timezone.utc).isoformat()
    exchange = exchange_module()
    contexts = exchange.report_contexts(report, ConceptMatcher(aliases).find)
    fragment = render_entries(exchange, artifact["concepts"], contexts, title="IPCC AR6 SYR Encyclopedia")
    document = '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>IPCC Encyclopedia</title></head><body>' + fragment + '</body></html>'
    if not raw_path.is_file():
        raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "concept_cleanup.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "ipcc_encyclopedia.html").write_text(document, encoding="utf-8")
    manifest = {"provenance": artifact["provenance"], "summary": artifact["summary"]}
    (output / "build.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ready = target.with_suffix(".json.tmp")
    ready.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ready.replace(target)
    print(json.dumps({"summary": artifact["summary"], "cleanup": artifact["provenance"]["concept_cleanup"]}, indent=2))
    return artifact


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


def _existing_extraction(output, source_hash):
    """Reuse only the selected model phrases from a matching installed build."""
    artifact_path = ROOT / "backend/generated_artifacts/encyclopedia_concepts.json"
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    provenance = artifact.get("provenance", {})
    if provenance.get("extractor") != "txt2phrases" or provenance.get("source_sha256") != source_hash:
        raise ValueError("Existing keyphrases do not match this IPCC report; rebuild the extraction first")
    wordlist = output / "wordlist.csv"
    with wordlist.open(encoding="utf-8", newline="") as stream:
        terms = [row["term"].strip() for row in csv.DictReader(stream)
                 if row.get("selected", "").casefold() == "yes" and row.get("term", "").strip()]
    if not terms or len(terms) != provenance.get("selected_keyphrases"):
        raise ValueError("Existing wordlist does not match the recorded extraction; rebuild it first")
    expected_hash = provenance.get("wordlist_sha256")
    if expected_hash and hashlib.sha256(wordlist.read_bytes()).hexdigest() != expected_hash:
        raise ValueError("The extracted wordlist changed; rebuild the extraction first")
    return terms, provenance, wordlist, output / "ipcc_reference.txt"


def build(source=None, *, top_n=500, max_terms=300, min_count=2, add_wikipedia=True,
          enrich_existing=False, glossary=None, reuse_report=False,
          glossary_top_n=500, glossary_max_terms=300, glossary_min_count=1):
    if source is None and tomllib.loads((ROOT / "config.toml").read_text(encoding="utf-8")).get("encyclopedia", {}).get("papers"):
        from backend.encyclopedia.corpus import build_corpus
        return build_corpus(ROOT, add_wikipedia=add_wikipedia, refresh_wikipedia=enrich_existing)
    if enrich_existing and not add_wikipedia:
        raise ValueError("--enrich-existing requires Wikipedia enrichment")
    if reuse_report and enrich_existing:
        raise ValueError("Choose --reuse-report or --enrich-existing")
    exchange = exchange_module()
    from backend.knowledge_graph.engine import ConceptMatcher

    source = Path(source or source_path()).resolve(strict=True)
    original = source.read_bytes()
    source_hash = hashlib.sha256(original).hexdigest()
    try:
        source_file = source.relative_to(ROOT).as_posix()
    except ValueError:
        source_file = source.as_posix()
    output = ROOT / "encyclopedia_assets/generated"
    output.parent.mkdir(parents=True, exist_ok=True)
    prior = None
    report_artifact = None
    if enrich_existing or reuse_report:
        terms, prior, old_wordlist, old_text = _existing_extraction(output, source_hash)
    if reuse_report:
        snapshot = output / "report_concepts.json"
        installed = ROOT / "backend/generated_artifacts/encyclopedia_concepts.json"
        report_artifact = json.loads((snapshot if snapshot.is_file() else installed).read_text(encoding="utf-8"))
        if (report_artifact.get("provenance", {}).get("source_sha256") != source_hash
                or report_artifact.get("provenance", {}).get("glossary")
                or not report_artifact.get("concepts")):
            raise ValueError("The report-only snapshot is missing or stale; rebuild the report first")
    # A failed extraction/enrichment leaves the currently installed build intact.
    with tempfile.TemporaryDirectory(prefix="ipcc-build-", dir=output.parent) as scratch:
        scratch = Path(scratch)
        if enrich_existing or reuse_report:
            from encyclopedia.pipeline.query_to_encyclopedia import create_encyclopedia_from_terms

            paths = {"html": scratch / "ipcc_encyclopedia.html",
                     "wordlist": scratch / "wordlist.csv", "text": scratch / "ipcc_reference.txt"}
            paths["wordlist"].write_bytes(old_wordlist.read_bytes())
            paths["text"].write_bytes(old_text.read_bytes())
            if not reuse_report:
                encyclopedia = create_encyclopedia_from_terms(
                    terms, "IPCC AR6 SYR Longer Report Encyclopedia", paths["html"], add_wikipedia=True,
                )
        else:
            from backend.encyclopedia.pipeline import build_report_encyclopedia

            encyclopedia, paths = build_report_encyclopedia(
                source, scratch, top_n=top_n, max_terms=max_terms,
                min_count=min_count, add_wikipedia=add_wikipedia,
            )
        if reuse_report:
            artifact = deepcopy(report_artifact)
            records = artifact["concepts"]
        else:
            records = export_records(encyclopedia.entries, source_file)
            if add_wikipedia and not any(record.get("wikipedia_url") and record.get("description")
                                         for record in records):
                raise RuntimeError("Wikipedia enrichment returned no article descriptions; previous build retained")
            portable = scratch / "entries.html"
            portable.write_text(exchange.render_entries(records), encoding="utf-8")
            artifact, _ = build_normalized_vocabulary(portable, scratch)
        for record in artifact["concepts"]:
            record["source_file"] = source_file
        if not artifact["concepts"]:
            raise ValueError("No Encyclopedia entries were produced; previous build retained")
        artifact["provenance"] = {
            **(prior or {}),
            "source_file": source_file, "source_sha256": source_hash,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "extractor": "txt2phrases",
            "extractor_version": prior["extractor_version"] if prior else version("txt2phrases"),
            "model": prior["model"] if prior else "ml6team/keyphrase-extraction-kbir-inspec",
            "top_n": prior["top_n"] if prior else top_n,
            "max_terms": prior["max_terms"] if prior else max_terms,
            "min_count": prior["min_count"] if prior else min_count,
            "wordlist_sha256": hashlib.sha256(paths["wordlist"].read_bytes()).hexdigest(),
            "wikipedia_requested": prior.get("wikipedia_requested", add_wikipedia) if reuse_report else add_wikipedia,
            "selected_keyphrases": prior["selected_keyphrases"] if reuse_report else len(encyclopedia.entries),
            "unresolved_entries": sum(not r.get("wikipedia_url") for r in records),
        }
        artifact["provenance"].pop("glossary", None)
        artifact["provenance"].pop("concept_cleanup", None)
        artifact["provenance"].pop("refined_at", None)
        if prior:
            artifact["provenance"]["extracted_at"] = prior.get("extracted_at", prior["generated_at"])
        # Keep a validated report-only snapshot so repeated glossary rebuilds
        # replace the glossary contribution instead of accumulating old terms.
        report_snapshot = deepcopy(artifact)
        if glossary is not None:
            artifact = enrich_artifact(
                artifact, glossary, scratch / "glossary", root=ROOT,
                top_n=glossary_top_n, max_terms=glossary_max_terms, min_count=glossary_min_count,
            )
            expected = artifact["provenance"]["glossary"]["source_sha256"]
            if hashlib.sha256(Path(glossary).read_bytes()).hexdigest() != expected:
                raise ValueError("The glossary changed during extraction; previous build retained")
        extracted_snapshot = deepcopy(artifact)
        glossary_html = (scratch / "glossary/IPCC_AR6_SYR_Glossary.html").read_text(encoding="utf-8") if glossary is not None else None
        artifact, cleanup = refine_artifact(artifact, source_file, original.decode("utf-8"), glossary_html)
        aliases, metadata, conflicts = merge_manual_and_imported({}, artifact["concepts"])
        artifact["provenance"]["vocabulary_conflicts"] = conflicts
        matcher = ConceptMatcher(aliases)
        contexts = exchange.report_contexts(original.decode("utf-8"), matcher.find)
        fragment = render_entries(exchange, artifact["concepts"], contexts,
                                  title="IPCC AR6 SYR Encyclopedia")
        document = ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
                    '<title>IPCC Encyclopedia</title></head><body>' + fragment + '</body></html>')
        if hashlib.sha256(source.read_bytes()).hexdigest() != source_hash:
            raise ValueError("The source report changed during extraction; previous build retained")
        output.mkdir(parents=True, exist_ok=True)
        (output / "wordlist.csv").write_bytes(paths["wordlist"].read_bytes())
        (output / "ipcc_reference.txt").write_bytes(paths["text"].read_bytes())
        (output / "ipcc_encyclopedia.html").write_text(document, encoding="utf-8")
        (output / "report_concepts.json").write_text(json.dumps(report_snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (output / "extracted_concepts.json").write_text(json.dumps(extracted_snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (output / "concept_cleanup.json").write_text(json.dumps(cleanup, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if glossary is not None:
            glossary_output = output / "glossary"
            glossary_output.mkdir(exist_ok=True)
            for name in ("IPCC_AR6_SYR_Glossary.html", "IPCC_AR6_SYR_Glossary.txt", "wordlist.csv", "entries.json"):
                (glossary_output / name).write_bytes((scratch / "glossary" / name).read_bytes())
        manifest = {"provenance": artifact["provenance"], "summary": artifact["summary"]}
        (output / "build.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        target = ROOT / "backend/generated_artifacts/encyclopedia_concepts.json"
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
    if config.get("papers"):
        parser = argparse.ArgumentParser(description="Rebuild the Encyclopedia from the configured report, glossary HTML and approved PMC papers, with existing Wikipedia enrichment.")
        wikipedia_options = parser.add_mutually_exclusive_group()
        wikipedia_options.add_argument("--enrich-existing", action="store_true",
                                       help="Reuse valid scientific extraction caches and refresh Wikipedia enrichment")
        wikipedia_options.add_argument("--no-wikipedia", action="store_true",
                                       help="Skip Wikipedia enrichment for this explicit build")
        args = parser.parse_args()
        from backend.encyclopedia.corpus import build_corpus
        print(json.dumps(build_corpus(ROOT, refresh_wikipedia=args.enrich_existing,
                                     add_wikipedia=not args.no_wikipedia)["summary"], indent=2))
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=source_path())
    parser.add_argument("--top-n", type=int, default=config.get("top_n", 500))
    parser.add_argument("--max-terms", type=int, default=config.get("max_terms", 300))
    parser.add_argument("--min-count", type=int, default=config.get("min_count", 2))
    parser.add_argument("--glossary", type=Path,
                        default=ROOT / config["glossary"] if config.get("glossary") else None,
                        help="IPCC glossary PDF to convert, extract and merge")
    parser.add_argument("--reuse-report", action="store_true",
                        help="Reuse the validated report vocabulary while rebuilding glossary enrichment")
    parser.add_argument("--refine-existing", action="store_true", help="Clean the installed extraction without rerunning txt2phrases or Wikipedia")
    wikipedia_options = parser.add_mutually_exclusive_group()
    wikipedia_options.add_argument("--no-wikipedia", action="store_true", help="Skip new Wikipedia lookups; IPCC glossary definitions remain available")
    wikipedia_options.add_argument("--enrich-existing", action="store_true",
                                   help="Enrich the installed txt2phrases wordlist without rerunning extraction")
    args = parser.parse_args()
    if args.refine_existing:
        if args.reuse_report or args.enrich_existing or args.no_wikipedia:
            parser.error("--refine-existing reuses all installed extraction and enrichment outputs")
        refine_existing()
        return
    build(args.source, top_n=args.top_n, max_terms=args.max_terms,
          min_count=args.min_count, add_wikipedia=not args.no_wikipedia,
          enrich_existing=args.enrich_existing, glossary=args.glossary, reuse_report=args.reuse_report,
          glossary_top_n=config.get("glossary_top_n", 500),
          glossary_max_terms=config.get("glossary_max_terms", 300),
          glossary_min_count=config.get("glossary_min_count", 1))


if __name__ == "__main__":
    main()
