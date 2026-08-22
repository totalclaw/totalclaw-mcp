"""签名鉴权：把密钥和时间戳按规则摘要成一次性签名，再注入请求。

一整类国内 API 用这个形态而不是直接传 key（企查查、部分聚合数据类接口等）：

    Token    = MD5(AppKey + Timespan + SecretKey) 转大写
    Timespan = Unix 秒级时间戳

pack 中的声明::

    auth:
      type: signature
      algorithm: md5                 # md5 | sha1 | sha256 | hmac_sha256
      parts: ["${QCC_KEY}", "{timestamp}", "${QCC_SECRET}"]
      uppercase: true
      inject:
        headers: {Token: "{signature}", Timespan: "{timestamp}"}
        query: {key: "${QCC_KEY}"}
      requires_env: [QCC_KEY, QCC_SECRET]

占位符：``${ENV}`` 环境变量；``{timestamp}`` 秒级时间戳；``{timestamp_ms}`` 毫秒；
``{nonce}`` 随机串；``{signature}`` 计算出的签名（只能出现在 inject 里）。

hmac_sha256 时 ``parts`` 拼接结果是待签名串，密钥取 ``hmac_key``（同样支持 ${ENV}）。
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

ALGORITHMS = {"md5", "sha1", "sha256", "hmac_sha256"}
_ENV_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class SigningError(Exception):
    """面向用户的签名错误。"""

    clean = True


@dataclass(frozen=True)
class Signature:
    algorithm: str
    parts: tuple[str, ...]
    uppercase: bool = True
    hmac_key: str | None = None
    inject_headers: dict[str, str] = field(default_factory=dict)
    inject_query: dict[str, str] = field(default_factory=dict)
    requires_env: tuple[str, ...] = ()


def _expand(text: str, ctx: dict[str, str]) -> str:
    def env_sub(m: re.Match[str]) -> str:
        v = os.environ.get(m.group(1))
        if not v:
            raise SigningError(f"缺少凭据环境变量：{m.group(1)}")
        return v

    out = _ENV_RE.sub(env_sub, text)
    for k, v in ctx.items():
        out = out.replace("{" + k + "}", v)
    return out


def compute(sig: Signature) -> dict[str, dict[str, str]]:
    """算出签名并返回 {"headers": {...}, "query": {...}}。"""
    missing = [e for e in sig.requires_env if not os.environ.get(e)]
    if missing:
        raise SigningError(f"缺少凭据环境变量：{', '.join(missing)}")

    now = time.time()
    ctx = {
        "timestamp": str(int(now)),
        "timestamp_ms": str(int(now * 1000)),
        "nonce": secrets.token_hex(8),
    }

    raw = "".join(_expand(p, ctx) for p in sig.parts)
    if sig.algorithm == "hmac_sha256":
        if not sig.hmac_key:
            raise SigningError("hmac_sha256 需要 auth.hmac_key")
        key = _expand(sig.hmac_key, ctx).encode()
        digest = hmac.new(key, raw.encode(), hashlib.sha256).hexdigest()
    else:
        digest = getattr(hashlib, sig.algorithm)(raw.encode()).hexdigest()
    ctx["signature"] = digest.upper() if sig.uppercase else digest

    return {
        "headers": {k: _expand(v, ctx) for k, v in sig.inject_headers.items()},
        "query": {k: _expand(v, ctx) for k, v in sig.inject_query.items()},
    }


def parse_signature(raw: dict, where: str) -> Signature:
    from .spec import PackError

    algo = str(raw.get("algorithm") or "md5").lower()
    if algo not in ALGORITHMS:
        raise PackError(f"{where}: auth.algorithm={algo!r} 非法，可选 {sorted(ALGORITHMS)}")
    parts = raw.get("parts")
    if not isinstance(parts, list) or not parts:
        raise PackError(f"{where}: auth.type=signature 需要非空的 parts 列表")
    req_env = tuple(str(e) for e in (raw.get("requires_env") or []))
    if not req_env:
        raise PackError(f"{where}: auth.type=signature 需要 requires_env 列出所需凭据变量")
    inject = raw.get("inject") or {}
    headers = {str(k): str(v) for k, v in (inject.get("headers") or {}).items()}
    query = {str(k): str(v) for k, v in (inject.get("query") or {}).items()}
    if not headers and not query:
        raise PackError(f"{where}: auth.inject 至少要指定 headers 或 query")
    if algo == "hmac_sha256" and not raw.get("hmac_key"):
        raise PackError(f"{where}: algorithm=hmac_sha256 需要 auth.hmac_key")
    return Signature(
        algorithm=algo,
        parts=tuple(str(p) for p in parts),
        uppercase=bool(raw.get("uppercase", True)),
        hmac_key=str(raw["hmac_key"]) if raw.get("hmac_key") else None,
        inject_headers=headers,
        inject_query=query,
        requires_env=req_env,
    )
