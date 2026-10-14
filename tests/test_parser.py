from pathlib import Path

from backend.ingest.jats_parser import parse_jats

CORPUS = Path(__file__).resolve().parents[1] / 'corpus'


def test_all_12_xml_files_parse():
    files = sorted(CORPUS.glob('*.xml'))
    assert len(files) == 12
    for path in files:
        sections = parse_jats(path)
        assert sections, path.name
        assert all(s.pmcid.startswith('PMC') for s in sections), path.name
        assert any(s.section_title == 'Abstract' for s in sections), path.name


def test_parser_preserves_nested_section_path():
    path = CORPUS / 'PMC10468509.xml'
    sections = parse_jats(path)
    assert all(s.section_path for s in sections)
