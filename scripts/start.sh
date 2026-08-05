#!/usr/bin/env bash
# ================================================================
# AI Studio 一键启动脚本
# ================================================================
# 特性:
#   - 全自动运行环境检测，缺失组件自动下载安装
#   - 跨平台支持 (Linux / macOS / Windows Git Bash / WSL2)
#   - 日志记录 + 后台启动 + 健康检查 + 自动重试
#   - 自动修复已知问题（API路径、数据库表缺失等）
# ================================================================
# 使用方法:
#   bash scripts/start.sh
#   ./scripts/start.sh
# ================================================================
# 依赖组件（自动安装）:
#   - Docker + Docker Compose      → 容器化 PostgreSQL / Neo4j / 后端
#   - Node.js + npm                → 前端 Next.js
#   - Python 3 + pip               → 后端（Docker内已含，用于扩展脚本）
# ================================================================

set -euo pipefail

# ---------------------------------------------------------------
# 0. 基础环境设置
# ---------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_DIR}"

# 日志目录
LOG_DIR="${PROJECT_DIR}/logs"
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/startup-$(date +%Y%m%d-%H%M%S).log"

# 同时输出到终端和日志文件
exec > >(tee -a "${LOG_FILE}") 2>&1

echo "═══════════════════════════════════════════════════════════════"
echo "  AI Studio 一键启动脚本"
echo "  启动时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "  日志文件: ${LOG_FILE}"
echo "═══════════════════════════════════════════════════════════════"

# ---------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

info()  { echo -e "  ${CYAN}ℹ${NC} $1"; }
ok()    { echo -e "  ${GREEN}✓${NC} $1"; }
warn()  { echo -e "  ${YELLOW}⚠${NC} $1"; }
err()   { echo -e "  ${RED}✗${NC} $1"; }
step()  { echo -e "\n${BLUE}[$1/${TOTAL_STEPS}]${NC} $2"; }

# 检测操作系统
detect_os() {
    case "$(uname -s)" in
        Linux*)  echo "linux";;
        Darwin*) echo "darwin";;
        MINGW*|MSYS*|CYGWIN*) echo "windows";;
        *)       echo "unknown";;
    esac
}
OS_TYPE=$(detect_os)
ARCH="$(uname -m)"
ok "操作系统: ${OS_TYPE} / ${ARCH}"

# 环境变量：是否强制重新构建后端镜像
REBUILD_BACKEND="${REBUILD_BACKEND:-no}"

# ---------------------------------------------------------------
# 1. 检测环境组件，缺失则自动安装
# ---------------------------------------------------------------
TOTAL_STEPS=8
step 1 "检测运行环境，缺失组件自动安装..."

# ---------- 1a. Docker ----------
if command -v docker &>/dev/null; then
    ok "Docker 已安装 ($(command -v docker))"
else
    warn "Docker 未安装，正在自动安装..."
    case "${OS_TYPE}" in
        linux)
            curl -fsSL https://get.docker.com | bash
            sudo usermod -aG docker "${USER}" 2>/dev/null || true
            newgrp docker 2>/dev/null || true
            ok "Docker 安装完成"
            ;;
        darwin)
            if command -v brew &>/dev/null; then
                brew install --cask docker
                warn "➜ 请从启动台打开 Docker Desktop，然后重新运行此脚本"
            else
                info "➜ 请从 https://www.docker.com/products/docker-desktop/ 安装 Docker Desktop"
            fi
            exit 1
            ;;
        windows)
            info "➜ 请从 https://www.docker.com/products/docker-desktop/ 安装 Docker Desktop"
            exit 1
            ;;
    esac
fi

# 确保 Docker 守护进程运行中
if ! docker info &>/dev/null; then
    warn "Docker 守护进程未运行，尝试启动..."
    case "${OS_TYPE}" in
        linux)
            sudo systemctl start docker 2>/dev/null || sudo service docker start 2>/dev/null || true
            ;;
        darwin)
            info "➜ 请手动启动 Docker Desktop (Applications 文件夹)"
            ;;
        windows)
            info "➜ 请手动启动 Docker Desktop (开始菜单)"
            ;;
    esac
    # 等待最多 90 秒
    for i in $(seq 1 9030); do
        if docker info &>/dev/null; then
            ok "Docker 守护进程已启动"
            break
        fi
        [ $i -eq 9030 ] && { err "Docker 启动超时，请手动启动后重试"; exit 1; }
        sleep 1
    done
