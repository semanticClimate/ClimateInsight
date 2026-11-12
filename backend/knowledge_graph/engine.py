"""
engine.py — Corpus-wide concept knowledge graph.

Builds one graph that connects every encyclopedia concept found in the
indexed sources (IPCC AR6 report + research papers):

  Nodes  : concepts from the Semantic Climate encyclopedia
           (extracted from the IPCC report, glossary HTML and 12 approved papers;
            Wikipedia supplies supplementary descriptions and identities).
           Synonyms ("sea-level rise", "sea level rise") merge into one
           node, keyed by the resolved article title or extracted term.
  Edges  : concepts share a sentence or a local window of at most 60 words.
           The displayed weight counts indexed passages with that evidence.
  Groups : Louvain communities use frequency-adjusted local co-occurrence;
           names describe representative concepts, with glossary terms preferred.

Deliberately AI-free: every node and edge is traceable to the passages
it came from, so the graph can be checked by hand. Built with networkx
(BSD-3) from the ChromaDB collection; cached until the collection or the
encyclopedia changes.

Display edges
-------------
The full co-occurrence graph is too dense to read (thousands of links).
The edges sent for display are the union of:
  - a maximum spanning forest  → every concept stays connected to the
    rest of its component through its strongest chain of links, and
  - each concept's TOP_K strongest links → local structure is visible.
Every local-evidence link remains available in neighbours and subgraphs.
"""

from __future__ import annotations

import itertools
import math
import re
import threading
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote

import networkx as nx
from backend.encyclopedia.concepts import noise_reason, normalise as normalise_term
from backend.knowledge_graph.topics import association_weight, relation_units, topic_representatives
from backend.encyclopedia.importer import (
    load_generated_concepts,
    merge_manual_and_imported,
)

from backend.encyclopedia.service import source_concepts, vocabulary_signature, settings
from backend.core.paths import PROJECT_ROOT as ROOT


def get_collection():
    # Vocabulary and glossary requests do not need to initialize the vector store.
    from backend.vectorstore.chroma_client import get_collection as collection
    return collection()

ENCYCLOPEDIA_JS = ROOT / "encyclopedia_assets" / "climate-wiki.js"
GENERATED_ENCYCLOPEDIA_JSON = ROOT / "backend" / "generated_artifacts" / "encyclopedia_concepts.json"
DEFAULT_IPCC_DOC = "ipcc_reference"

TOP_K = 3          # strongest links kept per concept for display
MAX_SOURCES = 8    # sources listed per concept
MAX_FOCUS = 15     # concepts highlighted for a question
MAX_MAIN = 3       # main (asked-about) concepts per question

# Short encyclopedia keys are mostly acronyms or chemical formulas
# ("no" → NO / nitric oxide, "co" → CO / carbon monoxide, "cop" → COP).
# Matched case-insensitively they hit ordinary words, so short keys must
# appear with at least one capital letter — except these real words/units.
SHORT_KEY_LEN = 4
LOWERCASE_OK = {"coal", "oil", "firn", "buoy", "ppm", "ppb", "2°c", "2 c"}
ACRONYMS = {"afolu", "beccs", "hcfcs", "llghg", "nmvoc", "slcps"}  # longer acronyms

# HTML extraction flattens subscripts: "CO<sub>2</sub>" becomes "CO 2", whose
# "CO" would then match carbon monoxide. Re-join formulas before matching.
_FORMULA_N2O = re.compile(r"\bN\s?2\s?O\b")
_FORMULA = re.compile(r"\b(CO|CH|SO|NO|NH|SF|NF|O)\s([2-6])\b")

# Concepts that are IPCC calibrated uncertainty language, not topics.
# They appear in almost every passage and would link everything to
# everything, so they are left out of the graph (tooltips still show them).
EXCLUDED_CONCEPTS = {"Likelihood"}


# ── Encyclopedia ──────────────────────────────────────────────────────────────


