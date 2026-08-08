#!/bin/bash
# ===========================================
# AI Studio 启动脚本（零依赖数据库）
# ===========================================

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  AI Studio 启动 (SQLite 模式)${NC}"
echo -e "${GREEN}========================================${NC}"
echo
echo -e "${BLUE}💡 无需安装数据库软件，数据自动保存在本地${NC}"
echo

# 检查 Docker
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}错误: Docker 未运行，请先启动 Docker Desktop${NC}"
    exit 1
fi

# 选择配置：如果本地 PostgreSQL 可用则使用它，否则用 SQLite
DB_TYPE="sqlite"
PG_AVAILABLE=false

# 检查 PostgreSQL 是否可用
if command -v psql &> /dev/null; then
    export PGPASSWORD=postgres
    if psql -U postgres -h localhost -d postgres -c "SELECT 1" &>/dev/null; then
        PG_AVAILABLE=true
    fi
fi

# Windows PostgreSQL 安装路径检查
if [ "$PG_AVAILABLE" = false ]; then
    for PSQL_PATH in "/c/Program Files/PostgreSQL"/*/bin/psql.exe; do
        if [ -f "$PSQL_PATH" ]; then
            export PATH="$(dirname $PSQL_PATH):$PATH"
            export PGPASSWORD=postgres
            if "$PSQL_PATH" -U postgres -h localhost -d postgres -c "SELECT 1" &>/dev/null; then
                PG_AVAILABLE=true
                break
            fi
        fi
    done
fi

if [ "$PG_AVAILABLE" = true ]; then
    DB_TYPE="postgresql"
    echo -e "${GREEN}[1/4] PostgreSQL 已检测到，将使用 PostgreSQL${NC}"
else
    echo -e "${YELLOW}[1/4] 未检测到 PostgreSQL，将使用 SQLite${NC}"
fi

# 同步数据库
echo -e "${YELLOW}[2/4] 启动 Docker 服务...${NC}"
docker compose -f docker-compose-local-db.yml down 2>/dev/null || true

# 清理 Neo4j Docker volume（确保全新开始，换设备时数据清空）
docker volume rm ai-studio_neo4j_data 2>/dev/null || true
docker volume rm ai-studio_neo4j_logs 2>/dev/null || true

# 清理本地 Neo4j 数据（确保全新开始）
rm -rf ./backend/data/neo4j ./backend/data/neo4j_logs 2>/dev/null || true

docker compose -f docker-compose-local-db.yml up -d neo4j

# 等待 Neo4j 启动
echo -e "${YELLOW}[3/4] 等待 Neo4j 就绪...${NC}"
for i in {1..60}; do
    if docker exec neo4j-ai-studio cypher-shell -u neo4j -p password 'RETURN 1' &>/dev/null 2>&1; then
        echo -e "${GREEN}      ✓ Neo4j 已就绪${NC}"
        break
    fi
    sleep 1
done

# 启动后端和前端
echo -e "${YELLOW}[4/4] 启动后端和前端...${NC}"
docker compose -f docker-compose-local-db.yml up -d --build backend frontend

# 等待服务启动
sleep 5

# 检查服务状态
echo
echo -e "${GREEN}容器状态:${NC}"
docker compose -f docker-compose-local-db.yml ps

# 显示访问地址
echo
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  服务已启动！${NC}"
echo -e "${GREEN}========================================${NC}"
echo
echo -e "  前端地址: ${GREEN}http://localhost:3000${NC}"
echo -e "  API 地址: ${GREEN}http://localhost:8500${NC}"
echo -e "  API 文档: ${GREEN}http://localhost:8500/docs${NC}"
echo -e "  Neo4j:    ${GREEN}http://localhost:7474${NC}"
echo
echo -e "数据库类型: ${GREEN}${DB_TYPE}${NC}"
echo -e "数据位置:   ${GREEN}backend/data/ai_studio.db${NC}"
echo
echo -e "常用命令:"
echo -e "  ${YELLOW}./stop.sh${NC}                                               # 暂停服务"
echo -e "  ${YELLOW}docker compose -f docker-compose-local-db.yml logs -f${NC}  # 查看日志"
echo -e "${GREEN}========================================${NC}"