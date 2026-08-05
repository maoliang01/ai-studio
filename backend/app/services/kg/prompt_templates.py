"""
知识自增强循环 - 提示词模板管理

提供预置的提示词模板，支持用户自定义。
模板使用 {{variable}} 语法定义变量。
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class PromptTemplate:
    """提示词模板"""
    id: str
    title: str
    content: str
    category: str
    variables: List[Dict[str, str]] = field(default_factory=list)
    description: str = ""
    is_builtin: bool = True


# ==================== 预置提示词模板 ====================

KNOWLEDGE_POINT_EXTRACTION = PromptTemplate(
    id="kp_extraction",
    title="知识点提取",
    category="knowledge_mining",
    description="从文章中提取核心知识点",
    variables=[
        {"name": "content", "description": "文章内容", "required": "true"},
        {"name": "max_points", "description": "最大知识点数量", "default": "10"},
        {"name": "language", "description": "输出语言", "default": "zh"},
    ],
    content="""你是一个知识提取专家。请从以下文本中提取核心知识点。

文本内容：
{{content}}

请提取最多 {{max_points}} 个知识点，每个知识点包含：
1. title: 知识点标题（简短，10-20字）
2. content: 知识点内容（100-200字，准确概括）
3. category: 类型，只能是以下之一：
   - concept: 核心概念、定义、术语
   - argument: 作者的观点、立场、论证
   - fact: 具体的数据、事件、案例
   - method: 解决方案、技术方法、流程
4. confidence: 置信度（0-1），基于文本明确程度
5. keywords: 关键词列表（3-5个）
6. evidence: 支撑该知识点的原文引用，必须来自输入文本
7. source_span: 原文中的最小相关片段，不得补写输入文本之外的内容

请以 JSON 数组格式返回：
[
  {
    "title": "知识点标题",
    "content": "知识点详细内容...",
    "category": "concept",
    "confidence": 0.9,
    "keywords": ["关键词1", "关键词2", "关键词3"],
    "evidence": ["原文引用"],
    "source_span": "原文中的相关片段"
  }
]

要求：
1. 每个知识点独立完整，不要重复
2. 内容准确，不要臆造
3. 优先提取核心和重要的知识点
4. 保持客观，不要添加个人理解
"""
)

RELATIONSHIP_DISCOVERY = PromptTemplate(
    id="rel_discovery",
    title="关系发现",
    category="knowledge_mining",
    description="发现知识点之间的关系",
    variables=[
        {"name": "knowledge_points", "description": "知识点列表（JSON格式）", "required": "true"},
    ],
    content="""你是一个关系发现专家。请分析以下知识点之间的关系。

知识点列表：
{{knowledge_points}}

请发现以下类型的关系：
1. related_to: 相关关系（主题相似或相关）
2. depends_on: 依赖关系（一个知识点依赖另一个）
3. causes: 因果关系（一个导致另一个）
4. part_of: 组成关系（一个是另一个的组成部分）
5. contradicts: 矛盾关系（观点对立）
6. supports: 支持关系（观点相互支持）
7. extends: 扩展关系（一个扩展了另一个）

输出格式（JSON）：
{
  "relationships": [
    {
      "source": "源知识点标题",
      "target": "目标知识点标题",
      "relation_type": "relation_type",
      "strength": 0.8,
      "evidence": "关系依据（简短说明）"
    }
  ]
}

要求：
1. 只提取有明确依据的关系
2. strength 基于证据充分程度（0-1）
3. 关系应该是有意义的，不要提取太弱的关系
4. 每个关系都要有简短的证据说明
"""
)

KNOWLEDGE_SYNTHESIS = PromptTemplate(
    id="knowledge_synthesis",
    title="知识综合文档",
    category="knowledge_mining",
    description="基于多篇资料生成带证据的可复用知识文档",
    variables=[
        {"name": "topic", "description": "主题", "required": "true"},
        {"name": "knowledge_points", "description": "知识声明和证据", "required": "true"},
    ],
    content="""你是研究分析员。请基于以下资料，围绕主题“{{topic}}”生成一份知识综合文档。

资料中的知识声明：
{{knowledge_points}}

