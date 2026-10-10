"""直连阿里云 vs 经 DeepLX-Aliyun 转接的性能对比压测。

用法：先启动网关（DeepLXAliyun.exe 或 `uv run python main.py --no-tray`），
并在 config.json 里填好 AccessKey，然后 `uv run python bench.py`。

场景：10 个任务 × 每任务 2 个短语 = 20 次请求；两端都带 lru_cache。
第一轮每个文本两端各跑一遍（冷缓存），第二轮重复（缓存命中）。
转接端缓存存在服务端进程内，跨运行保留；要测"真·冷缓存"请先重启网关。
"""
import json
import statistics
import time
import uuid
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path

import requests

import aliyun

def _load_cfg():
    for p in (Path(__file__).parent / "config.json",
              Path(__file__).parent / "dist" / "config.json"):
        if p.exists():
            c = json.loads(p.read_text(encoding="utf-8"))
            if "在此填写" not in c.get("access_key_id", ""):
                return c
    raise SystemExit("未找到填好 AccessKey 的 config.json（项目目录或 dist/）")


cfg = _load_cfg()

GATEWAY = f"http://{cfg['host']}:{cfg['port']}/translate"

TASKS = [
    ("保存更改后再关闭吗？", "未保存的更改将会丢失。", "EN"),
    ("Network error, please retry.", "Connection timed out after 30s.", "ZH"),
    ("设置已成功更新。", "更改将在重启后生效。", "EN"),
    ("Invalid username or password.", "Account locked for 5 minutes.", "ZH"),
    ("文件正在上传…", "上传完成后会自动关闭窗口。", "EN"),
    ("Version 1.2.0 is now available.", "Click here to download the update.", "ZH"),
    ("确认删除这条记录吗？", "此操作无法撤销。", "EN"),
    ("Low disk space on drive C:", "Free up at least 500 MB to continue.", "ZH"),
    ("新消息已到达。", "点击查看全部通知。", "EN"),
    ("Printing job queued.", "Estimated time: 2 minutes.", "ZH"),
]
TEXTS = [(t, tgt) for a, b, tgt in TASKS for t in (a, b)]


def _direct_call(text, target):
    params = {
        "Action": "TranslateGeneral", "Version": "2018-10-12",
        "FormatType": "text", "SourceLanguage": "auto", "TargetLanguage": target.lower(),
        "SourceText": text, "Scene": cfg["scene"],
        "AccessKeyId": cfg["access_key_id"],
        "SignatureMethod": "HMAC-SHA1", "SignatureVersion": "1.0",
        "SignatureNonce": str(uuid.uuid4()),
        "Timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    params["Signature"] = aliyun.sign_params(params, cfg["access_key_secret"])
    r = requests.get(cfg["endpoint"], params=params, timeout=30)
    code = ET.fromstring(r.content).find(".//Code")
    if r.status_code != 200 or (code is not None and (code.text or "") != "200"):
        raise RuntimeError(f"direct failed: HTTP {r.status_code}")
    return True


@lru_cache(maxsize=2000)
def direct_cached(text, target):
    return _direct_call(text, target)


def direct_once(text, target):
    t0 = time.perf_counter()
    direct_cached(text, target)
    return (time.perf_counter() - t0) * 1000


def proxy_once(text, target):
    t0 = time.perf_counter()
    r = requests.post(
        GATEWAY,
        json={"text": text, "source_lang": "auto", "target_lang": target},
        timeout=30,
    )
    dt = (time.perf_counter() - t0) * 1000
    if r.json().get("code") != 200:
        raise RuntimeError(f"proxy failed: {r.text[:200]}")
    return dt


def stats(label, lat):
    print(f"[{label}] {len(lat)} 次  总 {sum(lat):.0f}ms  平均 {statistics.mean(lat):.1f}  "
          f"中位 {statistics.median(lat):.1f}  最慢 {max(lat):.1f}")


if __name__ == "__main__":
    # 预热网络（不进两端的测试缓存）
    _direct_call("网络预热", "en")
    requests.post(GATEWAY, json={"text": "网络预热", "source_lang": "auto",
                                 "target_lang": "EN"}, timeout=30)

    # 第一轮：每个文本两端各跑一遍（冷缓存）
    d, p = [], []
    for text, target in TEXTS:
        d.append(direct_once(text, target))
        p.append(proxy_once(text, target))
    stats("第一轮·直连带缓存（冷）", d)
    stats("第一轮·转接带缓存（冷）", p)

    # 第二轮：两端缓存均命中
    stats("第二轮·直连带缓存（命中）", [direct_once(t, g) for t, g in TEXTS])
    stats("第二轮·转接带缓存（命中）", [proxy_once(t, g) for t, g in TEXTS])
