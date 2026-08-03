'use client'

import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Loader2, RefreshCw, BookOpen, Link, TrendingUp, FileText, Copy, Search, File, CheckSquare, Square, CheckCircle, AlertCircle } from 'lucide-react'

interface Article {
  id: string
  title: string
  summary: string
  word_count: number
  published_at: string | null
  scraped_at: string | null
  kg_status: string
  category_name: string | null
  source_type: string | null
}

interface KnowledgePoint {
  id: string
  article_id: string
  title: string
  content: string
  category: string
  confidence: number
  keywords: string[]
  created_at: string
}

interface Association {
  id: string
  source_id: string
  source_title: string
  target_id: string
  target_title: string
  relation_type: string
  strength: number
  evidence: string
}

interface EnhancementStats {
  total_articles_processed: number
  total_knowledge_points: number
  total_associations: number
  average_points_per_article: number
  average_associations_per_point: number
  last_processed_at: string | null
}

interface PromptTemplate {
  id: string
  title: string
  content: string
  category: string
  description: string
  variables: Array<{ name: string; description: string; required?: string; default?: string }>
  isBuiltin: boolean
}

export default function SelfEnhancementPage() {
  const [stats, setStats] = useState<EnhancementStats | null>(null)
  const [knowledgePoints, setKnowledgePoints] = useState<KnowledgePoint[]>([])
  const [associations, setAssociations] = useState<Association[]>([])
  const [templates, setTemplates] = useState<PromptTemplate[]>([])
  const [selectedTemplate, setSelectedTemplate] = useState<PromptTemplate | null>(null)
  const [loading, setLoading] = useState(false)
  const [processingResult, setProcessingResult] = useState<any>(null)

  // 文章选择相关状态
  const [articles, setArticles] = useState<Article[]>([])
  const [selectedArticle, setSelectedArticle] = useState<Article | null>(null)
  const [selectedArticles, setSelectedArticles] = useState<Set<string>>(new Set())
  const [articleSearchQuery, setArticleSearchQuery] = useState('')
  const [articlesLoading, setArticlesLoading] = useState(false)
  const [articleStatusFilter, setArticleStatusFilter] = useState<string>('all')

  // 批量处理相关状态
  const [batchProcessing, setBatchProcessing] = useState(false)
  const [batchProgress, setBatchProgress] = useState<{
    total: number
    processed: number
    failed: number
    percentage: number
    currentArticle: { id: string; title: string; index: number } | null
    errors: Array<{ article_id: string; error: string }>
  } | null>(null)
  const [pendingInfo, setPendingInfo] = useState<{ pending: number; processed: number } | null>(null)
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null)

  // 加载统计数据
  useEffect(() => {
    loadStats()
    loadKnowledgePoints()
    loadAssociations()
    loadTemplates()
    loadArticles()
  }, [])

  const loadStats = async () => {
    try {
      const response = await fetch('/api/kg/self-enhancement/stats')
      if (response.ok) {
        const data = await response.json()
        setStats(data)
      }
    } catch (error) {
      console.error('Failed to load stats:', error)
    }
  }

  const loadKnowledgePoints = async () => {
    try {
      const response = await fetch('/api/kg/self-enhancement/knowledge-points')
      if (response.ok) {
        const data = await response.json()
        setKnowledgePoints(data.knowledge_points || [])
      }
    } catch (error) {
      console.error('Failed to load knowledge points:', error)
    }
  }

  const loadAssociations = async () => {
    try {
      const response = await fetch('/api/kg/self-enhancement/associations')
      if (response.ok) {
        const data = await response.json()
        setAssociations(data.associations || [])
      }
    } catch (error) {
      console.error('Failed to load associations:', error)
    }
  }

  const loadTemplates = async () => {
    try {
      const response = await fetch('/api/kg/self-enhancement/templates')
      if (response.ok) {
        const data = await response.json()
        setTemplates(data.templates || [])
      }
    } catch (error) {
      console.error('Failed to load templates:', error)
    }
  }

  const loadArticles = async (query?: string, statusFilter?: string) => {
    setArticlesLoading(true)
    try {
      const params = new URLSearchParams()
      if (query) params.set('q', query)
      if (statusFilter && statusFilter !== 'all') {
        params.set('kg_status', statusFilter)
      }
      params.set('page_size', '50')

      const response = await fetch(`/api/kg/self-enhancement/articles?${params}`)
      if (response.ok) {
        const data = await response.json()
        setArticles(data.articles || [])
      }
    } catch (error) {
      console.error('Failed to load articles:', error)
    } finally {
      setArticlesLoading(false)
    }
  }

  const searchArticles = useCallback(async (query: string) => {
    setArticleSearchQuery(query)
    await loadArticles(query || undefined, articleStatusFilter)
  }, [articleStatusFilter])

  const selectArticle = (article: Article) => {
    setSelectedArticle(article)
  }

  const toggleArticleSelection = (articleId: string) => {
    setSelectedArticles(prev => {
      const newSet = new Set(prev)
      if (newSet.has(articleId)) {
        newSet.delete(articleId)
      } else {
        newSet.add(articleId)
      }
      return newSet
    })
  }

  const selectAllArticles = () => {
    if (selectedArticles.size === articles.length) {
      setSelectedArticles(new Set())
    } else {
      setSelectedArticles(new Set(articles.map(a => a.id)))
    }
  }

  const batchProcessArticles = async (forceReprocess: boolean = false) => {
    if (selectedArticles.size === 0) {
      alert('请先选择要处理的文章')
      return
    }

    setBatchProcessing(true)
    setBatchProgress({
      total: selectedArticles.size,
      processed: 0,
      failed: 0,
      percentage: 0,
      currentArticle: null,
      errors: []
    })

    try {
      const response = await fetch('/api/kg/self-enhancement/batch-process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          article_ids: Array.from(selectedArticles),
          force_reprocess: forceReprocess
        })
      })

      if (response.ok) {
        const result = await response.json()
        setCurrentTaskId(result.task_id)

        // 开始轮询进度
        pollBatchProgress(result.task_id)

        // 清除选择
        setSelectedArticles(new Set())
      } else {
        const error = await response.json()
        alert(`批量处理失败: ${error.detail || '未知错误'}`)
        setBatchProcessing(false)
        setBatchProgress(null)
      }
    } catch (error) {
      console.error('Failed to batch process:', error)
      alert('批量处理失败，请检查网络连接')
      setBatchProcessing(false)
      setBatchProgress(null)
    }
  }

  const pollBatchProgress = async (taskId: string) => {
    const pollInterval = 2000 // 2秒轮询一次
    let isCompleted = false

    while (!isCompleted) {
      try {
        const response = await fetch(`/api/kg/self-enhancement/batch-status/${taskId}`)
        if (response.ok) {
          const progress = await response.json()

          setBatchProgress({
            total: progress.total,
            processed: progress.processed,
            failed: progress.failed,
            percentage: progress.percentage,
            currentArticle: progress.current_article,
            errors: progress.errors || []
          })

          if (progress.status === 'completed' || progress.status === 'failed') {
            isCompleted = true
            setBatchProcessing(false)
            setCurrentTaskId(null)

            // 刷新数据
            loadStats()
            loadKnowledgePoints()
            loadAssociations()
            loadArticles(articleSearchQuery || undefined, articleStatusFilter)

            if (progress.status === 'completed') {
              alert(`批量处理完成！\n成功: ${progress.processed} 篇\n失败: ${progress.failed} 篇`)
            } else {
              alert(`批量处理失败: ${progress.error || '未知错误'}`)
            }
          }
        }
      } catch (error) {
        console.error('Failed to poll progress:', error)
      }

      if (!isCompleted) {
        await new Promise(resolve => setTimeout(resolve, pollInterval))
      }
    }
  }

  const detectPendingArticles = async () => {
    try {
      const response = await fetch('/api/kg/self-enhancement/auto-detect-pending')
      if (response.ok) {
        const data = await response.json()
        setPendingInfo({
          pending: data.pending_count,
          processed: data.processed_count
        })

        // 自动筛选待处理文章
        setArticleStatusFilter('pending')
        loadArticles(undefined, 'pending')
      }
    } catch (error) {
      console.error('Failed to detect pending articles:', error)
    }
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  const processArticle = async () => {
    if (!selectedArticle) {
      alert('请先选择一篇文章')
      return
    }

    setLoading(true)
    setProcessingResult(null)

    try {
      const response = await fetch('/api/kg/self-enhancement/process-article', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          article_id: selectedArticle.id
        })
      })

      if (response.ok) {
        const result = await response.json()
        setProcessingResult(result)
        // 刷新数据
        loadStats()
        loadKnowledgePoints()
        loadAssociations()
        // 刷新文章列表，保持当前筛选状态
        loadArticles(articleSearchQuery || undefined, articleStatusFilter)
        // 清除选中状态
        setSelectedArticle(null)
      } else {
        const error = await response.json()
        alert(`处理失败: ${error.detail || '未知错误'}`)
      }
    } catch (error) {
      console.error('Failed to process article:', error)
      alert('处理失败，请检查网络连接')
    } finally {
      setLoading(false)
    }
  }

  const getCategoryColor = (category: string) => {
    const colors: Record<string, string> = {
      concept: 'bg-blue-100 text-blue-800',
      argument: 'bg-green-100 text-green-800',
      fact: 'bg-yellow-100 text-yellow-800',
      method: 'bg-purple-100 text-purple-800'
    }
    return colors[category] || 'bg-gray-100 text-gray-800'
  }

  const getCategoryName = (category: string) => {
    const names: Record<string, string> = {
      concept: '概念',
      argument: '观点',
      fact: '事实',
      method: '方法'
    }
    return names[category] || category
  }

  const getKgStatusBadge = (status: string) => {
    const variants: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
      pending: 'outline',
      processing: 'secondary',
      success: 'default',
      failed: 'destructive',
    }
    const labels: Record<string, string> = {
      pending: '待处理',
      processing: '处理中',
      success: '已完成',
      failed: '失败',
    }
    return (
      <Badge variant={variants[status] || 'outline'}>
        {labels[status] || status}
      </Badge>
    )
  }

  return (
    <div className="container mx-auto p-6">
      <div className="flex items-center gap-3 mb-6">
        <TrendingUp className="h-8 w-8" />
        <h1 className="text-3xl font-bold">知识自增强循环</h1>
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">已处理文章</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{stats?.total_articles_processed || 0}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">知识点总数</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{stats?.total_knowledge_points || 0}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">关联总数</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{stats?.total_associations || 0}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">平均知识点/文章</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {stats?.average_points_per_article?.toFixed(2) || '0'}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 处理文章 - 文章列表选择 */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BookOpen className="h-5 w-5" />
            选择文章进行处理
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* 搜索栏 */}
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                <Input
                  placeholder="搜索文章标题或摘要..."
                  value={articleSearchQuery}
                  onChange={(e) => searchArticles(e.target.value)}
                  className="pl-10"
                />
              </div>
              <Button
                variant="outline"
                onClick={() => { setArticleSearchQuery(''); loadArticles(undefined, articleStatusFilter) }}
                disabled={articlesLoading}
              >
                <RefreshCw className={`h-4 w-4 ${articlesLoading ? 'animate-spin' : ''}`} />
              </Button>
            </div>

            {/* 状态筛选按钮 */}
            <div className="flex gap-2 flex-wrap">
              <span className="text-sm text-gray-500 self-center">筛选：</span>
              {[
                { value: 'pending', label: '待处理' },
                { value: 'all', label: '全部' },
                { value: 'success', label: '已完成' },
                { value: 'failed', label: '失败' },
              ].map((item) => (
                <Button
                  key={item.value}
                  variant={articleStatusFilter === item.value ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => {
                    setArticleStatusFilter(item.value)
                    loadArticles(articleSearchQuery || undefined, item.value)
                  }}
                  disabled={articlesLoading}
                >
                  {item.label}
                </Button>
              ))}
              <Button
                variant="outline"
                size="sm"
                onClick={detectPendingArticles}
                disabled={articlesLoading}
                className="ml-auto"
              >
                <FileText className="h-4 w-4 mr-1" />
                检测待处理
              </Button>
            </div>

            {/* 待处理信息提示 */}
            {pendingInfo && (
              <div className="flex items-center gap-3 p-3 bg-yellow-50 rounded-lg text-sm">
                <AlertCircle className="h-5 w-5 text-yellow-600" />
                <span>
                  共 <strong>{pendingInfo.pending}</strong> 篇待处理文章，
                  已处理 <strong>{pendingInfo.processed}</strong> 篇
                </span>
                <Button
                  variant="link"
                  size="sm"
                  onClick={() => {
                    setPendingInfo(null)
                    setArticleStatusFilter('all')
                    loadArticles(undefined, 'all')
                  }}
                >
                  清除提示
                </Button>
              </div>
            )}

            {/* 文章列表 */}
            <div className="border rounded-lg overflow-hidden">
              <div className="max-h-[400px] overflow-y-auto">
                {articlesLoading ? (
                  <div className="p-8 text-center text-gray-500">
                    <Loader2 className="h-6 w-6 animate-spin mx-auto mb-2" />
                    加载中...
                  </div>
                ) : articles.length === 0 ? (
                  <div className="p-8 text-center text-gray-500">暂无文章</div>
                ) : (
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 sticky top-0">
                      <tr>
                        <th className="text-left p-3 font-medium text-gray-600 w-8">
                          <input
                            type="checkbox"
                            checked={selectedArticles.size === articles.length && articles.length > 0}
                            onChange={selectAllArticles}
                            className="h-4 w-4"
                          />
                        </th>
                        <th className="text-left p-3 font-medium text-gray-600">标题</th>
                        <th className="text-left p-3 font-medium text-gray-600 w-20">字数</th>
                        <th className="text-left p-3 font-medium text-gray-600 w-24">分类</th>
                        <th className="text-left p-3 font-medium text-gray-600 w-20">状态</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {articles.map((article) => (
                        <tr
                          key={article.id}
                          className={`cursor-pointer transition-colors ${
                            selectedArticles.has(article.id)
                              ? 'bg-blue-50 hover:bg-blue-100'
                              : 'hover:bg-gray-50'
                          }`}
                        >
                          <td className="p-3">
                            <input
                              type="checkbox"
                              checked={selectedArticles.has(article.id)}
                              onChange={() => toggleArticleSelection(article.id)}
                              className="h-4 w-4"
                            />
                          </td>
                          <td className="p-3" onClick={() => selectArticle(article)}>
                            <div className="font-medium">{article.title}</div>
                            {article.summary && (
                              <div className="text-xs text-gray-500 mt-1 line-clamp-1">
                                {article.summary}
                              </div>
                            )}
                          </td>
                          <td className="p-3 text-gray-500" onClick={() => selectArticle(article)}>{article.word_count || '-'}</td>
                          <td className="p-3 text-gray-500" onClick={() => selectArticle(article)}>{article.category_name || '-'}</td>
                          <td className="p-3" onClick={() => selectArticle(article)}>{getKgStatusBadge(article.kg_status)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>

            {/* 选中文章信息 + 操作按钮 */}
            {selectedArticle && (
              <div className="flex items-center justify-between p-4 bg-blue-50 rounded-lg">
                <div className="flex-1">
                  <span className="text-sm text-gray-600">已选择：</span>
                  <span className="font-semibold">{selectedArticle.title}</span>
                  <span className="text-sm text-gray-500 ml-2">
                    ({selectedArticle.word_count || 0} 字)
                  </span>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setSelectedArticle(null)}
                  >
                    清除选择
                  </Button>
                  <Button onClick={processArticle} disabled={loading}>
                    {loading ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        处理中...
                      </>
                    ) : (
                      '开始处理'
                    )}
                  </Button>
                </div>
              </div>
            )}

            {/* 批量选择提示 */}
            {selectedArticles.size > 0 && (
              <div className="flex items-center justify-between p-4 bg-green-50 rounded-lg">
                <div className="flex-1">
                  <span className="text-sm text-gray-600">已选择 </span>
                  <span className="font-semibold">{selectedArticles.size}</span>
                  <span className="text-sm text-gray-600"> 篇文章</span>
                  <span className="text-sm text-gray-500 ml-2">
                    （待处理: {articles.filter(a => selectedArticles.has(a.id) && a.kg_status !== 'success').length}）
                  </span>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setSelectedArticles(new Set())}
                  >
                    清除选择
                  </Button>
                  <Button
                    onClick={(e) => {
                      e.preventDefault()
                      batchProcessArticles()
                    }}
                    disabled={batchProcessing}
                    variant="default"
                  >
                    {batchProcessing ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        处理中...
                      </>
                    ) : (
                      <>
                        <FileText className="mr-2 h-4 w-4" />
                        批量处理
                      </>
                    )}
                  </Button>
                  <Button
                    onClick={(e) => {
                      e.preventDefault()
                      if (confirm('确定要重新处理所有选中的文章吗？这将覆盖现有的知识提取结果。')) {
                        batchProcessArticles(true)
                      }
                    }}
                    disabled={batchProcessing}
                    variant="outline"
                  >
                    <RefreshCw className="mr-2 h-4 w-4" />
                    重新处理
                  </Button>
                </div>
              </div>
            )}

            {/* 未选择提示 */}
            {!selectedArticle && selectedArticles.size === 0 && (
              <div className="text-center text-gray-500 text-sm py-2">
                请点击复选框选择多篇文章进行批量处理，或点击文章标题选择单篇文章处理
              </div>
            )}
          </div>

          {/* 处理结果 */}
          {processingResult && (
            <div className="mt-4 p-4 bg-gray-50 rounded-lg">
              <h4 className="font-semibold mb-2">处理结果</h4>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-500">状态：</span>
                  <Badge variant={processingResult.status === 'completed' ? 'default' : 'destructive'}>
                    {processingResult.status === 'completed' ? '完成' : '失败'}
                  </Badge>
                </div>
                <div>
                  <span className="text-gray-500">知识点数量：</span>
                  <span className="font-semibold">{processingResult.knowledge_points_count}</span>
                </div>
                <div>
                  <span className="text-gray-500">关联数量：</span>
                  <span className="font-semibold">{processingResult.associations_count}</span>
                </div>
                <div>
                  <span className="text-gray-500">进度：</span>
                  <Progress value={processingResult.progress} className="h-2 w-24 inline-block" />
                </div>
              </div>
              {processingResult.summary && (
                <div className="mt-3">
                  <span className="text-gray-500 text-sm">总结：</span>
                  <p className="text-sm mt-1">{processingResult.summary}</p>
                </div>
              )}
            </div>
          )}

          {/* 批量处理进度 */}
          {batchProgress && (
            <div className="mt-4 p-4 bg-green-50 rounded-lg">
              <div className="flex items-center justify-between mb-3">
                <h4 className="font-semibold">批量处理进度</h4>
                {batchProcessing && (
                  <div className="flex items-center text-sm text-green-600">
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    处理中...
                  </div>
                )}
              </div>

              {/* 进度条 */}
              <div className="mb-3">
                <div className="flex justify-between text-sm mb-1">
                  <span>{batchProgress.percentage}%</span>
                  <span>{batchProgress.processed + batchProgress.failed} / {batchProgress.total}</span>
                </div>
                <Progress value={batchProgress.percentage} className="h-2" />
              </div>

              {/* 统计信息 */}
              <div className="grid grid-cols-3 gap-4 text-sm mb-3">
                <div>
                  <span className="text-gray-500">成功：</span>
                  <span className="font-semibold text-green-600">{batchProgress.processed}</span>
                </div>
                <div>
                  <span className="text-gray-500">失败：</span>
                  <span className="font-semibold text-red-600">{batchProgress.failed}</span>
                </div>
                <div>
                  <span className="text-gray-500">总数：</span>
                  <span className="font-semibold">{batchProgress.total}</span>
                </div>
              </div>

              {/* 当前处理的文章 */}
              {batchProgress.currentArticle && (
                <div className="text-sm text-gray-600 mb-2">
                  <span className="text-gray-500">当前处理：</span>
                  <span className="font-medium">
                    [{batchProgress.currentArticle.index}/{batchProgress.total}] {batchProgress.currentArticle.title}
                  </span>
                </div>
              )}

              {/* 错误信息 */}
              {batchProgress.errors.length > 0 && (
                <div className="mt-2 p-2 bg-red-50 rounded text-sm">
                  <div className="flex items-center text-red-600 mb-1">
                    <AlertCircle className="w-4 h-4 mr-1" />
                    <span className="font-medium">错误 ({batchProgress.errors.length})</span>
                  </div>
                  <div className="max-h-20 overflow-y-auto">
                    {batchProgress.errors.slice(0, 3).map((error, idx) => (
                      <div key={idx} className="text-red-500 text-xs">
                        文章 {error.article_id}: {error.error}
                      </div>
                    ))}
                    {batchProgress.errors.length > 3 && (
                      <div className="text-gray-500 text-xs">
                        还有 {batchProgress.errors.length - 3} 个错误...
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* 提示词模板 */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            提示词模板
            <Badge variant="secondary">{templates.length}</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="knowledge_mining">
            <TabsList>
              <TabsTrigger value="knowledge_mining">知识挖掘</TabsTrigger>
              <TabsTrigger value="prediction">趋势预测</TabsTrigger>
            </TabsList>

            <TabsContent value="knowledge_mining" className="mt-4">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {templates
                  .filter(t => t.category === 'knowledge_mining')
                  .map(template => (
                    <Card
                      key={template.id}
                      className={`cursor-pointer transition-colors ${
                        selectedTemplate?.id === template.id
                          ? 'border-primary bg-primary/5'
                          : 'hover:bg-gray-50'
                      }`}
                      onClick={() => setSelectedTemplate(template)}
                    >
                      <CardContent className="p-4">
                        <div className="flex justify-between items-start mb-2">
                          <h4 className="font-semibold text-sm">{template.title}</h4>
                          <Badge variant="outline" className="text-xs">
                            {template.variables.length} 变量
                          </Badge>
                        </div>
                        <p className="text-xs text-gray-500 mb-2">{template.description}</p>
                        <div className="flex flex-wrap gap-1">
                          {template.variables.slice(0, 3).map(v => (
                            <code key={v.name} className="text-xs bg-gray-100 px-1 rounded">
                              {`{{${v.name}}}`}
                            </code>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  ))}
              </div>
            </TabsContent>

            <TabsContent value="prediction" className="mt-4">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {templates
                  .filter(t => t.category === 'prediction')
                  .map(template => (
                    <Card
                      key={template.id}
                      className={`cursor-pointer transition-colors ${
                        selectedTemplate?.id === template.id
                          ? 'border-primary bg-primary/5'
                          : 'hover:bg-gray-50'
                      }`}
                      onClick={() => setSelectedTemplate(template)}
                    >
                      <CardContent className="p-4">
                        <div className="flex justify-between items-start mb-2">
                          <h4 className="font-semibold text-sm">{template.title}</h4>
                          <Badge variant="outline" className="text-xs">
                            {template.variables.length} 变量
                          </Badge>
                        </div>
                        <p className="text-xs text-gray-500 mb-2">{template.description}</p>
                        <div className="flex flex-wrap gap-1">
                          {template.variables.slice(0, 3).map(v => (
                            <code key={v.name} className="text-xs bg-gray-100 px-1 rounded">
                              {`{{${v.name}}}`}
                            </code>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  ))}
              </div>
            </TabsContent>
          </Tabs>

          {/* 选中的模板详情 */}
          {selectedTemplate && (
            <div className="mt-4 p-4 bg-gray-50 rounded-lg">
              <div className="flex justify-between items-start mb-3">
                <div>
                  <h4 className="font-semibold">{selectedTemplate.title}</h4>
                  <p className="text-sm text-gray-500">{selectedTemplate.description}</p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => copyToClipboard(selectedTemplate.content)}
                >
                  <Copy className="h-4 w-4 mr-1" />
                  复制
                </Button>
              </div>
              <div className="mb-3">
                <h5 className="text-sm font-medium mb-2">变量说明：</h5>
                <div className="flex flex-wrap gap-2">
                  {selectedTemplate.variables.map(v => (
                    <div key={v.name} className="text-xs bg-white p-2 rounded border">
                      <code className="font-mono">{`{{${v.name}}}`}</code>
                      <span className="text-gray-500 ml-2">{v.description}</span>
                      {v.required === 'true' && (
                        <Badge variant="destructive" className="ml-2 text-xs">必填</Badge>
                      )}
                    </div>
                  ))}
                </div>
              </div>
              <pre className="text-xs whitespace-pre-wrap bg-white p-3 rounded border font-mono max-h-64 overflow-y-auto">
                {selectedTemplate.content}
              </pre>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 知识点列表 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BookOpen className="h-5 w-5" />
              知识点库
              <Badge variant="secondary">{knowledgePoints.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4 max-h-[500px] overflow-y-auto">
              {knowledgePoints.length === 0 ? (
                <p className="text-gray-500 text-center py-8">暂无知识点</p>
              ) : (
                knowledgePoints.map((point) => (
                  <div key={point.id} className="border p-4 rounded-lg hover:bg-gray-50">
                    <div className="flex justify-between items-start mb-2">
                      <h3 className="font-semibold">{point.title}</h3>
                      <Badge className={getCategoryColor(point.category)}>
                        {getCategoryName(point.category)}
                      </Badge>
                    </div>
                    <p className="text-sm text-gray-600 mb-2">
                      {point.content.substring(0, 150)}...
                    </p>
                    <div className="flex items-center gap-2 text-xs text-gray-400">
                      <span>置信度: {(point.confidence * 100).toFixed(0)}%</span>
                      {point.keywords && point.keywords.length > 0 && (
                        <>
                          <span>•</span>
                          <span>关键词: {point.keywords.slice(0, 3).join(', ')}</span>
                        </>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>

        {/* 关联列表 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Link className="h-5 w-5" />
              知识关联
              <Badge variant="secondary">{associations.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4 max-h-[500px] overflow-y-auto">
              {associations.length === 0 ? (
                <p className="text-gray-500 text-center py-8">暂无关联</p>
              ) : (
                associations.map((assoc) => (
                  <div key={assoc.id} className="border p-4 rounded-lg hover:bg-gray-50">
                    <div className="flex justify-between items-center mb-2">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-sm">{assoc.source_title}</span>
                        <span className="text-gray-400">→</span>
                        <span className="font-semibold text-sm">{assoc.target_title}</span>
                      </div>
                      <Badge variant="outline">{assoc.relation_type}</Badge>
                    </div>
                    <div className="flex items-center gap-2">
                      <Progress value={assoc.strength * 100} className="h-2 flex-1" />
                      <span className="text-xs text-gray-500">
                        {(assoc.strength * 100).toFixed(0)}%
                      </span>
                    </div>
                    {assoc.evidence && (
                      <p className="text-xs text-gray-400 mt-2">{assoc.evidence}</p>
                    )}
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 刷新按钮 */}
      <div className="mt-6 flex justify-center">
        <Button variant="outline" onClick={() => {
          loadStats()
          loadKnowledgePoints()
          loadAssociations()
          loadArticles()
        }}>
          <RefreshCw className="mr-2 h-4 w-4" />
          刷新数据
        </Button>
      </div>
    </div>
  )
}
