#!/bin/bash
# ===========================================
# AI Studio 停止脚本
# ===========================================

echo "正在暂停 AI Studio 服务..."
docker compose -f docker-compose-local-db.yml stop
echo "服务已暂停"
echo ""
echo "注意: SQLite 数据保存在 backend/data/ai_studio.db"
echo "Neo4j 数据保存在 Docker volume 中"
echo ""
echo "下次启动: ./start.sh"