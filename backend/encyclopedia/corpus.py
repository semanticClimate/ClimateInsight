"""Build from the approved report, glossary HTML and explicitly listed papers.

Term extraction still uses txt2phrases/KBIR; Wikipedia enrichment uses the
existing Encyclopedia helper. Document evidence and external descriptions have
separate provenance. Cached descriptions never supply candidate terms.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
import csv
from datetime import datetime, timezone
from html import escape
import gc
from importlib.metadata import version
import json
from pathlib import Path
import re
import shutil
import tempfile

from backend.encyclopedia.concepts import normalise, refine_concepts
from backend.encyclopedia.glossary import merge_glossary, render_entries
from backend.encyclopedia.importer import build_normalized_vocabulary, merge_manual_and_imported, write_artifact
from backend.encyclopedia.sources import POLICY, configuration, digest, load_documents


MODEL = "ml6team/keyphrase-extraction-kbir-inspec"
PREPROCESSOR_VERSION = 1


def _save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    ready = path.with_suffix(path.suffix + ".tmp")
    ready.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ready.replace(path)


def _markup(document):
    return "<html><body>" + ''.join(f'<h2>{escape(h)}</h2>' for h in document.headings) + ''.join(
        f'<p id="{escape(p["html_id"], quote=True)}">{escape(p["text"])}</p>' for p in document.paragraphs
    ) + "</body></html>"


def _extract_corpus_keywords(inputs, output, top_n):
    """Use the same extractor, grouping independent sentences by length.

    This avoids padding every sentence to the longest sentence in an arbitrary
    batch. Each sentence is still processed independently by the original KBIR
    pipeline, and its existing counting/stop-word/ranking code is unchanged.
    """
    from txt2phrases.keyword import KeywordExtraction

    class LengthOrderedExtraction(KeywordExtraction):
        def _read_text(self, file_path, method="sentence"):
            sentences = super()._read_text(file_path, method=method)
            return sorted(sentences, key=len) if method == "sentence" else sentences

    for source in inputs:
        LengthOrderedExtraction(input_path=str(source), output_folder=str(output), top_n=top_n).extract()


def extract_document(document, root, cache, config):
    from backend.encyclopedia.pipeline import extract_report_wordlist, prepare_report

    output = cache / Path(document.source_file).stem
    metadata = {"source_file": document.source_file, "source_sha256": document.sha256,
                "model": MODEL, "preprocessor_version": PREPROCESSOR_VERSION,
                "top_n": config.get("top_n", 500), "max_terms": config.get("max_terms", 300),
                "min_count": config.get("glossary_min_count", 1) if document.kind == "ipcc_glossary" else config.get("min_count", 2)}
    marker = output / "source.json"
    content = normalise(document.content)

    def is_literal(term):
        return bool(re.search(r"(?<!\w)" + re.escape(normalise(term)) + r"(?!\w)", content))

    published = root / "encyclopedia_assets/generated/extraction" / output.name
    if not marker.exists() and (published / "source.json").exists():
        shutil.copytree(published, output, dirs_exist_ok=True)
    validated = None
    if marker.exists():
        saved = json.loads(marker.read_text(encoding="utf-8"))
        if ((output / "wordlist.csv").is_file()
                and saved.get("wordlist_sha256") == digest(output / "wordlist.csv")
                and all(is_literal(term) for term in saved["accepted_terms"])):
            validated = saved
            if saved.get("input") == metadata:
                terms = saved["accepted_terms"]
                print(f'Using validated extraction: {document.source_file} ({len(terms)} terms)', flush=True)
                return terms, output
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="extract-", dir=cache) as scratch:
        scratch = Path(scratch)
        source = scratch / (Path(document.source_file).stem + ".html")
        source.write_text(_markup(document), encoding="utf-8")
        if (validated and {**validated["input"], "source_sha256": document.sha256} == metadata
                and (output / "source.txt").is_file()):
            prepared = prepare_report(source, scratch / "prepared")
            # XML formatting and metadata can change without changing the exact
            # model input. Reuse only the same input, settings and intact wordlist.
            if prepared.read_text(encoding="utf-8") == (output / "source.txt").read_text(encoding="utf-8"):
                _save(marker, {**validated, "input": metadata})
                terms = validated["accepted_terms"]
                print(f'Using validated extraction (unchanged model input): {document.source_file} ({len(terms)} terms)', flush=True)
                return terms, output
        terms, wordlist, prepared = extract_report_wordlist(source, scratch / "phrases",
            top_n=metadata["top_n"], max_terms=metadata["max_terms"], min_count=metadata["min_count"],
            extract_keywords=_extract_corpus_keywords)
        accepted = [term for term in terms if is_literal(term)]
        accepted = sorted({term for term in accepted + document.keywords if term}, key=lambda s: (s.casefold(), s))
        output.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(wordlist, output / "wordlist.csv")
        shutil.copyfile(prepared, output / "source.txt")
        _save(marker, {"input": metadata, "accepted_terms": accepted,
                       "rejected_nonliteral_terms": [term for term in terms if term not in accepted],
                       "wordlist_sha256": digest(output / "wordlist.csv")})
    print(f'Extracted {len(accepted)} literal terms: {document.source_file}', flush=True)
    return accepted, output


def _seed_wikipedia_cache(target):
    """Preserve existing descriptions, without using them to select terms."""
    if not target.exists():
        return {}
    result = {}
    for record in json.loads(target.read_text(encoding="utf-8")).get("concepts", []):
        description = record.get("wikipedia_description") or (record.get("description") if not record.get("definition_source") else None)
        if not record.get("wikipedia_url") or not description:
            continue
        for term in [record["canonical_name"], *record.get("synonyms", [])]:
            result.setdefault(normalise(term), {"term": term, "search_term": term,
                "wikipedia_url": record["wikipedia_url"], "wikidata_id": record.get("wikidata_id"),
                "description_html": "<p>" + escape(description) + "</p>"})
    return result


def enrich_terms(terms, target, cache, *, refresh=False):
    # The Wikipedia lookup and description extraction are the same helper used
    # before corpus expansion. Caching changes repeated work, not term inputs.
    from encyclopedia.pipeline.query_to_encyclopedia import create_encyclopedia_from_terms

    cache_file = cache / "wikipedia.json"
    entries = {} if refresh else _seed_wikipedia_cache(target)
    if cache_file.exists() and not refresh:
        entries.update(json.loads(cache_file.read_text(encoding="utf-8")))
    pending = [term for term in terms if normalise(term) not in entries]
    print(f'Wikipedia: {len(terms) - len(pending)} cached; {len(pending)} terms to look up', flush=True)

    def lookup(term):
        from hashlib import sha256
        output = cache / "wiki-pages" / (sha256(term.encode()).hexdigest() + ".html")
        encyclopedia = create_encyclopedia_from_terms([term], "ClimateInsight term", output, add_wikipedia=True)
        entry = encyclopedia.entries[0]
        # Figure elements belong to the external renderer, not the JSON cache.
        # These are precisely the fields consumed by the existing exporter.
        return term, {key: entry.get(key) for key in (
            "term", "search_term", "wikipedia_url", "wikidata_id", "description_html", "content_note")}

    with ThreadPoolExecutor(max_workers=4) as executor:
        jobs = [executor.submit(lookup, term) for term in pending]
        for index, job in enumerate(as_completed(jobs), 1):
            term, entry = job.result()
            entries[normalise(term)] = entry
            if index % 10 == 0 or index == len(jobs):
                _save(cache_file, entries)
                print(f'Wikipedia progress: {index}/{len(jobs)}', flush=True)
    return [{**deepcopy(entries[normalise(term)]), "term": term, "search_term": term} for term in terms]


def build_corpus(root, *, refresh_wikipedia=False, add_wikipedia=True):
    from backend.encyclopedia.build import export_records
    from backend.encyclopedia.service import exchange_module
    from backend.knowledge_graph.engine import ConceptMatcher

    root = Path(root).resolve()
    config = configuration(root)
    if refresh_wikipedia and not add_wikipedia:
        raise ValueError("--enrich-existing requires Wikipedia enrichment")
    exchange = exchange_module()
    documents = load_documents(root)
    glossary = documents[1]
    output = root / "encyclopedia_assets/generated"
    target = root / "backend/generated_artifacts/encyclopedia_concepts.json"
    cache = root / "tmp/encyclopedia-build"
    cache.mkdir(parents=True, exist_ok=True)
    selections, origins, directories = {}, {}, {}
    for document in documents:
        print(f'Processing source: {document.source_file}', flush=True)
        terms, directory = extract_document(document, root, cache, config)
        selections[document.source_file] = terms
        directories[document.source_file] = directory
        for term in terms:
            origins.setdefault(normalise(term), []).append({"term": term, "source_file": document.source_file,
                "method": "author_keyword" if term in document.keywords else "txt2phrases"})
        gc.collect()
    terms = sorted({p[0]["term"] for p in origins.values()}, key=lambda s: (s.casefold(), s))
    if add_wikipedia:
        enriched = enrich_terms(terms, target, cache, refresh=True) if refresh_wikipedia else enrich_terms(terms, target, cache)
    else:
        from encyclopedia.pipeline.query_to_encyclopedia import create_encyclopedia_from_terms
        enriched = create_encyclopedia_from_terms(terms, "ClimateInsight terms", cache / "plain_entries.html",
                                                   add_wikipedia=False).entries
    records = []
    for term, entry in zip(terms, enriched):
        proofs = origins[normalise(term)]
        record = export_records([entry], proofs[0]["source_file"])[0]
        record.update({"source_files": sorted({p["source_file"] for p in proofs}), "term_sources": proofs,
                       "description_source": "Wikipedia" if record.get("description") else None})
        records.append(record)
    # Keep the original normalization boundary: multiple extracted phrases can
    # resolve to one Wikipedia/Wikidata entity before official definitions merge.
    portable = cache / "enriched_entries.html"
    portable.write_text(exchange.render_entries(records), encoding="utf-8")
    normalized, _ = build_normalized_vocabulary(portable, cache)
    raw_records, records = records, normalized["concepts"]
    for record in records:
        matching = [raw for raw in raw_records if
                    (raw.get("wikidata_id") == record["wikidata_id"] if record.get("wikidata_id")
                     else normalise(raw["canonical_name"]) == normalise(record["canonical_name"]))]
        record["source_files"] = sorted({source for raw in matching for source in raw["source_files"]})
        record["source_file"] = record["source_files"][0]
        record["term_sources"] = [proof for raw in matching for proof in raw["term_sources"]]
        record["description_source"] = "Wikipedia" if record.get("description") else None
    records = merge_glossary(records, glossary.definitions, selections[glossary.source_file], glossary.source_file)
    for record in records:
        if record.get("definition_source"):
            proof = {"term": record["definition_source"]["term"], "source_file": glossary.source_file, "method": "glossary_heading"}
            if proof not in record.setdefault("term_sources", []):
                record["term_sources"].append(proof)
    records, cleanup = refine_concepts(records, [(d.source_file, _markup(d)) for d in documents])
    for record in records:
        for proof in record.get("alias_sources", []):
            record.setdefault("term_sources", []).append({"term": proof["term"], "source_file": proof["source_file"], "method": "source_abbreviation"})
        if not record.get("term_sources"):
            # A glossary-extracted phrase can be added by merge_glossary.
            source = record["source_file"]
            record["term_sources"] = [{"term": record["canonical_name"], "source_file": source, "method": "txt2phrases"}]
    aliases, _, conflicts = merge_manual_and_imported({}, records)
    # Source-defined abbreviations and glossary headings own their aliases.
    # A Wikipedia redirect must not leave an extra, unrelated article-name
    # entry after its only extracted alias has moved to the source meaning.
    retained, excluded = [], []
    for record in records:
        names = [proof["term"] for proof in record["term_sources"]]
        names.extend(value for proof in record.get("alias_sources", []) for value in (proof["term"], proof["alias"]))
        supported = any(aliases.get(" ".join(name.split()).casefold()) == record["canonical_name"] for name in names)
        if record.get("definition_source") or supported:
            retained.append(record)
        else:
            excluded.append({"term": record["canonical_name"], "reason": "no_retained_source_alias",
                             "source_terms": record["term_sources"]})
    records = retained
    cleanup["removed"].extend(excluded)
    cleanup["output_concepts"] = len(records)
    aliases, _, conflicts = merge_manual_and_imported({}, records)
    matcher = ConceptMatcher(aliases)
    by_name = {record["canonical_name"]: record for record in records}
    for document in documents:
        for paragraph in document.paragraphs:
            for name in matcher.find(paragraph["text"]):
                record = by_name[name]
                examples = record.setdefault("source_excerpts", [])
                if len(examples) < 4 and not any(p["source_file"] == document.source_file for p in examples):
                    examples.append({"source_file": document.source_file, "title": document.title, **paragraph})
    manifest = [{**d.manifest(), "selected_terms": len(selections[d.source_file])} for d in documents]
    provenance = {"source_policy": POLICY, "sources": manifest,
        "source_file": documents[0].source_file, "source_sha256": documents[0].sha256,
        "extractor": "txt2phrases", "extractor_version": version("txt2phrases"), "model": MODEL,
        "top_n": config.get("top_n", 500), "max_terms": config.get("max_terms", 300), "min_count": config.get("min_count", 2),
        "generated_at": datetime.now(timezone.utc).isoformat(), "wikipedia_requested": add_wikipedia,
        "supplementary_sources": {"Wikipedia": "descriptions and article links", "Wikidata": "article-associated identifiers"} if add_wikipedia else {},
        "description_policy": "official_glossary_definitions_preferred; Wikipedia_descriptions_separately_attributed",
        "glossary": {"source_file": glossary.source_file, "source_sha256": glossary.sha256,
                     "html_sha256": glossary.sha256, "defined_terms": len(glossary.definitions)},
        "concept_cleanup": {key: cleanup[key] for key in ("version", "input_concepts", "output_concepts")},
        "vocabulary_conflicts": conflicts}
    artifact = {"schema_version": 1, "provenance": provenance,
        "summary": {"source_files_processed": len(documents), "research_papers_processed": len(documents) - 2,
                    "unique_concepts_exported": len(records), "glossary_defined_terms": len(glossary.definitions),
                    "concepts_with_ipcc_definitions": sum(bool(c.get("definition_source")) for c in records),
                    "concepts_with_descriptions": sum(bool(c.get("description")) for c in records),
                    "concepts_with_wikidata_ids": sum(bool(c.get("wikidata_id")) for c in records),
                    "concepts_with_source_excerpts": sum(bool(c.get("source_excerpts")) for c in records)}, "concepts": records}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="corpus-build-", dir=output.parent) as scratch:
        scratch = Path(scratch)
        for document in documents:
            shutil.copytree(directories[document.source_file], scratch / "extraction" / Path(document.source_file).stem)
        with (scratch / "wordlist.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["term", "source_file", "selected"])
            writer.writerows((term, source, "Yes") for source, selected in selections.items() for term in selected)
        _save(scratch / "source_manifest.json", {"source_policy": POLICY, "sources": manifest})
        _save(scratch / "build.json", {"provenance": provenance, "summary": artifact["summary"]})
        _save(scratch / "concept_cleanup.json", cleanup)
        _save(scratch / "extracted_concepts.json", artifact)
        (scratch / "ipcc_encyclopedia.html").write_text('<!DOCTYPE html><html><head><meta charset="utf-8"><title>ClimateInsight Encyclopedia</title></head><body>'
            + render_entries(exchange, records, title="ClimateInsight Encyclopedia") + '</body></html>', encoding="utf-8")
        if any(digest(root / document.source_file) != document.sha256 for document in documents):
            raise ValueError("An approved source changed during the build; previous build retained")
        output.mkdir(exist_ok=True)
        for item in scratch.iterdir():
            if item.is_dir():
                shutil.copytree(item, output / item.name, dirs_exist_ok=True)
            else:
                shutil.copyfile(item, output / item.name)
        write_artifact(artifact, target.with_suffix(".json.tmp"))
        target.with_suffix(".json.tmp").replace(target)
    return artifact
