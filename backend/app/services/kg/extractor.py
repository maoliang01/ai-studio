"""
实体抽取服务

使用 LLM 从文章内容中抽取实体和关系
"""
import json
import logging
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from app.core.llm import llm_service
from app.services.kg.graph import EntityNode, Relationship

logger = logging.getLogger("ai-studio")

# 实体类型
ENTITY_TYPES = [
    "PERSON",      # 人物
    "ORGANIZATION", # 组织/机构
    "LOCATION",    # 地点
    "TECHNOLOGY",  # 技术/产品
    "EVENT",       # 事件
    "CONCEPT",     # 概念/理论
    "DATE",        # 时间
]

# 关系类型
RELATION_TYPES = [
    "founded",      # 创立
    "related_to",   # 相关
    "located_in",   # 位于
    "developed",    # 开发
    "published",    # 发布
    "authored",     # 创作
    "uses",         # 使用
    "part_of",      # 属于
    "precedes",     # 先于
    "succeeds",     # 后于
]

# 细分领域建议(LLM 可自由发挥,这里只做引导)
SUBTYPE_GUIDE = {
    "PERSON":      "SCIENTIST|ENGINEER|ACADEMIC|POLITICIAN|ENTREPRENEUR|WRITER|ARTIST|HISTORICAL|OTHER",
    "ORGANIZATION": "COMPANY|RESEARCH_INST|UNIVERSITY|GOVERNMENT|INTERNATIONAL|NGO|OTHER",
    "LOCATION":    "CITY|COUNTRY|REGION|BUILDING|ASTRONOMICAL|NATURAL|OTHER",
    "TECHNOLOGY":  "AI_MODEL|ALGORITHM|PRODUCT|LANGUAGE|FRAMEWORK|TOOL|MATERIAL|BIOTECH|ENERGY|DEVICE|OTHER",
    "EVENT":       "DISCOVERY|CONFERENCE|PUBLICATION|AWARD|AGREEMENT|DISASTER|CONFLICT|OTHER",
    "CONCEPT":     "THEORY|LAW|METHOD|MODEL|SYSTEM|IDEA|DISCIPLINE|FIELD|OTHER",
    "DATE":        "YEAR|MONTH|DAY|ERA|PERIOD|OTHER",
}

# 抽取提示词
EXTRACTION_PROMPT = """你是一个知识图谱专家。请从以下文章中提取实体和关系。

要求：
1. 实体类型(必填)：{entity_types}
2. 细分类型 subtype(强烈建议,除非实在无法判断,可空字符串)：
   {subtype_guide}
3. 关系类型(必填)：{relation_types}
4. 每个实体输出:name(名称)、type(类型)、subtype(细分类型)、description(简要描述)
5. 每个关系输出:source(源实体)、target(目标实体)、rel_type(关系类型)
6. 只提取文章中明确提到的实体和关系
7. 实体名称要标准化(如 "OpenAI" 不写成 "open ai")
8. subtype 用英文大写单词,不要用空格/中文

输出格式(JSON,严格遵守):
{{
    "entities": [
        {{"name": "实体名称", "type": "实体类型", "subtype": "细分类型", "description": "简要描述"}}
    ],
    "relations": [
        {{"source": "源实体", "target": "目标实体", "rel_type": "关系类型"}}
    ]
}}

文章内容：
{content}
"""


@dataclass
class ExtractionResult:
    """抽取结果"""
    entities: List[EntityNode] = field(default_factory=list)
    relations: List[Relationship] = field(default_factory=list)
    raw_json: Optional[str] = None
    error: Optional[str] = None


