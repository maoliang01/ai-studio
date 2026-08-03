# 知识迭代与自生长系统 - 完整实现计划

## 📋 项目概述

基于现有 AI Studio 项目，实现一个完整的知识自增强循环系统，借鉴卡帕西思想，实现知识库的自动学习、关联、预测和优化。

**目标**：建立一个能够自主学习、迭代进化、持续优化的知识系统。

---

## 🎯 核心原则

1. **改动最小化**：不修改无关代码，仅新增必要模块
2. **前后端同步**：前后端功能一一对应，确保 API 可用性
3. **设置回滚点**：每个阶段完成后验证，发现问题及时回滚
4. **里程碑验收**：每个阶段自测通过后才进入下一阶段

---

## 🛠️ 技术栈

### 后端
| 技术 | 用途 | 备注 |
|------|------|------|
| FastAPI | Web 框架 | 已有 |
| Neo4j | 图数据库 | 已有 |
| OpenAI/LLM | 实体/关系抽取 | 使用现有配置 |
| Pydantic | 数据验证 | 已有 |
| NetworkX | 图算法（备选） | 新增 |

### 前端
| 技术 | 用途 | 备注 |
|------|------|------|
| Next.js 14 | React 框架 | 已有 |
| D3.js | 知识图谱可视化 | 已有 |
| TailwindCSS | UI 样式 | 已有 |
| Zustand | 状态管理 | 已有 |

---

## 📊 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    知识自增强循环系统                         │
├─────────────────────────────────────────────────────────────┤
│  输入层 → 理解层 → 关联层 → 预测层 → 输出层 → 反馈层      │
│     ↓         ↓         ↓         ↓         ↓         ↓    │
│  知识入库   实体抽取   关系发现   趋势预测   知识输出   自动学习│
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 实现阶段

### 阶段 1：基础架构搭建

**目标**：搭建知识自增强循环的基础框架

#### 1.1 后端模块创建

**文件**：`backend/app/services/kg/self_enhancement.py`

```python
# 知识自增强循环核心服务
class KnowledgeSelfEnhancement:
    """知识自增强循环管理器"""
    
    def __init__(self, kg_service, llm_client):
        # 初始化知识图谱服务和 LLM 客户端
        pass
    
    def process_new_article(self, article_id: str) -> SelfEnhancementResult:
        """
        处理新文章，启动自增强循环
        
        流程：
        1. 文章预处理（清洗、分段）
        2. 实体抽取（LLM 驱动）
        3. 关系发现（LLM + 规则）
        4. 知识点提取（LLM 总结）
        5. 关联发现（图算法）
        6. 知识输出（新知识点入库）
        """
        pass
    
    def extract_knowledge_points(self, content: str) -> List[KnowledgePoint]:
        """
        从内容中提取知识点
        
        使用 LLM 进行：
        - 关键概念识别
        - 核心观点提取
        - 知识点结构化
        """
        pass
    
    def discover_associations(self, knowledge_points: List[KnowledgePoint]) -> List[Association]:
        """
        发现知识点之间的关联
        
        使用：
        - 图数据库查询
        - 语义相似度计算
        - 共现分析
        """
        pass
    
    def generate_summary(self, article: Article, knowledge_points: List[KnowledgePoint]) -> str:
        """
        生成文章总结
        
        包含：
        - 核心观点摘要
        - 关键知识点列表
        - 与其他知识的关联
        """
        pass
```

**验收标准**：
- [ ] 类定义完整，方法签名清晰
- [ ] 包含必要的类型提示和文档字符串
- [ ] 代码通过 lint 检查

#### 1.2 API 端点添加

**文件**：`backend/app/api/kg.py` (追加)

```python
# 新增自增强循环相关 API

@router.post("/self-enhancement/process-article")
async def process_article_for_enhancement(article_id: str):
    """
    处理单篇文章，启动自增强循环
    
    请求体：
    - article_id: 文章 ID
    
    返回：
    - enhancement_id: 增强任务 ID
    - status: 处理状态
    - knowledge_points_count: 提取的知识点数量
    """
    pass

@router.get("/self-enhancement/status/{enhancement_id}")
async def get_enhancement_status(enhancement_id: str):
    """
    获取增强任务状态
    
    返回：
    - status: 处理状态 (pending/processing/completed/failed)
    - progress: 处理进度 (0-100)
    - result: 处理结果
    """
    pass

@router.get("/self-enhancement/knowledge-points")
async def list_knowledge_points(
    article_id: Optional[str] = None,
    limit: int = 50
):
    """
    获取知识点列表
    
    参数：
    - article_id: 可选，按文章筛选
    - limit: 返回数量限制
    
    返回：
    - knowledge_points: 知识点列表
    - total: 总数
    """
    pass

@router.get("/self-enhancement/associations")
async def list_associations(
    knowledge_point_id: Optional[str] = None,
    min_strength: float = 0.5
):
    """
    获取知识点关联列表
    
    参数：
    - knowledge_point_id: 可选，按知识点筛选
    - min_strength: 最小关联强度
    
    返回：
    - associations: 关联列表
    - total: 总数
    """
    pass
```

**验收标准**：
- [ ] API 端点定义完整
- [ ] 请求/响应模型定义正确
- [ ] 包含错误处理

#### 1.3 数据模型定义

**文件**：`backend/app/schemas/kg.py` (追加)

```python
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class KnowledgePoint(BaseModel):
    """知识点"""
    id: str
    article_id: str
    title: str
    content: str
    category: str  # concept/argument/fact/method
    confidence: float = Field(ge=0, le=1)
    created_at: datetime
    updated_at: datetime

class Association(BaseModel):
    """知识点关联"""
    id: str
    source_id: str
    target_id: str
    relation_type: str  # related_to/depends_on/causes/...
    strength: float = Field(ge=0, le=1)
    evidence: List[str]
    created_at: datetime

class SelfEnhancementResult(BaseModel):
    """自增强循环结果"""
    enhancement_id: str
    article_id: str
    status: str  # pending/processing/completed/failed
    progress: int = Field(ge=0, le=100)
    knowledge_points_count: int = 0
    associations_count: int = 0
    summary: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

class EnhancementStats(BaseModel):
    """增强统计"""
    total_articles_processed: int
    total_knowledge_points: int
    total_associations: int
    average_points_per_article: float
    average_associations_per_point: float
    last_processed_at: Optional[datetime]
```

**验收标准**：
- [ ] Pydantic 模型定义完整
- [ ] 字段验证规则正确
- [ ] 包含必要的默认值

#### 1.4 前端页面创建

**文件**：`frontend/src/app/kg/self-enhancement/page.tsx`

