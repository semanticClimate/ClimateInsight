"""
response_formatter.py
---------------------
Creates standardized API responses.

Every response returned by the chatbot should be formatted here.
"""


def _build_references(citations: list) -> list:
    """Extract paper-level references from citation entries.

    Returns a deduplicated list (by doi/pmcid) of reference objects
    for manifest-ingested chunks. IPCC citations without doi/pmcid are omitted.
    """
    seen = set()
    refs = []
    for c in citations:
        doi = c.get("doi", "")
        pmcid = c.get("pmcid", "")
        key = doi or pmcid
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        ref = {
            "citation_label": c.get("citation_label", ""),
            "doi": doi,
            "pmcid": pmcid,
            "url": f"https://doi.org/{doi}" if doi else (
                f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/" if pmcid else ""
            ),
        }
        refs.append(ref)
    return refs


def chat_response(
    answer: str,
    citations: list,
    session_id: str,
) -> dict:
    """
    Standard successful chatbot response.
    Includes a references list for manifest-ingested paper citations.
    """
    response = {
        "answer": answer,
        "citations": citations,
        "session_id": session_id,
    }
    references = _build_references(citations)
    if references:
        response["references"] = references
    return response


def error_response(message: str) -> dict:
    """Standard error response."""
    return {"error": message}


def health_response(status: str = "ok") -> dict:
    """Health check response."""
    return {"status": status}


def message_response(message: str) -> dict:
    """Generic success message."""
    return {"message": message}
