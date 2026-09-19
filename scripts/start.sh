#!/usr/bin/env bash
# 城市供水管网抢修管理平台 —— 一键启动（Docker Compose）
set -euo pipefail
cd "$(dirname "$0")/.."

# Pick the available compose command
if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE="docker-compose"
else
  echo "❌ 未检测到 Docker Compose，请先安装 Docker Desktop / docker-compose。"
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "❌ Docker 守护进程未运行，请先启动 Docker。"
  exit 1
fi

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-8080}"

echo "🐳 构建并启动：PostgreSQL + FastAPI 后端 + React 前端 …"
$COMPOSE up -d --build

echo "⏳ 等待后端健康检查通过 …"
TRIES=0
until curl -sf "http://localhost:${BACKEND_PORT}/health" >/dev/null 2>&1; do
  TRIES=$((TRIES + 1))
  if [ "$TRIES" -ge 40 ]; then
    echo "❌ 后端启动超时，可运行 \`docker compose logs backend\` 查看日志。"
    exit 1
  fi
  sleep 2
done

echo ""
echo "✅ 平台已启动："
echo "   🌐 前端控制台 : http://localhost:${FRONTEND_PORT}"
echo "   ⚙️  后端 API   : http://localhost:${BACKEND_PORT}"
echo "   📖 接口文档   : http://localhost:${BACKEND_PORT}/docs"
echo ""
echo "查看日志: docker compose logs -f"
echo "停止平台: ./scripts/stop.sh"
