"""知识图谱问答使用的 prompt 模板"""

SUBTYPE_GUIDE: dict = {
    "PERSON":      "SCIENTIST|ENGINEER|ACADEMIC|POLITICIAN|ENTREPRENEUR|WRITER|ARTIST|HISTORICAL|OTHER",
    "ORGANIZATION": "COMPANY|RESEARCH_INST|UNIVERSITY|GOVERNMENT|INTERNATIONAL|NGO|OTHER",
    "LOCATION":    "CITY|COUNTRY|REGION|BUILDING|ASTRONOMICAL|NATURAL|OTHER",
    "TECHNOLOGY":  "AI_MODEL|ALGORITHM|PRODUCT|LANGUAGE|FRAMEWORK|TOOL|MATERIAL|BIOTECH|ENERGY|DEVICE|OTHER",
    "EVENT":       "DISCOVERY|CONFERENCE|PUBLICATION|AWARD|AGREEMENT|DISASTER|CONFLICT|OTHER",
    "CONCEPT":     "THEORY|LAW|METHOD|MODEL|SYSTEM|IDEA|DISCIPLINE|FIELD|OTHER",
    "DATE":        "YEAR|MONTH|DAY|ERA|PERIOD|OTHER",
}


EXTRACT_ENTITIES_FROM_QUESTION_PROMPT = """你是实体抽取助手。从用户问题中识别关键实体。

要求:
- name: 实体原文(不要翻译、不要简化)
- type: 必须是以下之一: PERSON | ORGANIZATION | LOCATION | TECHNOLOGY | EVENT | CONCEPT | DATE
- subtype: 该 type 下的细分,候选如下:
{subtype_guide}
- 只输出 JSON 数组,无其他文字

示例问题: "OpenAI 是什么时候成立的?Sam Altman 之前在哪家公司?"
示例输出: [
  {{"name": "OpenAI", "type": "ORGANIZATION", "subtype": "COMPANY"}},
  {{"name": "Sam Altman", "type": "PERSON", "subtype": "ENTREPRENEUR"}}
]

用户问题: {question}
JSON 数组:
"""


ANSWER_WITH_GRAPH_PROMPT = """你是基于知识图谱的问答助手。严格依据下方"图谱事实"回答,不要编造。
如信息不足,直接说"图谱中暂未收录"。

回答要求:
- 用 [n] 标注引用,顺序对应下方事实
- 不要超出图谱事实范围
- 简洁,2-4 句

图谱事实:
{context}

用户问题: {question}
回答:
"""
