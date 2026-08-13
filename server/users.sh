#!/usr/bin/env bash
set -euo pipefail

USERS_FILE=/etc/sing-box/users.json
RENDER=/etc/sing-box/render.sh

write_render() {
  cat > "$RENDER" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
python3 /root/vpn/server/gen-server-conf.py --render
systemctl restart sing-box
EOF
  chmod +x "$RENDER"
}

add_user() {
  local uuid=$1
  python3 - "$USERS_FILE" "$uuid" <<'PY'
import json, sys
path, uuid = sys.argv[1], sys.argv[2]
data = json.load(open(path))
if uuid not in data["users"]:
    data["users"].append(uuid)
    json.dump(data, open(path, "w"))
PY
  write_render
  bash "$RENDER"
  echo "user added: $uuid"
}

del_user() {
  local uuid=$1
  python3 - "$USERS_FILE" "$uuid" <<'PY'
import json, sys
path, uuid = sys.argv[1], sys.argv[2]
data = json.load(open(path))
if uuid in data["users"]:
    data["users"].remove(uuid)
    json.dump(data, open(path, "w"))
PY
  write_render
  bash "$RENDER"
  echo "user removed: $uuid"
}

case "${1:-}" in
  add) add_user "${2:?uuid}";;
  del) del_user "${2:?uuid}";;
  list) cat "$USERS_FILE";;
  *) echo "usage: $0 {add UUID | del UUID | list}" >&2; exit 1;;
esac