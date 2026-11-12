"""Local evidence windows, frequency-adjusted edges and descriptive topic labels."""

from __future__ import annotations

import math
import re

from backend.encyclopedia.concepts import concept_key


def relation_units(text, max_words=60, overlap=15):
    """Sentences, with overlapping windows for unusually long sentences.

    Decimal numbers do not end a sentence. Remove report reference blocks so
    their punctuation does not create spurious evidence windows.
    """
    text = re.sub(r"\{[^{}]*\}", " ", text)
    text = re.sub(r"\b(?:e\.g\.|i\.e\.|et al\.|Fig\.|Dr\.)", lambda m: m.group().replace(".", "\u2024"), text)
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Za-z(\d])|\n\s*\n", text)
    for sentence in sentences:
        words = sentence.replace("\u2024", ".").split()
        for start in range(0, len(words), max_words - overlap):
            unit = " ".join(words[start:start + max_words])
            if unit:
                yield unit
            if start + max_words >= len(words):
                break


def association_weight(cooccurrences, left_count, right_count, unit_count):
    """Discount ubiquitous concepts while retaining every edge's source count."""
    cosine = cooccurrences / math.sqrt(left_count * right_count)
    left_idf = 1 + math.log((1 + unit_count) / (1 + left_count))
    right_idf = 1 + math.log((1 + unit_count) / (1 + right_count))
    return cosine * math.sqrt(left_idf * right_idf)


def topic_representatives(graph, members, passage_counts, metadata=None, limit=4):
    """Rank concepts that are central inside this group and distinctive to it."""
    scored = []
    for node in members:
        internal = sum(d.get("association", d["weight"]) for other, d in graph[node].items() if other in members)
        total = sum(d.get("association", d["weight"]) for d in graph[node].values())
        cohesion = internal / total if total else 1
        descriptive = 1.2 if len(node.split()) > 1 else 1
        entry = (metadata or {}).get(node, {})
        official_definition = bool(entry.get("definition_source")) and not (entry.get("description") or "").startswith("See:")
        authority = 1.5 if official_definition else 1
        score = (internal or 0.01) * cohesion * math.log1p(passage_counts[node]) * descriptive * authority
        scored.append((-score, node.casefold(), node))
    selected = []
    for _, _, node in sorted(scored):
        words = set(concept_key(node).split())
        if any(len(words & set(concept_key(prior).split())) / max(1, min(len(words), len(concept_key(prior).split()))) >= 0.75
               for prior in selected):
            continue
        selected.append(node)
        if len(selected) == limit:
            break
    return selected