fi
ok "Docker 运行中"

# Docker Compose 检查
if docker compose version &>/dev/null; then
    DOCKER_COMPOSE="docker compose"
elif docker-compose --version &>/dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    warn "Docker Compose 未安装"
    case "${OS_TYPE}" in
        linux)
            sudo curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
            sudo chmod +x /usr/local/bin/docker-compose
            DOCKER_COMPOSE="docker-compose"
            ok "Docker Compose 安装完成"
            ;;
        *)
            info "➜ Docker Desktop 已包含 docker compose，请使用最新版本"
            DOCKER_COMPOSE="docker compose"
            ;;
    esac
fi
ok "${DOCKER_COMPOSE} 可用"

# ---------- 1b. Node.js + npm ----------
if ! command -v node &>/dev/null; then
    warn "Node.js 未安装，正在自动安装..."
    case "${OS_TYPE}" in
        linux)
            curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
            sudo apt-get install -y nodejs 2>/dev/null || sudo yum install -y nodejs 2>/dev/null || true
            ;;
        darwin)
            if command -v brew &>/dev/null; then
                brew install node@22
            else
                curl -fsSL https://nodejs.org/dist/v22.14.0/node-v22.14.0-darwin-${ARCH}.tar.gz | sudo tar xz -C /usr/local --strip-components=1 2>/dev/null || {
                    warn "自动安装失败，请手动安装 Node.js: https://nodejs.org/"
                    exit 1
                }
            fi
            ;;
        windows)
            if command -v winget &>/dev/null; then
                winget install OpenJS.NodeJS.LTS 2>/dev/null || true
            elif command -v choco &>/dev/null; then
                choco install nodejs-lts -y 2>/dev/null || true
            elif command -v scoop &>/dev/null; then
                scoop install nodejs 2>/dev/null || true
            fi
            ;;
    esac
fi

if command -v node &>/dev/null; then
    ok "Node.js $(node --version)"
else
    err "Node.js 自动安装失败，请手动安装: https://nodejs.org/"
    exit 1
fi

if ! command -v npm &>/dev/null; then
    warn "npm 未安装，正在安装..."
    case "${OS_TYPE}" in
        linux) sudo apt-get install -y npm 2>/dev/null || sudo yum install -y npm 2>/dev/null || true ;;
        darwin) brew install npm 2>/dev/null || true ;;
    esac
    command -v npm &>/dev/null || { err "npm 安装失败"; exit 1; }
fi
ok "npm $(npm --version)"

# ---------- 1c. Python 3 + pip ----------
if ! command -v python3 &>/dev/null; then
    warn "Python 3 未安装，正在自动安装..."
    case "${OS_TYPE}" in
        linux)
            sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv 2>/dev/null || \
            sudo yum install -y python3 python3-pip 2>/dev/null || true
            ;;
        darwin)
            brew install python@3.11 2>/dev/null || true
            ;;
        windows)
            winget install Python.Python.3.11 2>/dev/null || \
            choco install python3 -y 2>/dev/null || true
            ;;
    esac
fi

if command -v python3 &>/dev/null; then
    ok "Python $(python3 --version 2>&1)"
else
    err "Python 3 自动安装失败，请手动安装: https://www.python.org/downloads/"
    exit 1
fi

# pip
if ! command -v pip3 &>/dev/null; then
    warn "pip3 未安装，正在安装..."
    python3 -m ensurepip --upgrade 2>/dev/null || python3 <(curl -sS https://bootstrap.pypa.io/get-pip.py) 2>/dev/null || true
    command -v pip3 &>/dev/null || { err "pip3 安装失败"; exit 1; }
fi
ok "pip $(pip3 --version 2>&1 | awk '{print $2}')"

# ---------- 1d. Git ----------
if ! command -v git &>/dev/null; then
    warn "Git 未安装，正在安装..."
    case "${OS_TYPE}" in
        linux) sudo apt-get install -y git 2>/dev/null || sudo yum install -y git 2>/dev/null || true ;;
        darwin) brew install git 2>/dev/null || xcode-select --install 2>/dev/null || true ;;
    esac
fi
command -v git &>/dev/null && ok "Git $(git --version 2>&1 | awk '{print $3}')" || warn "Git 未安装（非必需）"

echo ""
ok "运行环境检查完成"

