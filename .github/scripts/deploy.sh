#!/usr/bin/env bash
set -e
echo "🕐 $(date -u) — deploy start"

if git diff HEAD~1 --name-only | grep -qE "requirements.txt|Dockerfile|docker-compose.yml|pyproject.toml|poetry.lock"; then
  echo "📦 Dependencies changed — rebuilding image..."
  docker compose up -d --build bot
else
  echo "⚡ Code-only change — fast restart..."
  docker compose restart bot
fi

echo "✅ $(date -u) — done"
