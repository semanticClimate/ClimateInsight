from backend.retrieval.citations import validate_citations


def test_citations_are_only_resolved_against_retrieved_evidence():
    evidence=[
        {"citation_key":"C1","pmcid":"PMC1","title":"Paper one","text":"Alpha passage"},
        {"citation_key":"C2","pmcid":"PMC2","title":"Paper two","text":"Beta passage"},
    ]
    answer='Alpha is discussed [C1]. Ghost source [C999].'
    cleaned, cites=validate_citations(answer,evidence)
    assert '[C1]' in cleaned
    assert 'C999' not in cleaned
    assert [c['pmcid'] for c in cites]==['PMC1']


def test_no_section_name_fallback_exists():
    evidence=[{"citation_key":"C1","pmcid":"PMC1","title":"Paper one","text":"Intro"}]
    cleaned,cites=validate_citations('Claim [introduction].',evidence)
    assert cleaned=='Claim.'
    assert cites==[]