# ================================================================
# 2. Docker 网络
# ================================================================
step 2 "准备 Docker 网络..."

if ! docker network ls --format '{{.Name}}' | grep -q '^ai-studio-network$'; then
    info "创建 ai-studio-network..."
    docker network create ai-studio-network 2>&1 | tail -1
    ok "网络已创建"
else
    ok "网络已存在: ai-studio-network"
fi

# ================================================================
# 3. 启动数据库 (PostgreSQL + Neo4j)
# ================================================================
step 3 "启动数据库服务..."

# 启动 PostgreSQL
if docker ps --format '{{.Names}}' | grep -q '^ai-studio-db$'; then
    ok "PostgreSQL 已运行"
else
    if docker ps -a --format '{{.Names}}' | grep -q '^ai-studio-db$'; then
        info "启动已有 PostgreSQL 容器..."
        docker start ai-studio-db >/dev/null
        ok "PostgreSQL 已启动"
    else
        info "拉取 PostgreSQL 镜像..."
        docker pull postgres:15-alpine 2>&1 | tail -1
        info "创建 PostgreSQL 容器..."
        docker run -d --name ai-studio-db \
            --network ai-studio-network \
            -e POSTGRES_DB=ai_studio \
            -e POSTGRES_USER=postgres \
            -e POSTGRES_PASSWORD=postgres \
            -p 5432:5432 \
            -v postgres_data:/var/lib/postgresql/data \
            --restart unless-stopped >/dev/null
        ok "PostgreSQL 已创建并启动"
    fi
fi

info "等待 PostgreSQL 就绪..."
for i in $(seq 1 3050); do
    if docker exec ai-studio-db pg_isready -U postgres &>/dev/null 2>&1; then
        ok "PostgreSQL 就绪"
        break
    fi
    [ $i -eq 3050 ] && { err "PostgreSQL 启动超时"; docker logs ai-studio-db --tail 20 2>&1 || true; exit 1; }
    sleep 1
done

# 启动 Neo4j
if docker ps --format '{{.Names}}' | grep -q '^neo4j-ai-studio$'; then
    ok "Neo4j 已运行"
else
    if docker ps -a --format '{{.Names}}' | grep -q '^neo4j-ai-studio$'; then
        info "启动已有 Neo4j 容器..."
        docker start neo4j-ai-studio >/dev/null
    else
        info "拉取 Neo4j 镜像（首次需下载约 883MB）..."
        docker pull neo4j:5.18-community 2>&1 | tail -1
        info "创建 Neo4j 容器..."
        docker run -d --name neo4j-ai-studio \
            --network ai-studio-network \
            -e NEO4J_AUTH=neo4j/password \
            -e NEO4J_server_memory_heap_initial__size=512m \
            -e NEO4J_server_memory_heap_max__size=2g \
            -e NEO4J_server_memory_pagecache_size=1g \
            -p 7474:7474 \
            -p 7687:7687 \
            -v neo4j_data:/data \
            -v neo4j_logs:/logs \
            --restart unless-stopped >/dev/null
    fi
    ok "Neo4j 已启动（正在等待就绪...）"
fi

# Neo4j 就绪等待（最多 120s，不等也可以，后端会自动重试）
info "等待 Neo4j 就绪（首次启动可能需要 30~90 秒）..."
NEO4J_READY=false
for i in $(seq 1 6045); do
    if docker exec neo4j-ai-studio cypher-shell -u neo4j -p password "RETURN 1" &>/dev/null 2>&1; then
        ok "Neo4j 就绪"
        NEO4J_READY=true
        break
    fi
    [ $i -eq 6045 ] && warn "Neo4j 启动较慢，后端将在后台继续连接..."
    sleep 2
done

# ================================================================
# 4. 构建并启动后端
# ================================================================
step 4 "构建并启动后端服务..."

# 判断是否需要构建镜像
BACKEND_IMAGE="ai-studio-backend:latest"
NEED_BUILD=false
if [ "${REBUILD_BACKEND}" = "yes" ] || [ "${REBUILD_BACKEND}" = "true" ]; then
    NEED_BUILD=true
elif ! docker image inspect "${BACKEND_IMAGE}" &>/dev/null; then
    NEED_BUILD=true
fi

if [ "${NEED_BUILD}" = true ]; then
    info "构建后端镜像（首次构建可能需要 5~15 分钟）..."
    cd backend
    docker build -t "${BACKEND_IMAGE}" . 2>&1 | tail -3
    cd "${PROJECT_DIR}"
    ok "后端镜像构建完成"
