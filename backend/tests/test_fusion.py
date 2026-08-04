from app.memory.fusion import (
    bm25_scores,
    dense_scores,
    graph_expand_poi_indices,
    hybrid_retrieve_pois,
    reciprocal_rank_fusion,
)
from app.memory.seed_data import pois_for_city


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
    # Corpus entries carry their category in the description rather than in the
    # name or tags, so relevance has to be judged over the indexed text.
    haystacks = [f"{p.name} {p.description} {' '.join(p.tags)}".lower() for p in pois]
    assert any(
        any(word in text for word in ("museum", "art", "gallery", "exhibit"))
        for text in haystacks
    )


def test_graph_expand_orders_neighbours_by_relevance():
    """Expanded neighbours must carry a query signal, not arrive in corpus order.

    RRF weights positions almost equally at k=60, so an unranked neighbour at
    rank 4 votes nearly as hard as the top hit.
    """
    pois = pois_for_city("New York")
    relevance = [float(i) for i in range(len(pois))]  # last POI is most relevant
    seeds = [0]
    expanded = graph_expand_poi_indices(pois, seeds, limit=len(pois), relevance=relevance)

    assert expanded[0] == 0, "seeds come first"
    neighbours = expanded[1:]
    assert neighbours == sorted(neighbours, key=lambda i: relevance[i], reverse=True)


def test_hybrid_is_not_worse_than_dense_bm25():
    """Graph expansion must not cost recall.

    It previously did: the graph list repeats its seeds, so seeding it from dense
    alone made RRF count the weakest channel twice and dragged hybrid below plain
    dense+BM25.
    """
    from evals.retrieval.run_eval import run

    report = run()["strategies"]
    assert report["hybrid"]["recall@5"] >= report["dense_bm25"]["recall@5"]
    assert report["hybrid"]["recall@5"] > report["dense"]["recall@5"]