class EntityExtractor:
    """实体抽取器"""

    def __init__(self, model_id: Optional[str] = None):
        self.model_id = model_id

    async def extract(
        self,
        content: str,
        max_content_length: int = 8000,
        article_id: Optional[str] = None,
    ) -> ExtractionResult:
        """
        从文章内容中抽取实体和关系

        Args:
            content: 文章内容
            max_content_length: 最大内容长度（超出部分截断）
            article_id: 文章 id,非空时记录到 EntityNode.source_articles

        Returns:
            ExtractionResult: 抽取结果
        """
        # 截断超长内容
        if len(content) > max_content_length:
            content = content[:max_content_length]
            logger.debug(f"内容过长，已截断至 {max_content_length} 字符")

        # 构建提示词
        subtype_guide_str = "\n   ".join(
            f"- {k}: {v}" for k, v in SUBTYPE_GUIDE.items()
        )
        prompt = EXTRACTION_PROMPT.format(
            entity_types=", ".join(ENTITY_TYPES),
            subtype_guide=subtype_guide_str,
            relation_types=", ".join(RELATION_TYPES),
            content=content
        )

        try:
            # 调用 LLM
            messages = [{"role": "user", "content": prompt}]
            response = await llm_service.non_stream_chat(
                model_id=self.model_id or "default",
                messages=messages,
                temperature=0.3,  # 较低温度确保稳定性
                max_tokens=4096
            )

            # 解析 JSON
            result = self._parse_llm_response(response, article_id=article_id)
            return result

        except Exception as e:
            logger.error(f"实体抽取失败: {e}")
            return ExtractionResult(error=str(e))

    def _parse_llm_response(self, response: str, article_id: Optional[str] = None) -> ExtractionResult:
        """解析 LLM 返回的 JSON 响应"""
        # 提取 JSON 部分
        json_match = re.search(r'\{[\s\S]*\}', response)
        if not json_match:
            logger.warning("LLM 响应中未找到 JSON")
            return ExtractionResult(error="解析失败：响应中未找到 JSON")

        try:
            json_str = json_match.group(0)
            data = json.loads(json_str)

            entities = []
            relations = []

            # 解析实体
            for e in data.get("entities", []):
                if e.get("name") and e.get("type"):
                    # 标准化实体类型
                    entity_type = e["type"].upper()
                    if entity_type not in ENTITY_TYPES:
                        # 尝试映射
                        type_mapping = {
                            "PRODUCT": "TECHNOLOGY",
                            "COMPANY": "ORGANIZATION",
                            "PERSON": "PERSON",
                            "PLACE": "LOCATION",
                            "THEORY": "CONCEPT",
                            "MODEL": "CONCEPT",
                            "METHOD": "TECHNOLOGY",
                            "ALGORITHM": "TECHNOLOGY",
                        }
                        entity_type = type_mapping.get(entity_type, "CONCEPT")

                    # 标准化 subtype:大写、去空格、限长
                    raw_subtype = (e.get("subtype") or "").strip()
                    subtype = ""
                    if raw_subtype:
                        subtype = raw_subtype.upper().replace(" ", "_").replace("-", "_")[:32]

                    entities.append(EntityNode(
                        name=e["name"].strip(),
                        entity_type=entity_type,
                        description=e.get("description", "").strip(),
                        subtype=subtype,
                        source_articles=[article_id] if article_id else None,
                    ))

            # 解析关系
            for r in data.get("relations", []):
                if r.get("source") and r.get("target") and r.get("rel_type"):
                    # 标准化关系类型
                    rel_type = r["rel_type"].lower().replace("-", "_").replace(" ", "_")
                    if rel_type not in RELATION_TYPES:
                        rel_type = "related_to"

                    relations.append(Relationship(
                        source=r["source"].strip(),
                        target=r["target"].strip(),
                        rel_type=rel_type
                    ))

            logger.info(f"抽取完成：{len(entities)} 个实体, {len(relations)} 个关系")

            return ExtractionResult(
                entities=entities,
                relations=relations,
                raw_json=json_str
            )

        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            return ExtractionResult(error=f"JSON 解析失败: {e}")

    def validate_entity(self, entity: EntityNode) -> bool:
        """
        验证实体是否有效

        Args:
            entity: 实体节点

        Returns:
            bool: 是否有效
        """
        # 名称不能为空
        if not entity.name or len(entity.name.strip()) < 1:
            return False

        # 名称长度限制
        if len(entity.name) > 200:
            return False

        # 类型必须在支持列表中
        if entity.entity_type not in ENTITY_TYPES:
            return False

        # 排除明显不是实体的内容
        invalid_patterns = [
            r'^\d+$',  # 纯数字
            r'^\s+$',  # 纯空白
            r'^[，。、；：""''（）【】《》]+$',  # 纯标点
        ]
        for pattern in invalid_patterns:
            if re.match(pattern, entity.name):
                return False

        return True

    def deduplicate_entities(self, entities: List[EntityNode]) -> List[EntityNode]:
        """
        对实体列表进行去重

        Args:
            entities: 实体列表

        Returns:
            List[EntityNode]: 去重后的实体列表
        """
        seen = {}
        result = []

        for entity in entities:
            if not self.validate_entity(entity):
                continue

            key = entity.name.lower()
            if key not in seen:
                seen[key] = entity
                result.append(entity)

        return result


# 全局实例
entity_extractor = EntityExtractor()