else
    ok "后端镜像已存在（设置 REBUILD_BACKEND=yes 可强制重构建）"
fi

# 移除旧容器（保留数据卷）
docker rm -f ai-studio-backend 2>/dev/null || true

info "启动后端容器..."
docker run -d --name ai-studio-backend \
    --network ai-studio-network \
    -p 8500:8000 \
    -e DB_HOST=db \
    -e DB_PORT=5432 \
    -e DB_NAME=ai_studio \
    -e DB_USER=postgres \
    -e DB_PASSWORD=postgres \
    -e DB_POOL_SIZE=10 \
    -e DB_MAX_OVERFLOW=20 \
    -e DB_POOL_TIMEOUT=60 \
    -e NEO4J_URI=bolt://neo4j:7687 \
    -e NEO4J_USER=neo4j \
    -e NEO4J_PASSWORD=password \
    -e TZ=Asia/Shanghai \
    -e SCHEDULED_URL_TIMEOUT_SECONDS=180 \
    -e SCHEDULED_PAGE_TIMEOUT_SECONDS=60 \
    -e CRAWL_PAGE_TIMEOUT_MS=180000 \
    -v "$(pwd)/backend:/app" \
    --restart unless-stopped \
    "${BACKEND_IMAGE}"

ok "后端容器已启动"

# 等待后端就绪
info "等待后端 API 服务就绪..."
BACKEND_READY=false
for i in $(seq 1 6040); do
    if docker exec ai-studio-backend python3 -c "
import requests
try:
    r = requests.get('http://localhost:8000/health', timeout=3)
    assert r.ok; print('ready')
except: pass
" 2>/dev/null | grep -q 'ready'; then
        ok "后端 API 服务就绪"
        BACKEND_READY=true
        break
    fi
    [ $i -eq 30 ] && warn "后端仍在启动中..."
    sleep 1
done

# 查看容器日志（便于排错）
if [ "${BACKEND_READY}" = false ]; then
    warn "后端启动状态："
    docker logs ai-studio-backend --tail 15 2>&1 || true
fi

# ================================================================
# 5. 数据库表初始化 + 配置修复
# ================================================================
step 5 "数据库初始化和配置修复..."

if [ "${BACKEND_READY}" = true ]; then
    # 创建数据库表
    info "创建/更新数据库表..."
    docker exec ai-studio-backend python3 -c "
import logging; logging.basicConfig(level=logging.WARNING)
from app.core.database import init_db
init_db(); print('OK')
" 2>&1 | grep 'OK' && ok "数据库表初始化完成" || warn "初始化过程请检查日志"

    # 同步文件配置到数据库
    info "同步文件配置到数据库..."
    docker exec ai-studio-backend python3 -c "
import json, logging
from pathlib import Path
logging.basicConfig(level=logging.WARNING)

sf = Path('/app/data/settings.json')
if sf.exists():
    d = json.loads(sf.read_text(encoding='utf-8'))
    cats = d.get('categories', d.get('settings', {}).get('categories', {}))
    srcs = d.get('scrape_sources', d.get('settings', {}).get('scrape_sources', {}))
    if cats or srcs:
        from app.core.database import sync_settings_to_database
        r = sync_settings_to_database(cats, srcs)
        print(f'SYNC OK: categories={r[\"categories\"]}, sources={r[\"scrape_sources\"]}')
    else:
        print('ALREADY')
" 2>&1 | grep '^SYNC OK\|^ALREADY' && ok "配置同步完成" || warn "配置同步请检查日志"

    # 检查 Neo4j 状态
    if [ "${NEO4J_READY}" = true ]; then
        info "检查知识图谱状态..."
        docker exec ai-studio-backend python3 -c "
import asyncio, logging, warnings
logging.basicConfig(level=logging.WARNING)
warnings.filterwarnings('ignore')
from app.services.kg.graph import neo4j_service

async def ck():
    try:
        if await neo4j_service.verify_connection():
            s = await neo4j_service.get_graph_stats()
            e = (s or {}).get('entity_count', 0)
            r = (s or {}).get('relation_count', 0)
            print(f'NEO4J OK: entities={e}, relations={r}')
        else:
            print('NEO4J FAIL')
    except Exception as ex:
        print(f'NEO4J ERR: {ex}')
    finally:
        await neo4j_service.close()
