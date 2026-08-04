'use client'

import { useEffect, useRef, useState } from 'react'

interface Node {
  id: string
  title: string
  category: string
  x?: number
  y?: number
  vx?: number
  vy?: number
}

interface Edge {
  source: string
  target: string
  type: string
  strength: number
}

interface AssociationGraphProps {
  nodes: Node[]
  edges: Edge[]
  onNodeClick?: (nodeId: string) => void
  width?: number
  height?: number
}

export function AssociationGraph({
  nodes,
  edges,
  onNodeClick,
  width = 800,
  height = 500
}: AssociationGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const [hoveredNode, setHoveredNode] = useState<string | null>(null)

  const getCategoryColor = (category: string) => {
    const colors: Record<string, string> = {
      concept: '#3b82f6',
      argument: '#22c55e',
      fact: '#eab308',
      method: '#a855f7'
    }
    return colors[category] || '#6b7280'
  }

  useEffect(() => {
    if (!svgRef.current || nodes.length === 0) return

    const svg = svgRef.current
    const g = svg.querySelector('g')

    if (!g) return

    // 简单的力导向布局模拟
    const nodeMap = new Map<string, Node>()
    nodes.forEach((node, i) => {
      const angle = (2 * Math.PI * i) / nodes.length
      const radius = Math.min(width, height) / 4
      nodeMap.set(node.id, {
        ...node,
        x: width / 2 + radius * Math.cos(angle),
        y: height / 2 + radius * Math.sin(angle)
      })
    })

    // 简单迭代优化布局
    for (let iter = 0; iter < 50; iter++) {
      nodes.forEach(nodeA => {
        nodes.forEach(nodeB => {
          if (nodeA.id === nodeB.id) return
          const a = nodeMap.get(nodeA.id)!
          const b = nodeMap.get(nodeB.id)!
          const dx = a.x! - b.x!
          const dy = a.y! - b.y!
          const dist = Math.sqrt(dx * dx + dy * dy) || 1
          const force = 1000 / (dist * dist)
          a.vx = (a.vx || 0) + (dx / dist) * force
          a.vy = (a.vy || 0) + (dy / dist) * force
        })
      })

      // 边的引力
      edges.forEach(edge => {
        const source = nodeMap.get(edge.source)
        const target = nodeMap.get(edge.target)
        if (source && target) {
          const dx = target.x! - source.x!
          const dy = target.y! - source.y!
          const dist = Math.sqrt(dx * dx + dy * dy) || 1
          const force = (dist - 100) * 0.01
          source.vx = (source.vx || 0) + (dx / dist) * force
          source.vy = (source.vy || 0) + (dy / dist) * force
          target.vx = (target.vx || 0) - (dx / dist) * force
          target.vy = (target.vy || 0) - (dy / dist) * force
        }
      })

      // 更新位置
      nodes.forEach(node => {
        const n = nodeMap.get(node.id)!
        n.x = Math.max(50, Math.min(width - 50, n.x! + (n.vx || 0) * 0.1))
        n.y = Math.max(50, Math.min(height - 50, n.y! + (n.vy || 0) * 0.1))
        n.vx = (n.vx || 0) * 0.9
        n.vy = (n.vy || 0) * 0.9
      })
    }

    // 清空并重绘
    g.innerHTML = ''

    // 绘制边
    edges.forEach(edge => {
      const source = nodeMap.get(edge.source)
      const target = nodeMap.get(edge.target)
      if (source && target) {
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line')
        line.setAttribute('x1', String(source.x))
        line.setAttribute('y1', String(source.y))
        line.setAttribute('x2', String(target.x))
        line.setAttribute('y2', String(target.y))
        line.setAttribute('stroke', '#999')
        line.setAttribute('stroke-width', String(Math.max(1, edge.strength * 3)))
        line.setAttribute('stroke-opacity', '0.6')
        g.appendChild(line)
      }
    })

    // 绘制节点
    nodes.forEach(node => {
      const n = nodeMap.get(node.id)!
      const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle')
      circle.setAttribute('cx', String(n.x))
      circle.setAttribute('cy', String(n.y))
      circle.setAttribute('r', '15')
      circle.setAttribute('fill', getCategoryColor(n.category))
      circle.setAttribute('stroke', '#fff')
      circle.setAttribute('stroke-width', '2')
      circle.setAttribute('cursor', 'pointer')
      circle.setAttribute('data-id', n.id)

      circle.addEventListener('click', () => onNodeClick?.(n.id))
      circle.addEventListener('mouseenter', () => setHoveredNode(n.id))
      circle.addEventListener('mouseleave', () => setHoveredNode(null))

      g.appendChild(circle)

      // 添加标签
      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text')
      text.setAttribute('x', String(n.x))
      text.setAttribute('y', String(n.y! + 25))
      text.setAttribute('text-anchor', 'middle')
      text.setAttribute('font-size', '11')
      text.setAttribute('fill', '#333')
      text.textContent = n.title.length > 10 ? n.title.substring(0, 10) + '...' : n.title
      g.appendChild(text)
    })

  }, [nodes, edges, width, height, onNodeClick])

  if (nodes.length === 0) {
    return (
      <div className="flex items-center justify-center border rounded-lg bg-gray-50" style={{ width, height }}>
        <span className="text-gray-500">暂无数据</span>
      </div>
    )
  }

  return (
    <svg
      ref={svgRef}
      width="100%"
      height={height}
      className="border rounded-lg bg-white"
      viewBox={`0 0 ${width} ${height}`}
    >
      <g />
    </svg>
  )
}
