#!/usr/bin/env bash
# Установка Marzban (Xray + VLESS Reality) в Docker. Использование:
#   sudo bash server/install.sh <marzban_admin> <admin_password>
set -euo pipefail

ADMIN_USER="${1:?usage: install.sh <admin_user> <admin_password>}"
ADMIN_PASS="${2:?usage: install.sh <admin_user> <admin_password>}"
MARZBAN_DIR=/opt/marzban

apt-get update
apt-get install -y ca-certificates curl git ufw

if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi
docker compose version >/dev/null 2>&1 || {
  echo "docker compose plugin missing" >&2
  exit 1
}

mkdir -p "$MARZBAN_DIR"
cd "$MARZBAN_DIR"
if [ ! -f docker-compose.yml ]; then
cat > docker-compose.yml <<'EOF'
services:
  marzban:
    image: gozargah/marzban:latest
    restart: always
    env_file: .env
    network_mode: host
    volumes:
      - /var/lib/marzban:/var/lib/marzban
EOF
fi

ufw allow 22/tcp
ufw allow 443/tcp
ufw allow 8000/tcp   # подписки/панель Marzban (HTTP)
ufw --force enable

docker compose pull
docker compose up -d
sleep 10

# sudo-администратор панели (повторный запуск просто сообщит, что существует)
docker compose exec -T marzban marzban cli admin create-sudo-admin \
  --username "$ADMIN_USER" --password "$ADMIN_PASS" || true

# Reality-ключи
if [ ! -f /root/marzban-x25519.txt ]; then
  KEYS=$(docker compose exec -T marzban marzban core-x25519 2>/dev/null \
    || docker compose exec -T marzban xray x25519)
  echo "$KEYS" > /root/marzban-x25519.txt
fi
cat /root/marzban-x25519.txt

echo
echo "Готово. Дальше:"
echo "1. Отредактируйте /var/lib/marzban/xray_config.json: инбаунд VLESS на 443,"
echo "   security=reality, dest/sni=dl.google.com:443, fingerprint chrome,"
echo "   flow xtls-rprx-vision, shortIds из /root/marzban-x25519.txt."
echo "2. docker compose restart и проверьте: curl http://127.0.0.1:8000/api/system"
echo "3. Значения PBK/SID впишите в /root/vpn/backend/.env (REALITY_PBK, REALITY_SID)."