def load_manual_encyclopedia(path: Path = ENCYCLOPEDIA_JS) -> dict[str, str]:
    """Parse the archived manual WIKI_MAP → {lowercase term: title}."""
    if path == ENCYCLOPEDIA_JS:
        path = ROOT / "encyclopedia_assets/climate-wiki.legacy.js"
    src = path.read_text(encoding="utf-8")
    start = src.index("const WIKI_MAP = {")
    end = src.index("\n  };", start)
    pairs = re.findall(r'^\s*"([^"]+)"\s*:\s*"([^"]+)"', src[start:end], re.M)
    return {term.lower(): title for term, title in pairs}


_import_metadata: dict[str, dict] = {}
_import_conflicts: list[dict] = []


def load_encyclopedia(
    path: Path = ENCYCLOPEDIA_JS,
    generated_path: Path = GENERATED_ENCYCLOPEDIA_JSON,
) -> dict[str, str]:
    """Read approved-corpus concepts; manual mappings are used only in legacy mode."""
    global _import_metadata, _import_conflicts
    manual_map = load_manual_encyclopedia(path) if settings()[0] == "legacy" else {}
    concepts = source_concepts(generated_path)
    merged, _import_metadata, _import_conflicts = merge_manual_and_imported(manual_map, concepts)
    return merged


def imported_concept_metadata(concept_name: str) -> dict | None:
    return _import_metadata.get(concept_name)


def _requires_capital(term: str) -> bool:
    return term in ACRONYMS or (len(term) <= SHORT_KEY_LEN and term not in LOWERCASE_OK)


def _looks_like_acronym(matched: str) -> bool:
    """All capitals or at least two (NO, CO2, NDCs) — not "no" or "No"."""
    letters = [ch for ch in matched if ch.isascii() and ch.isalpha()]
    capitals = sum(ch.isupper() for ch in letters)
    return capitals >= 2 or (bool(letters) and capitals == len(letters))


def _normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = _FORMULA_N2O.sub("N2O", text or "")
    return _FORMULA.sub(r"\1\2", text)


class ConceptMatcher:
    """Finds encyclopedia concepts in text (longest term wins)."""

    def __init__(self, wiki_map: dict[str, str]):
        self.wiki_map = {
            term: title for term, title in wiki_map.items()
            if title not in EXCLUDED_CONCEPTS and not noise_reason(title) and not noise_reason(term)
        }
        terms = sorted(self.wiki_map, key=len, reverse=True)
        self._normalised = {normalise_term(term): title for term, title in self.wiki_map.items()}
        expressions = [r"[\s\u2010-\u2015-]+".join(re.escape(w) for w in re.split(r"[\s\u2010-\u2015-]+", term)) for term in terms]
        self.pattern = re.compile(
            r"(?<![\w-])(" + "|".join(expressions) + r")(?![\w-])" if terms else r"(?!)",
            re.IGNORECASE,
        )

    def spans(self, text: str) -> tuple[str, list[tuple[str, int, int]]]:
        """
        Return (normalised text, [(concept title, start, end), ...]).

        Offsets refer to the normalised text (flattened formulas re-joined),
        which is also what passage snippets are cut from.
        """
        norm = _normalise(text)
        out = []
        for m in self.pattern.finditer(norm):
            matched = m.group(1)
            term = normalise_term(matched)
            if _requires_capital(term) and not _looks_like_acronym(matched):
                continue  # "no", "No", "co" … as ordinary words
            out.append((self._normalised[term], m.start(1), m.end(1)))
        return norm, out

    def find(self, text: str) -> Counter:
        """Return {concept title: occurrences} for *text*."""
        return Counter(title for title, _, _ in self.spans(text)[1])


# ── Sources ───────────────────────────────────────────────────────────────────


