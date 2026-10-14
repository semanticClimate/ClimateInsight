from pathlib import Path

CORPUS=Path(__file__).resolve().parents[1]/'corpus'

def test_corpus_contains_only_xml():
    assert len(list(CORPUS.glob('*.xml')))==12
    assert not list(CORPUS.glob('*.html'))
