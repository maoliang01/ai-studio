import json

import pytest

from app.services.kg.event_interpretation import EventInterpretationService


def _specific_analysis():
    return {
        "analysis_status": "complete",
        "executive_judgment": "供给扩张可能压低部分产品溢价，并推动监管从项目审批转向产能与安全约束。",
        "event_summary": "两篇来源共同确认新增产能和利润承压，政策变化仍属推断。",
        "current_phase": "规模扩张",
        "signal_assessment": {
            "label": "信号分化",
            "meaning": "产能推进与盈利承压同时存在。",
            "evidence": "来源分别提供产能和利润信息。",
        },
        "impact_assessments": [
            {
                "dimension": "经济",
                "conclusion": "同质化产品利润空间可能继续收窄。",
                "mechanism": "新增产能释放 -> 供给增加 -> 议价能力下降",
                "affected_parties": ["生产企业", "下游采购方"],
                "horizon": "中期（6-24个月）",
                "likelihood": "中",
                "evidence_basis": "来源一披露产能，来源二披露利润占比较低。",
            },
            {
                "dimension": "政策/监管",
                "conclusion": "监管重点可能转向安全生产和低效产能约束。",
                "mechanism": "产能集中投放 -> 安全与竞争压力上升 -> 监管检查趋严",
                "affected_parties": ["生产企业", "地方监管部门"],
                "horizon": "短期（0-6个月）",
                "likelihood": "中",
                "evidence_basis": "多来源确认产能扩张，但尚无正式政策文件。",
            },
        ],
        "next_developments": [
            {
                "dimension": "经济",
                "title": "生产企业调整产品结构与报价策略",
                "likelihood": "中",
                "timeframe": "6-12个月",
                "mechanism": "利润承压 -> 压缩低毛利产线 -> 转向差异化产品",
                "affected_parties": ["生产企业", "客户"],
                "basis": "来源显示该产品利润贡献有限。",
                "watch_for": "产品报价、开工率和毛利率是否同步变化",
            },
            {
                "dimension": "政策",
                "title": "地方增加安全生产与环保核查频次",
                "likelihood": "中",
                "timeframe": "3-9个月",
                "mechanism": "集中扩产 -> 风险敞口增加 -> 地方部门加强现场核查",
                "affected_parties": ["生产企业", "园区"],
                "basis": "来源确认多个扩产项目推进。",
                "watch_for": "检查通报、排污许可和项目验收节奏",
            },
        ],
        "opportunities": [
            {
                "title": "高附加值差异化产品替代",
                "beneficiaries": ["具备研发能力的生产商"],
                "rationale": "避开同质化价格竞争。",
                "entry_condition": "完成客户验证并具备稳定良率",
                "horizon": "中期（6-24个月）",
            }
        ],
        "challenges": [
            {
                "title": "低效产能现金流承压",
                "exposed_parties": ["单一产品企业"],
                "rationale": "价格下行会放大固定成本负担。",
                "warning_signal": "开工率下降且库存连续上升",
                "horizon": "短中期",
            }
        ],
        "drivers": ["新增产能按期释放"],
        "risks": ["扩产项目延期会改变供需判断"],
        "watch_indicators": ["开工率", "产品价格", "监管检查通报"],
        "decision_value": {"category": "产业", "explanation": "提前评估产品结构和产能利用率。"},
    }


class FakeLlm:
    def __init__(self, result):
        self.result = result
        self.messages = None
        self.model_id = None
        self.response_format = None

    async def non_stream_chat(self, **kwargs):
        self.messages = kwargs["messages"]
        self.model_id = kwargs["model_id"]
        self.response_format = kwargs.get("response_format")
        return json.dumps(self.result, ensure_ascii=False)


@pytest.mark.asyncio
async def test_interpretation_returns_specific_cross_domain_analysis():
    llm = FakeLlm(_specific_analysis())
    service = EventInterpretationService(llm, timeout_seconds=1)
    result = await service.interpret(
        {
            "title": "产业扩产事件",
            "evidence_articles": [
                {"title": "来源甲", "summary": "摘要", "analysis_text": "正文中的产能数据和项目安排"},
                {"title": "来源乙", "summary": "摘要", "analysis_text": "正文中的利润和市场信息"},
            ],
        },
        {"trend": "up", "knowledge_points": 0, "cross_document_relations": 0, "model_id": "fast-model"},
    )

    assert result["analysis_status"] == "complete"
    assert result["generated_by"] == "llm"
    assert {item["dimension"] for item in result["impact_assessments"]} >= {"经济", "政策/监管"}
    assert "正文中的产能数据" in llm.messages[0]["content"]
    assert "不得原样输出" in llm.messages[0]["content"]
    assert llm.model_id == "fast-model"
    assert llm.response_format is None