def _source_of(meta: dict) -> tuple[str, dict]:
    """Stable key + display info for the document section a chunk came from."""
    pmcid = meta.get("pmcid", "")
    if pmcid or meta.get("source_type") == "research_article":
        key = pmcid or Path(meta.get("source_path", "")).stem
        return key, {
            "type": "paper",
            "label": meta.get("citation_label") or meta.get("document_title") or key,
            "pmcid": pmcid,
            "doi": meta.get("doi", ""),
        }
    section = meta.get("section", "")
    title = meta.get("section_title", "")
    doc = _ipcc_doc(meta)
    key = f"ipcc:{section}" if doc == DEFAULT_IPCC_DOC else f"ipcc:{doc}:{section}"
    report = "" if doc == DEFAULT_IPCC_DOC else (meta.get("document_title") or doc)
    return key, {
        "type": "ipcc",
        "label": " ".join(p for p in ("IPCC AR6", report, section, title) if p),
        "section": section,
        "document": doc,
    }


def _ipcc_doc(meta: dict) -> str:
    """Identify the report by source filename, keeping old SYR metadata working."""
    return Path(meta.get("source_path") or "").stem or DEFAULT_IPCC_DOC


# ── Graph construction ───────────────────────────────────────────────────────


def _bridge_components(G: nx.Graph, concept_sources: dict, concept_chunks: Counter) -> list:
    """
    Connect concepts that share no local evidence window with the main graph.

    A concept that only ever appears alone in its local text windows would float
    unconnected. Each such component is linked to the most-mentioned
    main-graph concept from the same source section / paper — a real but
    weaker relation, marked kind="source" (drawn dashed) with weight 0.5,
    below any passage link.
    """
    comps = sorted(nx.connected_components(G), key=lambda c: (-len(c), sorted(c)))
    if len(comps) <= 1:
        return []

    main = set(comps[0])
    in_source: dict = defaultdict(set)   # source key → main-graph concepts
    for c in main:
        for key in concept_sources[c]:
            in_source[key].add(c)

    bridges = []
    for comp in comps[1:]:
        best = None
        for c in sorted(comp):
            for key, n in sorted(concept_sources[c].items()):
                for m in sorted(in_source.get(key, ())):
                    score = (n, concept_chunks[m])
                    if best is None or score > best[0]:
                        best = (score, c, m, key)
        if best is None:
            continue  # shares no source with anything: leave it unconnected
        _, c, m, key = best
        G.add_edge(c, m, weight=0.5, association=0.01, kind="source", source=key)
        bridges.append({"from": c, "to": m, "source": key})
        main |= comp
        for n in comp:
            for k in concept_sources[n]:
                in_source[k].add(n)
    return bridges


