#!/usr/bin/env bash
# Local practice database, so you can write and test SQL without the class server.
# Usage: scripts/local_db.sh start | stop | reset | psql
# Needs PostgreSQL installed (macOS: brew install postgresql@16). Data lives in .tools/ (git-ignored).
set -euo pipefail
cd "$(dirname "$0")/.."
export LC_ALL=en_US.UTF-8
PGBIN="${PGBIN:-$(ls -d /opt/homebrew/opt/postgresql@*/bin /usr/local/opt/postgresql@*/bin 2>/dev/null | head -1 || true)}"
export PATH="$PGBIN:$PATH"
DATA=.tools/pgdata
PORT=55440
SOCK=/tmp

start() {
  if [ ! -d "$DATA" ]; then
    mkdir -p .tools
    initdb -D "$DATA" -A trust --locale=en_US.UTF-8 >/dev/null
  fi
  pg_ctl -D "$DATA" -o "-p $PORT -k $SOCK -c listen_addresses=127.0.0.1" -l .tools/pg.log -w start >/dev/null || true
  psql -h 127.0.0.1 -p $PORT -d postgres -qtc "SELECT 1 FROM pg_roles WHERE rolname='dev'" | grep -q 1 \
    || psql -h 127.0.0.1 -p $PORT -d postgres -qc "CREATE ROLE dev LOGIN SUPERUSER"
  psql -h 127.0.0.1 -p $PORT -d postgres -qtc "SELECT 1 FROM pg_database WHERE datname='proj1part2'" | grep -q 1 \
    || { psql -h 127.0.0.1 -p $PORT -d postgres -qc "CREATE DATABASE proj1part2 OWNER dev"; load; }
  echo "Local database is running on port $PORT."
  echo "Use in .env:  DB_USER=dev  DB_PASSWORD=dev  DB_HOST=127.0.0.1  DB_PORT=$PORT  DB_NAME=proj1part2"
}
load() {
  psql -h 127.0.0.1 -p $PORT -U dev -d proj1part2 -v ON_ERROR_STOP=1 -q -f db/schema.sql
  psql -h 127.0.0.1 -p $PORT -U dev -d proj1part2 -v ON_ERROR_STOP=1 -q -f db/data.sql
}
case "${1:-}" in
  start) start ;;
  stop) pg_ctl -D "$DATA" stop ;;
  reset) psql -h 127.0.0.1 -p $PORT -d postgres -qc "DROP DATABASE IF EXISTS proj1part2" -c "CREATE DATABASE proj1part2 OWNER dev"; load; echo "Reset to the Part 2 data." ;;
  psql) psql -h 127.0.0.1 -p $PORT -U dev -d proj1part2 ;;
  *) echo "usage: $0 start|stop|reset|psql"; exit 1 ;;
esac
