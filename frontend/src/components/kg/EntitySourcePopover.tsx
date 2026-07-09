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
                {data.entity.type}{data.entity.subtype ? ` · ${data.entity.subtype}` : ""}
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