```tsx
'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'

// 知识自增强循环页面
export default function SelfEnhancementPage() {
  const [stats, setStats] = useState<EnhancementStats | null>(null)
  const [processingArticles, setProcessingArticles] = useState([])
  const [knowledgePoints, setKnowledgePoints] = useState([])
  const [associations, setAssociations] = useState([])

  // 加载统计数据
  useEffect(() => {
    loadStats()
    loadKnowledgePoints()
    loadAssociations()
  }, [])

  const loadStats = async () => {
    const response = await fetch('/api/kg/self-enhancement/stats')
    const data = await response.json()
    setStats(data)
  }

  const processArticle = async (articleId: string) => {
    const response = await fetch('/api/kg/self-enhancement/process-article', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ article_id: articleId })
    })
    const result = await response.json()
    // 刷新列表
    loadStats()
  }

  return (
    <div className="container mx-auto p-6">
      <h1 className="text-3xl font-bold mb-6">知识自增强循环</h1>
      
      {/* 统计卡片 */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <Card>
          <CardHeader>
            <CardTitle>已处理文章</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-4xl font-bold">
              {stats?.total_articles_processed || 0}
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader>
            <CardTitle>知识点总数</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-4xl font-bold">
              {stats?.total_knowledge_points || 0}
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader>
            <CardTitle>关联总数</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-4xl font-bold">
              {stats?.total_associations || 0}
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader>
            <CardTitle>平均知识点/文章</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-4xl font-bold">
              {stats?.average_points_per_article?.toFixed(2) || '0'}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 知识点列表 */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>知识点库</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {knowledgePoints.map((point) => (
              <div key={point.id} className="border p-4 rounded-lg">
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="font-semibold">{point.title}</h3>
                    <p className="text-sm text-gray-500">{point.category}</p>
                    <p className="mt-2">{point.content.substring(0, 200)}...</p>
                  </div>
                  <Badge variant={point.confidence > 0.8 ? 'default' : 'secondary'}>
                    置信度: {(point.confidence * 100).toFixed(0)}%
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* 关联列表 */}
      <Card>
        <CardHeader>
          <CardTitle>知识关联</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {associations.map((assoc) => (
              <div key={assoc.id} className="border p-4 rounded-lg">
                <div className="flex justify-between items-center">
                  <div>
                    <span className="font-semibold">{assoc.source_title}</span>
                    <span className="mx-2">→</span>
                    <span className="font-semibold">{assoc.target_title}</span>
                  </div>
                  <Badge>{assoc.relation_type}</Badge>
                </div>
                <div className="mt-2">
                  <Progress value={assoc.strength * 100} className="h-2" />
                  <span className="text-sm text-gray-500">
                    强度: {(assoc.strength * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
```

**验收标准**：
- [ ] 页面组件定义完整
- [ ] 包含必要的状态管理
- [ ] 样式符合项目规范

#### 1.5 前端 API 路由

**文件**：`frontend/src/app/api/kg/self-enhancement/route.ts`

```typescript
import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8080'

// 获取增强统计
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const path = searchParams.get('path') || 'stats'
  
  try {
    const response = await fetch(`${BACKEND_URL}/api/kg/self-enhancement/${path}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })
    
    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to fetch enhancement data' },
      { status: 500 }
    )
  }
}

// 处理文章
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    
    const response = await fetch(`${BACKEND_URL}/api/kg/self-enhancement/process-article`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    })
    
    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to process article' },
      { status: 500 }
    )
  }
}
```

**验收标准**：
- [ ] API 路由定义完整
- [ ] 包含错误处理
- [ ] 正确代理到后端

#### 1.6 阶段 1 验收检查清单

```markdown
## 阶段 1 验收检查清单

### 后端验收
- [ ] self_enhancement.py 文件创建完成
- [ ] KnowledgeSelfEnhancement 类定义完整
- [ ] 核心方法签名清晰，包含类型提示
- [ ] kg.py API 端点添加完成
- [ ] 请求/响应模型定义正确
- [ ] 代码通过 lint 检查

### 前端验收
- [ ] self-enhancement 页面创建完成
- [ ] 页面组件渲染正常
- [ ] API 路由创建完成
- [ ] 可以正常调用后端 API

### 功能验收
- [ ] 可以访问自增强循环页面
- [ ] 页面显示统计数据（初始为 0）
- [ ] 可以触发文章处理（即使返回 mock 数据）

### 回滚点
- 备份当前代码状态
- 验证现有功能未受影响
- 如果有问题，回滚到上一个稳定版本
```

**预计时间**：2-3 小时

---

### 阶段 2：LLM 驱动的知识点提取

**目标**：实现基于 LLM 的智能知识点提取

#### 2.1 LLM 提示词模板

**文件**：`backend/app/services/kg/prompts.py`

```python
KNOWLEDGE_POINT_EXTRACTION_PROMPT = """
你是一个知识提取专家。请从以下文本中提取核心知识点。

文本内容：
{text}

请提取以下类型的知识点：
1. 概念 (concept): 核心概念、定义、术语
2. 观点 (argument): 作者的观点、立场、论证
3. 事实 (fact): 具体的数据、事件、案例
4. 方法 (method): 解决方案、技术方法、流程

输出格式（JSON）：
{
  "knowledge_points": [
    {
      "title": "知识点标题",
      "content": "知识点内容（100-200字）",
      "category": "concept|argument|fact|method",
      "confidence": 0.9,
      "keywords": ["关键词1", "关键词2"]
    }
  ]
}

请确保：
1. 每个知识点独立完整
2. 内容准确，不要臆造
3. 置信度基于文本明确程度
4. 提取 5-10 个核心知识点
"""

RELATIONSHIP_DISCOVERY_PROMPT = """
你是一个关系发现专家。请分析以下知识点之间的关系。

知识点列表：
{knowledge_points}

请发现以下类型的关系：
1. related_to: 相关关系
2. depends_on: 依赖关系
3. causes: 因果关系
4. part_of: 组成关系
5. contradicts: 矛盾关系
6. supports: 支持关系

输出格式（JSON）：
{
  "relationships": [
    {
      "source": "知识点1标题",
      "target": "知识点2标题",
      "relation_type": "relation_type",
      "strength": 0.8,
      "evidence": "关系依据"
    }
  ]
}

请确保：
1. 关系有明确的文本依据
2. 强度基于证据充分程度
3. 只提取有把握的关系
"""

SUMMARY_GENERATION_PROMPT = """
你是一个总结专家。请根据以下文章和提取的知识点，生成一份结构化的总结。

文章内容：
{article_content}

提取的知识点：
{knowledge_points}

请生成包含以下内容的总结：
1. 核心观点（1-2句话）
2. 关键知识点列表
3. 知识点之间的关联
4. 与已有知识的连接
5. 潜在应用价值

输出格式：
{
  "summary": "总结内容",
  "key_points": ["知识点1", "知识点2"],
  "connections": [
    {"from": "知识点A", "to": "知识点B", "relation": "关系描述"}
  ],
  "applications": ["应用场景1", "应用场景2"]
}
"""
```

**验收标准**：
- [ ] 提示词模板定义完整
- [ ] 包含必要的占位符
- [ ] 输出格式清晰

#### 2.2 LLM 客户端封装

**文件**：`backend/app/services/kg/llm_client.py`

```python
import json
import logging
from typing import List, Dict, Any
from ..llm import LLMClient

logger = logging.getLogger(__name__)

