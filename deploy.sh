#!/bin/bash
set -e

echo "=== RPA Scheduler Docker 部署脚本 ==="

# 创建必要目录
mkdir -p data logs ssl

# 构建前端
echo "构建前端..."
cd frontend
npm install
npm run build
cd ..

# 构建并启动 Docker 容器
echo "启动 Docker 容器..."
docker-compose down
docker-compose build
docker-compose up -d

echo "=== 部署完成 ==="
echo "访问地址: http://localhost 或 http://$(curl -s ifconfig.me 2>/dev/null || echo '服务器IP')"
echo ""
echo "常用命令:"
echo "  查看日志: docker-compose logs -f"
echo "  停止服务: docker-compose down"
echo "  重启服务: docker-compose restart"
