from app.services.kg.prompts import (
    EXTRACT_ENTITIES_FROM_QUESTION_PROMPT,
    ANSWER_WITH_GRAPH_PROMPT,
    SUBTYPE_GUIDE,
)


def test_extract_prompt_has_placeholders():
    assert "{question}" in EXTRACT_ENTITIES_FROM_QUESTION_PROMPT
    assert "{subtype_guide}" in EXTRACT_ENTITIES_FROM_QUESTION_PROMPT


def test_answer_prompt_has_placeholders():
    assert "{context}" in ANSWER_WITH_GRAPH_PROMPT
    assert "{question}" in ANSWER_WITH_GRAPH_PROMPT


def test_subtype_guide_has_seven_categories():
    for k in ("PERSON", "ORGANIZATION", "LOCATION", "TECHNOLOGY", "EVENT", "CONCEPT", "DATE"):
        assert k in SUBTYPE_GUIDE
