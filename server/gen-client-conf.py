#!/usr/bin/env python3
import json
import sys

RU_DOMAINS_SRS = "https://raw.githubusercontent.com/itdoginfo/allow-domains/master/src/domains/Russia-domains-lumped.srs"
RU_IPS_SRS = "https://raw.githubusercontent.com/itdoginfo/allow-domains/master/src/domains/Russia-ips-lumped.srs"
GEOSITE_RU_SRS = "https://raw.githubusercontent.com/itdoginfo/allow-domains/master/src/domains/geosite-ru.srs"
FALLBACK_HOST = "dl.google.com"
FINGERPRINT = "chrome"
UPDATE_INTERVAL = "1d"


def singbox_config(server, port, uuid, public_key, short_id, fallback_host=None):
    host = fallback_host or FALLBACK_HOST
    rule_sets = [
        {"type": "remote", "tag": "ru-domains", "url": RU_DOMAINS_SRS, "format": "binary", "update_interval": UPDATE_INTERVAL},
        {"type": "remote", "tag": "ru-ips", "url": RU_IPS_SRS, "format": "binary", "update_interval": UPDATE_INTERVAL},
        {"type": "remote", "tag": "geosite-ru", "url": GEOSITE_RU_SRS, "format": "binary", "update_interval": UPDATE_INTERVAL},
    ]
    return {
        "log": {"level": "info"},
        "dns": {
            "servers": [
                {"tag": "remote", "address": "https://1.1.1.1/dns-query"},
                {"tag": "local", "address": "local", "detour": "direct"},
            ],
            "rules": [
                {"rule_set": ["ru-domains", "geosite-ru"], "server": "local"},
                {"rule_set": ["ru-ips"], "server": "local"},
                {"query_type": ["A", "AAAA"], "server": "remote"},
            ],
            "strategy": "ipv4_only",
        },
        "inbounds": [
            {"type": "tun", "tag": "tun", "interface_name": "tun0", "mtu": 1500, "auto_route": True, "strict_route": True, "stack": "system"}
        ],
        "outbounds": [
            {
                "type": "vless",
                "tag": "proxy",
                "server": server,
                "server_port": port,
                "uuid": uuid,
                "flow": "xtls-rprx-vision",
                "tls": {
                    "enabled": True,
                    "server_name": host,
                    "utls": {"enabled": True, "fingerprint": FINGERPRINT},
                    "reality": {"enabled": True, "public_key": public_key, "short_id": short_id},
                },
            },
            {"type": "direct", "tag": "direct"},
            {"type": "block", "tag": "block"},
        ],
        "route": {
            "rules": [
                {"rule_set": ["ru-domains", "geosite-ru"], "outbound": "direct"},
                {"rule_set": ["ru-ips"], "outbound": "direct"},
                {"ip_cidr": ["geoip:private"], "outbound": "direct"},
            ],
            "rule_set": rule_sets,
            "auto_detect_interface": True,
            "final": "proxy",
        },
    }


def vless_uri(server, port, uuid, public_key, short_id, name, fallback_host=None):
    host = fallback_host or FALLBACK_HOST
    params = [
        "encryption=none",
        "security=reality",
        f"sni={host}",
        f"fp={FINGERPRINT}",
        f"pbk={public_key}",
        f"sid={short_id}",
        "type=tcp",
        "headerType=none",
        "flow=xtls-rprx-vision",
    ]
    return f"vless://{uuid}@{server}:{port}?{'&'.join(params)}#{name}"


def main():
    args = sys.argv[1:]
    if len(args) < 5:
        print("usage: gen-client-conf.py SERVER PORT UUID PUBKEY SHORTID [NAME] [OUT_JSON] [OUT_URI]", file=sys.stderr)
        sys.exit(1)
    server, port, uuid, pubkey, short_id = args[0], int(args[1]), args[2], args[3], args[4]
    name = args[5] if len(args) > 5 else "my-vpn"
    out_json = args[6] if len(args) > 6 else None
    out_uri = args[7] if len(args) > 7 else None
    cfg = json.dumps(singbox_config(server, port, uuid, pubkey, short_id), indent=2)
    uri = vless_uri(server, port, uuid, pubkey, short_id, name)
    if out_json:
        open(out_json, "w").write(cfg + "\n")
        open(out_uri, "w").write(uri + "\n") if out_uri else None
    else:
        print(cfg)
        print()
        print(uri)


if __name__ == "__main__":
    main()