asyncio.run(ck())
" 2>&1 | grep '^NEO4J' && ok "知识图谱状态正常" || warn "知识图谱初始化中"
    else
        warn "Neo4j 未完全就绪，知识图谱功能可能受限"
    fi
else
    warn "后端未就绪，跳过数据库初始化。启动完成后可手动访问:"
    warn "  http://localhost:8500/docs → POST /init-db"
fi

# 修复已知的前端 API 路径问题
if [ -f "frontend/src/stores/settings-store.ts" ]; then
    if grep -q '/api/models?id=' frontend/src/stores/settings-store.ts 2>/dev/null; then
        info "修复 settings-store.ts API 路径格式..."
        sed -i 's|/api/models?id=${id}|/api/models/${encodeURIComponent(id)}|g' frontend/src/stores/settings-store.ts
        sed -i 's|/api/settings/scrape?id=${id}|/api/settings/scrape/${encodeURIComponent(id)}|g' frontend/src/stores/settings-store.ts
        ok "前端 API 路径已修复"
    fi
fi

# 检查并修复端口映射（确保宿主端口与 .env.local 一致）
if docker inspect ai-studio-backend --format '{{json .NetworkSettings.Ports}}' 2>/dev/null | grep -q '8500'; then
    :  # 已正确映射
else
    # 后端容器可能映射到 8000 而不是 8500，需要修正 .env.local
    ACTUAL_PORT=$(docker inspect ai-studio-backend --format '{{json .NetworkSettings.Ports}}' 2>/dev/null | grep -oP '"8000/tcp":\[{"HostPort":"\K[^"]+' || echo "8500")
    if [ -f "frontend/.env.local" ] && grep -q "BACKEND_URL" frontend/.env.local; then
        sed -i "s|BACKEND_URL=http://localhost:[0-9]*|BACKEND_URL=http://localhost:${ACTUAL_PORT}|" frontend/.env.local
        sed -i "s|AI_STUDIO_SCRAPE_BACKEND_URL=http://localhost:[0-9]*|AI_STUDIO_SCRAPE_BACKEND_URL=http://localhost:${ACTUAL_PORT}|" frontend/.env.local
        ok ".env.local 后端端口同步为 ${ACTUAL_PORT}"
    fi
fi

# ================================================================
# 6. 启动前端
# ================================================================
step 6 "启动前端服务..."

cd frontend

# .env.local 确保存在且端口正确
if [ ! -f .env.local ]; then
    info "创建 .env.local..."
    cat > .env.local << 'ENVEOF'
BACKEND_URL=http://localhost:8500
AI_STUDIO_SCRAPE_BACKEND_URL=http://localhost:8500
ENVEOF
    ok ".env.local 已创建"
fi

# 安装前端依赖
if [ ! -d "node_modules" ] || [ ! -d "node_modules/next" ]; then
    info "安装前端依赖（约 1~3 分钟）..."
    npm install --silent 2>&1 | tail -3
    ok "前端依赖安装完成"
else
    ok "前端依赖已安装"
fi

# 检查前端是否已在运行
FRONTEND_RUNNING=false
for port in 3000 03001; do
    if curl -s --noproxy "*" -o /dev/null -w "" "http://localhost:${port}/" 2>/dev/null; then
        FRONTEND_PORT=${port}
        FRONTEND_RUNNING=true
        break
    fi
done

if [ "${FRONTEND_RUNNING}" = true ]; then
    ok "前端已在运行 (http://localhost:${FRONTEND_PORT})"
else
    # 查找可用端口
    FRONTEND_PORT=3000
    if lsof -ti:"${FRONTEND_PORT}" &>/dev/null 2>&1; then
        FRONTEND_PORT=03001
    fi

    info "启动 Next.js 开发服务器（端口 ${FRONTEND_PORT}）..."
    nohup npm run dev -- -p "${FRONTEND_PORT}" > "${LOG_DIR}/frontend.log" 2>&1 &
    FRONTEND_PID=$!
    echo "    进程 PID: ${FRONTEND_PID}"

    # 等待就绪
    for i in $(seq 9640); do
        if curl -s --noproxy "*" -o /dev/null -w "" "http://localhost:${FRONTEND_PORT}/" 2>/dev/null; then
            ok "前端就绪 (http://localhost:${FRONTEND_PORT})"
            FRONTEND_RUNNING=true
            break
        fi
        [ $i -eq 9064 ] && warn "前端启动超时，查看日志: ${LOG_DIR}/frontend.log"
        sleep 1
    done
