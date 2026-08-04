'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'

interface KnowledgePointDetailProps {
  point: {
    id: string
    title: string
    content: string
    category: string
    confidence: number
    keywords: string[]
    associations?: Array<{
      target: string
      type: string
      strength: number
    }>
  }
  onClose: () => void
}

export function KnowledgePointDetail({ point, onClose }: KnowledgePointDetailProps) {
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

  return (
    <Card className="w-full max-w-2xl">
      <CardHeader>
        <div className="flex justify-between items-start">
          <CardTitle className="text-lg">{point.title}</CardTitle>
          <Button variant="ghost" size="sm" onClick={onClose}>
            ×
          </Button>
        </div>
        <div className="flex gap-2">
          <Badge className={getCategoryColor(point.category)}>
            {getCategoryName(point.category)}
          </Badge>
          <Badge variant="outline">
            置信度: {(point.confidence * 100).toFixed(0)}%
          </Badge>
        </div>
      </CardHeader>

      <CardContent>
        <div className="space-y-4">
          <div>
            <h4 className="font-semibold mb-2">内容</h4>
            <p className="text-gray-700 text-sm leading-relaxed">{point.content}</p>
          </div>

          <Separator />

          <div>
            <h4 className="font-semibold mb-2">关键词</h4>
            <div className="flex flex-wrap gap-2">
              {point.keywords && point.keywords.length > 0 ? (
                point.keywords.map((keyword, i) => (
                  <Badge key={i} variant="secondary">{keyword}</Badge>
                ))
              ) : (
                <span className="text-gray-500 text-sm">暂无关键词</span>
              )}
            </div>
          </div>

          {point.associations && point.associations.length > 0 && (
            <>
              <Separator />
              <div>
                <h4 className="font-semibold mb-2">关联知识点</h4>
                <div className="space-y-2">
                  {point.associations.map((assoc, i) => (
                    <div key={i} className="flex justify-between items-center border p-2 rounded text-sm">
                      <span>{assoc.target}</span>
                      <div className="flex gap-2 items-center">
                        <Badge variant="outline">{assoc.type}</Badge>
                        <span className="text-gray-500">
                          {(assoc.strength * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
