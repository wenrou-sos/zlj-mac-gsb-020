#!/usr/bin/env bash
# =============================================================================
# 城市供水管网抢修管理平台 —— 一键启动脚本
#
# 用法:
#   ./start.sh              自动选择：优先 Docker Compose（PostgreSQL 全栈），
#                           未安装 Docker 时回退到本地模式（SQLite + uvicorn + vite）
#   ./start.sh docker       强制使用 Docker Compose
#   ./start.sh local        强制本地模式（自动创建 venv / 安装依赖）
#   ./start.sh test         运行后端测试（pytest，14 个用例，内存 SQLite）
#   ./start.sh stop         停止并清理（同时兼容 docker / local 两种模式）
# =============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
RUN_DIR="$ROOT_DIR/.run"
mkdir -p "$RUN_DIR"

BACKEND_URL="http://127.0.0.1:8000"
FRONTEND_URL="http://127.0.0.1:5173"
COMPOSE_URL="http://127.0.0.1:8080"

c_green() { printf "\033[32m%s\033[0m\n" "$*"; }
c_blue()  { printf "\033[34m%s\033[0m\n" "$*"; }
c_red()   { printf "\033[31m%s\033[0m\n" "$*"; }

have() { command -v "$1" >/dev/null 2>&1; }

# ---------------------------------------------------------------------------
docker_compose_cmd() {
  if docker compose version >/dev/null 2>&1; then echo "docker compose";
  elif command -v docker-compose >/dev/null 2>&1; then echo "docker-compose";
  else echo ""; fi
}

start_docker() {
  local dc
  dc="$(docker_compose_cmd)"
  if [ -z "$dc" ]; then
    c_red "未检测到 Docker，无法使用 docker 模式。可改用: ./start.sh local"
    exit 1
  fi
  c_blue "==> 使用 Docker Compose 启动 (React + FastAPI + PostgreSQL) ..."
  $dc -f "$ROOT_DIR/docker-compose.yml" up -d --build
  c_blue "==> 等待后端健康检查 ..."
  for i in $(seq 1 30); do
    if curl -fsS "$BACKEND_URL/health" >/dev/null 2>&1; then
      c_green "==> 后端已就绪"
      break
    fi
    sleep 2
    [ "$i" = "30" ] && { c_red "后端启动超时，请用 docker compose logs backend 查看"; exit 1; }
  done
  cat <<EOF

$(c_green '✅ 全栈已启动 (Docker 模式)')
  前端平台 : $COMPOSE_URL
  后端 API : $BACKEND_URL  (文档 $BACKEND_URL/docs)
  数据库   : PostgreSQL:5432 (watergrid/watergrid_pwd)
  停止服务 : ./start.sh stop
EOF
}

