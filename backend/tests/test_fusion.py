from app.memory.fusion import bm25_scores, dense_scores, hybrid_retrieve_pois, reciprocal_rank_fusion


def test_dense_and_bm25_nonzero():
    docs = ["statue liberty views harbor", "modern art museum indoor", "central park outdoor walk"]
    q = "outdoor views park"
    d = dense_scores(q, docs)
    b = bm25_scores(q, docs)
    assert len(d) == 3
    assert len(b) == 3
    assert max(b) > 0


def test_rrf_prefers_consensus():
    fused = reciprocal_rank_fusion([[0, 1, 2], [0, 2, 1]])
    assert sorted(fused.keys(), key=lambda i: fused[i], reverse=True)[0] == 0


def test_hybrid_nyc_returns_pois():
    pois = hybrid_retrieve_pois("New York", "museums art indoor", top_k=5, strategy="hybrid")
    assert len(pois) >= 3
    assert any("museum" in p.name.lower() or "art" in " ".join(p.tags) for p in pois)