要求：
1. 只使用资料中明确支持的内容，不得补造事实
2. 区分事实、来源观点、推断和待验证假设
3. 指出不同来源之间的共识、分歧和近期变化
4. 输出必须包含来源知识声明的编号
5. 内容应能被后续检索和复用，而不是简单重复单篇摘要

请严格返回 JSON 对象：
{
  "title": "主题标题",
  "summary": "不超过200字的结论摘要",
  "content": "完整知识综合文档",
  "quality_score": 0.0
}
"""
)

KNOWLEDGE_SUMMARY = PromptTemplate(
    id="kp_summary",
    title="知识总结",
    category="knowledge_mining",
    description="生成文章的知识总结",
    variables=[
        {"name": "article_content", "description": "文章内容", "required": "true"},
        {"name": "knowledge_points", "description": "提取的知识点", "required": "true"},
        {"name": "associations", "description": "知识点关联", "default": "[]"},
    ],
    content="""你是一个知识总结专家。请根据以下信息生成一份结构化的知识总结。

文章内容摘要：
{{article_content}}

提取的知识点：
{{knowledge_points}}

知识点关联：
{{associations}}

请生成包含以下内容的总结：

1. 核心观点（1-2句话，概括文章主旨）

2. 关键知识点（列出最重要的 3-5 个知识点，每个用一句话描述）

3. 知识点关联（描述知识点之间的主要关系）

4. 潜在应用（这个知识可以应用在哪些场景）

输出格式（JSON）：
{
  "summary": "核心观点总结",
  "key_points": [
    "知识点1: 简短描述",
    "知识点2: 简短描述"
  ],
  "connections": [
    {"from": "知识点A", "to": "知识点B", "relation": "关系描述"}
  ],
  "applications": ["应用场景1", "应用场景2"]
}

要求：
1. 总结要准确反映原文内容
2. 保持客观，不要添加原文没有的信息
3. 控制在 300 字以内
"""
)

TREND_PREDICTION = PromptTemplate(
    id="trend_predict",
    title="趋势预测",
    category="prediction",
    description="预测发展趋势",
    variables=[
        {"name": "topic", "description": "预测主题", "required": "true"},
        {"name": "historical_data", "description": "历史数据", "required": "true"},
        {"name": "time_range", "description": "预测时间范围", "default": "30天"},
    ],
    content="""你是一个趋势分析专家。请根据以下信息预测 "{{topic}}" 的发展趋势。

历史数据：
{{historical_data}}

预测时间范围：{{time_range}}

请分析并预测：

1. 趋势方向
   - up: 上升趋势
   - down: 下降趋势
   - stable: 稳定趋势

2. 影响因素（列出 3-5 个主要因素，每个说明是正面还是负面影响）

3. 置信度评估（0-1）

4. 时间线预测（按周或月给出预测值）

输出格式（JSON）：
{
  "trend": "up",
  "confidence": 0.75,
  "factors": [
    {"name": "因素1", "impact": "positive", "description": "影响说明"},
    {"name": "因素2", "impact": "negative", "description": "影响说明"}
  ],
  "timeline": [
    {"period": "第1周", "prediction": "预测值", "confidence": 0.8},
    {"period": "第2周", "prediction": "预测值", "confidence": 0.75}
  ],
  "analysis": "综合分析说明"
}

要求：
1. 基于数据进行客观分析
2. 考虑多种可能的影响因素
3. 给出合理的置信度评估
4. 预测应该符合常识和逻辑
"""
)

SENTIMENT_ANALYSIS = PromptTemplate(
    id="sentiment",
    title="舆情分析",
    category="prediction",
    description="分析舆情趋势和情感倾向",
    variables=[
        {"name": "topic", "description": "分析主题", "required": "true"},
        {"name": "content", "description": "相关文本内容", "required": "true"},
    ],
    content="""你是一个舆情分析专家。请分析关于 "{{topic}}" 的舆情情况。

相关文本内容：
{{content}}

请分析以下方面：

1. 情感倾向
   - positive: 正面
   - negative: 负面
   - neutral: 中性

2. 舆情热度评估（0-10）

3. 主要观点（列出 3-5 个主要观点或评论）

4. 潜在风险（如有负面舆情，识别潜在风险）

5. 建议措施（基于分析结果给出建议）

