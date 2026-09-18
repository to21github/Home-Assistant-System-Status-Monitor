#!/bin/sh
set -e

# HA 选项 port 和 INGRESS_PORT 注入端口；默认 8099
PORT="${PORT:-${INGRESS_PORT:-8099}}"

echo "系统状态监控启动中，端口: $PORT"
exec gunicorn -w 1 -b "0.0.0.0:${PORT}" --timeout 30 --access-logfile - "main:app"