def _build() -> dict:
    matcher = ConceptMatcher(load_encyclopedia())
    data = get_collection().get(include=["documents", "metadatas"])

    concept_chunks: Counter = Counter()          # concept → passages mentioning it
    concept_sources: dict = defaultdict(Counter)  # concept → {source key: passages}
    concept_kinds: dict = defaultdict(set)        # concept → {"ipcc", "paper"}
    pair_weights: Counter = Counter()             # (a, b) → shared passages
    pair_units: Counter = Counter()
    concept_units: Counter = Counter()
    pair_passages: dict = defaultdict(list)
    unit_count = 0
    concept_passages: dict = defaultdict(list)    # concept → passage indices
    sources: dict = {}

    for i, (text, meta) in enumerate(zip(data["documents"], data["metadatas"])):
        concepts = sorted(matcher.find(text))
        if not concepts:
            continue
        key, info = _source_of(meta or {})
        sources.setdefault(key, info)
        for c in concepts:
            concept_passages[c].append(i)
            concept_chunks[c] += 1
            concept_sources[c][key] += 1
            concept_kinds[c].add(info["type"])
        local_pairs = set()
        for unit in relation_units(text):
            local_concepts = sorted(matcher.find(unit))
            if not local_concepts:
                continue
            unit_count += 1
            concept_units.update(local_concepts)
            for pair in itertools.combinations(local_concepts, 2):
                pair_units[pair] += 1
                local_pairs.add(pair)
        for pair in sorted(local_pairs):
            pair_weights[pair] += 1
            pair_passages[pair].append(i)

    G = nx.Graph()
    G.add_nodes_from(concept_chunks)
    for (a, b), w in pair_weights.items():
        strength = association_weight(pair_units[(a, b)], concept_units[a], concept_units[b], unit_count)
        G.add_edge(a, b, weight=w, association=strength, kind="passage")

    passage_components = nx.number_connected_components(G)
    # Partition local-evidence edges before adding any weak display bridges.
    communities = (
        nx.community.louvain_communities(G, weight="association", seed=42)
        if G.number_of_edges() else [{n} for n in G]
    )
    communities = sorted(communities, key=lambda c: -sum(concept_chunks[n] for n in c))
    group_of, groups = {}, []
    for i, members in enumerate(communities):
        topics = topic_representatives(G, members, concept_chunks, _import_metadata)
        label = " / ".join(topic[0].upper() + topic[1:] for topic in topics[:2])
        groups.append({"id": i, "label": label, "topics": topics, "size": len(members)})
        for n in members:
            group_of[n] = i
    bridges = _bridge_components(G, concept_sources, concept_chunks)

    # Display edges: maximum spanning forest ∪ top-K links per concept
    shown = {tuple(sorted((u, v))) for u, v in nx.maximum_spanning_edges(G, weight="association", data=False)}
    for n in G:
        strongest = sorted(G[n].items(), key=lambda kv: (-kv[1].get("association", 0), -kv[1]["weight"], kv[0]))[:TOP_K]
        shown.update(tuple(sorted((n, m))) for m, _ in strongest)

    nodes = []
    for n in G:
        neighbours = sorted(G[n].items(), key=lambda kv: (-kv[1].get("association", 0), -kv[1]["weight"], kv[0]))
        imported = imported_concept_metadata(n)
        nodes.append({
            "id": n,
            "label": n,
            "wiki": n,
            "count": concept_chunks[n],
            "group": group_of[n],
            "kinds": sorted(concept_kinds[n]),
            "degree": G.degree(n),
            "neighbors": [
                {"id": m, "weight": d["weight"], "kind": d["kind"]}
                for m, d in neighbours[:10]
            ],
            "sources": [
                {"key": k, "passages": c}
                for k, c in concept_sources[n].most_common(MAX_SOURCES)
            ],
            **({"encyclopedia": imported} if imported else {}),
        })

    edges = [
        {"from": a, "to": b, "weight": G[a][b]["weight"], "kind": G[a][b]["kind"]}
        for a, b in sorted(shown)
    ]

    components = list(nx.connected_components(G))
    stats = {
        "encyclopedia_concepts": len(set(matcher.wiki_map.values())),
        "concepts": G.number_of_nodes(),
        "links": len(pair_weights),
        "links_shown": len(edges),
        "source_bridges": len(bridges),
        "passages": len(data["documents"]),
        "components_by_passage": passage_components,
        "components": len(components),
        "largest_component": max((len(c) for c in components), default=0),
        "clusters": len(groups),
        "relation_units": unit_count,
        "relation_scope": "sentence_or_60_word_window",
        "clustering_weight": "frequency_adjusted_local_cooccurrence",
    }

    return {
        "graph": {
            "nodes": nodes,
            "edges": edges,
            "groups": groups,
            "sources": sources,
            "stats": stats,
        },
        "matcher": matcher,
        "G": G,
        "documents": data["documents"],
        "metadatas": data["metadatas"],
        "concept_passages": concept_passages,
        "pair_passages": pair_passages,
    }


_cache: dict = {}
_lock = threading.Lock()


def _state() -> dict:
    """Build once; rebuild when the collection or encyclopedia changes."""
    generated_mtime = (
        GENERATED_ENCYCLOPEDIA_JSON.stat().st_mtime
        if GENERATED_ENCYCLOPEDIA_JSON.is_file()
        else None
    )
    key = (
        get_collection().count(),
        ENCYCLOPEDIA_JS.stat().st_mtime,
        generated_mtime,
        vocabulary_signature(),
    )
    with _lock:
        if _cache.get("key") != key:
            _cache["state"] = _build()
            _cache["key"] = key
        return _cache["state"]


