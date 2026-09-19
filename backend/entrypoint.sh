#!/bin/sh
# Wait for PostgreSQL to accept connections, then start the API.
set -e

MAX_TRIES=${DB_WAIT_MAX_TRIES:-30}
TRIES=0

until python -c "
import os, sys, time
from sqlalchemy import create_engine, text
url = os.environ['WATER_DATABASE_URL']
engine = create_engine(url)
for i in range(3):
    try:
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        sys.exit(0)
    except Exception:
        time.sleep(1)
sys.exit(1)
"; do
  TRIES=$((TRIES + 1))
  if [ "$TRIES" -ge "$MAX_TRIES" ]; then
    echo "⚠️  数据库等待超时（${MAX_TRIES} 次），仍然尝试启动…"
    break
  fi
  echo "⏳ 等待 PostgreSQL 就绪… (${TRIES}/${MAX_TRIES})"
  sleep 2
done

echo "🚀 启动供水管网抢修管理 API"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
