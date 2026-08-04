"""Offline retrieval strategy comparison. Reports measured metrics only."""

from __future__ import annotations

import json
from pathlib import Path

from app.memory.fusion import hybrid_retrieve_pois

# Labels live in dataset.json, not here. They were duplicated in both places and
# drifted apart, so the committed run scored against ids the corpus no longer had.
DATASET_PATH = Path(__file__).resolve().parent / "dataset.json"
DATASET = json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def recall_at_k(retrieved_ids: list[str], relevant: list[str], k: int) -> float:
    top = set(retrieved_ids[:k])
    if not relevant:
        return 0.0
    return len(top.intersection(relevant)) / len(relevant)


def run() -> dict:
    strategies = ["dense", "dense_bm25", "hybrid"]
    report: dict = {"strategies": {}, "dataset_size": len(DATASET)}
    for strategy in strategies:
        recalls = []
        for row in DATASET:
            pois = hybrid_retrieve_pois(row["city"], row["query"], top_k=5, strategy=strategy)
            ids = [p.id for p in pois]
            recalls.append(recall_at_k(ids, row["relevant_ids"], 5))
        avg = sum(recalls) / len(recalls)
        report["strategies"][strategy] = {"recall@5": round(avg, 4), "per_query": recalls}
    # Coherence proxy: neighborhood diversity inverse (lower unique neighborhoods among top results = tighter)
    hybrid_pois = hybrid_retrieve_pois("New York", "art museums midtown", top_k=5, strategy="hybrid")
    neighborhoods = {p.neighborhood for p in hybrid_pois}
    report["hybrid_neighborhood_count_top5"] = len(neighborhoods)
    baseline = report["strategies"]["dense"]["recall@5"]
    hybrid = report["strategies"]["hybrid"]["recall@5"]
    if baseline > 0:
        report["hybrid_vs_dense_recall_lift"] = round((hybrid - baseline) / baseline, 4)
    else:
        report["hybrid_vs_dense_recall_lift"] = None
    return report


if __name__ == "__main__":
    out = run()
    dest = Path(__file__).resolve().parent / "results.json"
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