class KnowledgeLLMClient:
    """知识提取专用 LLM 客户端"""
    
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
    
    async def extract_knowledge_points(self, text: str) -> List[Dict[str, Any]]:
        """提取知识点"""
        from .prompts import KNOWLEDGE_POINT_EXTRACTION_PROMPT
        
        prompt = KNOWLEDGE_POINT_EXTRACTION_PROMPT.format(text=text)
        
        try:
            response = await self.llm_client.generate(prompt)
            result = json.loads(response)
            return result.get('knowledge_points', [])
        except Exception as e:
            logger.error(f"Failed to extract knowledge points: {e}")
            return []
    
    async def discover_relationships(self, knowledge_points: List[Dict]) -> List[Dict]:
        """发现知识点关系"""
        from .prompts import RELATIONSHIP_DISCOVERY_PROMPT
        
        points_text = json.dumps(knowledge_points, ensure_ascii=False, indent=2)
        prompt = RELATIONSHIP_DISCOVERY_PROMPT.format(knowledge_points=points_text)
        
        try:
            response = await self.llm_client.generate(prompt)
            result = json.loads(response)
            return result.get('relationships', [])
        except Exception as e:
            logger.error(f"Failed to discover relationships: {e}")
            return []
    
    async def generate_summary(self, article_content: str, knowledge_points: List[Dict]) -> Dict:
        """生成总结"""
        from .prompts import SUMMARY_GENERATION_PROMPT
        
        points_text = json.dumps(knowledge_points, ensure_ascii=False, indent=2)
        prompt = SUMMARY_GENERATION_PROMPT.format(
            article_content=article_content,
            knowledge_points=points_text
        )
        
        try:
            response = await self.llm_client.generate(prompt)
            result = json.loads(response)
            return result
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            return {}
```

**验收标准**：
- [ ] LLM 客户端封装完整
- [ ] 包含错误处理和日志
- [ ] 返回格式标准化

#### 2.3 增强核心逻辑

**文件**：`backend/app/services/kg/self_enhancement.py` (更新)

```python
class KnowledgeSelfEnhancement:
    """知识自增强循环管理器"""
    
    def __init__(self, kg_service, llm_client, db_session):
        self.kg_service = kg_service
        self.llm_client = KnowledgeLLMClient(llm_client)
        self.db_session = db_session
        self.stats = EnhancementStats()
    
    async def process_new_article(self, article_id: str) -> SelfEnhancementResult:
        """
        处理新文章，启动自增强循环
        
        完整流程：
        1. 获取文章内容
        2. 文章预处理
        3. LLM 提取知识点
        4. LLM 发现关系
        5. 存储到图数据库
        6. 生成总结
        7. 返回结果
        """
        enhancement_id = f"enh_{article_id}_{int(time.time())}"
        
        try:
            # 1. 获取文章内容
            article = await self._get_article(article_id)
            if not article:
                raise ValueError(f"Article not found: {article_id}")
            
            # 2. 文章预处理
            processed_content = self._preprocess_article(article)
            
            # 3. LLM 提取知识点
            knowledge_points = await self.llm_client.extract_knowledge_points(
                processed_content
            )
            
            # 4. LLM 发现关系
            relationships = await self.llm_client.discover_relationships(
                knowledge_points
            )
            
            # 5. 存储到图数据库
            await self._store_knowledge_points(article_id, knowledge_points)
            await self._store_relationships(relationships)
            
            # 6. 生成总结
            summary = await self.llm_client.generate_summary(
                article.content, knowledge_points
            )
            
            # 7. 更新统计
            self._update_stats(len(knowledge_points), len(relationships))
            
            return SelfEnhancementResult(
                enhancement_id=enhancement_id,
                article_id=article_id,
                status='completed',
                progress=100,
                knowledge_points_count=len(knowledge_points),
                associations_count=len(relationships),
                summary=summary.get('summary', ''),
                created_at=datetime.now(),
                completed_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Failed to process article {article_id}: {e}")
            return SelfEnhancementResult(
                enhancement_id=enhancement_id,
                article_id=article_id,
                status='failed',
                progress=0,
                created_at=datetime.now()
            )
    
    def _preprocess_article(self, article) -> str:
        """文章预处理"""
        # 清洗 HTML、特殊字符等
        content = article.content
        content = re.sub(r'<[^>]+>', '', content)  # 移除 HTML 标签
        content = re.sub(r'\s+', ' ', content)  # 合并空白
        return content.strip()
    
    async def _store_knowledge_points(self, article_id: str, points: List[Dict]):
        """存储知识点到图数据库"""
        for point in points:
            await self.kg_service.create_entity(
                name=point['title'],
                entity_type='KnowledgePoint',
                properties={
                    'article_id': article_id,
                    'content': point['content'],
                    'category': point['category'],
                    'confidence': point['confidence'],
                    'keywords': point.get('keywords', [])
                }
            )
    
    async def _store_relationships(self, relationships: List[Dict]):
        """存储关系到图数据库"""
        for rel in relationships:
            await self.kg_service.create_relationship(
                source_name=rel['source'],
                target_name=rel['target'],
                relationship_type=rel['relation_type'],
                properties={
                    'strength': rel['strength'],
                    'evidence': rel['evidence']
                }
            )
    
    def _update_stats(self, points_count: int, relationships_count: int):
        """更新统计信息"""
        self.stats.total_knowledge_points += points_count
        self.stats.total_associations += relationships_count
        self.stats.last_processed_at = datetime.now()
```

**验收标准**：
- [ ] 核心处理流程完整
- [ ] 包含错误处理
- [ ] 统计信息更新正确

#### 2.4 阶段 2 验收检查清单

```markdown
## 阶段 2 验收检查清单

### 后端验收
- [ ] prompts.py 提示词模板定义完整
- [ ] llm_client.py 封装完成
- [ ] self_enhancement.py 核心逻辑实现
- [ ] 可以成功调用 LLM 进行知识点提取
- [ ] 可以成功存储到 Neo4j 图数据库

### 前端验收
- [ ] 页面可以显示提取的知识点
- [ ] 可以触发文章处理
- [ ] 处理状态实时更新

### 功能验收
- [ ] 创建测试文章（约 500 字）
- [ ] 触发自增强循环
- [ ] 验证知识点被正确提取（5-10 个）
- [ ] 验证关系被正确发现
- [ ] 验证总结被正确生成

### 测试用例
```python
# 测试文章
test_article = """
人工智能（AI）是计算机科学的一个分支，致力于创建能够模拟人类智能的系统。
近年来，深度学习技术取得了突破性进展，特别是在图像识别和自然语言处理领域。
GPT 系列模型展示了大语言模型的强大能力，能够理解和生成自然语言。
AI 技术在医疗、金融、教育等领域有广泛应用，但也引发了关于隐私和就业的讨论。
"""
```

### 回滚点
- 备份阶段 1 完成的代码
- 验证 LLM 调用正常
- 如果 LLM 调用失败，检查 API 配置
```

**预计时间**：3-4 小时

---

### 阶段 3：知识关联发现

**目标**：实现智能的知识关联发现算法

#### 3.1 关联发现算法

**文件**：`backend/app/services/kg/association.py`

```python
import numpy as np
from typing import List, Dict, Tuple
from collections import defaultdict

class AssociationDiscovery:
    """知识关联发现算法"""
    
    def __init__(self, kg_service):
        self.kg_service = kg_service
    
    async def discover_all_associations(self, article_id: str) -> List[Dict]:
        """
        发现文章中知识点的所有关联
        
        算法组合：
        1. 基于 LLM 的语义关联
        2. 基于关键词的共现关联
        3. 基于图结构的结构关联
        4. 基于时间的时序关联
        """
        associations = []
        
        # 1. 语义关联
        semantic_assocs = await self._discover_semantic_associations(article_id)
        associations.extend(semantic_assocs)
        
        # 2. 共现关联
        cooccurrence_assocs = await self._discover_cooccurrence_associations(article_id)
        associations.extend(cooccurrence_assocs)
        
        # 3. 结构关联
        structural_assocs = await self._discover_structural_associations(article_id)
        associations.extend(structural_assocs)
        
        # 去重和排序
        unique_assocs = self._deduplicate_associations(associations)
        ranked_assocs = self._rank_associations(unique_assocs)
        
        return ranked_assocs
    
    async def _discover_semantic_associations(self, article_id: str) -> List[Dict]:
        """基于语义相似度发现关联"""
        # 获取文章中的知识点
        knowledge_points = await self.kg_service.get_entities_by_article(article_id)
        
        associations = []
        for i, point_a in enumerate(knowledge_points):
            for point_b in knowledge_points[i+1:]:
                # 计算语义相似度
                similarity = self._calculate_semantic_similarity(
                    point_a.content, point_b.content
                )
                
                if similarity > 0.6:  # 阈值
                    associations.append({
                        'source': point_a.name,
                        'target': point_b.name,
                        'type': 'semantic',
                        'strength': similarity,
                        'evidence': f'语义相似度: {similarity:.2f}'
                    })
        
        return associations
    
    def _calculate_semantic_similarity(self, text_a: str, text_b: str) -> float:
        """计算语义相似度（简化版，实际应使用 embeddings）"""
        # 使用 TF-IDF + 余弦相似度
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform([text_a, text_b])
        similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
        
        return float(similarity)
    
    async def _discover_cooccurrence_associations(self, article_id: str) -> List[Dict]:
        """基于关键词共现发现关联"""
        knowledge_points = await self.kg_service.get_entities_by_article(article_id)
        
        # 提取所有关键词
        keyword_to_points = defaultdict(list)
        for point in knowledge_points:
            for keyword in point.properties.get('keywords', []):
                keyword_to_points[keyword].append(point.name)
        
        associations = []
        for keyword, points in keyword_to_points.items():
            if len(points) > 1:
                # 多个知识点共享同一关键词
                for i in range(len(points)):
                    for j in range(i+1, len(points)):
                        associations.append({
                            'source': points[i],
                            'target': points[j],
                            'type': 'cooccurrence',
                            'strength': 0.5,
                            'evidence': f'共享关键词: {keyword}'
                        })
        
        return associations
    
    async def _discover_structural_associations(self, article_id: str) -> List[Dict]:
        """基于图结构发现关联"""
        # 查询已存在的关联
        existing_associations = await self.kg_service.get_relationships_by_article(article_id)
        
        # 发现间接关联（A -> B -> C，推断 A -> C）
        indirect_assocs = self._find_indirect_associations(existing_associations)
        
        return indirect_assocs
    
    def _find_indirect_associations(self, direct_associations: List[Dict]) -> List[Dict]:
        """发现间接关联"""
        # 构建邻接表
        graph = defaultdict(set)
        for assoc in direct_associations:
            graph[assoc['source']].add(assoc['target'])
            graph[assoc['target']].add(assoc['source'])
        
        indirect = []
        for node_a in graph:
            for node_b in graph[node_a]:
                for node_c in graph[node_b]:
                    if node_c != node_a and node_c not in graph[node_a]:
                        indirect.append({
                            'source': node_a,
                            'target': node_c,
                            'type': 'indirect',
                            'strength': 0.3,
                            'evidence': f'通过 {node_b} 间接关联'
                        })
        
        return indirect
    
    def _deduplicate_associations(self, associations: List[Dict]) -> List[Dict]:
        """去重"""
        seen = set()
        unique = []
        
        for assoc in associations:
            key = (assoc['source'], assoc['target'], assoc['type'])
            if key not in seen:
                seen.add(key)
                unique.append(assoc)
        
        return unique
    
    def _rank_associations(self, associations: List[Dict]) -> List[Dict]:
        """按强度排序"""
        return sorted(associations, key=lambda x: x['strength'], reverse=True)
```

**验收标准**：
- [ ] 关联发现算法实现完整
- [ ] 包含多种关联类型
- [ ] 包含去重和排序逻辑

#### 3.2 阶段 3 验收检查清单

```markdown
## 阶段 3 验收检查清单

### 后端验收
- [ ] association.py 文件创建完成
- [ ] AssociationDiscovery 类定义完整
- [ ] 包含语义、共现、结构三种关联发现算法
- [ ] 关联去重和排序逻辑正确

### 功能验收
- [ ] 使用阶段 2 的测试文章
- [ ] 发现至少 5 个知识点关联
- [ ] 验证关联强度计算正确
- [ ] 验证关联证据完整

### 测试用例
```python
# 验证关联发现
test_article_id = "test_article_1"
associations = await association_discovery.discover_all_associations(test_article_id)
assert len(associations) >= 5
assert all('strength' in a for a in associations)
assert all('evidence' in a for a in associations)
```

### 回滚点
- 备份阶段 2 完成的代码
- 验证 LLM 调用正常
- 验证图数据库操作正常
```

**预计时间**：2-3 小时

---

### 阶段 4：知识总结生成

**目标**：实现智能的知识总结生成

#### 4.1 总结生成器

**文件**：`backend/app/services/kg/summarizer.py`

```python
from typing import Dict, List
from .llm_client import KnowledgeLLMClient

class KnowledgeSummarizer:
    """知识总结生成器"""
    
    def __init__(self, llm_client: KnowledgeLLMClient):
        self.llm_client = llm_client
    
    async def generate_article_summary(
        self, 
        article_content: str,
        knowledge_points: List[Dict],
        associations: List[Dict]
    ) -> Dict:
        """
        生成文章总结
        
        包含：
        1. 核心观点
        2. 关键知识点
        3. 知识关联
        4. 应用价值
        """
        from .prompts import SUMMARY_GENERATION_PROMPT
        
        # 准备输入
        points_text = self._format_knowledge_points(knowledge_points)
        associations_text = self._format_associations(associations)
        
        prompt = SUMMARY_GENERATION_PROMPT.format(
            article_content=article_content[:2000],  # 限制长度
            knowledge_points=points_text,
            associations=associations_text
        )
        
        try:
            response = await self.llm_client.generate(prompt)
            result = self._parse_summary_response(response)
            return result
        except Exception as e:
            return self._generate_fallback_summary(knowledge_points)
    
    def _format_knowledge_points(self, points: List[Dict]) -> str:
        """格式化知识点"""
        lines = []
        for i, point in enumerate(points, 1):
            lines.append(f"{i}. [{point.get('category', 'unknown')}] {point['title']}")
            lines.append(f"   {point.get('content', '')[:100]}")
        return "\n".join(lines)
    
    def _format_associations(self, associations: List[Dict]) -> str:
        """格式化关联"""
        lines = []
        for assoc in associations[:10]:  # 只取前 10 个
            lines.append(f"- {assoc['source']} → {assoc['target']} ({assoc['type']})")
        return "\n".join(lines)
    
    def _parse_summary_response(self, response: str) -> Dict:
        """解析总结响应"""
        import json
        try:
            return json.loads(response)
        except:
            return {
                'summary': response[:500],
                'key_points': [],
                'connections': [],
                'applications': []
            }
    
    def _generate_fallback_summary(self, knowledge_points: List[Dict]) -> Dict:
        """生成备用总结"""
        key_points = [p['title'] for p in knowledge_points[:5]]
        return {
            'summary': f"本文提取了 {len(knowledge_points)} 个知识点，包括：{', '.join(key_points)} 等。",
            'key_points': key_points,
            'connections': [],
            'applications': []
        }
    
    async def generate_knowledge_graph_summary(self, entity_name: str) -> Dict:
        """
        生成知识图谱总结
        
        基于实体在图谱中的关系和上下文
        """
        # 获取实体关系
        relationships = await self.kg_service.get_relationships(entity_name)
        
        # 生成总结
        summary_prompt = f"""
        请总结以下实体在知识图谱中的角色和重要性：
        
        实体: {entity_name}
        
        相关关系:
        {self._format_relationships(relationships)}
        
        请提供：
        1. 实体定义
        2. 在图谱中的角色
        3. 重要关系
        4. 潜在应用
        """
        
        response = await self.llm_client.generate(summary_prompt)
        return self._parse_summary_response(response)
    
    def _format_relationships(self, relationships: List[Dict]) -> str:
        """格式化关系"""
        lines = []
        for rel in relationships:
            lines.append(f"- {rel.get('type', 'related_to')}: {rel.get('target', 'unknown')}")
        return "\n".join(lines)
```

**验收标准**：
- [ ] 总结生成器实现完整
- [ ] 包含备用总结逻辑
- [ ] 格式化输出正确

#### 4.2 阶段 4 验收检查清单

```markdown
## 阶段 4 验收检查清单

### 后端验收
- [ ] summarizer.py 文件创建完成
- [ ] KnowledgeSummarizer 类定义完整
- [ ] 包含文章总结和图谱总结功能
- [ ] 包含备用总结逻辑

### 功能验收
- [ ] 使用阶段 2 的测试文章
- [ ] 生成完整的文章总结
- [ ] 验证总结包含核心观点
- [ ] 验证总结包含关键知识点
- [ ] 验证总结包含应用价值

### 测试用例
```python
# 验证总结生成
test_article_id = "test_article_1"
knowledge_points = await get_knowledge_points(test_article_id)
associations = await get_associations(test_article_id)

summary = await summarizer.generate_article_summary(
    article_content="...",
    knowledge_points=knowledge_points,
    associations=associations
)

assert 'summary' in summary
assert 'key_points' in summary
assert len(summary['key_points']) > 0
```

### 回滚点
- 备份阶段 3 完成的代码
- 验证 LLM 调用正常
- 验证总结质量
```

**预计时间**：2-3 小时

---

### 阶段 5：前端交互优化

**目标**：完善前端交互体验

#### 5.1 知识点详情组件

**文件**：`frontend/src/components/kg/KnowledgePointDetail.tsx`

```tsx
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
    associations: Array<{
      target: string
      type: string
      strength: number
    }>
  }
  onClose: () => void
}

