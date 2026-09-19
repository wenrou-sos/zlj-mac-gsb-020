#!/usr/bin/env bash
# 停止并清理城市供水管网抢修管理平台容器（默认保留数据库数据卷）
set -euo pipefail
cd "$(dirname "$0")/.."

if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
else
  COMPOSE="docker-compose"
fi

PURGE="${1:-}"

echo "🛑 停止容器 …"
$COMPOSE down

if [ "$PURGE" = "--purge" ]; then
  echo "🗑  同时删除数据库数据卷 …"
  $COMPOSE down -v || true
fi

echo "✅ 已停止。重新启动请运行 ./scripts/start.sh"
