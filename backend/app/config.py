import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    bot_token: str = ""
    admin_ids: list = field(default_factory=list)
    jwt_secret: str = ""
    vps_ip: str = ""
    vps_port: int = 443
    singbox_dir: str = "/etc/sing-box"
    users_script: str = "/root/vpn/server/users.sh"
    gen_script: str = "/root/vpn/server/gen-client-conf.py"
    db_path: str = "data/vpn.db"
    payment_provider: str = "manual"
    webapp_url: str = ""


def load_settings() -> Settings:
    s = Settings()
    s.bot_token = os.getenv("BOT_TOKEN", "")
    s.admin_ids = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
    s.jwt_secret = os.getenv("JWT_SECRET", "")
    s.vps_ip = os.getenv("VPS_IP", "")
    s.vps_port = int(os.getenv("VPS_PORT", "443"))
    s.singbox_dir = os.getenv("SINGBOX_DIR", s.singbox_dir)
    s.users_script = os.getenv("USERS_SCRIPT", s.users_script)
    s.gen_script = os.getenv("GEN_SCRIPT", s.gen_script)
    s.db_path = os.getenv("DB_PATH", s.db_path)
    s.payment_provider = os.getenv("PAYMENT_PROVIDER", s.payment_provider)
    s.webapp_url = os.getenv("WEBAPP_URL", "")
    return s


settings = load_settings()