export function KnowledgePointDetail({ point, onClose }: KnowledgePointDetailProps) {
  const getCategoryColor = (category: string) => {
    const colors = {
      concept: 'bg-blue-100 text-blue-800',
      argument: 'bg-green-100 text-green-800',
      fact: 'bg-yellow-100 text-yellow-800',
      method: 'bg-purple-100 text-purple-800'
    }
    return colors[category] || 'bg-gray-100 text-gray-800'
  }

  return (
    <Card className="w-full max-w-2xl">
      <CardHeader>
        <div className="flex justify-between items-start">
          <CardTitle>{point.title}</CardTitle>
          <Button variant="ghost" onClick={onClose}>×</Button>
        </div>
        <div className="flex gap-2">
          <Badge className={getCategoryColor(point.category)}>
            {point.category}
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
            <p className="text-gray-700">{point.content}</p>
          </div>
          
          <Separator />
          
          <div>
            <h4 className="font-semibold mb-2">关键词</h4>
            <div className="flex flex-wrap gap-2">
              {point.keywords.map((keyword, i) => (
                <Badge key={i} variant="secondary">{keyword}</Badge>
              ))}
            </div>
          </div>
          
          <Separator />
          
          <div>
            <h4 className="font-semibold mb-2">关联知识点</h4>
            <div className="space-y-2">
              {point.associations.map((assoc, i) => (
                <div key={i} className="flex justify-between items-center border p-2 rounded">
                  <span>{assoc.target}</span>
                  <div className="flex gap-2">
                    <Badge variant="outline">{assoc.type}</Badge>
                    <span className="text-sm text-gray-500">
                      {(assoc.strength * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
```

**验收标准**：
- [ ] 组件定义完整
- [ ] 样式符合项目规范
- [ ] 包含知识点详情展示

#### 5.2 关联图谱可视化

**文件**：`frontend/src/components/kg/AssociationGraph.tsx`

```tsx
'use client'

import { useEffect, useRef } from 'react'
import * as d3 from 'd3'

interface AssociationGraphProps {
  nodes: Array<{ id: string; title: string; category: string }>
  edges: Array<{ source: string; target: string; type: string; strength: number }>
  onNodeClick: (nodeId: string) => void
}

export function AssociationGraph({ nodes, edges, onNodeClick }: AssociationGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null)

  useEffect(() => {
    if (!svgRef.current) return

    const svg = d3.select(svgRef.current)
    const width = 800
    const height = 600

    svg.selectAll('*').remove()

    const g = svg.append('g')

    // 缩放和平移
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform)
      })

    svg.call(zoom)

    // 定义箭头
    svg.append('defs').append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '-0 -5 10 10')
      .attr('refX', 20)
      .attr('refY', 0)
      .attr('orient', 'auto')
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#999')

    // 力导向布局
    const simulation = d3.forceSimulation(nodes as any)
      .force('link', d3.forceLink(edges as any).id((d: any) => d.id).distance(100))
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(width / 2, height / 2))

    // 绘制边
    const link = g.append('g')
      .attr('class', 'links')
      .selectAll('line')
      .data(edges)
      .enter()
      .append('line')
      .attr('stroke', '#999')
      .attr('stroke-opacity', 0.6)
      .attr('stroke-width', (d) => Math.sqrt(d.strength) * 2)
      .attr('marker-end', 'url(#arrowhead)')

    // 绘制节点
    const node = g.append('g')
      .attr('class', 'nodes')
      .selectAll('circle')
      .data(nodes)
      .enter()
      .append('circle')
      .attr('r', 10)
      .attr('fill', (d) => {
        const colors = {
          concept: '#3b82f6',
          argument: '#22c55e',
          fact: '#eab308',
          method: '#a855f7'
        }
        return colors[d.category] || '#6b7280'
      })
      .call(d3.drag<SVGCircleElement, any>()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended))
      .on('click', (event, d) => onNodeClick(d.id))

    // 添加标签
    const label = g.append('g')
      .attr('class', 'labels')
      .selectAll('text')
      .data(nodes)
      .enter()
      .append('text')
      .attr('dx', 15)
      .attr('dy', 4)
      .text((d) => d.title.substring(0, 10) + '...')
      .style('font-size', '12px')

    // 模拟更新
    simulation.on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y)

      node
        .attr('cx', (d: any) => d.x)
        .attr('cy', (d: any) => d.y)

      label
        .attr('x', (d: any) => d.x)
        .attr('y', (d: any) => d.y)
    })

    function dragstarted(event: any, d: any) {
      if (!event.active) simulation.alphaTarget(0.3).restart()
      d.fx = d.x
      d.fy = d.y
    }

    function dragged(event: any, d: any) {
      d.fx = event.x
      d.fy = event.y
    }

    function dragended(event: any, d: any) {
      if (!event.active) simulation.alphaTarget(0)
      d.fx = null
      d.fy = null
    }

    return () => {
      simulation.stop()
    }
  }, [nodes, edges])

  return (
    <svg
      ref={svgRef}
      width="100%"
      height="600"
      className="border rounded-lg bg-white"
    />
  )
}
```

**验收标准**：
- [ ] D3.js 力导向图实现完整
- [ ] 支持缩放和平移
- [ ] 支持节点拖拽
- [ ] 支持点击交互

#### 5.3 阶段 5 验收检查清单

```markdown
## 阶段 5 验收检查清单

