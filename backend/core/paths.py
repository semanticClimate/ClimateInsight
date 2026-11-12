"""Stable resource locations, independent of a module's folder or working directory.

Moving Python code must not move the source corpus, generated vocabulary, or
the existing Chroma collection. Modules share this one project-root anchor.
"""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = PROJECT_ROOT / "frontend"
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PAPERS_DIR = RAW_DATA_DIR / "ocean_heatwaves_2026"
ENCYCLOPEDIA_ASSETS_DIR = PROJECT_ROOT / "encyclopedia_assets"
CHROMA_DIR = PROJECT_ROOT / "backend" / "chroma_db"
GENERATED_CONCEPTS = PROJECT_ROOT / "backend" / "generated_artifacts" / "encyclopedia_concepts.json"
