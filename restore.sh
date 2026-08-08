#!/bin/bash
# ===========================================
# AI Studio 数据恢复脚本
# ===========================================

set -e

if [ -z "$1" ]; then
    echo "用法: $0 <备份文件路径>"
    echo "示例: $0 ./backups/ai-studio-backup-20240101_120000.sql"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "错误: 文件不存在 - $BACKUP_FILE"
    exit 1
fi

echo "========================================"
echo "  AI Studio 数据恢复"
echo "========================================"
echo

echo "[1/4] 确认备份文件..."
LINE_COUNT=$(wc -l < "$BACKUP_FILE")
echo "      行数: $LINE_COUNT"

echo "[2/4] 等待数据库就绪..."
for i in {1..30}; do
    if docker exec ai-studio-db pg_isready -U postgres > /dev/null 2>&1; then
        echo "      数据库已就绪"
        break
    fi
    sleep 1
done

echo "[3/4] 清空现有数据..."
docker exec ai-studio-db psql -U postgres -d ai_studio -c "
    DROP SCHEMA public CASCADE;
    CREATE SCHEMA public;
    GRANT ALL ON SCHEMA public TO postgres;
    GRANT ALL ON SCHEMA public TO public;
" 2>/dev/null || true

echo "[4/4] 恢复数据..."
docker exec -i ai-studio-db psql -U postgres -d ai_studio < "$BACKUP_FILE" 2>/dev/null || true

echo
echo "========================================"
echo "  恢复完成！"
echo "========================================"
echo
echo "验证数据..."
docker exec ai-studio-db psql -U postgres -d ai_studio -c "SELECT 'articles' as tbl, COUNT(*) FROM articles UNION ALL SELECT 'categories', COUNT(*) FROM categories UNION ALL SELECT 'scrape_sources', COUNT(*) FROM scrape_sources;" 2>&1