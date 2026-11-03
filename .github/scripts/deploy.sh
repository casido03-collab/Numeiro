#!/usr/bin/env bash
set -euo pipefail
echo "🕐 $(date -u) — deploy start"

# The verified entrypoint checks source hashes embedded in the image.
# Always rebuild (Docker reuses unchanged layers), even for code-only releases.
# Build first so a build failure leaves the running service untouched.
echo "📦 Building verified bot image..."
docker compose build bot
docker compose up -d --no-deps --force-recreate bot

echo "✅ $(date -u) — done"
