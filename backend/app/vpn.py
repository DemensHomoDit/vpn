import json
import subprocess
import uuid as uuidlib
from pathlib import Path

from .config import settings


def _load_meta() -> dict:
    meta_path = Path(settings.singbox_dir) / "meta.json"
    return json.loads(meta_path.read_text())


def _run(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT).strip()
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"{cmd[0]} failed ({e.returncode}): {e.output}") from e


def new_uuid() -> str:
    return str(uuidlib.uuid4())


def add_user(uuid: str):
    _run(["sudo", "-n", settings.users_script, "add", uuid])


def del_user(uuid: str):
    _run(["sudo", "-n", settings.users_script, "del", uuid])


def build_client(uuid: str, name: str) -> tuple[str, str]:
    meta = _load_meta()
    out_json = f"/tmp/client-{name}.json"
    out_uri = f"/tmp/client-{name}.uri"
    _run([
        "python3", settings.gen_script,
        settings.vps_ip, str(settings.vps_port),
        uuid, meta["public_key"], meta["short_id"],
        name, out_json, out_uri,
    ])
    return Path(out_json).read_text(), Path(out_uri).read_text().strip()


def server_info() -> dict:
    meta = _load_meta()
    return {"ip": settings.vps_ip, "port": settings.vps_port, "public_key": meta["public_key"],
            "short_id": meta["short_id"]}