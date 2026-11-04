"""Tests for encyclopedia concept matching and citation clean-up."""

import pytest

from knowledge_graph import ConceptMatcher, load_encyclopedia
from retrieval.citation_parser import strip_ghost_citations


@pytest.fixture(scope="module")
def matcher():
    return ConceptMatcher(load_encyclopedia())


def test_ordinary_words_are_not_acronyms(matcher):
    found = matcher.find("There is no evidence. No change, and co-benefits.")
    assert "Nitric oxide" not in found
    assert "Carbon monoxide" not in found


def test_acronyms_match_in_capitals(matcher):
    found = matcher.find("NO emissions, NDCs and PV panels.")
    assert {"Nitric oxide", "Nationally determined contribution", "Photovoltaics"} <= set(found)


def test_flattened_subscripts_are_formulas(matcher):
    # HTML extraction turns CO<sub>2</sub> into "CO 2"
    found = matcher.find("Atmospheric CO 2 and CH 4 and N 2 O rose.")
    assert {"Carbon dioxide", "Methane", "Nitrous oxide"} <= set(found)
    assert "Carbon monoxide" not in found


def test_short_real_words_still_match(matcher):
    found = matcher.find("flood risk, ozone, coal and oil")
    assert {"Flood", "Ozone"} <= set(found)


def test_likelihood_language_is_not_a_concept(matcher):
    assert "Likelihood" not in matcher.find("It is very likely that warming continues.")


def test_strip_ghost_citations_keeps_only_retrieved_refs():
    chunks = [{"ref": "3.3.1"}, {"ref": "P1"}]
    text = "Budget is 500 GtCO2 [2.1]. Pathways [3.3.1] and a paper [P1] [P9]."
    assert strip_ghost_citations(text, chunks) == "Budget is 500 GtCO2. Pathways [3.3.1] and a paper [P1]."
