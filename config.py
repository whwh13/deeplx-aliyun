import json
import sys
from pathlib import Path

DEFAULTS = {
    "host": "127.0.0.1",
    "port": 5188,
    "endpoint": "https://mt.aliyuncs.com",
    "region": "cn-hangzhou",
    "scene": "general",
    "access_key_id": "",
    "access_key_secret": "",
}

EXAMPLE = {
    "host": "127.0.0.1",
    "port": 5188,
    "endpoint": "https://mt.aliyuncs.com",
    "region": "cn-hangzhou",
    "scene": "general",
    "access_key_id": "在此填写 AccessKey ID",
    "access_key_secret": "在此填写 AccessKey Secret",
}


def config_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "config.json"
    return Path(__file__).parent / "config.json"


def load_config() -> dict:
    path = config_path()
    if not path.exists():
        path.write_text(
            json.dumps(EXAMPLE, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    return {**DEFAULTS, **data}