### 前端验收
- [ ] KnowledgePointDetail 组件创建完成
- [ ] AssociationGraph 组件创建完成
- [ ] 组件样式符合项目规范
- [ ] 交互功能正常

### 功能验收
- [ ] 可以查看知识点详情
- [ ] 可以查看关联图谱
- [ ] 图谱支持缩放和平移
- [ ] 节点支持拖拽
- [ ] 点击节点可以查看详情

### 回滚点
- 备份阶段 4 完成的代码
- 验证前端构建正常
- 验证所有组件渲染正常
```

**预计时间**：3-4 小时

---

### 阶段 6：自动触发机制

**目标**：实现知识库更新的自动触发

#### 6.1 事件监听器

**文件**：`backend/app/services/kg/event_listener.py`

```python
import logging
from typing import Callable, List
from datetime import datetime

logger = logging.getLogger(__name__)

class KnowledgeEventListener:
    """知识库事件监听器"""
    
    def __init__(self, self_enhancement_service):
        self.self_enhancement = self_self_enhancement_service
        self.handlers = {}
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """注册默认事件处理器"""
        self.register_handler('article_created', self._on_article_created)
        self.register_handler('article_updated', self._on_article_updated)
        self.register_handler('entity_created', self._on_entity_created)
    
    def register_handler(self, event_type: str, handler: Callable):
        """注册事件处理器"""
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)
    
    async def emit(self, event_type: str, data: dict):
        """触发事件"""
        logger.info(f"Emitting event: {event_type}")
        
        if event_type in self.handlers:
            for handler in self.handlers[event_type]:
                try:
                    await handler(data)
                except Exception as e:
                    logger.error(f"Handler error for {event_type}: {e}")
    
    async def _on_article_created(self, data: dict):
        """文章创建事件"""
        article_id = data.get('article_id')
        if article_id:
            logger.info(f"Article created: {article_id}, starting self-enhancement")
            await self.self_enhancement.process_new_article(article_id)
    
    async def _on_article_updated(self, data: dict):
        """文章更新事件"""
        article_id = data.get('article_id')
        if article_id:
            logger.info(f"Article updated: {article_id}, re-processing")
            # 可以选择重新处理或跳过
            await self.self_enhancement.process_new_article(article_id)
    
    async def _on_entity_created(self, data: dict):
        """实体创建事件"""
        entity_name = data.get('entity_name')
        if entity_name:
            logger.info(f"Entity created: {entity_name}")
            # 可以触发关联发现
