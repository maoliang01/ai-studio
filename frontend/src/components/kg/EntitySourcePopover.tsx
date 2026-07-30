"use client";
import { useEffect, useState } from "react";
import { ExternalLink, X, Loader2 } from "lucide-react";
import { getEntityContext, type EntityContextResponse } from "@/lib/api-kg";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface Props {
  entityName: string;
  onClose: () => void;
  onJumpToArticle?: (articleId: string) => void;
}

const ENTITY_TYPE_LABELS: Record<string, string> = {
  PERSON: "人物",
  ORGANIZATION: "组织",
  LOCATION: "地点",
  TECHNOLOGY: "技术",
  EVENT: "事件",
  CONCEPT: "概念",
  DATE: "时间",
};

const SUBTYPE_LABELS: Record<string, string> = {
  SCIENTIST: "科学家",
  ENGINEER: "工程师",
  ACADEMIC: "学者",
  LEADER: "领导",
  ENTREPRENEUR: "企业家",
  WRITER: "作家",
  ARTIST: "艺术家",
  HISTORICAL: "历史人物",
  COMPANY: "公司",
  RESEARCH_INST: "研究机构",
  UNIVERSITY: "大学",
  GOVERNMENT: "政府",
  INTERNATIONAL: "国际组织",
  NGO: "NGO",
  CITY: "城市",
  COUNTRY: "国家",
  REGION: "地区",
  BUILDING: "建筑",
  ASTRONOMICAL: "天文",
  NATURAL: "自然",
  AI_MODEL: "AI 模型",
  ALGORITHM: "算法",
  PRODUCT: "产品",
  LANGUAGE: "编程语言",
  FRAMEWORK: "框架",
  TOOL: "工具",
  MATERIAL: "材料",
  BIOTECH: "生物技术",
  ENERGY: "能源",
  DEVICE: "设备",
  DISCOVERY: "发现",
  CONFERENCE: "会议",
  PUBLICATION: "出版物",
  AWARD: "奖项",
  AGREEMENT: "协议",
  DISASTER: "灾害",
  CONFLICT: "冲突",
  THEORY: "理论",
  LAW: "定律",
  METHOD: "方法",
  MODEL: "模型",
  SYSTEM: "系统",
  IDEA: "思想",
  DISCIPLINE: "学科",
  FIELD: "领域",
  YEAR: "年",
  MONTH: "月",
  DAY: "日",
  ERA: "时代",
  PERIOD: "时期",
  OTHER: "其他",
};

const colorMap: Record<string, string> = {
  PERSON: "bg-emerald-100 text-emerald-700",
  ORGANIZATION: "bg-blue-100 text-blue-700",
  LOCATION: "bg-amber-100 text-amber-700",
  TECHNOLOGY: "bg-violet-100 text-violet-700",
  EVENT: "bg-pink-100 text-pink-700",
  CONCEPT: "bg-cyan-100 text-cyan-700",
  DATE: "bg-slate-100 text-slate-700",
};

function highlightSnippet(snippet: string, entityName: string) {
  if (!snippet || !entityName) return snippet;
  const parts = snippet.split(new RegExp(`(${entityName})`, "gi"));
  return parts.map((p, i) =>
    p.toLowerCase() === entityName.toLowerCase() ? (
      <mark key={i} className="bg-yellow-200 px-0.5 rounded">{p}</mark>
    ) : (
      <span key={i}>{p}</span>
    ),
  );
}

export default function EntitySourcePopover({ entityName, onClose, onJumpToArticle }: Props) {
  const [data, setData] = useState<EntityContextResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getEntityContext(entityName, 5)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && console.error(e))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [entityName]);

  return (
    <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] overflow-hidden flex flex-col" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between p-4 border-b">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-slate-800">{entityName}</h3>
            {data?.entity?.type && (
              <Badge className={colorMap[data.entity.type] || "bg-slate-100 text-slate-700"}>
                {ENTITY_TYPE_LABELS[data.entity.type] || data.entity.type}
                {data.entity.subtype ? ` · ${SUBTYPE_LABELS[data.entity.subtype] || data.entity.subtype}` : ""}
              </Badge>
            )}
          </div>
          <Button size="icon" variant="ghost" onClick={onClose}><X className="h-4 w-4" /></Button>
        </div>
        <div className="flex-1 overflow-auto p-4 space-y-3">
          {loading ? (
            <div className="flex items-center justify-center py-8 text-slate-400">
              <Loader2 className="h-5 w-5 animate-spin mr-2" />加载中…
            </div>
          ) : !data || data.articles.length === 0 ? (
            <p className="text-sm text-slate-400 italic text-center py-6">图谱中暂无该实体的原文出处</p>
          ) : (
            data.articles.map((a) => (
              <div key={a.article_id} className="border border-slate-200 rounded-md p-3 hover:border-blue-400 transition">
                <div className="flex items-start justify-between gap-2">
                  <div className="font-medium text-sm text-slate-800">{a.title}</div>
                  {onJumpToArticle && (
                    <Button size="sm" variant="ghost" onClick={() => onJumpToArticle(a.article_id)} className="text-blue-600 hover:text-blue-800 h-7 px-2">
                      <ExternalLink className="h-3 w-3 mr-1" />在文章中查看
                    </Button>
                  )}
                </div>
                {a.snippet && (
                  <p className="mt-2 text-xs text-slate-600 leading-relaxed">…{highlightSnippet(a.snippet, entityName)}…</p>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