@pytest.mark.asyncio
async def test_interpretation_rejects_generic_next_steps():
    generic = _specific_analysis()
    generic["next_developments"][0]["title"] = "出现后续公开报道或官方进展"
    service = EventInterpretationService(FakeLlm(generic), timeout_seconds=1)

    result = await service.interpret(
        {"title": "事件", "evidence_articles": [{"title": "甲"}, {"title": "乙"}]},
        {"trend": "up"},
    )

    assert result["analysis_status"] == "unavailable"
    assert result["next_developments"] == []
    assert "拒绝展示模板化推断" in result["analysis_error"]


@pytest.mark.asyncio
async def test_interpretation_rejects_structured_but_vague_output():
    vague = _specific_analysis()
    vague["next_developments"][0]["title"] = "企业年金管理机构行为变化"
    vague["next_developments"][0]["watch_for"] = "企业年金管理机构的行为变化"
    service = EventInterpretationService(FakeLlm(vague), timeout_seconds=1)

    result = await service.interpret(
        {"title": "事件", "evidence_articles": [{"title": "甲"}, {"title": "乙"}]},
        {"trend": "up", "model_id": "fast-model"},
    )

    assert result["analysis_status"] == "unavailable"
    assert result["impact_assessments"] == []


@pytest.mark.asyncio
async def test_interpretation_accepts_chinese_causal_connectors_and_string_parties():
    analysis = _specific_analysis()
    analysis["impact_assessments"][0]["mechanism"] = "新增供给释放，导致市场竞争加剧，进而促使企业降低报价"
    analysis["impact_assessments"][1]["mechanism"] = "风险敞口增加 → 地方监管部门提高检查频率"
    analysis["next_developments"][0]["mechanism"] = "利润承压导致企业压缩低毛利产线，从而转向差异化产品"
    analysis["next_developments"][0]["affected_parties"] = "生产企业"
    service = EventInterpretationService(FakeLlm(analysis), timeout_seconds=1)

    result = await service.interpret(
        {"title": "事件", "evidence_articles": [{"title": "甲"}, {"title": "乙"}]},
        {"trend": "up", "model_id": "fast-model"},
    )

    assert result["analysis_status"] == "complete"
    assert result["next_developments"][0]["affected_parties"] == ["生产企业"]


def test_parse_reports_truncated_json_reason():
    parsed, reason = EventInterpretationService._parse_with_reason(
        '{"executive_judgment":"内容被截断"'
    )

    assert parsed is None
    assert "截断" in reason


def test_parse_repairs_missing_comma_without_weakening_validation():
    malformed = json.dumps(_specific_analysis(), ensure_ascii=False)
    malformed = malformed.replace(', "event_summary"', ' "event_summary"', 1)

    parsed, reason = EventInterpretationService._parse_with_reason(malformed)

    assert reason == ""
    assert parsed is not None
    assert parsed["analysis_status"] == "complete"
    assert len(parsed["next_developments"]) == 2


@pytest.mark.asyncio
async def test_one_weak_extra_item_does_not_discard_complete_analysis():
    analysis = _specific_analysis()
    third = dict(analysis["next_developments"][0])
    third["title"] = "生产企业降低低毛利产品供应规模"
    fourth = dict(analysis["next_developments"][0])
    fourth["title"] = "持续关注后续进展"
    analysis["next_developments"].extend([third, fourth])
    service = EventInterpretationService(FakeLlm(analysis), timeout_seconds=1)

    result = await service.interpret(
        {"title": "事件", "evidence_articles": [{"title": "甲"}, {"title": "乙"}]},
        {"trend": "up", "model_id": "fast-model"},
    )

    assert result["analysis_status"] == "complete"
    assert len(result["next_developments"]) == 3
    assert any("通用后续话术" in item for item in result["quality_warnings"])


@pytest.mark.asyncio
async def test_mechanism_does_not_require_specific_connector_words():
    analysis = _specific_analysis()
    analysis["next_developments"][0]["mechanism"] = "企业重新评估低毛利产线并把资源配置到差异化产品"
    analysis["next_developments"][1]["mechanism"] = "地方部门基于项目风险敞口强化现场核查频率"
    service = EventInterpretationService(FakeLlm(analysis), timeout_seconds=1)

    result = await service.interpret(
        {"title": "事件", "evidence_articles": [{"title": "甲"}, {"title": "乙"}]},
        {"trend": "up", "model_id": "fast-model"},
    )

    assert result["analysis_status"] == "complete"
    assert len(result["next_developments"]) == 2


@pytest.mark.asyncio
async def test_missing_llm_does_not_invent_rule_based_prediction():
    result = await EventInterpretationService().interpret(
        {"title": "事件", "evidence_articles": [{"title": "甲"}, {"title": "乙"}]},
        {"trend": "up"},
    )

    assert result["analysis_status"] == "unavailable"
    assert result["impact_assessments"] == []
    assert result["opportunities"] == []
    assert "模板" in result["analysis_error"]
