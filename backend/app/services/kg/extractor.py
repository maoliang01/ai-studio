"""
实体抽取服务

使用 LLM 从文章内容中抽取实体和关系
"""
import json
import logging
import re
import unicodedata
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
    "causes",       # 导致
    "enables",      # 促进/使能
]

# 细分领域建议(LLM 可自由发挥,这里只做引导)
SUBTYPE_GUIDE = {
    "PERSON":      "SCIENTIST|ENGINEER|ACADEMIC|LEADER|ENTREPRENEUR|WRITER|ARTIST|HISTORICAL|OTHER",
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
5. 每个关系输出:source(源实体)、target(目标实体)、rel_type(关系类型)、evidence(原文依据)、confidence(0到1)
6. 只提取文章中明确提到的实体和关系
7. 实体名称要标准化(如 "OpenAI" 不写成 "open ai")
8. subtype 用英文大写单词,不要用空格/中文
9. 每个实体必须至少参与一条关系；不要输出只有名称、没有任何关系的孤立实体

**重要:subtype 选择指南(严格遵守):**
- PERSON 类型:
  - SCIENTIST:科学家(从事科研工作)
  - ENGINEER:工程师(从事技术开发)
  - ACADEMIC:学者/教授(从事教学科研)
  - LEADER:行政领导(如院长、校长、所长、企业CEO等企事业单位负责人)
  - ENTREPRENEUR:企业家(创办企业)
  - WRITER:作家/记者
  - HISTORICAL:历史人物
  - OTHER:其他
- **注意:不要使用 POLITICIAN!只有真正的政府官员、政党领袖才用 LEADER,企事业单位领导也用 LEADER**

输出格式(JSON,严格遵守):
{{
    "entities": [
        {{"name": "实体名称", "type": "实体类型", "subtype": "细分类型", "description": "简要描述"}}
    ],
    "relations": [
        {{"source": "源实体", "target": "目标实体", "rel_type": "关系类型", "evidence": "原文中的简短依据", "confidence": 0.9}}
    ]
}}

文章内容：
{content}
"""

JSON_REPAIR_PROMPT = """请把下面的知识图谱抽取结果修复为严格合法的 JSON。
只能输出 JSON 对象，不要输出解释、Markdown 或思考过程。
顶层必须包含 entities 和 relations 两个数组；不要新增原结果中不存在的事实。

待修复内容：
{response}
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
            model_error = self._get_model_error(response)
            if model_error:
                return ExtractionResult(error=f"模型调用失败: {model_error}")

            # 解析 JSON；模型偶尔会输出缺逗号或附带说明，失败时进行一次低温修复。
            result = self._parse_llm_response(response, article_id=article_id)
            if result.error:
                repair_response = await llm_service.non_stream_chat(
                    model_id=self.model_id or "default",
                    messages=[{
                        "role": "user",
                        "content": JSON_REPAIR_PROMPT.format(response=str(response)[:16000]),
                    }],
                    temperature=0.0,
                    max_tokens=4096,
                )
                repair_error = self._get_model_error(repair_response)
                if repair_error:
                    return ExtractionResult(error=f"模型修复调用失败: {repair_error}")
                repaired = self._parse_llm_response(
                    repair_response,
                    article_id=article_id,
                )
                if not repaired.error:
                    logger.info("实体抽取 JSON 自动修复成功")
                    return repaired
                logger.warning(
                    "实体抽取 JSON 自动修复失败: 原始=%s, 修复=%s",
                    result.error,
                    repaired.error,
                )
            return result

        except Exception as e:
            logger.error(f"实体抽取失败: {e}")
            return ExtractionResult(error=str(e))

    @staticmethod
    def _get_model_error(response: Any) -> Optional[str]:
        """识别 LLMService 错误响应，避免把网络错误误报成 JSON 错误。"""
        text = str(response or "").strip()
        if text.startswith("[错误]"):
            return text.removeprefix("[错误]").strip()
        return None

    def _parse_llm_response(self, response: str, article_id: Optional[str] = None) -> ExtractionResult:
        """解析 LLM 返回的 JSON 响应"""
        json_str = self._extract_json_object(response)
        if not json_str:
            logger.warning("LLM 响应中未找到 JSON")
            return ExtractionResult(error="解析失败：响应中未找到 JSON")

        try:
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
            entity_names = {
                self._normalize_entity_name(entity.name): entity.name
                for entity in entities
            }
            relation_items = data.get("relations", data.get("relationships", []))
            for r in relation_items:
                if r.get("source") and r.get("target") and r.get("rel_type"):
                    source = entity_names.get(
                        self._normalize_entity_name(str(r["source"]))
                    )
                    target = entity_names.get(
                        self._normalize_entity_name(str(r["target"]))
                    )
                    if not source or not target or source == target:
                        continue
                    # 标准化关系类型
                    rel_type = r["rel_type"].lower().replace("-", "_").replace(" ", "_")
                    if rel_type not in RELATION_TYPES:
                        rel_type = "related_to"

                    try:
                        confidence = float(r.get("confidence", 0.8))
                    except (TypeError, ValueError):
                        confidence = 0.8
                    confidence = max(0.0, min(confidence, 1.0))

                    relations.append(Relationship(
                        source=source,
                        target=target,
                        rel_type=rel_type,
                        properties={
                            "article_id": article_id,
                            "evidence": str(r.get("evidence") or "").strip()[:500],
                            "confidence": confidence,
                        },
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

    @staticmethod
    def _normalize_entity_name(name: str) -> str:
        """Normalize harmless formatting differences in relation endpoints."""
        normalized = unicodedata.normalize("NFKC", name or "").casefold().strip()
        return re.sub(r"[\s\-_·•]+", "", normalized)

    @staticmethod
    def _extract_json_object(response: Any) -> Optional[str]:
        """从代码块或说明文字中提取第一个可解码的 JSON 对象。"""
        if isinstance(response, dict):
            return json.dumps(response, ensure_ascii=False)
        text = str(response or "").strip()
        decoder = json.JSONDecoder()
        for index, char in enumerate(text):
            if char != "{":
                continue
            try:
                data, end = decoder.raw_decode(text[index:])
                if not isinstance(data, dict) or "entities" not in data:
                    continue
                if "relations" not in data and "relationships" not in data:
                    continue
                return text[index:index + end]
            except json.JSONDecodeError:
                continue
        return None

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

            key = self._normalize_entity_name(entity.name)
            if key not in seen:
                seen[key] = entity
                result.append(entity)

        return result


# 全局实例
entity_extractor = EntityExtractor()
