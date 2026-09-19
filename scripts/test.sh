#!/usr/bin/env bash
# 一键运行全部测试：后端 pytest（SQLite 隔离库）+ 前端生产构建
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 [1/2] 后端 API 测试（pytest）"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd "$ROOT/backend"

# Prefer an isolated virtualenv; fall back to the user's interpreter.
VENV_OK=0
if [ -x ".venv/bin/python" ] && .venv/bin/python -c "import pip" >/dev/null 2>&1; then
  VENV_OK=1
elif python3 -c "import venv, ensurepip" >/dev/null 2>&1 && python3 -m venv .venv >/dev/null 2>&1 \
     && .venv/bin/python -c "import pip" >/dev/null 2>&1; then
  VENV_OK=1
else
  rm -rf .venv
fi

if [ "$VENV_OK" -eq 1 ]; then
  # shellcheck disable=SC1091
  . .venv/bin/activate
  PY=python
  python -m pip install --quiet --upgrade pip || true
  pip install --quiet -r requirements.txt
else
  echo "ℹ️  python venv 不可用，改用用户级 pip 安装依赖"
  if ! python3 -m pip --version >/dev/null 2>&1; then
    echo "⏳ 系统缺少 pip，正在通过 get-pip.py 引导…"
    TMP_GETPIP="$(mktemp)"
    if command -v curl >/dev/null 2>&1; then
      curl -sS https://bootstrap.pypa.io/get-pip.py -o "$TMP_GETPIP"
    else
      wget -qO "$TMP_GETPIP" https://bootstrap.pypa.io/get-pip.py
    fi
    python3 "$TMP_GETPIP" --user --break-system-packages
    rm -f "$TMP_GETPIP"
  fi
  python3 -m pip install --quiet --user --break-system-packages -r requirements.txt \
    || python3 -m pip install --quiet --user -r requirements.txt
  PY=python3
fi

export WATER_DATABASE_URL="sqlite:////tmp/watergrid_test_$$.db"
export WATER_SEED_ON_STARTUP="true"

cleanup() { rm -f "/tmp/watergrid_test_$$.db"; }
trap cleanup EXIT

"$PY" -m pytest tests/ -v
TEST_RC=$?

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🏗  [2/2] 前端构建检查（vite build）"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd "$ROOT/frontend"
if [ ! -d node_modules ]; then
  npm install --no-audit --no-fund
fi
npm run build

echo ""
if [ "$TEST_RC" -eq 0 ]; then
  echo "🎉 全部测试与构建检查通过。"
else
  echo "❌ 存在失败的测试。"
  exit "$TEST_RC"
fi
