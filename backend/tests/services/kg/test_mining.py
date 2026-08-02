from app.services.kg.mining import (
    discover_alias_candidates,
    discover_causal_candidates,
    discover_historical_causal_claims,
    discover_transitive_inferences,
    build_spectral_embeddings,
    evaluate_embedding_quality,
    find_relation_evidence,
    louvain_entity_communities,
    predict_structural_links,
    rank_embedding_similarities,
)


def test_alias_candidates_use_cross_document_overlap():
    entities = [
        {"name": "空天院", "entity_type": "ORGANIZATION", "article_ids": ["a1", "a2", "a3"]},
        {"name": "中国科学院空天信息创新研究院", "entity_type": "ORGANIZATION", "article_ids": ["a1", "a2", "a3", "a4"]},
        {"name": "北京大学", "entity_type": "ORGANIZATION", "article_ids": ["a1"]},
    ]

    candidates = discover_alias_candidates(entities)

    assert len(candidates) == 1
    assert candidates[0]["left"]["name"] == "空天院"
    assert candidates[0]["score"] > 0.4


def test_louvain_finds_disconnected_groups():
    nodes = [
        {"name": name, "entity_type": "CONCEPT", "article_ids": [name]}
        for name in ["A", "B", "C", "X", "Y", "Z"]
    ]
    edges = [
        {"source": "A", "target": "B", "weight": 2},
        {"source": "B", "target": "C", "weight": 2},
        {"source": "A", "target": "C", "weight": 1},
        {"source": "X", "target": "Y", "weight": 2},
        {"source": "Y", "target": "Z", "weight": 2},
        {"source": "X", "target": "Z", "weight": 1},
    ]

    communities = louvain_entity_communities(nodes, edges, min_size=3)

    assert len(communities) == 2
    assert sorted(community["size"] for community in communities) == [3, 3]
    assert all(community["summary"] for community in communities)
    assert all(len(community["core_entities"]) == 3 for community in communities)


def test_relation_evidence_requires_both_entities_in_same_sentence():
    content = "甲参加会议。乙发布报告。甲随后加入乙并负责项目。"

    assert find_relation_evidence(content, "甲", "乙") == "甲随后加入乙并负责项目。"
    assert find_relation_evidence(content, "甲", "丙") == ""


def test_transitive_inference_returns_explainable_path_without_direct_edges():
    edges = [
        {
            "source": "实验室",
            "target": "研究院",
            "rel_type": "part_of",
            "confidence": 0.9,
            "source_articles": ["a1"],
        },
        {
            "source": "研究院",
            "target": "科学院",
            "rel_type": "part_of",
            "confidence": 0.8,
            "source_articles": ["a2"],
        },
    ]

    inferences = discover_transitive_inferences(edges)

    assert len(inferences) == 1
    assert inferences[0]["source"] == "实验室"
    assert inferences[0]["target"] == "科学院"
    assert inferences[0]["path"] == ["实验室", "研究院", "科学院"]
    assert inferences[0]["confidence"] == 0.72
    assert inferences[0]["source_articles"] == ["a1", "a2"]


def test_link_prediction_uses_common_neighbors_and_skips_existing_edges():
    nodes = [
        {"name": name, "entity_type": "CONCEPT"}
        for name in ["A", "B", "C", "X"]
    ]
    edges = [
        {"source": "A", "target": "B"},
        {"source": "A", "target": "C"},
        {"source": "X", "target": "B"},
        {"source": "X", "target": "C"},
    ]

    predictions = predict_structural_links(nodes, edges, min_common_neighbors=2)

    predicted_pairs = [{item["source"], item["target"]} for item in predictions]
    assert {"A", "X"} in predicted_pairs
    candidate = next(item for item in predictions if {item["source"], item["target"]} == {"A", "X"})
    assert candidate["common_neighbors"] == ["B", "C"]
    assert candidate["score"] >= 0.2


def test_spectral_embeddings_support_similarity_ranking():
    nodes = [
        {"name": name, "entity_type": "CONCEPT", "subtype": "TEST"}
        for name in ["A", "B", "C", "D"]
    ]
    edges = [
        {"source": "A", "target": "B", "weight": 2.0},
        {"source": "A", "target": "C", "weight": 2.0},
        {"source": "D", "target": "B", "weight": 1.0},
        {"source": "D", "target": "C", "weight": 1.0},
    ]

    embeddings = build_spectral_embeddings(nodes, edges, dimensions=3)
    results = rank_embedding_similarities(
        "B", embeddings, {node["name"]: node for node in nodes}
    )

    assert set(embeddings) == {"A", "B", "C", "D"}
    assert all(len(vector) == 3 for vector in embeddings.values())
    assert results[0]["name"] == "C"


def test_causal_candidates_require_explicit_markers_and_both_entities():
    claims = [
        {
            "source": "新技术",
            "target": "效率提升",
            "evidence": "新技术推动效率提升。",
            "confidence": 0.8,
            "article_id": "a1",
        },
        {
            "source": "平台",
            "target": "服务",
            "evidence": "平台与服务受到关注。",
            "confidence": 0.9,
            "article_id": "a2",
        },
    ]

    candidates = discover_causal_candidates(claims)

    assert len(candidates) == 1
    assert candidates[0]["source"] == "新技术"
    assert candidates[0]["target"] == "效率提升"
    assert candidates[0]["rel_type"] == "enables"
    assert candidates[0]["markers"] == ["推动"]


def test_historical_causal_claims_require_linked_entities_around_marker():
    articles = [{
        "id": "a1",
        "content": "太空云推动卫星资源互联互通。无关实体也出现在文章其他位置。",
        "summary": "",
    }]
    entities = {
        "a1": [
            {"name": "太空云", "entity_type": "CONCEPT"},
            {"name": "卫星资源", "entity_type": "CONCEPT"},
            {"name": "无关实体", "entity_type": "CONCEPT"},
        ]
    }

    records = discover_historical_causal_claims(articles, entities)
    candidates = discover_causal_candidates(records)

    assert len(records) == 1
    assert records[0]["source"] == "太空云"
    assert records[0]["target"] == "卫星资源"
    assert candidates[0]["discovery_sources"] == ["historical_article"]


def test_embedding_quality_reports_neighbor_recovery():
    embeddings = {
        "A": [1.0, 0.0],
        "B": [0.9, 0.1],
        "C": [0.0, 1.0],
    }
    quality = evaluate_embedding_quality(
        embeddings,
        [{"source": "A", "target": "B"}],
        k=1,
    )

    assert quality["embedded_entities"] == 3
    assert quality["evaluated_entities"] == 2
    assert quality["precision_at_k"] == 1.0
    assert quality["recall_at_k"] == 1.0
