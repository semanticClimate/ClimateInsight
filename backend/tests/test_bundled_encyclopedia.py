"""A relocated ClimateInsight copy must not need a sibling Encyclopedia checkout."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import textwrap

import pytest

from backend.core.paths import PROJECT_ROOT


@pytest.fixture
def standalone_checkout(tmp_path):
    root = tmp_path / "projects" / "ClimateInsight"
    for package in ("backend", "encyclopedia"):
        for source in (PROJECT_ROOT / package).rglob("*.py"):
            relative = source.relative_to(PROJECT_ROOT)
            if "tests" in relative.parts:
                continue
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    raw = root / "data/raw"
    raw.mkdir(parents=True)
    (raw / "report.html").write_text(
        '<html><body><p id="p1">Climate change affects the ocean.</p></body></html>',
        encoding="utf-8",
    )
    (raw / "glossary.html").write_text(
        '<html><body><section class="glossary-entry" id="climate" '
        'data-term="Climate change" data-page="1"><h2>Climate change</h2>'
        '<p class="definition">A persistent change in climate.</p></section></body></html>',
        encoding="utf-8",
    )
    (raw / "PMC123.xml").write_text(
        '<article><front><article-meta><article-id pub-id-type="pmc">PMC123</article-id>'
        '<title-group><article-title>Ocean study</article-title></title-group>'
        '</article-meta></front><body><sec><title>Results</title>'
        '<p>Marine heatwaves affect ocean ecosystems.</p></sec></body></article>',
        encoding="utf-8",
    )
    (root / "config.toml").write_text(
        '[encyclopedia]\nmode="generated"\nrepository="."\n'
        'source="data/raw/report.html"\nglossary="data/raw/glossary.html"\n'
        'papers=["data/raw/PMC123.xml"]\nmin_count=1\n', encoding="utf-8",
    )
    assert not (root.parent / "encyclopedia").exists()
    return root


def run_isolated(root, script):
    env = os.environ.copy()
    for name in ("CLIMATEINSIGHT_ENCYCLOPEDIA_REPO", "CLIMATEINSIGHT_ENCYCLOPEDIA_MODE"):
        env.pop(name, None)
    return subprocess.run(
        [sys.executable, "-I", "-B", "-c", textwrap.dedent(script), str(root)],
        cwd=root.parent, env=env, capture_output=True, text=True,
        encoding="utf-8", timeout=90,
    )


@pytest.mark.parametrize("explicit_repository", [True, False])
def test_viewer_loads_only_bundled_helpers_without_build_dependencies(
    standalone_checkout, explicit_repository,
):
    root = standalone_checkout
    # This minimal vocabulary exercises runtime serving without any extraction.
    (root / "config.toml").write_text(
        '[encyclopedia]\nmode="generated"\nsource="data/raw/report.html"\n'
        + ('repository="."\n' if explicit_repository else ''), encoding="utf-8",
    )
    artifact = root / "backend/generated_artifacts/encyclopedia_concepts.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(json.dumps({
        "schema_version": 1,
        "concepts": [{"canonical_name": "Climate change", "synonyms": [],
                      "description": "A changing climate."}],
        "provenance": {"source_sha256": hashlib.sha256(
            (root / "data/raw/report.html").read_bytes()).hexdigest()},
    }), encoding="utf-8")
    result = run_isolated(root, """
        import importlib.abc
        from pathlib import Path
        import sys
        root = Path(sys.argv[1])
        sys.path.insert(0, str(root))

        class RejectBuildDependencies(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split('.')[0] in {'amilib', 'txt2phrases', 'torch', 'transformers'}:
                    raise AssertionError('Runtime loaded build dependency: ' + fullname)
        sys.meta_path.insert(0, RejectBuildDependencies())
        from backend.encyclopedia import service
        assert service.settings()[1] == root
        assert Path(service.exchange_module().__file__) == root / 'encyclopedia/exchange.py'
        report = (root / 'data/raw/report.html').read_text(encoding='utf-8')
        assert 'role="ami_entry"' in service.render_report(report)
        assert 'Climate change' in service.render_glossary(report)
        assert 'ENCYCLOPEDIA_CONCEPTS' in service.render_viewer_script('/* ENCYCLOPEDIA_DATA */')
        print('Standalone viewer OK')
    """)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Standalone viewer OK" in result.stdout


def test_build_command_uses_bundled_extraction_and_enrichment_helpers(standalone_checkout):
    root = standalone_checkout
    result = run_isolated(root, """
        import csv
        import json
        from pathlib import Path
        import runpy
        import sys
        from unittest.mock import patch
        root = Path(sys.argv[1])
        sys.path.insert(0, str(root))
        from backend.encyclopedia import corpus, service
        assert Path(service.exchange_module().__file__).is_relative_to(root)

        def extract(inputs, output, top_n):
            output.mkdir(parents=True)
            for source in inputs:
                text = source.read_text(encoding='utf-8')
                term = 'Marine heatwaves' if 'Marine heatwaves' in text else 'Climate change'
                with (output / (source.stem + '_keywords.csv')).open('w', newline='', encoding='utf-8') as stream:
                    writer = csv.writer(stream)
                    writer.writerow(['keyword', 'count'])
                    writer.writerow([term, 3])

        # Replace only expensive inference and external requests. Text preparation,
        # wordlist aggregation, entry generation, export and CLI use the real code.
        with patch.object(corpus, '_extract_corpus_keywords', extract), \\
             patch.object(corpus, 'version', return_value='test-extractor'), \\
             patch('amilib.wikimedia.WikipediaPage.lookup_wikipedia_page_for_term', return_value=None):
            sys.argv = ['backend.encyclopedia.build']
            runpy.run_module('backend.encyclopedia.build', run_name='__main__')
        artifact = json.loads((root / 'backend/generated_artifacts/encyclopedia_concepts.json').read_text(encoding='utf-8'))
        assert artifact['summary']['source_files_processed'] == 3
        assert artifact['provenance']['wikipedia_requested'] is True
        concepts = {record['canonical_name']: record for record in artifact['concepts']}
        assert concepts['Climate change']['definition_source']
        assert 'Marine heatwaves' in concepts
        assert (root / 'encyclopedia_assets/generated/source_manifest.json').is_file()
        report = (root / 'data/raw/report.html').read_text(encoding='utf-8')
        assert 'role="ami_entry"' in service.render_report(report)
        print('Standalone build OK')
    """)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Standalone build OK" in result.stdout