# ---------------------------------------------------------------------------
start_local() {
  c_blue "==> 本地模式启动（SQLite，无需 Docker）..."

  # ---- python deps --------------------------------------------------------
  local PY="$BACKEND_DIR/.venv/bin/python"
  local VENV_OK=0
  if [ -x "$PY" ] && "$PY" -m pip --version >/dev/null 2>&1; then
    VENV_OK=1
  elif have python3; then
    c_blue "==> 创建 Python 虚拟环境 ..."
    rm -rf "$BACKEND_DIR/.venv"
    if python3 -m venv "$BACKEND_DIR/.venv" >/dev/null 2>&1 \
       && "$BACKEND_DIR/.venv/bin/python" -m pip --version >/dev/null 2>&1; then
      VENV_OK=1
    else
      c_blue "==> venv 不可用（系统缺 python3-venv），回退到系统 Python + --user 安装"
      rm -rf "$BACKEND_DIR/.venv"
    fi
  else
    c_blue "==> 未找到 python3 虚拟环境支持，回退到系统 Python + --user 安装"
  fi

  if [ "$VENV_OK" = "1" ]; then
    "$PY" -m pip install -q --upgrade pip
    "$PY" -m pip install -q -r "$BACKEND_DIR/requirements.txt"
  else
    PY="python3"
    if ! "$PY" -c "import fastapi" >/dev/null 2>&1; then
      if ! "$PY" -m pip --version >/dev/null 2>&1; then
        c_blue "==> 系统 Python 缺少 pip，尝试 bootstrap ..."
        (cd /tmp && curl -fsS https://bootstrap.pypa.io/get-pip.py -o get-pip.py \
          && "$PY" get-pip.py --user --break-system-packages -q)
      fi
      "$PY" -m pip install -q --user --break-system-packages -r "$BACKEND_DIR/requirements.txt"
    fi
  fi

  # ---- node deps ----------------------------------------------------------
  if ! have node; then c_red "未找到 node，请安装 Node.js 18+"; exit 1; fi
  if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    c_blue "==> 安装前端依赖 ..."
    (cd "$FRONTEND_DIR" && npm install --no-audit --no-fund)
  fi

  # ---- run tests first ----------------------------------------------------
  c_blue "==> 运行后端测试 ..."
  (cd "$BACKEND_DIR" && "$PY" -m pytest -q)

  # ---- start backend ------------------------------------------------------
  c_blue "==> 启动 FastAPI (端口 8000) ..."
  setsid bash -c "
    cd '$BACKEND_DIR'
    DATABASE_URL='sqlite:///$BACKEND_DIR/watergrid.db' SEED_ON_STARTUP=true \
      '$PY' -m uvicorn app.main:app --host 0.0.0.0 --port 8000
  " >"$RUN_DIR/backend.log" 2>&1 &
  echo $! > "$RUN_DIR/backend.pid"

  # ---- start frontend -----------------------------------------------------
  c_blue "==> 启动 Vite 开发服务器 (端口 5173) ..."
  setsid bash -c "cd '$FRONTEND_DIR' && npm run dev" >"$RUN_DIR/frontend.log" 2>&1 &
  echo $! > "$RUN_DIR/frontend.pid"

  for i in $(seq 1 20); do
    curl -fsS "$BACKEND_URL/health" >/dev/null 2>&1 && break
    sleep 1
  done
  if ! curl -fsS "$BACKEND_URL/health" >/dev/null 2>&1; then
    c_red "后端启动失败，日志: $RUN_DIR/backend.log"; tail -20 "$RUN_DIR/backend.log"; exit 1
  fi

  cat <<EOF

$(c_green '✅ 平台已启动 (本地模式)')
  前端平台 : $FRONTEND_URL
  后端 API : $BACKEND_URL  (文档 $BACKEND_URL/docs)
  数据文件 : $BACKEND_DIR/watergrid.db
  后端日志 : $RUN_DIR/backend.log
  前端日志 : $RUN_DIR/frontend.log
  停止服务 : ./start.sh stop
EOF
}

# ---------------------------------------------------------------------------
stop_all() {
  c_blue "==> 停止服务 ..."
  local dc
  dc="$(docker_compose_cmd)"
  if [ -n "$dc" ] && $dc -f "$ROOT_DIR/docker-compose.yml" ps -q 2>/dev/null | grep -q .; then
    $dc -f "$ROOT_DIR/docker-compose.yml" down
    c_green "Docker 服务已停止"
  fi
  for svc in backend frontend; do
    if [ -f "$RUN_DIR/$svc.pid" ]; then
      local pid
      pid="$(cat "$RUN_DIR/$svc.pid")"
      # kill the whole process group (npm spawns vite/esbuild children)
      kill -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
      rm -f "$RUN_DIR/$svc.pid"
      c_green "$svc 已停止"
    fi
  done
  pkill -f "uvicorn app.main:app" 2>/dev/null || true
  pkill -f "vite" 2>/dev/null || true
  sleep 1
}

run_tests() {
  local PY="$BACKEND_DIR/.venv/bin/python"
  [ -x "$PY" ] || PY="python3"
  if [ "$PY" = "python3" ]; then
    python3 -m pytest --version >/dev/null 2>&1 || python3 -m pip install -q --user -r "$BACKEND_DIR/requirements.txt"
  fi
  (cd "$BACKEND_DIR" && $PY -m pytest -v)
}

# ---------------------------------------------------------------------------
MODE="${1:-auto}"
case "$MODE" in
  docker) start_docker ;;
  local)  start_local ;;
  test)   run_tests ;;
  stop)   stop_all ;;
  auto)
    if [ -n "$(docker_compose_cmd)" ] && docker info >/dev/null 2>&1; then
      start_docker
    else
      c_blue "未检测到可用 Docker（或守护进程未运行），自动切换本地模式"
      start_local
    fi
    ;;
  *)
    echo "用法: ./start.sh [auto|docker|local|test|stop]"; exit 1 ;;
esac
