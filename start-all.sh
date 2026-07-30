#!/bin/bash
# AI Studio 启动脚本 - 一键启动所有服务
#
# 会自动启动：
# - Firecrawl 网页爬取服务 (Docker)
# - Neo4j 知识图谱服务 (Docker)
# - 后端 API 服务 (FastAPI)
# - 前端开发服务器 (Next.js)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "   AI Studio 一键启动"
echo "=========================================="

# ============ 配置一致性检测 ============
echo -e "\n${YELLOW}[0/4] 配置一致性检测...${NC}"

# 定义实际使用的端口
BACKEND_PORT=8080
FRONTEND_PORT=3000
NEO4J_PORT=7474
NEO4J_BOLT_PORT=7687
FIRECRAWL_PORT=3002

# 读取 .env.local 配置的端口
ENV_FILE="$SCRIPT_DIR/frontend/.env.local"
if [ -f "$ENV_FILE" ]; then
    CONFIGURED_BACKEND_PORT=$(grep -oP 'BACKEND_URL=http://localhost:\K[0-9]+' "$ENV_FILE" 2>/dev/null || echo "")
    CONFIGURED_SCRAPE_PORT=$(grep -oP 'AI_STUDIO_SCRAPE_BACKEND_URL=http://localhost:\K[0-9]+' "$ENV_FILE" 2>/dev/null || echo "")
else
    CONFIGURED_BACKEND_PORT=""
    CONFIGURED_SCRAPE_PORT=""
fi

# 检测函数
check_port_consistency() {
    local config_name=$1
    local configured_port=$2
    local actual_port=$3
    local file_path=$4

    if [ -n "$configured_port" ] && [ "$configured_port" != "$actual_port" ]; then
        echo -e "  ${RED}❌ $config_name: 配置端口 $configured_port ≠ 实际端口 $actual_port${NC}"
        echo -e "  ${YELLOW}   正在自动修复 $file_path ...${NC}"
        return 1
    elif [ -n "$configured_port" ]; then
        echo -e "  ${GREEN}✅ $config_name: 端口 $configured_port 一致${NC}"
        return 0
    else
        echo -e "  ${YELLOW}⚠️  $config_name: 未配置，将使用默认端口 $actual_port${NC}"
        return 0
    fi
}

# 执行检测
PORT_ISSUES=0

# 检测 BACKEND_URL 端口
if ! check_port_consistency "BACKEND_URL" "$CONFIGURED_BACKEND_PORT" "$BACKEND_PORT" "$ENV_FILE"; then
    sed -i "s/BACKEND_URL=http:\/\/localhost:[0-9]*/BACKEND_URL=http:\/\/localhost:$BACKEND_PORT/g" "$ENV_FILE"
    PORT_ISSUES=$((PORT_ISSUES + 1))
fi

# 检测 AI_STUDIO_SCRAPE_BACKEND_URL 端口
if ! check_port_consistency "AI_STUDIO_SCRAPE_BACKEND_URL" "$CONFIGURED_SCRAPE_PORT" "$BACKEND_PORT" "$ENV_FILE"; then
    sed -i "s/AI_STUDIO_SCRAPE_BACKEND_URL=http:\/\/localhost:[0-9]*/AI_STUDIO_SCRAPE_BACKEND_URL=http:\/\/localhost:$BACKEND_PORT/g" "$ENV_FILE"
    PORT_ISSUES=$((PORT_ISSUES + 1))
fi

# 检测 models_config.json 是否存在
if [ ! -f "$SCRIPT_DIR/backend/models_config.json" ]; then
    echo -e "  ${RED}❌ 模型配置文件不存在: backend/models_config.json${NC}"
    PORT_ISSUES=$((PORT_ISSUES + 1))
else
    echo -e "  ${GREEN}✅ 模型配置文件存在${NC}"
fi

# 检测 Neo4j 端口配置
if [ -f "$SCRIPT_DIR/docker-compose.kg.yml" ]; then
    NEO4J_CONFIGURED=$(grep -oP '"$NEO4J_PORT"' "$SCRIPT_DIR/docker-compose.kg.yml" 2>/dev/null || echo "")
    if [ -n "$NEO4J_CONFIGURED" ]; then
        echo -e "  ${GREEN}✅ Neo4j 端口配置: $NEO4J_PORT${NC}"
    fi
