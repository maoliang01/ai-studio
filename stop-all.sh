#!/bin/bash
# AI Studio 停止脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "停止 AI Studio 服务..."

# 停止后端
if [ -f "$SCRIPT_DIR/.pids/backend.pid" ]; then
  PID=$(cat "$SCRIPT_DIR/.pids/backend.pid")
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    echo "✅ 后端已停止"
  fi
  rm "$SCRIPT_DIR/.pids/backend.pid"
fi

# 停止前端
if [ -f "$SCRIPT_DIR/.pids/frontend.pid" ]; then
  PID=$(cat "$SCRIPT_DIR/.pids/frontend.pid")
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    echo "✅ 前端已停止"
  fi
  rm "$SCRIPT_DIR/.pids/frontend.pid"
fi

# Firecrawl Docker 容器不停止，保持运行
echo ""
echo "📝 注意：Firecrawl Docker 服务仍在后台运行"
echo "   如需停止，执行: sudo docker stop \$(sudo docker ps -q --filter name=firecrawl)"
echo ""
echo "全部完成！"