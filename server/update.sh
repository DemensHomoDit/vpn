#!/usr/bin/env bash
# Updates the application while preserving machine-local secrets in backend/.env.
set -euo pipefail

REPO_DIR="${REPO_DIR:-/root/vpn}"
cd "$REPO_DIR"

test -f backend/.env || { echo "backend/.env is missing; update cancelled" >&2; exit 1; }
test -z "$(git status --porcelain)" || { echo "local changes found; update cancelled" >&2; exit 1; }

# Marzban must listen on 0.0.0.0:8000 (клиентские подписки http://IP:8000);
# env инжектится только при создании контейнера, поэтому при ошибке — recreate
if command -v ss >/dev/null \
   && ss -tln | grep -q '127\.0\.0\.1:8000' \
   && ! ss -tln | grep -qE '(0\.0\.0\.0|\*):8000'; then
  echo "marzban bound to 127.0.0.1 only; recreating container" >&2
  docker compose -f /opt/marzban/docker-compose.yml up -d --force-recreate || true
  sleep 10
fi

git fetch --prune origin
if [ "$(git rev-parse HEAD)" = "$(git rev-parse '@{u}')" ]; then
  echo "Already up to date"
  exit 0
fi

git merge --ff-only '@{u}'
backend/.venv/bin/pip install --disable-pip-version-check -r backend/requirements.txt
( cd webapp && npm ci && npm run build )
systemctl restart vpn-api.service vpn-bot.service
echo "Updated to $(git rev-parse --short HEAD)"
