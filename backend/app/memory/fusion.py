"""Hybrid retrieval: dense + BM25-like + graph expand with RRF fusion."""

from __future__ import annotations

import math
import re
from collections import defaultdict

import numpy as np

from app.memory.seed_data import NEIGHBORHOOD_LINKS, pois_for_city, restaurants_for_city
from app.schemas.trip import POI, RestaurantCandidate, SettingKind


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _hash_embed(text: str, dim: int = 64) -> np.ndarray:
    vec = np.zeros(dim, dtype=np.float64)
    for tok in _tokenize(text):
        h = hash(tok) % dim
        vec[h] += 1.0
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec


def dense_scores(query: str, docs: list[str]) -> list[float]:
    q = _hash_embed(query)
    scores: list[float] = []
    for doc in docs:
        d = _hash_embed(doc)
        scores.append(float(np.dot(q, d)))
    return scores


def bm25_scores(query: str, docs: list[str], k1: float = 1.5, b: float = 0.75) -> list[float]:
    tokenized = [_tokenize(d) for d in docs]
    q_tokens = _tokenize(query)
    n = len(docs)
    if n == 0:
        return []
    avgdl = sum(len(t) for t in tokenized) / n
    df: dict[str, int] = defaultdict(int)
    for tokens in tokenized:
        for term in set(tokens):
            df[term] += 1
    scores: list[float] = []
    for tokens in tokenized:
        tf: dict[str, int] = defaultdict(int)
        for t in tokens:
            tf[t] += 1
        score = 0.0
        dl = len(tokens) or 1
        for term in q_tokens:
            if term not in tf:
                continue
            idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
            freq = tf[term]
            score += idf * (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * dl / avgdl))
        scores.append(score)
    return scores


def reciprocal_rank_fusion(rank_lists: list[list[int]], k: int = 60) -> dict[int, float]:
    fused: dict[int, float] = defaultdict(float)
    for ranks in rank_lists:
        for rank, idx in enumerate(ranks):
            fused[idx] += 1.0 / (k + rank + 1)
    return fused


def _top_indices(scores: list[float], top_k: int) -> list[int]:
    indexed = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    return indexed[:top_k]


def graph_expand_poi_indices(pois: list[POI], seed_indices: list[int], limit: int = 8) -> list[int]:
    neighborhoods = {pois[i].neighborhood for i in seed_indices if pois[i].neighborhood}
    expanded = set(seed_indices)
    related: set[str] = set()
    for n in neighborhoods:
        related.add(n)
        related.update(NEIGHBORHOOD_LINKS.get(n, []))
    for i, poi in enumerate(pois):
        if poi.neighborhood in related:
            expanded.add(i)
    # Prefer seeds first, then neighbors
    ordered = list(seed_indices)
    for i in expanded:
        if i not in ordered:
            ordered.append(i)
    return ordered[:limit]


def hybrid_retrieve_pois(
    city: str,
    query: str,
    top_k: int = 10,
    strategy: str = "hybrid",
) -> list[POI]:
    pois = pois_for_city(city)
    docs = [f"{p.name} {p.description} {' '.join(p.tags)} {p.neighborhood}" for p in pois]
    dense = dense_scores(query, docs)
    sparse = bm25_scores(query, docs)

    if strategy == "dense":
        idxs = _top_indices(dense, top_k)
    elif strategy == "dense_bm25":
        fused = reciprocal_rank_fusion([_top_indices(dense, top_k), _top_indices(sparse, top_k)])
        idxs = sorted(fused.keys(), key=lambda i: fused[i], reverse=True)[:top_k]
    else:
        dense_top = _top_indices(dense, top_k)
        sparse_top = _top_indices(sparse, top_k)
        graph_top = graph_expand_poi_indices(pois, dense_top[:3], limit=top_k)
        fused = reciprocal_rank_fusion([dense_top, sparse_top, graph_top])
        idxs = sorted(fused.keys(), key=lambda i: fused[i], reverse=True)[:top_k]

    results: list[POI] = []
    for i in idxs:
        poi = pois[i].model_copy(deep=True)
        poi.score = float(0.6 * dense[i] + 0.4 * (sparse[i] / (max(sparse) or 1)))
        results.append(poi)
    return results


def hybrid_retrieve_restaurants(city: str, query: str, top_k: int = 8) -> list[RestaurantCandidate]:
    restaurants = restaurants_for_city(city)
    docs = [f"{r.name} {r.cuisine} {r.description} {' '.join(r.tags)}" for r in restaurants]
    dense = dense_scores(query, docs)
    sparse = bm25_scores(query, docs)
    fused = reciprocal_rank_fusion([_top_indices(dense, top_k), _top_indices(sparse, top_k)])
    idxs = sorted(fused.keys(), key=lambda i: fused[i], reverse=True)[:top_k]
    out: list[RestaurantCandidate] = []
    for i in idxs:
        r = restaurants[i].model_copy(deep=True)
        r.score = float(0.5 * dense[i] + 0.5 * (sparse[i] / (max(sparse) or 1)))
        out.append(r)
    return out


def filter_by_setting(pois: list[POI], setting: SettingKind) -> list[POI]:
    if setting == SettingKind.EITHER:
        return pois
    preferred = [p for p in pois if p.setting == setting or p.setting == SettingKind.EITHER]
    return preferred or pois
