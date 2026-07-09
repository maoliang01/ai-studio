// 知识图谱前端 API 客户端

export interface GraphNode {
  id: string;
  name: string;
  type: string;
  subtype?: string | null;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
}

export interface SourceArticle {
  article_id: string;
  title: string;
  snippet: string;
  highlight_positions: [number, number][];
}

export interface EntityInfo {
  name: string;
  type: string | null;
  subtype: string | null;
  description: string | null;
}

export interface AnswerResponse {
  status: "ok" | "degraded";
  answer: string;
  subgraph: { nodes: GraphNode[]; edges: GraphEdge[] } | null;
  sources: SourceArticle[];
  cited_entities: string[];
}

export interface EntityContextResponse {
  entity: EntityInfo;
  articles: SourceArticle[];
}

const BASE = "/api/kg";

export async function qaAnswer(
  question: string,
  modelId: string,
  sessionId?: string,
): Promise<AnswerResponse> {
  const r = await fetch(`${BASE}/qa/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, model_id: modelId, session_id: sessionId }),
  });
  if (!r.ok) throw new Error(`qa/answer failed: ${r.status}`);
  return r.json();
}

export async function getEntityContext(
  name: string,
  limit = 5,
): Promise<EntityContextResponse> {
  const r = await fetch(
    `${BASE}/entity-context/${encodeURIComponent(name)}?limit=${limit}`,
  );
  if (!r.ok) throw new Error(`entity-context failed: ${r.status}`);
  return r.json();
}
