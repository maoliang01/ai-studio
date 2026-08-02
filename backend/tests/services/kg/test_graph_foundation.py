from app.services.kg.graph import build_claim_id, build_entity_id


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