# ── Public API ────────────────────────────────────────────────────────────────


def get_graph() -> dict:
    """The full knowledge graph: {nodes, edges, groups, sources, stats}."""
    return _state()["graph"]


def focus_concepts(question: str, chunks: list[dict]) -> list[str]:
    """
    Concepts relevant to a question: those named in the question itself,
    then those most mentioned in the retrieved passages.
    """
    state = _state()
    matcher, G = state["matcher"], state["G"]

    scores: Counter = Counter()
    for c, n in matcher.find(question).items():
        scores[c] += 10 * n            # named in the question → always first
    for chunk in chunks:
        weight = max(chunk.get("score") or 0.0, 0.1)
        for c, n in matcher.find(chunk.get("text", "")).items():
            frequency = len(state["concept_passages"].get(c, []))
            specificity = 1 + math.log((1 + len(state["documents"])) / (1 + frequency))
            scores[c] += n * weight * specificity

    return [c for c, _ in scores.most_common() if c in G][:MAX_FOCUS]


def main_concepts(question: str, focus: list[str]) -> list[str]:
    """
    The concept(s) the question is about — shown as the hub of the view.

    These are the concepts named in the question itself (up to MAX_MAIN,
    most-mentioned first). If the question names none (e.g. it uses a word
    the encyclopedia doesn't cover), the top-ranked focus concept is used.
    """
    state = _state()
    G, nodes = state["G"], {n["id"]: n for n in state["graph"]["nodes"]}
    named = [c for c in state["matcher"].find(question) if c in G]
    named.sort(key=lambda c: -nodes[c]["count"])
    if named:
        return named[:MAX_MAIN]
    return focus[:1]


def subgraph(concepts: list[str]) -> dict:
    """Nodes for *concepts* plus every co-occurrence link among them."""
    state = _state()
    G = state["G"]
    by_id = {n["id"]: n for n in state["graph"]["nodes"]}
    keep = [c for c in concepts if c in G]
    H = G.subgraph(keep)
    return {
        "nodes": [by_id[c] for c in keep],
        "edges": [
            {"from": a, "to": b, "weight": d["weight"], "kind": d["kind"]}
            for a, b, d in H.edges(data=True)
        ],
    }


# ── Sources behind a concept or a link ───────────────────────────────────────

MAX_PASSAGES = 40      # passages returned per concept / link
SNIPPET_CHARS = 420    # longest single-sentence excerpt
_SENTENCE = re.compile(r"[^.!?]+(?:[.!?]+|$)")


def _link_for(meta: dict) -> str:
    """Where the reader can open the source of a passage."""
    pmcid = meta.get("pmcid", "")
    if pmcid:
        return f"/paper/{re.sub(r'^PMC', '', pmcid, flags=re.I)}"
    if meta.get("doi"):
        return f"https://doi.org/{meta['doi']}"
    if meta.get("source_type") == "ipcc_report":
        anchor = meta.get("html_id") or meta.get("section")
        if not anchor:
            return ""
        doc = _ipcc_doc(meta)
        query = "" if doc == DEFAULT_IPCC_DOC else f"?doc={quote(doc, safe='')}"
        return f"/ipcc-reference{query}#{quote(anchor, safe='')}"
    return ""


