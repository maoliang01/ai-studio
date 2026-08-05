'use client'

import { useEffect, useState } from 'react'
import { AlertCircle, CheckCircle2, FileText, Loader2, RefreshCw, TrendingUp } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

interface EventEvidence {
  id: string
  title: string
  summary: string
  url: string
  published_at?: string | null
  scraped_at?: string | null
}

interface DiscoveredEvent {
  id: string
  title: string
  topic: string
  confidence: number
  signal_type: string
  signal_reasons: string[]
  evidence_articles: EventEvidence[]
}

interface PredictionResult {
  prediction_id: string
  topic: string
  trend: string
  confidence: number
  prediction_type: string
  generated_at: string
  factors: Array<{ type: string; name: string; evidence?: string }>
  scenarios: Array<{ name: string; trend: string; probability: number; basis: string }>
  interpretation?: {
    event_summary: string
    current_phase: string
    next_developments: Array<{ title: string; likelihood: string; basis: string; watch_for: string }>
    drivers: string[]
    risks: string[]
    watch_indicators: string[]
    decision_value: { category: string; explanation: string }
  }
  knowledge_basis: {
    event_id?: string
    evidence_articles?: number
    knowledge_points?: number
    cross_document_relations?: number
    multi_document?: boolean
    evidence_titles?: string[]
    support_level?: string
    knowledge_point_details?: Array<{ title: string; content: string; category: string; evidence?: string; source_url?: string | null }>
    relation_details?: Array<{ source: string; target: string; type: string; strength: number; evidence?: string }>
  }
}

interface Synthesis {
  id: string
  topic: string
  title: string
  summary: string
  content: string
  status: string
  iteration: number
  source_document_ids: string[]
  source_claim_ids: string[]
  quality_score: number | null
  created_at: string | null
}

interface PredictionRecord {
  id: string
  topic: string
  trend: string
  confidence: number
  status: string
  actual_trend: string | null
  accuracy_score: number | null
  knowledge_basis?: { support_level?: string }
  created_at: string | null
}

interface Stats {
  total_articles_processed: number
  total_knowledge_points: number
  total_associations: number
  quality_metrics?: {
    knowledge_points?: { evidence_coverage: number; source_coverage: number }
    candidates?: { pending: number }
  }
}

const trendLabels: Record<string, string> = { up: '上升', down: '下降', stable: '稳定' }

function trendLabel(value: string) {
  return trendLabels[value] || value
}

const categoryLabels: Record<string, string> = {
  concept: '概念',
  fact: '事实',
  argument: '观点',
  method: '方法',
}

const relationLabels: Record<string, string> = {
  same_as: '同一内容',
  related_to: '相关',
  supports: '支持',
  contradicts: '矛盾',
  extends: '延伸',
}

async function readJson(response: Response) {
  const data = await response.json()
  if (!response.ok) throw new Error(data.detail || '请求失败')
  return data
}

