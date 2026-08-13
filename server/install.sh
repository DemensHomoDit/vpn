#!/usr/bin/env bash
set -euo pipefail

ARCH=$(uname -m)
case "$ARCH" in
  x86_64) BIN_ARCH=amd64 ;;
  aarch64) BIN_ARCH=arm64 ;;
  *) echo "unsupported arch: $ARCH" >&2; exit 1 ;;
esac

apt-get update
apt-get install -y curl jq

LATEST=$(curl -fsSL https://api.github.com/repos/SagerNet/sing-box/releases/latest | jq -r .tag_name)
URL="https://github.com/SagerNet/sing-box/releases/download/${LATEST}/sing-box-${LATEST#v}-linux-${BIN_ARCH}.tar.gz"
echo "Downloading sing-box ${LATEST}..."
curl -fsSL -o /tmp/sing-box.tar.gz "$URL"
mkdir -p /tmp/sing-box-extract
tar -xzf /tmp/sing-box.tar.gz -C /tmp/sing-box-extract
install -m 755 /tmp/sing-box-extract/sing-box-*/sing-box /usr/local/bin/sing-box
rm -rf /tmp/sing-box.tar.gz /tmp/sing-box-extract

mkdir -p /etc/sing-box
if [ ! -f /etc/systemd/system/sing-box.service ]; then
  cat > /etc/systemd/system/sing-box.service <<EOF
[Unit]
Description=sing-box proxy server
After=network.target

[Service]
ExecStart=/usr/local/bin/sing-box run -c /etc/sing-box/config.json
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
fi

sysctl -w net.ipv4.ip_forward=1
grep -q "net.ipv4.ip_forward" /etc/sysctl.conf || echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf

ufw allow 22/tcp
ufw allow 443/tcp
ufw --force enable

echo "OK: sing-box ${LATEST} installed. Next: sudo python3 gen-server-conf.py"
sing-box version