def _snippet(text: str, spans: list, targets: list[str]) -> tuple[str, list]:
    """
    Cut the sentence(s) that mention the target concepts out of a passage.

    Prefers one sentence naming every target; otherwise the first sentence
    naming each. Returns (snippet, [[start, end], ...]) where the ranges
    mark the target terms inside the snippet, for highlighting.
    """
    sentences = [(m.start(), m.end()) for m in _SENTENCE.finditer(text)]
    hits = [(t, a, b) for t, a, b in spans if t in targets]

    def sentence_at(pos):
        return next(((s, e) for s, e in sentences if s <= pos < e), (pos, pos))

    chosen = []
    for s, e in sentences:
        if {t for t, a, _ in hits if s <= a < e} >= set(targets):
            chosen = [(s, e)]
            break
    if not chosen:
        for t in targets:
            first = next((a for tt, a, _ in hits if tt == t), None)
            if first is not None and sentence_at(first) not in chosen:
                chosen.append(sentence_at(first))
    chosen.sort()

    parts, marks, offset = [], [], 0
    for s, e in chosen:
        # Trim whitespace, then cap very long sentences around the first hit
        while s < e and text[s].isspace():
            s += 1
        while e > s and text[e - 1].isspace():
            e -= 1
        prefix = suffix = ""
        if e - s > SNIPPET_CHARS:
            first = next((a for _, a, _ in hits if s <= a < e), s)
            start = max(s, first - SNIPPET_CHARS // 3)
            end = min(e, start + SNIPPET_CHARS)
            prefix = "…" if start > s else ""
            suffix = "…" if end < e else ""
            s, e = start, end
        if parts:
            parts.append(" … ")
            offset += 3
        parts.append(prefix)
        offset += len(prefix)
        for _, a, b in hits:
            if s <= a and b <= e:
                marks.append([offset + a - s, offset + b - s])
        parts.append(text[s:e] + suffix)
        offset += e - s + len(suffix)
    return "".join(parts), marks


def _passages(indices: list[int], targets: list[str]) -> list[dict]:
    state = _state()
    matcher, docs, metas = state["matcher"], state["documents"], state["metadatas"]
    out = []
    for i in indices:
        meta = metas[i] or {}
        norm, spans = matcher.spans(docs[i])
        if len(targets) > 1:
            # Show a real local witness for a relationship, rather than two
            # unrelated sentences that happen to share a retrieval chunk.
            witness = next((unit for unit in relation_units(norm) if set(matcher.find(unit)) >= set(targets)), None)
            if witness:
                norm, spans = matcher.spans(witness)
        _, info = _source_of(meta)
        snippet, marks = _snippet(norm, spans, targets)
        out.append({
            "source": info["label"],
            "type": info["type"],
            "part": meta.get("section_title", "") if info["type"] == "paper" else "",
            "link": _link_for(meta),
            "doi": meta.get("doi", ""),
            "snippet": snippet,
            "highlights": marks,
            "mentions": sum(1 for t, _, _ in spans if t in targets),
        })
    out.sort(key=lambda p: -p["mentions"])
    return out[:MAX_PASSAGES]


def concept_resources(concept: str) -> dict:
    """Every passage that mentions *concept*, with the sentence it appears in."""
    state = _state()
    if concept not in state["G"]:
        raise KeyError(concept)
    indices = state["concept_passages"][concept]
    return {
        "concept": concept,
        "total": len(indices),
        "passages": _passages(indices, [concept]),
    }


def link_resources(a: str, b: str) -> dict:
    """
    The passages behind a link: those containing a local co-occurrence. For a
    source-section link (dashed), the two concepts share no local text window,
    so the passages mentioning either one in that shared source are given.
    """
    state = _state()
    G = state["G"]
    if not G.has_edge(a, b):
        raise KeyError(f"{a} — {b}")
    edge = G[a][b]
    pa, pb = state["concept_passages"][a], state["concept_passages"][b]

    if edge["kind"] == "source":
        key = edge.get("source", "")
        metas = state["metadatas"]
        indices = [i for i in sorted(set(pa) | set(pb)) if _source_of(metas[i] or {})[0] == key]
        note = ("These concepts have no shared sentence or local text window. "
                "They are linked because both appear in the same source section.")
    else:
        indices = state["pair_passages"].get(tuple(sorted((a, b))), [])
        note = "Both concepts appear in the same sentence or a local window of up to 60 words in each passage."

    return {
        "from": a,
        "to": b,
        "kind": edge["kind"],
        "total": len(indices),
        "note": note,
        "passages": _passages(indices, [a, b]),
    }