```

**验收标准**：
- [ ] 事件监听器实现完整
- [ ] 包含默认事件处理器
- [ ] 支持自定义事件处理器

#### 6.2 集成到文档管理

**文件**：`backend/app/services/kg_sync.py` (修改)

```python
# 在文档创建/更新时触发事件

async def on_article_created(article_id: str, content: str):
    """文章创建后触发"""
    # 原有的实体抽取逻辑
    await extract_and_link_entities(article_id, content)
    
    # 新增：触发自增强循环
    from .kg.event_listener import KnowledgeEventListener
    from .kg.self_enhancement import KnowledgeSelfEnhancement
    
    # 初始化服务（实际应使用依赖注入）
    event_listener = KnowledgeEventListener(self_enhancement_service)
    await event_listener.emit('article_created', {
        'article_id': article_id,
        'content': content
    })
```

**验收标准**：
- [ ] 事件触发逻辑集成完成
- [ ] 文章创建时自动触发自增强循环
- [ ] 包含错误处理

#### 6.3 阶段 6 验收检查清单

```markdown
## 阶段 6 验收检查清单

### 后端验收
- [ ] event_listener.py 文件创建完成
- [ ] KnowledgeEventListener 类定义完整
- [ ] 事件处理器注册正常
- [ ] 事件触发逻辑正确

### 功能验收
- [ ] 创建新文章时自动触发自增强循环
- [ ] 更新文章时自动触发自增强循环
- [ ] 事件日志正确记录
- [ ] 错误处理正常

### 测试用例
```python
# 测试自动触发
article_id = await create_test_article("测试文章内容")
await asyncio.sleep(5)  # 等待异步处理

# 验证知识点已提取
knowledge_points = await get_knowledge_points(article_id)
assert len(knowledge_points) > 0
```

### 回滚点
- 备份阶段 5 完成的代码
- 验证原有文档管理功能正常
- 验证自增强循环正常触发
```

**预计时间**：2-3 小时

---

### 阶段 7：趋势预测功能

**目标**：实现基于知识图谱的趋势预测

#### 7.1 预测引擎

**文件**：`backend/app/services/kg/prediction.py`

```python
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import numpy as np

