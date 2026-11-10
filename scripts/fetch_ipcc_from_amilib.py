"""Fetch AR6 chapters that semanticClimate's amilib has already cleaned.

ClimateInsight does not clean IPCC web pages itself. amilib publishes each
chapter as ``html_with_ids.html`` (navigation removed, sections nested,
paragraph ids added). This script copies chosen chapters from a pinned
amilib commit into ``data/raw/ipcc/`` and records where each came from.

    python scripts/fetch_ipcc_from_amilib.py --list
    python scripts/fetch_ipcc_from_amilib.py wg1/Chapter01 wg2/Chapter05
    python scripts/fetch_ipcc_from_amilib.py wg1/Chapter01 --ref <new amilib sha>

Then ingest them:

    cd backend && python -m ingest.ingest --dir ../data/raw/ipcc

To pick up a change in the IPCC source: have it re-cleaned in amilib, rerun
this with the new ``--ref``, run the tests, then re-ingest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

AMILIB_REPO = "semanticClimate/amilib"
# amilib commit the current ClimateInsight data was checked against.
DEFAULT_REF = "bcd4317f896eea61b110a2ac55f07d3564e10dee"
CLEANED_DIR = "test/resources/ipcc/cleaned_content"

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "raw" / "ipcc"


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "ClimateInsight-fetch"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def list_chapters(ref: str) -> list[str]:
    url = f"https://api.github.com/repos/{AMILIB_REPO}/git/trees/{ref}?recursive=1"
    tree = json.loads(_get(url))["tree"]
    prefix, suffix = CLEANED_DIR + "/", "/html_with_ids.html"
    return sorted(
        item["path"][len(prefix):-len(suffix)]
        for item in tree
        if item["path"].startswith(prefix)
        and item["path"].endswith(suffix)
        and item["path"].count("/") == prefix.count("/") + 2  # report/chapter/file only
    )


def fetch(chapter: str, ref: str) -> Path:
    """Download one chapter, e.g. 'wg1/Chapter01', and return the saved path."""
    report, name = chapter.strip("/").split("/")
    url = f"https://raw.githubusercontent.com/{AMILIB_REPO}/{ref}/{CLEANED_DIR}/{report}/{name}/html_with_ids.html"
    data = _get(url)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # Report in the filename: the chunker prefixes chunk ids with the file stem.
    out = OUT_DIR / f"{report}_{name}.html"
    out.write_bytes(data)

    sources_file = OUT_DIR / "SOURCES.json"
    sources = json.loads(sources_file.read_text()) if sources_file.exists() else {}
    sources[out.name] = {
        "amilib_repo": AMILIB_REPO,
        "amilib_ref": ref,
        "path": f"{CLEANED_DIR}/{report}/{name}/html_with_ids.html",
        "sha256": hashlib.sha256(data).hexdigest(),
        "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    sources_file.write_text(json.dumps(sources, indent=2, sort_keys=True) + "\n")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("chapters", nargs="*", help="e.g. wg1/Chapter01 syr/longer-report")
    parser.add_argument("--ref", default=DEFAULT_REF, help="amilib commit, branch or tag (default: pinned commit)")
    parser.add_argument("--list", action="store_true", help="list chapters available at --ref")
    args = parser.parse_args(argv)

    if args.list:
        print("\n".join(list_chapters(args.ref)))
        return 0
    if not args.chapters:
        parser.error("name at least one chapter, or use --list")
    for chapter in args.chapters:
        print(f"saved {fetch(chapter, args.ref).relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
