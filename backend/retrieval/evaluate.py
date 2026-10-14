from __future__ import annotations

import json
from pathlib import Path

from .hybrid import retrieve

GOLD = Path(__file__).resolve().parents[2] / "tests" / "golden_questions.json"


def main():
    cases = json.loads(GOLD.read_text(encoding="utf-8"))
    hits = {1: 0, 3: 0, 5: 0}
    for case in cases:
        results = retrieve(case["question"], top_k=5)
        pmcids = [x.pmcid for x in results]
        expected = case["pmcid"]
        print(f"\nQ: {case['question']}\nExpected: {expected}\nTop: {pmcids}")
        for k in hits:
            if expected in pmcids[:k]:
                hits[k] += 1
    total = len(cases)
    print("\nRetrieval recall:")
    for k, hit in hits.items():
        print(f"Recall@{k}: {hit}/{total} = {hit/total:.1%}")


if __name__ == "__main__":
    main()