class TrendPredictionEngine:
    """趋势预测引擎"""
    
    def __init__(self, kg_service):
        self.kg_service = kg_service
    
    async def predict_trend(
        self,
        topic: str,
        time_range: int = 30,  # 预测天数
        prediction_type: str = 'general'
    ) -> Dict:
        """
        预测趋势
        
        参数：
        - topic: 预测主题
        - time_range: 预测时间范围
        - prediction_type: 预测类型 (general/technology/sentiment)
        
        返回：
        - trend: 趋势方向 (up/down/stable)
        - confidence: 置信度
        - factors: 影响因素
        - timeline: 时间线预测
        """
        
        # 1. 收集历史数据
        historical_data = await self._collect_historical_data(topic)
        
        # 2. 分析影响因素
        factors = await self._analyze_factors(topic)
        
        # 3. 生成预测
        prediction = self._generate_prediction(
            historical_data, factors, time_range, prediction_type
        )
        
        return prediction
    
    async def _collect_historical_data(self, topic: str) -> Dict:
        """收集历史数据"""
        # 获取实体及其关系
        entities = await self.kg_service.search_entities(topic)
        
        # 获取时间线数据
        timeline = await self.kg_service.get_entity_timeline(topic)
        
        # 获取关联实体
        related_entities = await self.kg_service.get_related_entities(topic)
        
        return {
            'entities': entities,
            'timeline': timeline,
            'related_entities': related_entities
        }
    
    async def _analyze_factors(self, topic: str) -> List[Dict]:
        """分析影响因素"""
        factors = []
        
        # 1. 因果关系分析
        causal_factors = await self._analyze_causal_factors(topic)
        factors.extend(causal_factors)
        
        # 2. 关联强度分析
        association_factors = await self._analyze_association_factors(topic)
        factors.extend(association_factors)
        
        # 3. 社区影响分析
        community_factors = await self._analyze_community_factors(topic)
        factors.extend(community_factors)
        
        return factors
    
    async def _analyze_causal_factors(self, topic: str) -> List[Dict]:
        """分析因果因素"""
        causal_chains = await self.kg_service.get_causal_chains(topic)
        
        factors = []
        for chain in causal_chains:
            factors.append({
                'type': 'causal',
                'entity': chain['target'],
                'strength': chain['strength'],
                'direction': 'positive' if chain['strength'] > 0 else 'negative'
            })
        
        return factors
    
    async def _analyze_association_factors(self, topic: str) -> List[Dict]:
        """分析关联因素"""
        associations = await self.kg_service.get_associations(topic)
        
        factors = []
        for assoc in associations:
            factors.append({
                'type': 'association',
                'entity': assoc['target'],
                'strength': assoc['strength'],
                'direction': 'positive'
            })
        
        return factors
    
    async def _analyze_community_factors(self, topic: str) -> List[Dict]:
        """分析社区因素"""
        communities = await self.kg_service.get_entity_communities(topic)
        
        factors = []
        for community in communities:
            factors.append({
                'type': 'community',
                'community_id': community['id'],
                'size': community['size'],
                'influence': community.get('influence', 0.5)
            })
        
        return factors
    
    def _generate_prediction(
        self,
        historical_data: Dict,
        factors: List[Dict],
        time_range: int,
        prediction_type: str
    ) -> Dict:
        """生成预测"""
        
        # 计算基础趋势
        base_trend = self._calculate_base_trend(historical_data)
        
        # 计算因子影响
        factor_impact = self._calculate_factor_impact(factors)
        
        # 综合预测
        combined_trend = base_trend + factor_impact
        
        # 生成时间线
        timeline = self._generate_timeline(combined_trend, time_range)
        
        # 确定趋势方向
        if combined_trend > 0.1:
            trend = 'up'
        elif combined_trend < -0.1:
            trend = 'down'
        else:
            trend = 'stable'
        
        # 计算置信度
        confidence = self._calculate_confidence(historical_data, factors)
        
        return {
            'topic': historical_data.get('entities', [{}])[0].get('name', 'unknown'),
            'trend': trend,
            'confidence': confidence,
            'factors': factors[:5],  # 只返回前 5 个主要因素
            'timeline': timeline,
            'prediction_type': prediction_type,
            'generated_at': datetime.now().isoformat()
        }
    
    def _calculate_base_trend(self, historical_data: Dict) -> float:
        """计算基础趋势"""
        timeline = historical_data.get('timeline', [])
        if not timeline:
            return 0.0
        
        # 简单线性回归
        values = [entry.get('value', 0) for entry in timeline]
        if len(values) < 2:
            return 0.0
        
        x = np.arange(len(values))
        y = np.array(values)
        
        # 计算斜率
        slope = np.polyfit(x, y, 1)[0]
        
        return slope
    
    def _calculate_factor_impact(self, factors: List[Dict]) -> float:
        """计算因子影响"""
        if not factors:
            return 0.0
        
        total_impact = 0.0
        for factor in factors:
            strength = factor.get('strength', 0.5)
            if factor.get('direction') == 'negative':
                strength = -strength
            total_impact += strength
        
        return total_impact / len(factors)
    
    def _generate_timeline(self, trend: float, days: int) -> List[Dict]:
        """生成时间线预测"""
        timeline = []
        base_value = 100  # 基准值
        
        for day in range(days):
            date = datetime.now() + timedelta(days=day)
            predicted_value = base_value * (1 + trend * day / 30)
            
            timeline.append({
                'date': date.strftime('%Y-%m-%d'),
                'predicted_value': round(predicted_value, 2),
                'confidence_interval': {
                    'lower': round(predicted_value * 0.9, 2),
                    'upper': round(predicted_value * 1.1, 2)
                }
            })
        
        return timeline
    
    def _calculate_confidence(self, historical_data: Dict, factors: List[Dict]) -> float:
        """计算置信度"""
        # 基于数据量和因子数量
        data_points = len(historical_data.get('timeline', []))
        factor_count = len(factors)
        
        # 基础置信度
        base_confidence = min(data_points / 10, 0.5)
        
        # 因子加成
        factor_bonus = min(factor_count / 5, 0.3)
        
        return min(base_confidence + factor_bonus, 0.9)
    
    async def predict_sentiment(self, topic: str) -> Dict:
        """预测舆情趋势"""
        return await self.predict_trend(topic, prediction_type='sentiment')
    
    async def predict_technology(self, topic: str) -> Dict:
        """预测技术趋势"""
        return await self.predict_trend(topic, prediction_type='technology')
    
    async def predict_knowledge_evolution(self, topic: str) -> Dict:
        """预测知识演化"""
        return await self.predict_trend(topic, prediction_type='knowledge')
```

**验收标准**：
- [ ] 预测引擎实现完整
- [ ] 包含多种预测类型
- [ ] 包含时间线预测
- [ ] 包含置信度计算

#### 7.2 预测 API

**文件**：`backend/app/api/kg.py` (追加)

```python
@router.post("/prediction/trend")
async def predict_trend(request: TrendPredictionRequest):
    """
    预测趋势
    
    请求体：
    - topic: 预测主题
    - time_range: 预测天数 (默认 30)
    - prediction_type: 预测类型 (general/technology/sentiment)
    
    返回：
    - trend: 趋势方向
    - confidence: 置信度
    - factors: 影响因素
    - timeline: 时间线预测
    """
    engine = TrendPredictionEngine(kg_service)
    result = await engine.predict_trend(
        topic=request.topic,
        time_range=request.time_range,
        prediction_type=request.prediction_type
    )
    return result

@router.post("/prediction/sentiment")
async def predict_sentiment(request: TrendPredictionRequest):
    """预测舆情趋势"""
    engine = TrendPredictionEngine(kg_service)
    result = await engine.predict_sentiment(topic=request.topic)
    return result

@router.post("/prediction/technology")
async def predict_technology(request: TrendPredictionRequest):
    """预测技术趋势"""
    engine = TrendPredictionEngine(kg_service)
    result = await engine.predict_technology(topic=request.topic)
    return result

class TrendPredictionRequest(BaseModel):
    topic: str
    time_range: int = 30
    prediction_type: str = 'general'
```

**验收标准**：
- [ ] 预测 API 定义完整
- [ ] 请求/响应模型正确
- [ ] 包含错误处理

#### 7.3 阶段 7 验收检查清单

```markdown
## 阶段 7 验收检查清单

### 后端验收
- [ ] prediction.py 文件创建完成
- [ ] TrendPredictionEngine 类定义完整
- [ ] 包含多种预测类型
- [ ] 预测 API 定义完整

### 功能验收
- [ ] 可以预测一般趋势
- [ ] 可以预测技术趋势
- [ ] 可以预测舆情趋势
- [ ] 预测结果包含置信度
- [ ] 预测结果包含时间线

### 测试用例
```python
# 测试趋势预测
result = await predict_trend(
    topic="人工智能",
    time_range=30,
    prediction_type="technology"
)

assert result['trend'] in ['up', 'down', 'stable']
assert 0 <= result['confidence'] <= 1
assert len(result['timeline']) == 30
```

### 回滚点
- 备份阶段 6 完成的代码
- 验证预测算法正常
- 验证 API 调用正常
```

**预计时间**：3-4 小时

---

### 阶段 8：测试与优化

**目标**：全面测试和性能优化

#### 8.1 单元测试

**文件**：`backend/tests/test_self_enhancement.py`

```python
import pytest
from app.services.kg.self_enhancement import KnowledgeSelfEnhancement
from app.services.kg.association import AssociationDiscovery
from app.services.kg.summarizer import KnowledgeSummarizer
from app.services.kg.prediction import TrendPredictionEngine

