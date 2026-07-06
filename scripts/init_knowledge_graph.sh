#!/bin/bash
# 知识图谱启动脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_DIR/backend"

echo "=========================================="
echo "  AI Studio 知识图谱初始化"
echo "=========================================="

# 1. 启动 Neo4j
echo ""
echo "[1/4] 启动 Neo4j..."
cd "$PROJECT_DIR"
if docker ps | grep -q neo4j-ai-studio; then
    echo "  ✓ Neo4j 已在运行"
else
    docker-compose -f docker-compose.kg.yml up -d
    echo "  ✓ Neo4j 已启动"
fi

# 2. 等待 Neo4j 就绪
echo ""
echo "[2/4] 等待 Neo4j 就绪..."
for i in {1..30}; do
    if curl -s http://localhost:7474 > /dev/null 2>&1; then
        echo "  ✓ Neo4j 已就绪"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "  ⚠ Neo4j 启动超时，请手动检查"
    fi
    sleep 2
done

# 3. 安装 Python 依赖
echo ""
echo "[3/4] 检查 Python 依赖..."
cd "$BACKEND_DIR"
pip show neo4j > /dev/null 2>&1 || pip install neo4j -q
pip show sentence-transformers > /dev/null 2>&1 || pip install sentence-transformers -q
echo "  ✓ Python 依赖已就绪"

# 4. 初始化数据库
echo ""
echo "[4/4] 初始化向量数据库..."
python scripts/init_kg_migration.py
echo "  ✓ 向量数据库已初始化"

echo ""
echo "=========================================="
echo "  初始化完成！"
echo ""
echo "下一步操作："
echo "  1. 启动后端: cd $BACKEND_DIR && uvicorn app.main:app --reload --port 8000"
echo "  2. 访问 API 文档: http://localhost:8000/docs"
echo "  3. 初始化图谱: POST /api/kg/init"
echo "  4. 批量处理文章: POST /api/kg/batch-process"
echo "=========================================="