export default function SelfEnhancementPage() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [events, setEvents] = useState<DiscoveredEvent[]>([])
  const [syntheses, setSyntheses] = useState<Synthesis[]>([])
  const [history, setHistory] = useState<PredictionRecord[]>([])
  const [prediction, setPrediction] = useState<PredictionResult | null>(null)
  const [loadingEvents, setLoadingEvents] = useState(false)
  const [loadingEventId, setLoadingEventId] = useState<string | null>(null)
  const [loadingSynthesis, setLoadingSynthesis] = useState(false)

  const loadStats = async () => {
    const response = await fetch('/api/kg/self-enhancement/stats')
    if (response.ok) setStats(await response.json())
  }

  const loadEvents = async () => {
    setLoadingEvents(true)
    try {
      const response = await fetch('/api/kg/prediction/discover-events?limit=20&days=90')
      const data = await readJson(response)
      setEvents(data.events || [])
    } catch (error) {
      console.error(error)
    } finally {
      setLoadingEvents(false)
    }
  }

  const loadSyntheses = async () => {
    const response = await fetch('/api/kg/self-enhancement/syntheses?limit=20')
    if (response.ok) setSyntheses((await response.json()).syntheses || [])
  }

  const loadHistory = async () => {
    const response = await fetch('/api/kg/prediction/history?limit=20')
    if (response.ok) setHistory((await response.json()).predictions || [])
  }

  const reload = async () => {
    await Promise.all([loadStats(), loadEvents(), loadSyntheses(), loadHistory()])
  }

  useEffect(() => {
    reload()
  }, [])

  const predictEvent = async (event: DiscoveredEvent) => {
    setLoadingEventId(event.id)
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 35000)
    try {
      const response = await fetch('/api/kg/prediction/discovered-event', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ event_id: event.id, time_range: 30, prediction_type: 'general' }),
        signal: controller.signal,
      })
      setPrediction(await readJson(response))
      await loadHistory()
    } catch (error) {
      alert(error instanceof DOMException && error.name === 'AbortError' ? '交叉分析超时，请稍后重试。系统已将 LLM 解读限制在 10 秒内。' : error instanceof Error ? error.message : '交叉分析失败')
    } finally {
      window.clearTimeout(timeout)
      setLoadingEventId(null)
    }
  }

  const createAutoSynthesis = async () => {
    setLoadingSynthesis(true)
    try {
      const response = await fetch('/api/kg/self-enhancement/syntheses/auto', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ limit: 5 }),
      })
      await readJson(response)
      await loadSyntheses()
    } catch (error) {
      alert(error instanceof Error ? error.message : '知识综合失败')
    } finally {
      setLoadingSynthesis(false)
    }
  }

  const reviewSynthesis = async (id: string, decision: 'approved' | 'rejected') => {
    const response = await fetch(`/api/kg/self-enhancement/syntheses/${id}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision }),
    })
    if (!response.ok) {
      const data = await response.json()
      alert(data.detail || '审核失败')
      return
    }
    await loadSyntheses()
  }

  const submitFeedback = async (id: string, actualTrend: 'up' | 'down' | 'stable') => {
    const response = await fetch(`/api/kg/prediction/history/${id}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ actual_trend: actualTrend }),
    })
    if (response.ok) await loadHistory()
  }

  const multiDocumentEvents = events.filter((event) => event.evidence_articles.length >= 2)
  const evidenceCoverage = stats?.quality_metrics?.knowledge_points?.evidence_coverage || 0

  return (
    <main className="container mx-auto max-w-7xl p-6">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <TrendingUp className="h-8 w-8" />
            <h1 className="text-3xl font-bold">知识洞察中心</h1>
          </div>
          <p className="mt-2 text-sm text-gray-600">
            系统从持续进入的文章中发现事件，交叉比较多篇来源，生成可审核的趋势、舆情、科技和商机洞察。
          </p>
        </div>
        <Button variant="outline" onClick={reload} title="重新加载数据">
          <RefreshCw className="mr-2 h-4 w-4" />刷新
        </Button>
      </div>

      <Card className="mb-6 border-blue-200 bg-blue-50/40">
        <CardContent className="grid gap-4 p-4 text-sm md:grid-cols-4">
          <div><strong>1. 数据进入</strong><p className="mt-1 text-gray-600">爬虫或外部导入文章，系统自动去重并保留来源。</p></div>
          <div><strong>2. 事件发现</strong><p className="mt-1 text-gray-600">从近期文章中发现至少两个来源共同指向的变化。</p></div>
          <div><strong>3. 交叉分析</strong><p className="mt-1 text-gray-600">比较文章、知识点和关系，输出多种可能情景。</p></div>
          <div><strong>4. 审核反馈</strong><p className="mt-1 text-gray-600">发布有价值的综合知识，并反馈预测是否命中。</p></div>
        </CardContent>
      </Card>

      <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        <Card><CardHeader className="pb-2"><CardTitle className="text-sm text-gray-500">已处理文档</CardTitle></CardHeader><CardContent><div className="text-3xl font-bold">{stats?.total_articles_processed || 0}</div></CardContent></Card>
        <Card><CardHeader className="pb-2"><CardTitle className="text-sm text-gray-500">知识点</CardTitle></CardHeader><CardContent><div className="text-3xl font-bold">{stats?.total_knowledge_points || 0}</div><p className="mt-1 text-xs text-gray-500">作为分析证据，不是最终洞察</p></CardContent></Card>
        <Card><CardHeader className="pb-2"><CardTitle className="text-sm text-gray-500">已审核关系</CardTitle></CardHeader><CardContent><div className="text-3xl font-bold">{stats?.total_associations || 0}</div><p className="mt-1 text-xs text-gray-500">已确认的知识点之间关系</p></CardContent></Card>
        <Card><CardHeader className="pb-2"><CardTitle className="text-sm text-gray-500">证据覆盖率</CardTitle></CardHeader><CardContent><div className="text-3xl font-bold">{Math.round(evidenceCoverage * 100)}%</div><p className="mt-1 text-xs text-gray-500">知识点带原文证据的比例</p></CardContent></Card>
      </div>

      <Tabs defaultValue="events">
        <TabsList className="mb-4">
          <TabsTrigger value="events">候选事件与交叉分析</TabsTrigger>
          <TabsTrigger value="synthesis">知识综合</TabsTrigger>
          <TabsTrigger value="feedback">预测反馈</TabsTrigger>
        </TabsList>

        <TabsContent value="events" className="space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-start justify-between gap-4">
              <div>
                <CardTitle>系统发现的候选事件</CardTitle>
                <p className="mt-1 text-sm text-gray-500">只有至少 2 篇相关文档的事件才能交叉分析。按钮会读取这些文档的摘要、知识点和关系，输出基准、乐观和风险情景。</p>
              </div>
              <Button variant="outline" onClick={loadEvents} disabled={loadingEvents}>
                <RefreshCw className={`mr-2 h-4 w-4 ${loadingEvents ? 'animate-spin' : ''}`} />刷新发现
              </Button>
            </CardHeader>
            <CardContent className="space-y-3">
              {multiDocumentEvents.length === 0 ? (
                <div className="rounded border border-dashed p-8 text-center text-sm text-gray-500">暂时没有多来源候选事件，请等待更多文章进入。</div>
              ) : multiDocumentEvents.map((event) => (
                <div key={event.id} className="rounded-lg border p-4">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <h3 className="font-semibold">{event.title}</h3>
                      <p className="mt-1 text-sm text-gray-500">发现置信度 {Math.round(event.confidence * 100)}% · 来源 {event.evidence_articles.length} 篇</p>
                      <div className="mt-2 flex flex-wrap gap-2">{event.signal_reasons.map((reason) => <Badge key={reason} variant="outline">{reason}</Badge>)}</div>
                    </div>
                    <Button onClick={() => predictEvent(event)} disabled={loadingEventId !== null}>
                      {loadingEventId === event.id ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <TrendingUp className="mr-2 h-4 w-4" />}
                      交叉分析
                    </Button>
                  </div>
                  <details className="mt-3 rounded bg-gray-50 p-3 text-sm">
                    <summary className="cursor-pointer font-medium">查看参与分析的文章</summary>
                    <div className="mt-2 space-y-2">{event.evidence_articles.map((article) => <div key={article.id} className="border-b pb-2 last:border-0"><p className="font-medium">{article.title}</p><p className="text-xs text-gray-500">{article.summary || '无摘要'}</p></div>)}</div>
                  </details>
                </div>
              ))}
            </CardContent>
          </Card>

          {prediction && (
            <Card className="border-green-200">
              <CardHeader><CardTitle>交叉分析结果</CardTitle><p className="text-sm text-gray-500">{prediction.topic}</p></CardHeader>
              <CardContent className="space-y-4">
                <div className="rounded border border-slate-200 bg-slate-50 p-3 text-sm text-gray-700">“证据支持度”表示当前资料对判断方向的支持程度，不是事件发生概率，也不是统计学置信区间。分数越高，说明来源、知识点和已审核关系越充分。</div>
                <div className="flex flex-wrap gap-2"><Badge>判断方向：{trendLabel(prediction.trend)}</Badge><Badge variant="outline">证据支持度：{prediction.knowledge_basis.support_level || '待评估'}（{Math.round(prediction.confidence * 100)}分）</Badge><Badge variant="outline">来源：{prediction.knowledge_basis.evidence_articles || 0} 篇</Badge><Badge variant="outline">结构化知识点：{prediction.knowledge_basis.knowledge_points || 0} 个</Badge><Badge variant="outline">已审核关系：{prediction.knowledge_basis.cross_document_relations || 0} 条</Badge></div>
                {(prediction.knowledge_basis.knowledge_points || 0) === 0 && <div className="flex gap-2 rounded bg-amber-50 p-3 text-sm text-amber-800"><AlertCircle className="h-4 w-4 shrink-0" />本次使用了多篇文章，但这些文章尚未形成知识点或正式关系，结果主要依据文章内容，可信度需要谨慎解读。</div>}
                <div className="rounded-lg border border-blue-200 bg-blue-50/40 p-4"><div className="flex flex-wrap items-center justify-between gap-2"><h4 className="font-medium">事件解读</h4><Badge variant="outline">{prediction.interpretation?.current_phase || '待补充阶段判断'}</Badge></div><p className="mt-2 text-sm leading-6 text-gray-700">{prediction.interpretation?.event_summary || '当前结果主要反映来源文章中的共同信号，尚未形成进一步解读。'}</p>{prediction.interpretation?.next_developments?.length ? <div className="mt-4"><h5 className="mb-2 text-sm font-medium">可能的下一步</h5><div className="grid gap-3 md:grid-cols-2">{prediction.interpretation.next_developments.map((item) => <div key={item.title} className="rounded border bg-white p-3"><div className="flex flex-wrap justify-between gap-2"><strong className="text-sm">{item.title}</strong><Badge variant="outline">可能性：{item.likelihood}</Badge></div><p className="mt-2 text-xs text-gray-600">判断依据：{item.basis}</p><p className="mt-1 text-xs text-gray-500">观察：{item.watch_for}</p></div>)}</div></div> : null}<div className="mt-4 grid gap-4 text-sm md:grid-cols-2"><div><h5 className="mb-1 font-medium">推动因素</h5><ul className="list-disc space-y-1 pl-5 text-gray-600">{(prediction.interpretation?.drivers || []).map((item) => <li key={item}>{item}</li>)}</ul></div><div><h5 className="mb-1 font-medium">风险与不确定性</h5><ul className="list-disc space-y-1 pl-5 text-gray-600">{(prediction.interpretation?.risks || []).map((item) => <li key={item}>{item}</li>)}</ul></div></div><div className="mt-4"><h5 className="mb-1 text-sm font-medium">继续观察</h5><p className="text-sm text-gray-600">{(prediction.interpretation?.watch_indicators || []).join('；') || '等待新的独立来源或可验证结果。'}</p></div>{prediction.interpretation?.decision_value && <div className="mt-4 rounded border bg-white p-3 text-sm"><strong>决策价值：{prediction.interpretation.decision_value.category}</strong><p className="mt-1 text-gray-600">{prediction.interpretation.decision_value.explanation}</p></div>}</div>
                <div><div className="mb-2 flex flex-wrap items-center justify-between gap-2"><h4 className="font-medium">可能情景</h4><span className="text-xs text-gray-500">情景参考权重，不是统计概率</span></div><div className="grid gap-3 md:grid-cols-3">{prediction.scenarios.map((scenario) => <div key={scenario.name} className="rounded border p-3"><div className="flex justify-between"><strong>{scenario.name}</strong><Badge variant="outline">{trendLabel(scenario.trend)}</Badge></div><p className="mt-1 text-sm text-gray-500">参考权重：{Math.round(scenario.probability * 100)}%</p><p className="mt-1 text-xs text-gray-500">{scenario.basis}</p></div>)}</div></div>
                <details><summary className="cursor-pointer text-sm font-medium">查看参与判断的知识证据</summary><div className="mt-2 space-y-1 text-sm text-gray-600">{prediction.knowledge_basis.evidence_titles?.map((title) => <p key={title}>· {title}</p>)}</div></details>
                <details open className="rounded border p-3"><summary className="cursor-pointer text-sm font-medium">查看参与判断的知识证据</summary><div className="mt-3 space-y-3 text-sm text-gray-600"><div><p className="font-medium text-gray-800">结构化知识点</p>{prediction.knowledge_basis.knowledge_point_details?.map((point, index) => <div key={`${point.title}-${index}`} className="mt-2 rounded border bg-white p-2"><div className="font-medium text-gray-800">{point.title} <span className="text-xs text-gray-500">（{categoryLabels[point.category] || point.category}）</span></div><p className="mt-1">{point.content}</p>{point.evidence && <p className="mt-1 text-xs text-gray-500">原文依据：{point.evidence}</p>}</div>)}</div>{(prediction.knowledge_basis.relation_details || []).length > 0 && <div><p className="font-medium text-gray-800">已审核关系</p>{prediction.knowledge_basis.relation_details?.map((relation, index) => <div key={`${relation.source}-${relation.target}-${index}`} className="mt-2 rounded border bg-white p-2"><p className="font-medium text-gray-800">{relation.source} → {relation.target} <span className="text-xs text-gray-500">（{relationLabels[relation.type] || relation.type}）</span></p>{relation.evidence && <p className="mt-1 text-xs text-gray-500">关系依据：{relation.evidence}</p>}</div>)}</div>}{!prediction.knowledge_basis.knowledge_point_details?.length && !prediction.knowledge_basis.relation_details?.length && <p className="text-amber-700">本次没有可用的结构化知识点或已审核关系，判断主要来自文章之间的共同信号。</p>}</div></details>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="synthesis" className="space-y-4">
          <Card>
            <CardHeader><CardTitle>知识综合</CardTitle><p className="text-sm text-gray-500">系统自动选择候选事件的来源文档和知识点，生成可复用的知识草稿。发布前必须人工审核。</p></CardHeader>
            <CardContent><Button onClick={createAutoSynthesis} disabled={loadingSynthesis}>{loadingSynthesis ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <FileText className="mr-2 h-4 w-4" />}自动发现并生成草稿</Button></CardContent>
          </Card>
          {syntheses.map((synthesis) => <Card key={synthesis.id}><CardHeader><div className="flex flex-wrap items-center justify-between gap-3"><div><CardTitle>{synthesis.title}</CardTitle><p className="mt-1 text-sm text-gray-500">来源 {synthesis.source_document_ids.length} 篇 · 知识声明 {synthesis.source_claim_ids.length} 条</p></div><Badge variant={synthesis.status === 'published' ? 'default' : 'secondary'}>{synthesis.status}</Badge></div></CardHeader><CardContent><p className="text-sm text-gray-600">{synthesis.summary}</p>{(synthesis.status === 'draft' || synthesis.status === 'review') && <div className="mt-3 flex gap-2"><Button onClick={() => reviewSynthesis(synthesis.id, 'approved')}><CheckCircle2 className="mr-2 h-4 w-4" />审核发布</Button><Button variant="outline" onClick={() => reviewSynthesis(synthesis.id, 'rejected')}>驳回</Button></div>}<details className="mt-3"><summary className="cursor-pointer text-sm font-medium">查看综合内容</summary><pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap rounded bg-gray-50 p-3 text-xs">{synthesis.content}</pre></details></CardContent></Card>)}
          {syntheses.length === 0 && <div className="rounded border border-dashed p-8 text-center text-sm text-gray-500">还没有综合草稿，点击上方按钮开始。</div>}
        </TabsContent>

        <TabsContent value="feedback" className="space-y-4">
          <div className="rounded border border-slate-200 bg-slate-50 p-3 text-sm text-gray-700">反馈的用途：未来确认事件实际方向后回填“实际上升、实际稳定或实际下降”。系统据此计算方向一致度，帮助判断过去的规则是否可靠，不会把这次反馈直接当成新的事实。</div>
          <Card><CardHeader><CardTitle>预测反馈</CardTitle><p className="text-sm text-gray-500">预测结果不会自动变成事实。未来观察到实际结果后，请标记真实趋势，系统会统计命中率。</p></CardHeader><CardContent className="space-y-3">{history.map((item) => <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 border-b pb-3 last:border-0"><div><p className="font-medium">{item.topic}</p><p className="text-xs text-gray-500">预测：{trendLabel(item.trend)} · 置信度 {Math.round(item.confidence * 100)}% {item.status === 'evaluated' ? `· 命中率 ${Math.round((item.accuracy_score || 0) * 100)}%` : ''}</p></div>{item.status !== 'evaluated' && <div className="flex gap-2"><Button size="sm" variant="outline" onClick={() => submitFeedback(item.id, 'up')}>上升</Button><Button size="sm" variant="outline" onClick={() => submitFeedback(item.id, 'stable')}>稳定</Button><Button size="sm" variant="outline" onClick={() => submitFeedback(item.id, 'down')}>下降</Button></div>}</div>)}{history.length === 0 && <p className="py-8 text-center text-sm text-gray-500">完成一次交叉分析后，这里会出现预测记录。</p>}</CardContent></Card>
        </TabsContent>
      </Tabs>
    </main>
  )
}