输出格式（JSON）：
{
  "sentiment": "positive",
  "heat_level": 7.5,
  "main_opinions": [
    {"opinion": "观点内容", "sentiment": "positive"},
    {"opinion": "观点内容", "sentiment": "negative"}
  ],
  "risks": ["风险1", "风险2"],
  "suggestions": ["建议1", "建议2"],
  "summary": "舆情总结"
}

要求：
1. 客观分析，不要带个人偏见
2. 区分事实和观点
3. 识别潜在的舆情风险
4. 给出可操作的建议
"""
)

CAUSAL_ANALYSIS = PromptTemplate(
    id="causal",
    title="因果分析",
    category="knowledge_mining",
    description="分析事件之间的因果关系",
    variables=[
        {"name": "events", "description": "事件列表", "required": "true"},
        {"name": "context", "description": "背景信息", "default": ""},
    ],
    content="""你是一个因果分析专家。请分析以下事件之间的因果关系。

事件列表：
{{events}}

背景信息：
{{context}}

请分析：

1. 因果关系（识别明确的因果关系）

2. 因果链（描述从原因到结果的完整链条）

3. 置信度（每个因果关系的置信度 0-1）

4. 反向因果可能性（是否存在反向因果）

输出格式（JSON）：
{
  "causal_relationships": [
    {
      "cause": "原因事件",
      "effect": "结果事件",
      "confidence": 0.8,
      "evidence": "因果依据",
      "bidirectional": false
    }
  ],
  "causal_chains": [
    {
      "chain": ["事件A", "事件B", "事件C"],
      "description": "因果链条说明"
    }
  ],
  "summary": "因果分析总结"
}

要求：
1. 只识别有证据支持的因果关系
2. 区分相关性和因果性
3. 考虑其他可能的解释
4. 给出合理的置信度评估
"""
)

# ==================== 模板注册表 ====================

BUILTIN_TEMPLATES: List[PromptTemplate] = [
    KNOWLEDGE_POINT_EXTRACTION,
    RELATIONSHIP_DISCOVERY,
    KNOWLEDGE_SYNTHESIS,
    KNOWLEDGE_SUMMARY,
    TREND_PREDICTION,
    SENTIMENT_ANALYSIS,
    CAUSAL_ANALYSIS,
]


class PromptTemplateManager:
    """
    提示词模板管理器

    负责加载、管理和使用提示词模板。
    支持内置模板和用户自定义模板。
    """

    def __init__(self):
        self.templates: Dict[str, PromptTemplate] = {}
        self._load_builtin_templates()

    def _load_builtin_templates(self):
        """加载内置模板"""
        for template in BUILTIN_TEMPLATES:
            self.templates[template.id] = template

    def get_template(self, template_id: str) -> Optional[PromptTemplate]:
        """获取模板"""
        return self.templates.get(template_id)

    def list_templates(self, category: Optional[str] = None) -> List[PromptTemplate]:
        """列出模板"""
        templates = list(self.templates.values())
        if category:
            templates = [t for t in templates if t.category == category]
        return templates

    def render_template(
        self,
        template_id: str,
        variables: Dict[str, str]
    ) -> str:
        """
        渲染模板

        将模板中的 {{variable}} 替换为实际值。
        """
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")

        rendered = template.content

        for var in template.variables:
            var_name = var["name"]
            value = variables.get(var_name)

            if value is None:
                if var.get("required") == "true":
                    raise ValueError(f"Required variable missing: {var_name}")
                value = var.get("default", "")

            rendered = rendered.replace(f"{{{{{var_name}}}}}", value)

        return rendered

    def register_template(self, template: PromptTemplate):
        """注册自定义模板"""
        template.is_builtin = False
        self.templates[template.id] = template

    def delete_template(self, template_id: str) -> bool:
        """删除模板（只能删除自定义模板）"""
        template = self.templates.get(template_id)
        if not template:
            return False

        if template.is_builtin:
            return False  # 不能删除内置模板

        del self.templates[template_id]
        return True

    def get_template_for_frontend(self, template_id: str) -> Optional[Dict]:
        """获取前端友好的模板格式"""
        template = self.get_template(template_id)
        if not template:
            return None

        return {
            "id": template.id,
            "title": template.title,
            "content": template.content,
            "category": template.category,
            "description": template.description,
            "variables": template.variables,
            "isBuiltin": template.is_builtin,
        }


# 全局模板管理器实例
template_manager = PromptTemplateManager()
