import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    bot_token: str = ""
    admin_ids: list = field(default_factory=list)
    jwt_secret: str = ""
    # Marzban
    marzban_url: str = "http://127.0.0.1:8000"
    marzban_username: str = ""
    marzban_password: str = ""
    inbound_tag: str = "VLESS-REALITY"
    marzban_public_url: str = ""  # публичный адрес подписок, напр. http://IP:8000
    # Reality-параметры для сборки vless:// ссылок
    vps_ip: str = ""
    vps_port: int = 443
    reality_sni: str = "dl.google.com"
    reality_pbk: str = ""
    reality_sid: str = ""
    db_path: str = "data/vpn.db"
    payment_provider: str = "manual"
    webapp_url: str = ""


def load_settings() -> Settings:
    s = Settings()
    s.bot_token = os.getenv("BOT_TOKEN", "")
    s.admin_ids = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
    s.jwt_secret = os.getenv("JWT_SECRET", "")
    s.marzban_url = os.getenv("MARZBAN_URL", s.marzban_url)
    s.marzban_username = os.getenv("MARZBAN_USERNAME", "")
    s.marzban_password = os.getenv("MARZBAN_PASSWORD", "")
    s.inbound_tag = os.getenv("MARZBAN_INBOUND_TAG", s.inbound_tag)
    s.marzban_public_url = os.getenv("MARZBAN_PUBLIC_URL", "").rstrip("/")
    s.vps_ip = os.getenv("VPS_IP", "")
    s.vps_port = int(os.getenv("VPS_PORT", "443"))
    s.reality_sni = os.getenv("REALITY_SNI", s.reality_sni)
    s.reality_pbk = os.getenv("REALITY_PBK", "")
    s.reality_sid = os.getenv("REALITY_SID", "")
    s.db_path = os.getenv("DB_PATH", s.db_path)
    s.payment_provider = os.getenv("PAYMENT_PROVIDER", s.payment_provider)
    s.webapp_url = os.getenv("WEBAPP_URL", "")
    return s


settings = load_settings()
