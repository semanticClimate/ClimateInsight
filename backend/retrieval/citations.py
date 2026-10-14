from __future__ import annotations

import re

CITE_RE = re.compile(r"\[(C\d+)\]")


def validate_citations(answer: str, evidence: list[dict]) -> tuple[str, list[dict]]:
    cited = list(dict.fromkeys(CITE_RE.findall(answer)))
    allowed = {e["citation_key"]: e for e in evidence}
    valid = [allowed[k] for k in cited if k in allowed]

    # Remove invalid citation handles and legacy section-name style brackets.
    cleaned = CITE_RE.sub(lambda m: f"[{m.group(1)}]" if m.group(1) in allowed else "", answer)
    cleaned = re.sub(r"\[(?!C\d+\])[^\]]{1,120}\]", "", cleaned)
    cleaned = re.sub(r"\s+([,.!?;:])", r"\1", cleaned)
    return cleaned.strip(), valid


def has_valid_citation(answer: str, evidence: list[dict]) -> bool:
    _, valid = validate_citations(answer, evidence)
    return bool(valid)


def extractive_fallback(question: str, evidence: list[dict]) -> tuple[str, list[dict]]:
    if not evidence:
        return "I couldn't find enough evidence in the 12 indexed papers to answer that.", []
    e = evidence[0]
    sentence = e["text"].split(". ")[0].strip()
    return f"The most relevant passage I found states: {sentence} [C1]", [e]
