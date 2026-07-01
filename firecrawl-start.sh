#!/bin/bash
# Firecrawl 启动脚本

cd /tmp/firecrawl

echo "正在启动 Firecrawl 服务..."
sudo docker compose up -d

echo ""
echo "等待服务启动..."
sleep 10

echo ""
echo "检查服务状态..."
sudo docker ps | grep -E "firecrawl|CONTAINER"

echo ""
echo "========================================"
echo "Firecrawl 服务已启动！"
echo "API 地址: http://localhost:3002"
echo "========================================"
echo ""
echo "测试 API（抓取网页）:"
echo 'curl -X POST http://localhost:3002/v1/scrape \
  -H "Content-Type: application/json" \
  -d "{\"url\":\"https://example.com\",\"formats\":[\"markdown\"]}"'