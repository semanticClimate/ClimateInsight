"""Source-backed cleanup between phrase extraction and encyclopedia matching.

This is deliberately separate from extraction: wordlists remain an audit of
the model output, while spelling/plural variants and explicit abbreviations
become one concept. No legacy dictionary or generated definitions are used.
"""

from __future__ import annotations

from copy import deepcopy
import re
import unicodedata
from urllib.parse import unquote, urlparse

from lxml import html


CLEANUP_VERSION = 1
_CONNECTOR = re.compile(r"^(?:and|or|of|the|a|an|to|for|with|by|in|on|from|as)(?:\s|$)|(?:^|\s)(?:and|or|of|the|a|an|to|for|with|by|in|on|from|as)$", re.I)
_REFERENCE = re.compile(r"^(?:(?:ar\s*[1-6]|wg\s*(?:iii|ii|i)|spm|ts|syr)(?:\b|(?=\d))|(?:figure|table|chapter|section|rfc)\s*\d|ipcc (?:first|second|third|fourth|fifth|sixth) assessment report)", re.I)
_UNCERTAINTY = re.compile(r"^(?:(?:(?:very\s+)?(?:low|medium|high)|analytic)\s+)?confidence$|^(?:very\s+)?(?:un)?likely$|^likelihood$|^certainty$", re.I)
_GENERIC = {
    "age", "at", "capture", "change", "changes", "classification", "component", "components", "current", "degree", "end",
    "global", "higher", "high", "increase", "increases", "level", "levels", "low", "lower",
    "net", "new", "other", "period", "potential", "rate", "rates", "reduction", "reductions",
    "remaining", "result", "results", "synthesis report", "term", "terms", "total", "use", "uses", "value", "values",
}


def normalise(value):
    value = unicodedata.normalize("NFKC", value).casefold()
    value = re.sub(r"[\u2010-\u2015_-]", " ", value)
    return " ".join(value.split()).strip()


def concept_key(value):
    """Conservative inflection key, used only to unite observed aliases."""
    words = normalise(value).split()
    if not words:
        return ""
    word = words[-1]
    if len(word) > 4 and word.endswith("ies"):
        word = word[:-3] + "y"
    elif re.search(r"(?:sses|xes|zes|ches|shes|gases)$", word):
        word = word[:-2]
    elif len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is", "ous")):
        word = word[:-1]
    # Only alternative forms actually present in the sources become aliases.
    words[-1] = word
    return " ".join(words).replace("isation", "ization").replace("ising", "izing").replace("ised", "ized")


def noise_reason(term):
    value = normalise(term)
    if _REFERENCE.search(value):
        return "report_reference"
    if _UNCERTAINTY.fullmatch(value):
        return "calibrated_uncertainty"
    if value in _GENERIC:
        return "generic_expression"
    original_spacing = " ".join(unicodedata.normalize("NFKC", term).split())
    if _CONNECTOR.search(original_spacing) or not any(c.isalpha() for c in value):
        return "incomplete_expression"
    return None


def _long_form(before, short, known):
    """Resolve an explicit parenthetical abbreviation from its surrounding text."""
    matches = list(re.finditer(r"\w+(?:['’\-]\w+)*", before, flags=re.UNICODE))[-min(len(short) * 2 + 3, 16):]
    words = [match.group() for match in matches]
    if not words:
        return None
    chemical = any(c.isdigit() for c in short) and bool(re.fullmatch(r"(?:[A-Z][a-z]?\d*){1,4}", short))
    if any(c.isdigit() for c in short) and not chemical:
        return None
    if chemical:
        for size in range(min(4, len(words)), 0, -1):
            value = " ".join(words[-size:])
            if not any(c.isdigit() for c in value) and concept_key(value) in known and not noise_reason(value):
                return value
        # Methane (CH4), for example, is a chemical name rather than initials.
        if re.fullmatch(r"[a-z]+(?:ane|ene|yne)", words[-1], re.I):
            return words[-1]
    letters = re.sub(r"[^A-Za-z]", "", short).casefold()
    if len(letters) < 2:
        return None
    # Keep punctuation from the source (e.g. "Land use, land-use change and
    # forestry"), so an abbreviation cannot create an unobserved name variant.
    candidate = before[matches[0].start():].strip()
    position = len(candidate) - 1
    for index in range(len(letters) - 1, -1, -1):
        char = letters[index]
        while position >= 0 and (candidate[position].casefold() != char or
                                (index == 0 and position > 0 and candidate[position - 1].isalnum())):
            position -= 1
        if position < 0:
            return None
        position -= 1
    result = candidate[position + 1:]
    if (len(result.split()) > 8 or noise_reason(result) or any(c.isdigit() for c in result)
            or re.search(r"\b[A-Z]{2,}(?:-|\b)", result)):
        return None
    return result


