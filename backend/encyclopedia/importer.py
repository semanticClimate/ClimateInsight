"""Standalone importer for exported Encyclopedia HTML files.

The importer intentionally does not import the Encyclopedia runtime or require
amilib. It reads the public ami_entry/ami_dictionary HTML structure and writes
a generated JSON vocabulary for ClimateInsight.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import OrderedDict
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup
from backend.core.paths import GENERATED_CONCEPTS


SCHEMA_VERSION = 1
WIKIDATA_RE = re.compile(r"^[QP]\d+$", re.I)
COMMON_AMBIGUOUS_TERMS = {
    "air", "change", "cloud", "coal", "energy", "feedback", "fire", "flood",
    "forcing", "heat", "media", "oil", "risk", "science", "system", "systems",
    "temperature", "the", "time", "water", "weather", "wind", "world",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _normalise_term(value: str) -> str:
    return _clean_text(value).casefold()


def _valid_wikidata_id(value: str) -> str | None:
    value = _clean_text(value or "").strip()
    if WIKIDATA_RE.fullmatch(value):
        return value.upper()
    return None


def _wikipedia_url(entry) -> str | None:
    for link in entry.select("a[href]"):
        href = _clean_text(link.get("href", ""))
        if "en.wikipedia.org/wiki/" in href:
            if href.startswith("//"):
                return "https:" + href
            return href
    return None


def _description(entry) -> str:
    paragraph = entry.select_one("p.wpage_first_para")
    if paragraph is None:
        paragraph = entry.select_one("p[class*='first_para']")
    return _clean_text(paragraph.get_text(" ", strip=True)) if paragraph else ""


def _synonyms(entry) -> list[str]:
    synonyms: list[str] = []

    canonical_items = entry.select("li.canonical_synonym")
    for item in canonical_items:
        text = _clean_text(item.get_text(" ", strip=True))
        text = re.sub(r"\s*\(canonical\)\s*$", "", text, flags=re.I)
        if text:
            synonyms.append(text)

    for item in entry.select("ul.synonym_list li"):
        text = _clean_text(item.get_text(" ", strip=True))
        text = re.sub(r"\s*\(canonical\)\s*$", "", text, flags=re.I)
        if text:
            synonyms.append(text)

    for attr in ("term", "name"):
        value = _clean_text(entry.get(attr, "") if hasattr(entry, "get") else "")
        if value:
            synonyms.append(value)

    return sorted(set(synonyms), key=lambda value: value.casefold())


def _raw_entry(entry, source_file: str) -> dict | None:
    if not hasattr(entry, "get"):
        return None

    wikidata_id = _valid_wikidata_id(
        entry.get("wikidataID")
        or entry.get("wikidataid")
        or entry.get("wikidata_id")
        or entry.get("data-wikidata-id")
        or entry.get("data-entry-id")
    )

    canonical_candidates = []
    canonical_items = entry.select("li.canonical_synonym")
    if canonical_items:
        for item in canonical_items:
            text = re.sub(
                r"\s*\(canonical\)\s*$",
                "",
                _clean_text(item.get_text(" ", strip=True)),
                flags=re.I,
            )
            if text:
                canonical_candidates.append(text)

    term = _clean_text(entry.get("term", "") or entry.get("name", ""))
    if term:
        canonical_candidates.append(term)

    wikipedia_link = entry.select_one("a.wikipedia-link, a[href*='en.wikipedia.org/wiki/']")
    if wikipedia_link:
        link_text = _clean_text(wikipedia_link.get_text(" ", strip=True))
        if link_text:
            canonical_candidates.append(link_text)

    canonical_name = ""
    if canonical_items:
        canonical_name = _clean_text(canonical_items[0].get_text(" ", strip=True))
        canonical_name = re.sub(
            r"\s*\(canonical\)\s*$",
            "",
            canonical_name,
            flags=re.I,
        )
    elif canonical_candidates:
        canonical_name = canonical_candidates[0]

    if not canonical_name:
        return None

    synonyms = _synonyms(entry)
    synonyms = [item for item in synonyms if _normalise_term(item) != _normalise_term(canonical_name)]

    return {
        "canonical_name": canonical_name,
        "synonyms": synonyms,
        "description": _description(entry),
        "wikidata_id": wikidata_id,
        "wikipedia_url": _wikipedia_url(entry),
        "source_file": source_file,
    }


def _entry_elements(soup: BeautifulSoup):
    return soup.select("[role='ami_entry'], div[role='ami_dictionary'] div[role='ami_entry']")


def extract_file(path: Path, source_root: Path | None = None) -> tuple[list[dict], int]:
    try:
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    except (OSError, UnicodeDecodeError):
        return [], 0

    entries = _entry_elements(soup)
    source_root = source_root or path.parent
    try:
        source_file = path.resolve().relative_to(source_root.resolve()).as_posix()
    except ValueError:
        source_file = path.as_posix()

    raw_entries = []
    for entry in entries:
        raw = _raw_entry(entry, source_file)
        if raw:
            raw_entries.append(raw)
    return raw_entries, len(entries)


def iter_source_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path] if input_path.suffix.lower() in {".html", ".htm", ".xml"} else []
    if input_path.is_dir():
        return sorted(
            (
                path for path in input_path.rglob("*")
                if path.is_file() and path.suffix.lower() in {".html", ".htm", ".xml"}
            ),
            key=lambda path: path.as_posix().casefold(),
        )
    return []


def build_normalized_vocabulary(
    input_path: Path,
    source_root: Path | None = None,
) -> tuple[dict, dict]:
    input_path = input_path.resolve()
    if source_root is None:
        source_root = input_path if input_path.is_dir() else input_path.parent
    else:
        source_root = source_root.resolve()
    files = iter_source_files(input_path)

    raw_entries: list[dict] = []
    source_entries: dict[str, int] = {}
    skipped = []
    for path in files:
        extracted, discovered = extract_file(path, source_root)
        raw_entries.extend(extracted)
        try:
            source_key = path.resolve().relative_to(source_root.resolve()).as_posix()
        except ValueError:
            source_key = path.as_posix()
        source_entries[source_key] = discovered
        if discovered and len(extracted) == 0:
            skipped.append({"source_file": path.name, "reason": "no usable ami_entry fields"})

    groups: OrderedDict[tuple[str, str], dict] = OrderedDict()
    for raw in raw_entries:
        wikidata_id = raw["wikidata_id"]
        if wikidata_id:
            key = ("wikidata", wikidata_id)
        else:
            key = ("name", _normalise_term(raw["canonical_name"]))

        if key not in groups:
            groups[key] = {
                "canonical_name": raw["canonical_name"],
                "synonyms": set(),
                "description": "",
                "wikidata_id": wikidata_id,
                "wikipedia_url": None,
                "sources": [],
                "canonical_candidates": [],
            }

        group = groups[key]
        group["canonical_candidates"].append(raw["canonical_name"])
        group["synonyms"].update(raw["synonyms"])
        if raw["canonical_name"]:
            group["synonyms"].add(raw["canonical_name"])
        if not group["description"] and raw["description"]:
            group["description"] = raw["description"]
        if not group["wikipedia_url"] and raw["wikipedia_url"]:
            group["wikipedia_url"] = raw["wikipedia_url"]
        if raw["source_file"] not in group["sources"]:
            group["sources"].append(raw["source_file"])

    concepts = []
    for key, group in sorted(groups.items(), key=lambda item: (
        item[1]["wikidata_id"] or "",
        min(item[1]["canonical_candidates"], key=lambda value: value.casefold()).casefold(),
    )):
        canonical_name = min(
            set(group["canonical_candidates"]),
            key=lambda value: value.casefold(),
        )
        synonyms = sorted(
            (item for item in group["synonyms"] if _normalise_term(item) != _normalise_term(canonical_name)),
            key=lambda value: value.casefold(),
        )
        concepts.append({
            "canonical_name": canonical_name,
            "synonyms": synonyms,
            "description": group["description"] or None,
            "wikidata_id": group["wikidata_id"],
            "wikipedia_url": group["wikipedia_url"],
            "source_file": sorted(group["sources"])[0],
        })

    summary = {
        "source_files_processed": len(files),
        "raw_entries_discovered": sum(source_entries.values()),
        "unique_concepts_exported": len(concepts),
        "concepts_with_descriptions": sum(bool(item["description"]) for item in concepts),
        "concepts_with_synonyms": sum(bool(item["synonyms"]) for item in concepts),
        "concepts_with_wikidata_ids": sum(bool(item["wikidata_id"]) for item in concepts),
        "skipped_or_conflicting_entries": len(skipped),
        "skipped": skipped,
    }
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "summary": summary,
        "concepts": concepts,
    }
    return artifact, {"raw_entries": raw_entries, "source_entries": source_entries}


def write_artifact(artifact: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def alias_is_safe(alias: str) -> bool:
    alias = _clean_text(alias)
    normalised = _normalise_term(alias)
    if not alias:
        return False
    if normalised in COMMON_AMBIGUOUS_TERMS:
        return False
    if len(alias) <= 2:
        return False
    if len(alias) <= 3 and not (alias.isupper() and alias.isascii()):
        return False
    return True


def load_generated_concepts(generated_path: Path) -> list[dict]:
    if not generated_path.is_file():
        return []
    try:
        data = json.loads(generated_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    if data.get("schema_version") != SCHEMA_VERSION or not isinstance(data.get("concepts"), list):
        return []
    return [item for item in data["concepts"] if isinstance(item, dict)]


def _identity_name(value: str) -> str:
    return _normalise_term(unquote(value or "").replace("_", " "))


def _article_title(value: str) -> str:
    parsed = urlparse(value or "")
    if parsed.hostname != "en.wikipedia.org" or not parsed.path.startswith("/wiki/"):
        return ""
    return unquote(parsed.path[len("/wiki/"):]).replace("_", " ")


def merge_manual_and_imported(
    manual_map: dict[str, str],
    concepts: Iterable[dict],
) -> tuple[dict[str, str], dict[str, dict], list[dict]]:
    """Use Wikidata identity internally while retaining existing public graph IDs.

    A matching title/article can anchor an imported entity to a manual node.
    An alias collision alone cannot establish that two entities are the same.
    """
    merged = {_normalise_term(alias): title for alias, title in manual_map.items()}
    manual_titles = {_identity_name(title): title for title in manual_map.values()}
    groups: dict[tuple, list[dict]] = {}
    conflicts = []
    for concept in concepts:
        canonical = _clean_text(concept.get("canonical_name", ""))
        if canonical:
            qid = _valid_wikidata_id(concept.get("wikidata_id"))
            key = ("wikidata", qid) if qid else ("name", _identity_name(canonical))
            groups.setdefault(key, []).append(concept)

    resolved = []
    for key, records in groups.items():
        records = sorted(records, key=lambda r: (
            _normalise_term(r["canonical_name"]), r["canonical_name"],
            r.get("source_file") or "", r.get("wikipedia_url") or "",
        ))
        anchors = set()
        for record in records:
            for name in (record["canonical_name"], _article_title(record.get("wikipedia_url"))):
                if _identity_name(name) in manual_titles:
                    anchors.add(manual_titles[_identity_name(name)])
        if len(anchors) > 1:
            conflicts.append({"reason": "ambiguous_identity", "canonical_name": records[0]["canonical_name"]})
        target = next(iter(anchors)) if len(anchors) == 1 else _clean_text(records[0]["canonical_name"])
        resolved.append((target, key, records))

    # Do not attach an arbitrary QID when separate entities claim the same title.
    qids_by_target: dict[str, set] = {}
    for target, key, records in resolved:
        if key[0] == "wikidata":
            qids_by_target.setdefault(target, set()).add(key[1])

    metadata: dict[str, dict] = {}
    for target, key, records in sorted(resolved, key=lambda item: (item[0].casefold(), item[0], item[1])):
        ambiguous_qid = len(qids_by_target.get(target, ())) > 1
        aliases = set()
        for record in records:
            aliases.add(_clean_text(record["canonical_name"]))
            aliases.update(_clean_text(a) for a in record.get("synonyms") or [])
        accepted = []
        for alias in sorted(aliases, key=lambda value: (value.casefold(), value)):
            normalised = _normalise_term(alias)
            proved_acronym = (2 <= len(alias) <= 8 and sum(c.isupper() for c in alias) >= 2 and
                              any(proof.get("alias") == alias for record in records for proof in record.get("alias_sources", [])))
            if not alias_is_safe(alias) and not proved_acronym:
                conflicts.append({"alias": alias, "reason": "ambiguous_common_or_short_term", "canonical_name": target})
            elif normalised in merged and merged[normalised] != target:
                conflicts.append({"alias": alias, "reason": "manual_vocabulary_precedence",
                                  "canonical_name": target, "manual_title": merged[normalised]})
            elif not ambiguous_qid:
                merged[normalised] = target
                accepted.append(alias)
        if ambiguous_qid:
            conflicts.append({"reason": "conflicting_wikidata_ids", "canonical_name": target})
            continue
        entry = metadata.setdefault(target, {
            "canonical_name": target, "synonyms": [], "description": None,
            "wikidata_id": None, "wikipedia_url": None, "source_file": None,
        })
        entry["synonyms"] = sorted(set(entry["synonyms"] + accepted) - {target}, key=lambda value: (value.casefold(), value))
        for record in records:
            for field in ("description", "wikidata_id", "wikipedia_url", "source_file"):
                if not entry[field] and record.get(field):
                    entry[field] = _valid_wikidata_id(record[field]) if field == "wikidata_id" else record[field]
            # Carry definition provenance through to graph metadata and the
            # report viewer; an IPCC definition must never be labelled Wikipedia.
            for field in ("description_source", "definition_source", "wikipedia_description", "replaced_report_identities"):
                if record.get(field) and not entry.get(field):
                    entry[field] = record[field]
            for field in ("alias_sources", "source_excerpts", "term_sources"):
                for proof in record.get(field, []):
                    if proof not in entry.setdefault(field, []):
                        entry[field].append(proof)
            if record.get("source_files"):
                entry["source_files"] = sorted(set(entry.get("source_files", []) + record["source_files"]))
    return merged, metadata, conflicts


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a ClimateInsight vocabulary from Encyclopedia HTML/XML exports.")
    parser.add_argument("input", help="HTML/XML file or directory containing Encyclopedia exports")
    parser.add_argument(
        "--output",
        default=str(GENERATED_CONCEPTS),
        help="Destination JSON artifact",
    )
    parser.add_argument(
        "--source-root",
        default=None,
        help="Root used to write relative source-file provenance",
    )
    args = parser.parse_args()

    artifact, _ = build_normalized_vocabulary(
        Path(args.input),
        Path(args.source_root).resolve() if args.source_root else None,
    )
    write_artifact(artifact, Path(args.output))
    print(json.dumps(artifact["summary"], indent=2))


if __name__ == "__main__":
    main()
