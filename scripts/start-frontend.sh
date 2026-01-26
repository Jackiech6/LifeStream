#!/usr/bin/env bash
# Build and run Next.js frontend on http://localhost:3000 (production mode).
# Use this for testing. Do NOT use "npm run dev"—it can cause blank pages (chunk errors).

set -e
cd "$(dirname "$0")/../frontend"

# Free port 3000 if something is using it (e.g. old npm run dev)
PORT=3000
if command -v lsof >/dev/null 2>&1; then
  PIDS=$(lsof -i :3000 -t 2>/dev/null || true)
  if [ -n "$PIDS" ]; then
    echo "Killing process(es) on port 3000: $PIDS"
    echo "$PIDS" | xargs kill -9 2>/dev/null || true
    sleep 3
  fi
  if lsof -i :3000 -t >/dev/null 2>&1; then
    echo "Port 3000 still in use. Starting on port 3001 instead."
    PORT=3001
  fi
fi

if [ ! -f .env.local ]; then
  echo "Creating .env.local with staging API URL..."
  echo "NEXT_PUBLIC_API_URL=https://4wq95qxnmb.execute-api.us-east-1.amazonaws.com/staging" > .env.local
fi

echo "Building frontend..."
rm -rf .next
NODE_ENV=production npm run build

# Use standalone server (bundles all server files; avoids MODULE_NOT_FOUND on some systems)
if [ -f .next/standalone/server.js ]; then
  cp -r .next/static .next/standalone/.next/static 2>/dev/null || true
  [ -d public ] && cp -r public .next/standalone/ 2>/dev/null || true
  echo ""
  echo "Starting LifeStream frontend at http://localhost:$PORT (PRODUCTION, standalone)"
  echo "If the browser shows 'Internal Server Error', check this terminal for the error message."
  echo ""
  exec env PORT="$PORT" sh -c 'cd .next/standalone && exec node server.js'
fi

# Fallback: next start (if standalone was not produced)
echo ""
echo "Starting LifeStream frontend at http://localhost:$PORT (PRODUCTION)"
echo "If the browser shows 'Internal Server Error', check this terminal for the error message."
echo ""
exec npx next start -p "$PORT"
