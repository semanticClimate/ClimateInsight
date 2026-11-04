"""ClimateInsight adapter for one local IPCC report, without building a graph.

Reuse the IPCC txt2phrases adapter, case folding, and the main Encyclopedia
entry generator. Callers choose all output paths; no report or vector store is
modified. Model loading and Wikipedia access happen only during this build.
"""

from __future__ import annotations

import csv
from pathlib import Path

from lxml import html

from encyclopedia_service import exchange_module

# Resolve the configured sibling package before importing its existing helpers.
exchange_module()

from encyclopedia.ipcc.cli import _extract_keywords_with_txt2phrases, _prepare_text_inputs


def prepare_report(source: Path, output_dir: Path) -> Path:
    """Remove executable/navigation content before the existing text adapter."""
    source = Path(source)
    root = html.document_fromstring(source.read_text(encoding="utf-8"))
    for node in root.xpath("//script|//style|//noscript|//nav|//*[@role='ami_encyclopedia']"):
        node.drop_tree()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cleaned = output_dir / source.name
    cleaned.write_text(html.tostring(root, encoding="unicode"), encoding="utf-8")
    return _prepare_text_inputs([cleaned], output_dir)[0]


def extract_report_wordlist(source, output_dir, *, top_n=500, max_terms=300, min_count=2):
    """Extract and rank report terms using the same workflow as ipcc.cli."""
    from encyclopedia.ipcc.phase1_wordlist import aggregate_keyword_counts

    if min(top_n, max_terms, min_count) < 1:
        raise ValueError("top_n, max_terms and min_count must be positive")
    output_dir = Path(output_dir)
    prepared = prepare_report(Path(source), output_dir / "prepared")
    keywords = output_dir / "keywords"
    # Use a fresh build directory: stale CSVs from an older source must not mix in.
    if keywords.exists():
        raise ValueError(f"Use a fresh build directory: {keywords}")
    _extract_keywords_with_txt2phrases([prepared], keywords, top_n)
    counts = aggregate_keyword_counts(sorted(keywords.glob("*.csv")))
    ranked = sorted(
        ((term, count) for term, count in counts.items()
         if count >= min_count and 1 <= len(term.split()) <= 8),
        key=lambda item: (-item[1], item[0].casefold()),
    )
    if not ranked:
        raise ValueError("The extractor produced no terms meeting the count threshold")
    wordlist = output_dir / "wordlist.csv"
    with wordlist.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["term", "count", "manual_delete", "selected"])
        writer.writerows((term, count, "No", "Yes" if i < max_terms else "No")
                         for i, (term, count) in enumerate(ranked))
    return [term for term, _ in ranked[:max_terms]], wordlist, prepared


def build_report_encyclopedia(source, output_dir, *, top_n=500, max_terms=300,
                              min_count=2, add_wikipedia=True):
    """HTML -> model keyphrases -> Wikipedia-backed ami_entry HTML.

    Returns the actual AmiEncyclopedia and build paths so an application can
    export its own vocabulary while keeping unresolved extracted terms.
    """
    from encyclopedia.pipeline.query_to_encyclopedia import create_encyclopedia_from_terms

    output_dir = Path(output_dir)
    terms, wordlist, prepared = extract_report_wordlist(
        source, output_dir, top_n=top_n, max_terms=max_terms, min_count=min_count,
    )
    target = output_dir / "ipcc_encyclopedia.html"
    encyclopedia = create_encyclopedia_from_terms(
        terms, "IPCC AR6 SYR Longer Report Encyclopedia", target,
        add_wikipedia=add_wikipedia,
    )
    return encyclopedia, {"html": target, "wordlist": wordlist, "text": prepared}
