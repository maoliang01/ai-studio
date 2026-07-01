#!/bin/bash
# AI Studio 启动脚本 - 一键启动所有服务
#
# 会自动启动：
# - Firecrawl 网页爬取服务 (Docker)
# - 后端 API 服务 (FastAPI)
# - 前端开发服务器 (Next.js)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "   AI Studio 一键启动"
echo "=========================================="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查并启动 Firecrawl (Docker)
echo -e "\n${YELLOW}[1/3] 检查 Firecrawl 服务...${NC}"
if ! curl -s http://localhost:3002/v1/scrape -X POST \
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
    if curl -s http://localhost:3002/v1/scrape -X POST \
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

# 启动后端
echo -e "\n${YELLOW}[2/3] 启动后端服务...${NC}"
cd "$SCRIPT_DIR/backend"
nohup python3 -m uvicorn app.main:app --reload --port 8080 > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
echo -e "  ${GREEN}✅ 后端已启动 (PID: $BACKEND_PID)${NC}"

# 等待后端启动
sleep 3

# 启动前端
echo -e "\n${YELLOW}[3/3] 启动前端服务...${NC}"
cd "$SCRIPT_DIR/frontend"
nohup npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo -e "  ${GREEN}✅ 前端已启动 (PID: $FRONTEND_PID)${NC}"

# 等待前端启动
sleep 5

# 保存 PIDs 到文件
echo "$BACKEND_PID" > "$SCRIPT_DIR/.pids/backend.pid"
echo "$FRONTEND_PID" > "$SCRIPT_DIR/.pids/frontend.pid"

echo -e "\n=========================================="
echo -e "   ${GREEN}所有服务已启动！${NC}"
echo -e "==========================================="
echo ""
echo "  🔗 访问地址："
echo "     前端: http://localhost:3000"
echo "     后端: http://localhost:8080"
echo "     爬虫: http://localhost:3002"
echo ""
echo "  📁 日志文件:"
echo "     后端: logs/backend.log"
echo "     前端: logs/frontend.log"
echo ""
echo "  停止所有服务: ./stop-all.sh"
echo -e "==========================================\n"