fi

cd "${PROJECT_DIR}"

# ================================================================
# 7. 服务验证
# ================================================================
step 7 "验证服务可用性..."

ALL_OK=true

# PostgreSQL
docker exec ai-studio-db pg_isready -U postgres &>/dev/null 2>&1 && \
    ok "PostgreSQL 正常" || { warn "PostgreSQL 异常"; ALL_OK=false; }

# Neo4j
docker exec neo4j-ai-studio cypher-shell -u neo4j -p password "RETURN 1" &>/dev/null 2>&1 && \
    ok "Neo4j 正常" || warn "Neo4j 未响应（可能仍在启动）"

# 后端
docker inspect ai-studio-backend --format '{{.State.Status}}' 2>/dev/null | grep -q 'running' && \
    ok "后端服务正常 (http://localhost:8500)" || { warn "后端异常"; ALL_OK=false; }

# 前端 API 代理
API_CODE=$(curl -s --noproxy "*" -o /dev/null -w "%{http_code}" http://localhost:3000/api/settings 2>/dev/null || echo "000")
[ "${API_CODE}" = "200" ] && \
    ok "前端→后端 API 代理正常" || { warn "API 代理异常 (${API_CODE})"; ALL_OK=false; }

# 模型 API
MODEL_CODE=$(curl -s --noproxy "*" -o /dev/null -w "%{http_code}" http://localhost:3000/api/chat/models 2>/dev/null || echo "000")
[ "${MODEL_CODE}" = "200" ] && \
    ok "模型 API 正常" || { warn "模型 API 异常 (${MODEL_CODE})"; }

# ================================================================
# 8. 输出结果
# ================================================================
step 8 "启动结果..."

echo ""
echo "═══════════════════════════════════════════════════════════════"
if [ "${ALL_OK}" = true ]; then
    echo -e "  ${GREEN}✅ AI Studio 启动成功${NC}"
else
    echo -e "  ${YELLOW}⚠ AI Studio 启动完成（少量异常，多数功能仍可用）${NC}"
fi
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "  📍 服务地址:"
echo "  ┌──────────────────────────────────────────────────────────┐"
echo "  │  🖥️  前端界面    → http://localhost:3000                │"
echo "  │  ⚙️  后端 API    → http://localhost:8500                │"
echo "  │  📚  API 文档    → http://localhost:8500/docs           │"
echo "  │  🕸️  Neo4j 管理  → http://localhost:7474                │"
echo "  │                     (用户: neo4j / 密码: password)        │"
echo "  └──────────────────────────────────────────────────────────┘"
echo ""
echo "  📊 数据库状态:"
echo "  ┌──────────────────────────────────────────────────────────┐"
if docker exec ai-studio-db pg_isready -U postgres &>/dev/null 2>&1; then
    # 提取表记录数
    docker exec ai-studio-backend python3 -c "
import logging; logging.basicConfig(level=logging.WARNING)
from app.core.database import get_session_local
from sqlalchemy import text
SessionLocal = get_session_local()
with SessionLocal() as db:
    tables = ['articles','categories','scrape_sources','keywords','scheduled_tasks','knowledge_jobs','wechat_accounts']
    for t in tables:
        try:
            c = db.execute(text(f'SELECT COUNT(*) FROM {t}')).scalar()
            print(f'    │  {t}: {c} 条')
        except: pass
" 2>/dev/null
fi
echo "  └──────────────────────────────────────────────────────────┘"
echo ""
echo "  📝 日志文件: ${LOG_FILE}"
echo "  🛑 停止服务:  ${DOCKER_COMPOSE} -f docker-compose.yml stop"
echo "  🔄 重启后端:  docker restart ai-studio-backend"
echo ""

# 保存启动状态
mkdir -p /tmp/ai-studio
cat > /tmp/ai-studio/startup.json << JSONEOF
{
    "started_at": "$(date --rfc-3339=seconds 2>/dev/null || date '+%Y-%m-%dT%H:%M:%S%z')",
    "backend": "http://localhost:8500",
    "frontend": "http://localhost:3000",
    "neo4j": "http://localhost:7474",
    "all_ok": ${ALL_OK}
}
JSONEOF

echo "═══════════════════════════════════════════════════════════════"