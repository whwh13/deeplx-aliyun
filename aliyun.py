import base64
import hashlib
import hmac
import threading
import time
import urllib.parse
import uuid
import xml.etree.ElementTree as ET
from functools import lru_cache

import requests

# 线程局部会话：ThreadingHTTPServer 每条客户端连接一个线程，
# 会话在该线程内复用与阿里云的 TLS 连接；trust_env=False 跳过
# 每请求一次的注册表系统代理探测（endpoint 固定走直连）。
_thread = threading.local()


def _session() -> requests.Session:
    s = getattr(_thread, "session", None)
    if s is None:
        s = requests.Session()
        s.trust_env = False
        adapter = requests.adapters.HTTPAdapter(pool_maxsize=16)
        s.mount("https://", adapter)
        _thread.session = s
    return s

# DeepLX 大写语种 → 阿里云小写语种（未列出的按小写直传）
LANG_MAP = {
    "AR": "ar", "BG": "bg", "CS": "cs", "DA": "da", "DE": "de", "EL": "el",
    "EN": "en", "ES": "es", "ET": "et", "FI": "fi", "FR": "fr", "HU": "hu",
    "ID": "id", "IT": "it", "JA": "ja", "KO": "ko", "LT": "lt", "LV": "lv",
    "MS": "ms", "NB": "nb", "NL": "nl", "PL": "pl", "PT": "pt", "RO": "ro",
    "RU": "ru", "SK": "sk", "SL": "sl", "SV": "sv", "TH": "th", "TR": "tr",
    "UK": "uk", "VI": "vi", "ZH": "zh", "ZH-TW": "zh-tw", "AUTO": "auto",
}

MAX_CHARS = 5000


def normalize_lang(code: str) -> str:
    return LANG_MAP.get(code.upper(), code.lower())


def _percent_encode(s: str) -> str:
    return urllib.parse.quote(s, safe="-_.~")


def sign_params(params: dict, access_key_secret: str) -> str:
    sorted_pairs = sorted(
        (_percent_encode(k), _percent_encode(v)) for k, v in params.items()
    )
    query = "&".join(f"{k}={v}" for k, v in sorted_pairs)
    string_to_sign = "GET&%2F&" + _percent_encode(query)
    digest = hmac.new(
        (access_key_secret + "&").encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


def split_text(text: str, max_len: int = 4800) -> list[str]:
    if len(text) <= max_len:
        return [text]
    chunks = []
    rest = text
    while len(rest) > max_len:
        window = rest[:max_len]
        # 优先在段落/句子边界断开，避免拆散句子
        cut = max(window.rfind("\n"), window.rfind("。"), window.rfind(". "), 0)
        if cut < max_len // 2:
            cut = max_len
        else:
            cut += 1
        chunks.append(rest[:cut])
        rest = rest[cut:]
    if rest:
        chunks.append(rest)
    return chunks


class AliyunMtError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def translate(
    text: str,
    source_lang: str,
    target_lang: str,
    cfg: dict,
    timeout: float = 30.0,
) -> tuple[str, str]:
    """返回 (译文, 检测到的源语言)。出错抛 AliyunMtError。"""
    src = normalize_lang(source_lang)
    tgt = normalize_lang(target_lang)
    if not text:
        return "", ""
    return _translate_cached(
        text, src, tgt,
        cfg["endpoint"], cfg["scene"],
        cfg["access_key_id"], cfg["access_key_secret"],
        timeout,
    )


@lru_cache(maxsize=2000)
def _translate_cached(
    text: str,
    src: str,
    tgt: str,
    endpoint: str,
    scene: str,
    ak_id: str,
    ak_secret: str,
    timeout: float,
) -> tuple[str, str]:
    detected = ""
    parts = []
    for chunk in split_text(text):
        params = {
            "Action": "TranslateGeneral",
            "Version": "2018-10-12",
            "FormatType": "text",
            "SourceLanguage": src,
            "TargetLanguage": tgt,
            "SourceText": chunk,
            "Scene": scene,
            "AccessKeyId": ak_id,
            "SignatureMethod": "HMAC-SHA1",
            "SignatureVersion": "1.0",
            "SignatureNonce": str(uuid.uuid4()),
            "Timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        params["Signature"] = sign_params(params, ak_secret)
        try:
            resp = _session().get(endpoint, params=params, timeout=timeout)
        except requests.RequestException as e:
            raise AliyunMtError(502, f"请求阿里云失败: {e}") from e
        # 阿里云 RPC 成功/失败都返回 XML（<TranslateGeneralResponse> 或 <Error>）
        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError:
            raise AliyunMtError(502, f"阿里云返回异常 HTTP {resp.status_code}")
        code_el = root.find(".//Code")
        code_text = (code_el.text or "") if code_el is not None else ""
        if code_text not in ("", "200"):
            msg_el = root.find(".//Message")
            err_msg = (msg_el.text or "") if msg_el is not None else ""
            hint = (
                "（请检查 AccessKey 对应的 RAM 账号是否有 alimt:TranslateGeneral 权限）"
                if code_text == "NoPermission"
                else ""
            )
            raise AliyunMtError(
                500, f"阿里云错误码 {code_text}: {err_msg}{hint}"
            )
        data_el = root.find(".//Data")
        if data_el is not None:
            det_el = data_el.find("DetectedLanguage")
            if det_el is not None and det_el.text:
                detected = det_el.text
            tr_el = data_el.find("Translated")
            parts.append(tr_el.text if tr_el is not None and tr_el.text else "")
    return "".join(parts), detected
