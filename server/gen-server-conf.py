#!/usr/bin/env python3
import json
import secrets
import sys
import subprocess

CONF = "/etc/sing-box/config.json"
USERS_FILE = "/etc/sing-box/users.json"
META_FILE = "/etc/sing-box/meta.json"
PORT = 443
FALLBACK_HOST = "www.microsoft.com"
SHORT_ID_LEN = 8


def run(cmd):
    return subprocess.check_output(cmd, text=True).strip()


def render(fallback_host):
    users = json.load(open(USERS_FILE))["users"]
    meta = json.load(open(META_FILE))
    config = {
        "log": {"level": "info", "timestamp": True},
        "inbounds": [
            {
                "type": "vless",
                "tag": "vless-in",
                "listen": "::",
                "listen_port": PORT,
                "users": [{"uuid": u, "flow": "xtls-rprx-vision"} for u in users],
                "tls": {
                    "enabled": True,
                    "server_name": fallback_host,
                    "reality": {
                        "enabled": True,
                        "handshake": {"server": fallback_host, "server_port": 443},
                        "private_key": meta["private_key"],
                        "short_id": [meta["short_id"]],
                    },
                },
            }
        ],
        "outbounds": [{"type": "direct", "tag": "direct"}],
    }
    with open(CONF, "w") as f:
        json.dump(config, f, indent=2)


def main():
    if not any(a in sys.argv for a in ("--render", "--regen")):
        if "init" not in sys.argv:
            print("usage: gen-server-conf.py [init | --render]", file=sys.stderr)
            sys.exit(1)
    if "init" in sys.argv:
        if not subprocess.run(["test", "-f", USERS_FILE]).returncode == 0:
            json.dump({"users": []}, open(USERS_FILE, "w"))
        keypair = run(["sing-box", "generate", "reality-keypair"])
        keys = dict(line.split(": ", 1) for line in keypair.splitlines())
        meta = {
            "private_key": keys["PrivateKey"],
            "public_key": keys["PublicKey"],
            "short_id": secrets.token_hex(SHORT_ID_LEN // 2),
        }
        json.dump(meta, open(META_FILE, "w"))
        render(FALLBACK_HOST)
        print("keys generated, empty users list, config written")
    else:
        render(FALLBACK_HOST)
        print("config re-rendered")
    print("public key:  ", json.load(open(META_FILE))["public_key"])
    print("short id:    ", json.load(open(META_FILE))["short_id"])
    print("fallback:    ", FALLBACK_HOST)
    print("Restart: sudo systemctl restart sing-box")


if __name__ == "__main__":
    main()