class TestKnowledgeSelfEnhancement:
    """知识自增强循环测试"""
    
    @pytest.fixture
    def mock_kg_service(self):
        """模拟知识图谱服务"""
        # TODO: 实现 mock
        pass
    
    @pytest.fixture
    def mock_llm_client(self):
        """模拟 LLM 客户端"""
        # TODO: 实现 mock
        pass
    
    def test_process_new_article(self, mock_kg_service, mock_llm_client):
        """测试处理新文章"""
        service = KnowledgeSelfEnhancement(mock_kg_service, mock_llm_client)
        
        # TODO: 实现测试
        pass
    
    def test_extract_knowledge_points(self, mock_llm_client):
        """测试知识点提取"""
        # TODO: 实现测试
        pass
    
    def test_discover_associations(self, mock_kg_service):
        """测试关联发现"""
        discovery = AssociationDiscovery(mock_kg_service)
        
        # TODO: 实现测试
        pass
    
    def test_generate_summary(self, mock_llm_client):
        """测试总结生成"""
        summarizer = KnowledgeSummarizer(mock_llm_client)
        
        # TODO: 实现测试
        pass

class TestTrendPrediction:
    """趋势预测测试"""
    
    @pytest.fixture
    def mock_kg_service(self):
        """模拟知识图谱服务"""
        # TODO: 实现 mock
        pass
    
    def test_predict_trend(self, mock_kg_service):
        """测试趋势预测"""
        engine = TrendPredictionEngine(mock_kg_service)
        
        # TODO: 实现测试
        pass
    
    def test_predict_sentiment(self, mock_kg_service):
        """测试舆情预测"""
        engine = TrendPredictionEngine(mock_kg_service)
        
        # TODO: 实现测试
        pass
```

**验收标准**：
- [ ] 测试文件创建完成
- [ ] 包含核心功能测试
- [ ] 测试用例覆盖主要场景

#### 8.2 集成测试

**文件**：`backend/tests/integration/test_self_enhancement_integration.py`

```python
import pytest
import asyncio
from httpx import AsyncClient
from app.main import app

class TestSelfEnhancementIntegration:
    """自增强循环集成测试"""
    
    @pytest.mark.asyncio
    async def test_process_article_api(self):
        """测试文章处理 API"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # 创建测试文章
            article_response = await client.post("/api/articles", json={
                "title": "测试文章",
                "content": "这是一篇测试文章，用于验证自增强循环功能。"
            })
            article_id = article_response.json()["id"]
            
            # 触发自增强循环
            response = await client.post("/api/kg/self-enhancement/process-article", json={
                "article_id": article_id
            })
            
            assert response.status_code == 200
            result = response.json()
            assert result["status"] == "completed"
            assert result["knowledge_points_count"] > 0
    
    @pytest.mark.asyncio
    async def test_get_knowledge_points(self):
        """测试获取知识点"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/kg/self-enhancement/knowledge-points")
            
            assert response.status_code == 200
            data = response.json()
            assert "knowledge_points" in data
            assert "total" in data
    
    @pytest.mark.asyncio
    async def test_prediction_api(self):
        """测试预测 API"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post("/api/kg/prediction/trend", json={
                "topic": "人工智能",
                "time_range": 30
            })
            
            assert response.status_code == 200
            result = response.json()
            assert "trend" in result
            assert "confidence" in result
            assert "timeline" in result
```

**验收标准**：
- [ ] 集成测试文件创建完成
- [ ] 包含 API 端点测试
- [ ] 测试用例覆盖主要场景

#### 8.3 性能优化

**优化点**：

1. **LLM 调用优化**
   - 批量处理多个知识点
   - 缓存常见提取结果
   - 使用异步并发调用

2. **图数据库查询优化**
   - 添加索引
   - 优化查询语句
   - 使用连接池

3. **前端渲染优化**
   - 虚拟滚动
   - 懒加载
   - 缓存机制

#### 8.4 阶段 8 验收检查清单

```markdown
## 阶段 8 验收检查清单

### 测试验收
- [ ] 单元测试文件创建完成
- [ ] 集成测试文件创建完成
- [ ] 测试覆盖率 > 60%
- [ ] 所有测试通过

### 性能验收
- [ ] LLM 调用响应时间 < 5s
- [ ] 图数据库查询 < 1s
- [ ] 前端页面加载 < 2s

### 文档验收
- [ ] API 文档更新
- [ ] 使用说明文档
- [ ] 部署文档

### 回滚点
- 最终版本备份
- 验证所有功能正常
- 准备发布
```

**预计时间**：4-5 小时

---

## 📊 项目时间表

| 阶段 | 内容 | 预计时间 | 状态 |
|------|------|----------|------|
| 阶段 1 | 基础架构搭建 | 2-3h | ⏳ 待开始 |
| 阶段 2 | LLM 知识点提取 | 3-4h | ⏳ 待开始 |
| 阶段 3 | 知识关联发现 | 2-3h | ⏳ 待开始 |
| 阶段 4 | 知识总结生成 | 2-3h | ⏳ 待开始 |
| 阶段 5 | 前端交互优化 | 3-4h | ⏳ 待开始 |
| 阶段 6 | 自动触发机制 | 2-3h | ⏳ 待开始 |
| 阶段 7 | 趋势预测功能 | 3-4h | ⏳ 待开始 |
| 阶段 8 | 测试与优化 | 4-5h | ⏳ 待开始 |
| **总计** | | **21-29h** | |

---

## 🔄 回滚策略

### 回滚点设置
1. **阶段 1 完成后**：基础架构验证点
2. **阶段 3 完成后**：功能完整性验证点
3. **阶段 5 完成后**：前端交互验证点
4. **阶段 7 完成后**：最终功能验证点

### 回滚操作
```bash
# 备份当前版本
git tag -a v1.0-phase-N -m "Phase N complete"
git push origin v1.0-phase-N

# 如果需要回滚
git checkout v1.0-phase-(N-1)
```

### 回滚检查清单
- [ ] 验证现有功能未受影响
- [ ] 验证数据库状态正常
- [ ] 验证 API 调用正常
- [ ] 验证前端渲染正常

---

## 📝 注意事项

1. **代码改动最小化**
   - 仅新增文件，不修改现有文件
   - 如需修改，只修改必要部分
   - 保持原有代码风格

2. **前后端同步**
   - 后端 API 定义后，前端立即实现对应组件
   - 每个阶段完成后，验证前后端联调

3. **自测要求**
   - 每个阶段完成后，必须进行功能自测
   - 自测通过后，才进入下一阶段
   - 自测失败，立即回滚并修复

4. **文档同步**
   - 每个阶段完成后，更新相关文档
   - 包括 API 文档、使用说明、部署文档

---

## 🎯 成功标准

### 功能完整性
- [ ] 知识点自动提取
- [ ] 知识关联自动发现
- [ ] 知识总结自动生成
- [ ] 趋势预测功能
- [ ] 自动触发机制

### 性能指标
- [ ] 知识点提取准确率 > 80%
- [ ] 关联发现准确率 > 70%
- [ ] 预测置信度 > 60%
- [ ] 系统响应时间 < 5s

### 用户体验
- [ ] 界面友好，操作简单
- [ ] 结果可视化清晰
- [ ] 交互响应及时

---

**计划制定日期**：2024-01-XX
**预计完成日期**：2024-01-XX
**负责人**：AI Studio 开发团队
