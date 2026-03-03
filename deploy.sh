#!/bin/bash
set -e

echo "=== RPA Scheduler Docker 部署脚本 ==="

# 解析参数
REBUILD_FRONTEND=true
SKIP_FRONTEND_BUILD=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --skip-frontend)
      SKIP_FRONTEND_BUILD=true
      shift
      ;;
    --no-rebuild)
      REBUILD_FRONTEND=false
      shift
      ;;
    --help)
      echo "用法: ./deploy.sh [选项]"
      echo ""
      echo "选项:"
      echo "  --skip-frontend    跳过前端构建（前端代码没有修改时使用）"
      echo "  --no-rebuild       不重新构建 Docker 镜像"
      echo "  --help             显示帮助信息"
      echo ""
      echo "示例:"
      echo "  ./deploy.sh                          # 完整部署（构建前端+镜像）"
      echo "  ./deploy.sh --skip-frontend          # 只更新后端，不重新构建前端"
      echo "  ./deploy.sh --skip-frontend --no-rebuild  # 只重启容器"
      exit 0
      ;;
    *)
      echo "未知选项: $1"
      echo "使用 --help 查看帮助"
      exit 1
      ;;
  esac
done

# 创建必要目录
mkdir -p data logs ssl

# 构建前端
if [ "$SKIP_FRONTEND_BUILD" = false ]; then
  echo "构建前端..."
  cd frontend
  npm install
  npm run build
  cd ..
else
  echo "跳过前端构建..."
fi

# 构建并启动 Docker 容器
echo "启动 Docker 容器..."
docker-compose down

if [ "$REBUILD_FRONTEND" = true ]; then
  docker-compose build
fi

docker-compose up -d

echo "=== 部署完成 ==="
echo "访问地址: http://localhost 或 http://$(curl -s ifconfig.me 2>/dev/null || echo '服务器IP')"
echo ""
echo "常用命令:"
echo "  查看日志: docker-compose logs -f"
echo "  停止服务: docker-compose down"
echo "  重启服务: docker-compose restart"
