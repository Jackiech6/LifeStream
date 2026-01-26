#!/usr/bin/env bash
# Kill whatever is on port 3000, then start the LifeStream frontend.
# Run this in your own terminal (e.g. from the project root).

set -e
cd "$(dirname "$0")/.."

echo "Freeing port 3000..."
for _ in 1 2 3; do
  PIDS=$(lsof -i :3000 -t 2>/dev/null || true)
  [ -z "$PIDS" ] && break
  echo "  Killing: $PIDS"
  echo "$PIDS" | xargs kill -9 2>/dev/null || true
  sleep 2
done

if lsof -i :3000 -t >/dev/null 2>&1; then
  echo "Port 3000 still in use. start-frontend.sh will use 3001 if needed."
else
  echo "Port 3000 is free."
fi
echo ""

exec ./scripts/start-frontend.sh
