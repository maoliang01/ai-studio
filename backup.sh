#!/bin/bash
# ===========================================
# AI Studio 数据备份脚本
# ===========================================

set -e

BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/ai-studio-backup-${TIMESTAMP}.sql"

mkdir -p "$BACKUP_DIR"

echo "========================================"
echo "  AI Studio 数据备份"
echo "========================================"
echo

echo "[1/3] 备份 PostgreSQL 数据..."
docker exec ai-studio-db pg_dump -U postgres ai_studio > "$BACKUP_FILE"
echo "      已保存到: $BACKUP_FILE"

echo "[2/3] 备份配置和数据统计..."
docker exec ai-studio-db psql -U postgres -d ai_studio -c "COPY (SELECT COUNT(*) FROM articles) TO STDOUT;" >> "$BACKUP_FILE"
echo "      文章数量: $(tail -1 < "$BACKUP_FILE")"

echo "[3/3] 清理旧备份（保留最近10个）..."
cd "$BACKUP_DIR"
ls -t ai-studio-backup-*.sql 2>/dev/null | tail -n +11 | xargs rm -f 2>/dev/null || true
cd -

echo
echo "========================================"
echo "  备份完成！"
echo "========================================"
echo
echo "备份文件: $BACKUP_FILE"
echo ""
echo "在新设备部署时："
echo "  1. 启动服务: ./start.sh"
echo "  2. 恢复数据: ./restore.sh $BACKUP_FILE"