"""Report extraction reuses the IPCC workflow without a live model or network."""

import csv
from pathlib import Path

import pytest

import ipcc_encyclopedia_pipeline as report


def test_report_extraction_reads_source_folds_case_and_ranks_without_a_manual_map(tmp_path, monkeypatch):
    source = tmp_path / "ipcc_reference.html"
    source.write_text('<html><body><script>hardcoded term</script><style>fake keyword</style>'
                      '<p id="p1">Green infrastructure and carbon tax. Climate change.</p>'
                      '<nav>Navigation terms</nav></body></html>', encoding="utf-8")
    original = source.read_bytes()

    def extractor(inputs, output, top_n):
        text = inputs[0].read_text(encoding="utf-8")
        assert "Green infrastructure" in text
        assert all(value not in text for value in ("hardcoded term", "fake keyword", "Navigation terms"))
        assert top_n == 10
        output.mkdir()
        (output / "ipcc_reference_keywords.csv").write_text(
            'keyword,count\nGreen infrastructure,2\ngreen infrastructure,3\ncarbon tax,4\nclimate change,1\n',
            encoding="utf-8")

    monkeypatch.setattr(report, "_extract_keywords_with_txt2phrases", extractor)
    terms, wordlist, prepared = report.extract_report_wordlist(
        source, tmp_path / "build", top_n=10, max_terms=1, min_count=2)
    assert terms == ["green infrastructure"]
    with wordlist.open(encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert [(r["term"], r["count"], r["selected"]) for r in rows] == [
        ("green infrastructure", "5", "Yes"), ("carbon tax", "4", "No")]
    assert source.read_bytes() == original
    with pytest.raises(ValueError, match="fresh build directory"):
        report.extract_report_wordlist(source, tmp_path / "build")


def test_extracted_terms_are_passed_to_the_existing_encyclopedia_builder(tmp_path, monkeypatch):
    from encyclopedia.pipeline import query_to_encyclopedia
    expected = object()
    monkeypatch.setattr(report, "extract_report_wordlist", lambda *a, **kw: (
        ["carbon tax", "Greenhouse gas emissions"], tmp_path / "wordlist.csv", tmp_path / "report.txt"))

    def create(terms, title, target, **options):
        assert terms == ["carbon tax", "Greenhouse gas emissions"]
        assert options == {"add_wikipedia": True}
        assert target == tmp_path / "ipcc_encyclopedia.html"
        return expected

    monkeypatch.setattr(query_to_encyclopedia, "create_encyclopedia_from_terms", create)
    encyclopedia, paths = report.build_report_encyclopedia(tmp_path / "source.html", tmp_path)
    assert encyclopedia is expected
    assert paths["html"].name == "ipcc_encyclopedia.html"
