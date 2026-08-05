"""把交叉分析结果转换为用户可理解的事件解读。"""

import json
import logging
import asyncio
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ai-studio.event_interpretation")


class EventInterpretationService:
    """基于证据生成事件阶段、后续走势和决策关注点。"""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    async def interpret(
        self,
        event: Dict[str, Any],
        prediction: Dict[str, Any],
    ) -> Dict[str, Any]:
        evidence = event.get("evidence_articles") or []
        fallback = self._fallback(event, prediction)
        if not self.llm_client:
            return fallback
        source_text = "\n\n".join(
            f"来源{i + 1}: {item.get('title', '')}\n{item.get('summary', '')[:800]}"
            for i, item in enumerate(evidence)
        )
        prompt = f"""
你是事件研判分析师。请只依据下方来源和交叉分析结果，生成可审核的事件解读。
不要把“上升/下降”解释成股价或确定事实，不要补造来源没有的信息。
输出严格 JSON：
{{
  "event_summary": "当前发生了什么",
  "current_phase": "已发生/扩散中/推进中/转折风险/证据不足",
  "next_developments": [{{"title":"可能的下一步", "likelihood":"高/中/低", "basis":"依据", "watch_for":"观察信号"}}],
  "drivers": ["推动事件发展的因素"],
  "risks": ["不确定性或反向因素"],
  "watch_indicators": ["未来需要继续跟踪的指标或事件"],
  "decision_value": {{"category":"舆情/科技/商机/风险/综合", "explanation":"对用户的价值"}}
}}

事件：{event.get('title', '')}
交叉分析趋势：{prediction.get('trend', 'stable')}
证据文档数：{len(evidence)}
知识点数：{prediction.get('knowledge_points', 0)}
正式关系数：{prediction.get('cross_document_relations', 0)}
来源：
{source_text[:10000]}
"""
        try:
            response = await asyncio.wait_for(
                self.llm_client.non_stream_chat(
                    model_id=None,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.15,
                    max_tokens=1800,
                ),
                timeout=10,
            )
            parsed = self._parse(response)
            if parsed:
                return {**fallback, **parsed, "generated_by": "llm"}
        except Exception as exc:
            logger.warning("事件进一步解读生成失败，使用保守解读: %s", exc)
        return fallback

    @staticmethod
    def _fallback(event: Dict[str, Any], prediction: Dict[str, Any]) -> Dict[str, Any]:
        evidence = event.get("evidence_articles") or []
        trend = prediction.get("trend", "stable")
        marker_text = " ".join(event.get("signal_reasons") or [])
        phase = "扩散中" if len(evidence) >= 3 else "证据不足"
        if any(marker in marker_text for marker in ("完成", "获批", "上线", "建成")):
            phase = "推进中"
        return {
            "event_summary": f"当前有 {len(evidence)} 篇来源文档指向同一事件或主题，信号方向为{trend}。",
            "current_phase": phase,
            "next_developments": [
                {"title": "出现后续公开报道或官方进展", "likelihood": "中", "basis": "当前已有多来源关注", "watch_for": "新增来源、正式通知或执行结果"},
                {"title": "事件进入具体执行或反馈阶段", "likelihood": "中", "basis": "事件已出现明确动作信号", "watch_for": "时间表、参与主体和结果数据"},
            ],
            "drivers": ["来源数量和近期关注度", "事件标题中的动作信号"],
            "risks": ["当前知识点或正式关系不足，无法确认更深层因果", "来源可能存在同源转载，需核验独立性"],
            "watch_indicators": ["是否出现新的独立来源", "是否出现可验证的结果或数据", "是否出现相反信息"],
            "decision_value": {"category": "综合", "explanation": "适合作为后续跟踪线索，不应单独作为确定性决策依据。"},
            "generated_by": "rule",
        }

    @staticmethod
    def _parse(response: str) -> Optional[Dict[str, Any]]:
        if not response:
            return None
        text = response[response.find("{"): response.rfind("}") + 1] if "{" in response and "}" in response else response
        try:
            data = json.loads(text)
        except (TypeError, json.JSONDecodeError):
            return None
        required = {"event_summary", "current_phase", "next_developments", "drivers", "risks", "watch_indicators", "decision_value"}
        if not required.issubset(data):
            return None
        return data