def source_abbreviations(sources, known):
    """Keep the exact paragraph and file supporting each name/abbreviation pair."""
    found = {}
    for source_file, markup in sources:
        document = html.fromstring(markup)
        for node in document.xpath("//script|//style|//nav|//p[@class='source']"):
            node.drop_tree()
        paragraphs = document.xpath("//p") or [document]
        for paragraph in paragraphs:
            text = unicodedata.normalize("NFKC", " ".join(paragraph.text_content().split()))
            text = re.sub(r"\b(CO|CH|N|NO|SO|H)\s+([2346])\b", r"\1\2", text)
            for match in re.finditer(r"\(([A-Za-z][A-Za-z0-9+\-]{1,11})\)", text):
                short = match.group(1)
                if sum(c.isupper() for c in short) < 2 or noise_reason(short):
                    continue
                before = re.split(r"[.;:!?]", text[:match.start()])[-1]
                long = _long_form(before, short, known)
                if not long:
                    continue
                anchor = paragraph.get("id")
                if not anchor:
                    parents = paragraph.xpath("ancestor::*[@id][1]/@id")
                    anchor = parents[0] if parents else None
                found.setdefault((concept_key(long), short), {
                    "term": long, "alias": short, "source_file": source_file, "html_id": anchor,
                    "text": text[max(0, match.start() - len(long) - 1):match.end()],
                })
    return sorted(found.values(), key=lambda r: (concept_key(r["term"]), r["alias"]))


