from app.services.kg.graph import (
    build_claim_id,
    build_embedding_version,
    build_entity_id,
    build_review_id,
)


def test_entity_id_is_stable_across_spacing_and_case():
    assert build_entity_id("Open AI", "organization") == build_entity_id(
        "open-ai",
        "ORGANIZATION",
    )


def test_claim_id_changes_with_article_or_evidence():
    first = build_claim_id("a1", "甲", "part_of", "乙", "甲加入乙")

    assert first == build_claim_id("a1", "甲", "part_of", "乙", "甲加入乙")
    assert first != build_claim_id("a2", "甲", "part_of", "乙", "甲加入乙")
    assert first != build_claim_id("a1", "甲", "part_of", "乙", "另一条证据")


def test_review_id_is_stable_for_reversed_candidate_pair():
    first = build_review_id("alias", "空天院", "中国科学院空天信息创新研究院")
    reversed_pair = build_review_id("alias", "中国科学院空天信息创新研究院", "空天院")

    assert first == reversed_pair
    assert first != build_review_id(
        "cross_document", "空天院", "中国科学院空天信息创新研究院"
    )


def test_directional_review_ids_preserve_endpoint_order():
    for review_type in ("causal", "inference", "legacy_relation"):
        forward = build_review_id(review_type, "source", "target", "causes")
        reverse = build_review_id(review_type, "target", "source", "causes")

        assert forward != reverse

    assert build_review_id("link_prediction", "source", "target") == build_review_id(
        "link_prediction", "target", "source"
    )


def test_embedding_version_changes_when_isolated_node_is_added():
    nodes = [{"name": "A", "entity_type": "CONCEPT", "subtype": "TEST"}]
    first = build_embedding_version(nodes, [], 4)
    second = build_embedding_version(
        nodes + [{"name": "B", "entity_type": "CONCEPT", "subtype": "TEST"}],
        [],
        4,
    )

    assert first != second
