"""
knowledge_graph.py — Corpus-wide concept knowledge graph.

Builds one graph that connects every encyclopedia concept found in the
indexed sources (IPCC AR6 report + research papers):

  Nodes  : concepts from the Semantic Climate encyclopedia
           (encyclopedia/climate-wiki.js — term → Wikipedia article).
           Synonyms ("sea-level rise", "sea level rise") merge into one
           node, keyed by the Wikipedia article title.
  Edges  : two concepts are linked when they occur in the same indexed
           passage (chunk); the weight is the number of shared passages.
  Groups : Louvain communities over the weighted graph (clusters of
           concepts that are discussed together).

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
All weights are still used for clustering, neighbours and subgraphs.
"""

from __future__ import annotations

import itertools
import re
import threading
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx

from vectorstore.chroma_client import get_collection

ROOT = Path(__file__).resolve().parent.parent
ENCYCLOPEDIA_JS = ROOT / "encyclopedia" / "climate-wiki.js"

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


def load_encyclopedia(path: Path = ENCYCLOPEDIA_JS) -> dict[str, str]:
    """Parse the WIKI_MAP object in climate-wiki.js → {lowercase term: title}."""
    src = path.read_text(encoding="utf-8")
    start = src.index("const WIKI_MAP = {")
    end = src.index("\n  };", start)
    pairs = re.findall(r'^\s*"([^"]+)"\s*:\s*"([^"]+)"', src[start:end], re.M)
    return {term.lower(): title for term, title in pairs}


def _requires_capital(term: str) -> bool:
    return term in ACRONYMS or (len(term) <= SHORT_KEY_LEN and term not in LOWERCASE_OK)


def _looks_like_acronym(matched: str) -> bool:
    """All capitals or at least two (NO, CO2, NDCs) — not "no" or "No"."""
    letters = [ch for ch in matched if ch.isascii() and ch.isalpha()]
    capitals = sum(ch.isupper() for ch in letters)
    return capitals >= 2 or (bool(letters) and capitals == len(letters))


def _normalise(text: str) -> str:
    text = _FORMULA_N2O.sub("N2O", text or "")
    return _FORMULA.sub(r"\1\2", text)


class ConceptMatcher:
    """Finds encyclopedia concepts in text (longest term wins)."""

    def __init__(self, wiki_map: dict[str, str]):
        self.wiki_map = {
            term: title for term, title in wiki_map.items()
            if title not in EXCLUDED_CONCEPTS
        }
        terms = sorted(self.wiki_map, key=len, reverse=True)
        self.pattern = re.compile(
            r"(?<![\w-])(" + "|".join(re.escape(t) for t in terms) + r")(?![\w-])",
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
            term = matched.lower()
            if _requires_capital(term) and not _looks_like_acronym(matched):
                continue  # "no", "No", "co" … as ordinary words
            out.append((self.wiki_map[term], m.start(1), m.end(1)))
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
    return f"ipcc:{section}", {
        "type": "ipcc",
        "label": f"IPCC AR6 {section} {title}".strip(),
        "section": section,
    }


# ── Graph construction ───────────────────────────────────────────────────────


def _bridge_components(G: nx.Graph, concept_sources: dict, concept_chunks: Counter) -> list:
    """
    Connect concepts that share no passage with the main graph.

    A concept that only ever appears alone in its passages would float
    unconnected. Each such component is linked to the most-mentioned
    main-graph concept from the same source section / paper — a real but
    weaker relation, marked kind="source" (drawn dashed) with weight 0.5,
    below any passage link.
    """
    comps = sorted(nx.connected_components(G), key=len, reverse=True)
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
        for c in comp:
            for key, n in concept_sources[c].items():
                for m in in_source.get(key, ()):
                    score = (n, concept_chunks[m])
                    if best is None or score > best[0]:
                        best = (score, c, m, key)
        if best is None:
            continue  # shares no source with anything: leave it unconnected
        _, c, m, key = best
        G.add_edge(c, m, weight=0.5, kind="source", source=key)
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
        for a, b in itertools.combinations(concepts, 2):
            pair_weights[(a, b)] += 1

    G = nx.Graph()
    G.add_nodes_from(concept_chunks)
    for (a, b), w in pair_weights.items():
        G.add_edge(a, b, weight=w, kind="passage")

    passage_components = nx.number_connected_components(G)
    bridges = _bridge_components(G, concept_sources, concept_chunks)

    # Clusters: communities of concepts discussed together
    communities = (
        nx.community.louvain_communities(G, weight="weight", seed=42)
        if G.number_of_edges() else [{n} for n in G]
    )
    communities = sorted(communities, key=lambda c: -sum(concept_chunks[n] for n in c))
    group_of, groups = {}, []
    for i, members in enumerate(communities):
        lead = max(members, key=lambda n: concept_chunks[n])
        groups.append({"id": i, "label": lead, "size": len(members)})
        for n in members:
            group_of[n] = i

    # Display edges: maximum spanning forest ∪ top-K links per concept
    shown = {tuple(sorted((u, v))) for u, v in nx.maximum_spanning_edges(G, data=False)}
    for n in G:
        strongest = sorted(G[n].items(), key=lambda kv: -kv[1]["weight"])[:TOP_K]
        shown.update(tuple(sorted((n, m))) for m, _ in strongest)

    nodes = []
    for n in G:
        neighbours = sorted(G[n].items(), key=lambda kv: -kv[1]["weight"])
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
    }


_cache: dict = {}
_lock = threading.Lock()


def _state() -> dict:
    """Build once; rebuild when the collection or encyclopedia changes."""
    key = (get_collection().count(), ENCYCLOPEDIA_JS.stat().st_mtime)
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
            scores[c] += n * weight

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
    if meta.get("source_type") == "ipcc_report" and meta.get("section"):
        return f"/ipcc-reference#{meta['section']}"
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
    The passages behind a link: those mentioning both concepts. For a
    source-section link (dashed), the two concepts never share a passage,
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
        note = ("These concepts never appear in the same passage. "
                "They are linked because both appear in the same source section.")
    else:
        indices = sorted(set(pa) & set(pb))
        note = ""

    return {
        "from": a,
        "to": b,
        "kind": edge["kind"],
        "total": len(indices),
        "note": note,
        "passages": _passages(indices, [a, b]),
    }
