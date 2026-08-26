#!/usr/bin/env bash
# Updates the application while preserving machine-local secrets in backend/.env.
set -euo pipefail

REPO_DIR="${REPO_DIR:-/root/vpn}"
cd "$REPO_DIR"

test -f backend/.env || { echo "backend/.env is missing; update cancelled" >&2; exit 1; }
test -z "$(git status --porcelain)" || { echo "local changes found; update cancelled" >&2; exit 1; }

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