def refine_concepts(concepts, sources=()):
    """Return cleaned concepts and an auditable list of exclusions and merges."""
    removed, records = [], []
    for original in concepts:
        record = deepcopy(original)
        reason = noise_reason(record["canonical_name"])
        if reason and not record.get("definition_source"):
            removed.append({"term": record["canonical_name"], "reason": reason})
            continue
        record["synonyms"] = [a for a in record.get("synonyms", []) if not noise_reason(a)]
        records.append(record)
    known = {concept_key(a) for c in records for a in [c["canonical_name"], *c["synonyms"]]}
    abbreviations = source_abbreviations(sources, known)
    for pair in abbreviations:
        key = concept_key(pair["term"])
        targets = [c for c in records if key in {concept_key(a) for a in [c["canonical_name"], *c["synonyms"]]}]
        if len(targets) == 1:
            record = targets[0]
        elif not targets:
            name = pair["term"][0].upper() + pair["term"][1:]
            record = {"canonical_name": name, "synonyms": [], "description": None,
                      "description_source": None, "wikidata_id": None, "wikipedia_url": None,
                      "source_file": pair["source_file"], "source_files": [pair["source_file"]]}
            records.append(record)
        else:
            continue
        record["synonyms"] = sorted(set(record["synonyms"] + [pair["alias"], pair["term"]]) - {record["canonical_name"]}, key=str.casefold)
        proofs = record.setdefault("alias_sources", [])
        if pair not in proofs:
            proofs.append(pair)
        for other in records:
            if other is record or other.get("definition_source"):
                continue
            if normalise(other["canonical_name"]) != normalise(pair["alias"]):
                continue
            article = unquote(urlparse(other.get("wikipedia_url") or "").path.removeprefix("/wiki/")).replace("_", " ")
            if article and normalise(article) == normalise(pair["alias"]) and concept_key(pair["term"]) != concept_key(article):
                # An acronym-only Wikipedia page can describe another meaning
                # (PM -> time of day). The source explicitly defines this use.
                other.setdefault("replaced_report_identities", []).append({
                    "canonical_name": other["canonical_name"], "wikidata_id": other.get("wikidata_id"),
                    "wikipedia_url": other.get("wikipedia_url"), "reason": "source_abbreviation_disambiguation"})
                for field in ("wikidata_id", "wikipedia_url", "description", "description_source", "wikipedia_description"):
                    other[field] = None

    # Components join spelling/plural aliases, while distinct official glossary
    # definitions and incompatible Wikidata identities remain separate.
    parents = list(range(len(records)))
    meanings = [{normalise(c["definition_source"]["term"])} if c.get("definition_source") else set() for c in records]
    entities = [{c["wikidata_id"]} if c.get("wikidata_id") else set() for c in records]

    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    by_alias = {}
    for i, record in enumerate(records):
        for alias in [record["canonical_name"], *record["synonyms"]]:
            key = concept_key(alias)
            if key in by_alias:
                j = by_alias[key]
                left, right = root(i), root(j)
                different_definitions = meanings[left] and meanings[right] and meanings[left] != meanings[right]
                different_entities = entities[left] and entities[right] and entities[left] != entities[right]
                if not different_definitions and not different_entities:
                    parents[left] = right
                    meanings[right] |= meanings[left]
                    entities[right] |= entities[left]
            else:
                by_alias[key] = i
    groups = {}
    for i, record in enumerate(records):
        groups.setdefault(root(i), []).append(record)
    merged, cleaned = [], []
    for group in groups.values():
        group.sort(key=lambda c: (not bool(c.get("definition_source")), not bool(c.get("description")),
                                  bool(re.fullmatch(r"[A-Z][A-Z0-9]+s?", c["canonical_name"])),
                                  len(c["canonical_name"]), c["canonical_name"].casefold(), c["canonical_name"]))
        target = deepcopy(group[0])
        aliases = {a for c in group for a in [c["canonical_name"], *c["synonyms"]]}
        target["synonyms"] = sorted(aliases - {target["canonical_name"]}, key=lambda s: (s.casefold(), s))
        for field in ("source_files", "alias_sources", "term_sources", "replaced_report_identities"):
            values = []
            for c in group:
                for value in c.get(field, []):
                    if value not in values:
                        values.append(value)
            if values:
                target[field] = values
        for field in ("wikidata_id", "wikipedia_url", "wikipedia_description"):
            target[field] = next((c[field] for c in group if c.get(field)), target.get(field))
        if len(group) > 1:
            merged.append({"concept": target["canonical_name"], "terms": sorted({c["canonical_name"] for c in group})})
        cleaned.append(target)

    # Add literal hyphen/space variants observed in the approved source text.
    source_text = unicodedata.normalize("NFKC", " ".join(html.fromstring(markup).text_content() for _, markup in sources))
    for record in cleaned:
        aliases = set(record["synonyms"])
        for value in [record["canonical_name"], *record["synonyms"]]:
            words = re.split(r"[\s\u2010-\u2015-]+", value)
            if len(words) < 2 or len(words) > 8:
                continue
            pattern = r"(?<!\w)" + r"[\s\u2010-\u2015-]+".join(re.escape(w) for w in words) + r"(?!\w)"
            aliases.update(" ".join(m.group().split()) for m in re.finditer(pattern, source_text, re.I))
        record["synonyms"] = sorted(aliases - {record["canonical_name"]}, key=lambda s: (s.casefold(), s))
        record["graph_eligible"] = noise_reason(record["canonical_name"]) is None
    cleaned.sort(key=lambda c: (c["canonical_name"].casefold(), c["canonical_name"]))
    return cleaned, {"version": CLEANUP_VERSION, "input_concepts": len(concepts), "output_concepts": len(cleaned),
                     "removed": sorted(removed, key=lambda r: r["term"]), "merged": merged,
                     "source_abbreviations": abbreviations}