fi

# 汇总检测结果
if [ $PORT_ISSUES -gt 0 ]; then
    echo -e "\n${YELLOW}已修复 $PORT_ISSUES 个端口配置问题${NC}"
else
    echo -e "\n${GREEN}所有配置检测通过！${NC}"
fi

# 检查并启动 Firecrawl (Docker)
echo -e "\n${YELLOW}[1/4] 检查 Firecrawl 服务...${NC}"
if ! curl -s http://localhost:$FIRECRAWL_PORT/v1/scrape -X POST \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer local' \
  -d '{"url":"https://example.com","formats":["markdown"]}' > /dev/null 2>&1; then

  echo "  Firecrawl 服务未运行，正在启动..."
  if [ -d "/tmp/firecrawl" ]; then
    cd /tmp/firecrawl
    echo "1qaz@WSX" | sudo -S docker compose up -d > /dev/null 2>&1 || true
    cd "$SCRIPT_DIR"
    echo -e "  ${YELLOW}等待服务启动 (10秒)...${NC}"
    sleep 10

    # 再次检查
    if curl -s http://localhost:$FIRECRAWL_PORT/v1/scrape -X POST \
      -H 'Content-Type: application/json' \
      -H 'Authorization: Bearer local' \
      -d '{"url":"https://example.com","formats":["markdown"]}' > /dev/null 2>&1; then
      echo -e "  ${GREEN}✅ Firecrawl 服务已启动${NC}"
    else
      echo -e "  ${RED}⚠️ Firecrawl 服务启动可能有问题，但仍继续...${NC}"
    fi
  else
    echo -e "  ${YELLOW}⚠️ Firecrawl 代码未找到，跳过${NC}"
  fi
else
  echo -e "  ${GREEN}✅ Firecrawl 服务已就绪${NC}"
fi

# 检查并启动 Neo4j
echo -e "\n${YELLOW}[2/4] 检查 Neo4j 服务...${NC}"
if ! docker compose -f "$SCRIPT_DIR/docker-compose.kg.yml" exec -T neo4j \
  cypher-shell -u neo4j -p "${NEO4J_PASSWORD:-password}" "RETURN 1" > /dev/null 2>&1; then
  docker compose -f "$SCRIPT_DIR/docker-compose.kg.yml" up -d neo4j
  echo -e "  ${YELLOW}Neo4j 正在启动，后端健康检查会持续对账${NC}"
else
  echo -e "  ${GREEN}✅ Neo4j 服务已就绪${NC}"
fi

# 启动后端
echo -e "\n${YELLOW}[3/4] 启动后端服务...${NC}"
cd "$SCRIPT_DIR/backend"
nohup python3 -m uvicorn app.main:app --reload --port $BACKEND_PORT > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
echo -e "  ${GREEN}✅ 后端已启动 (PID: $BACKEND_PID)${NC}"

# 等待后端启动
sleep 3

# 启动前端
echo -e "\n${YELLOW}[4/4] 启动前端服务...${NC}"
cd "$SCRIPT_DIR/frontend"
nohup npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo -e "  ${GREEN}✅ 前端已启动 (PID: $FRONTEND_PID)${NC}"

# 等待前端启动
sleep 5

# 保存 PIDs 到文件
mkdir -p "$SCRIPT_DIR/.pids"
echo "$BACKEND_PID" > "$SCRIPT_DIR/.pids/backend.pid"
echo "$FRONTEND_PID" > "$SCRIPT_DIR/.pids/frontend.pid"

echo -e "\n=========================================="
echo -e "   ${GREEN}所有服务已启动！${NC}"
echo -e "==========================================="
echo ""
echo "  🔗 访问地址："
echo "     前端: http://localhost:$FRONTEND_PORT"
echo "     后端: http://localhost:$BACKEND_PORT"
echo "     Neo4j: http://localhost:$NEO4J_PORT"
echo ""
echo "  📁 日志文件:"
echo "     后端: logs/backend.log"
echo "     前端: logs/frontend.log"
echo ""
echo "  停止所有服务: ./stop-all.sh"
echo -e "==========================================\n"
