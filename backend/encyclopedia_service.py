"""Connect the sibling Encyclopedia package, graph vocabulary and report viewer.

Page requests only read the generated report vocabulary; extraction runs through
build_ipcc_encyclopedia.py. No ChromaDB ingestion or graph construction occurs here.
"""

from __future__ import annotations

from functools import lru_cache
import importlib
import hashlib
import json
import logging
import os
from pathlib import Path
import sys

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from encyclopedia_importer import load_generated_concepts, merge_manual_and_imported


ROOT = Path(__file__).resolve().parent.parent
GENERATED = ROOT / "backend/data/generated/encyclopedia_concepts.json"
log = logging.getLogger(__name__)


def settings():
    path = ROOT / "config.toml"
    config = tomllib.loads(path.read_text(encoding="utf-8")).get("encyclopedia", {})
    mode = os.environ.get("CLIMATEINSIGHT_ENCYCLOPEDIA_MODE", config.get("mode", "generated"))
    repo = Path(os.environ.get("CLIMATEINSIGHT_ENCYCLOPEDIA_REPO", config.get("repository", "../encyclopedia")))
    repo = (ROOT / repo).resolve()
    sources = tuple((ROOT / name).resolve() for name in config.get("sources", []))
    return mode, repo, sources


def _stamp(path):
    try:
        stat = path.stat()
        return str(path), stat.st_mtime_ns, stat.st_size
    except FileNotFoundError:
        return str(path), None, None


def vocabulary_signature():
    mode, repo, sources = settings()
    return (mode, str(repo), _stamp(ROOT / "config.toml"),
            _stamp(ROOT / "encyclopedia/climate-wiki.js"), _stamp(GENERATED),
            _stamp(source_path()), tuple(_stamp(path) for path in sources))


def exchange_module():
    _, repo, _ = settings()
    expected = repo / "encyclopedia/exchange.py"
    if not expected.is_file():
        raise ImportError(f"Encyclopedia exchange module not found: {expected}")
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    module = importlib.import_module("encyclopedia.exchange")
    if Path(module.__file__).resolve() != expected.resolve():
        raise ImportError("A different Encyclopedia installation is already loaded; restart with the configured repository.")
    return module


def source_path():
    config = tomllib.loads((ROOT / "config.toml").read_text(encoding="utf-8")).get("encyclopedia", {})
    return (ROOT / config.get("source", "data/raw/ipcc_reference.html")).resolve()


@lru_cache(maxsize=8)
def _source_hash(stamp):
    return hashlib.sha256(Path(stamp[0]).read_bytes()).hexdigest()


@lru_cache(maxsize=4)
def _generated_concepts(signature, path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not data.get("concepts"):
        raise ValueError("Build the IPCC Encyclopedia: python backend/build_ipcc_encyclopedia.py")
    provenance = data.get("provenance", {})
    if provenance.get("source_sha256") != _source_hash(_stamp(source_path())):
        raise ValueError("The IPCC Encyclopedia is missing or stale; rerun backend/build_ipcc_encyclopedia.py")
    # No old AMOC exports, old Chapter 18 artifact, or manual aliases are mixed in.
    return tuple(data["concepts"])


def source_concepts(generated_path=GENERATED):
    if settings()[0] == "legacy":
        archived = ROOT / "backend/data/generated/encyclopedia_concepts.legacy.json"
        return load_generated_concepts(archived if Path(generated_path) == GENERATED else Path(generated_path))
    return list(_generated_concepts(vocabulary_signature() + (_stamp(Path(generated_path)),), str(generated_path)))


def vocabulary():
    from knowledge_graph import ConceptMatcher
    aliases, metadata, conflicts = merge_manual_and_imported({}, source_concepts())
    matcher = ConceptMatcher(aliases)
    by_title = {}
    for title in sorted(set(matcher.wiki_map.values())):
        record = dict(metadata[title])
        record["synonyms"] = sorted(alias for alias, target in matcher.wiki_map.items()
                                    if target == title and alias != title.casefold())
        by_title[title] = record
    return matcher, by_title, conflicts


def _require_package():
    if settings()[0] == "legacy":
        raise ImportError("The legacy Encyclopedia viewer is selected.")
    return exchange_module()


@lru_cache(maxsize=4)
def _report_glossary(signature, report_html):
    exchange = _require_package()
    matcher, metadata, _ = vocabulary()
    contexts = exchange.report_contexts(report_html, matcher.find)
    return exchange.render_entries(
        [metadata[name] for name in contexts], contexts,
        title="IPCC AR6 SYR Longer Report Encyclopedia",
    )


_STYLE = """<style>
#ci-report-encyclopedia{margin:2rem 1rem;padding:1rem;border:1px solid #bbb;background:white;color:#222}
#ci-encyclopedia [role=ami_entry]{margin:1rem 0;padding:1rem;border-bottom:1px solid #ccc}
#ci-encyclopedia h2{font-size:1.3rem}#ci-encyclopedia h3{font-size:1rem}
#ci-encyclopedia .definition-source{font-size:.85rem;color:#555}
#ci-encyclopedia blockquote{font-size:.95rem;border-left:3px solid #aaa;padding-left:1rem}
</style>"""


def render_report(report_html):
    if settings()[0] == "legacy":
        return report_html
    exchange = _require_package()
    fragment = _report_glossary(vocabulary_signature() + (_stamp(GENERATED),), report_html)
    rendered = exchange.report_with_entries(report_html, fragment, glossary_url="/ipcc-encyclopedia")
    return rendered.replace("</head>", _STYLE + "</head>", 1)


def render_glossary(report_html):
    _require_package()
    fragment = _report_glossary(vocabulary_signature() + (_stamp(GENERATED),), report_html)
    return ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
            '<title>IPCC Report Encyclopedia</title>' + _STYLE + '</head><body>'
            '<h1>IPCC AR6 SYR Longer Report Encyclopedia</h1>'
            '<p>Wikipedia descriptions and separately cited IPCC passages.</p>'
            '<p><a href="/ipcc-reference">Return to the IPCC report</a></p>' + fragment + '</body></html>')


def render_viewer_script(template):
    """Fill the vocabulary slot in the active, data-free viewer script."""
    _require_package()
    matcher, metadata, _ = vocabulary()
    marker = "/* ENCYCLOPEDIA_DATA */"
    if template.count(marker) != 1:
        raise ValueError("The active viewer is missing its generated vocabulary slot")
    payload = ("const ENCYCLOPEDIA_CONCEPTS = " + json.dumps(metadata, ensure_ascii=True) + ";\n"
               "  const WIKI_MAP = " + json.dumps(matcher.wiki_map, ensure_ascii=True) + ";")
    return template.replace(marker, payload, 1)
