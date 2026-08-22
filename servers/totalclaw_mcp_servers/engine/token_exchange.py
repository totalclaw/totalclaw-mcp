"""令牌交换：企业微信 / 飞书 / 钉钉这类「先换 access_token 再调接口」的 API。

这些平台不接受直接用 secret 调业务接口，必须先拿 corpid+secret（或 app_id+app_secret）
换一个有时效的 access_token。令牌在进程内缓存到过期前 60 秒，避免每次工具调用都换一次
（上游对换取接口的调用频次有限制，频繁换取会触发封禁）。

pack 中的声明::

    auth:
      type: token_exchange
      token_url: https://qyapi.weixin.qq.com/cgi-bin/gettoken
      token_method: GET                     # GET | POST
      token_query: {corpid: "${WECOM_CORP_ID}", corpsecret: "${WECOM_SECRET}"}
      token_pick: access_token               # 响应里取令牌的点号路径
      expires_pick: expires_in               # 有效期秒数的路径，可选
      place: query                           # 令牌放哪：query | header
      name: access_token                     # query 参数名或 header 名
      prefix: ""                             # header 值前缀，如 "Bearer "
      requires_env: [WECOM_CORP_ID, WECOM_SECRET]
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Any

_LOCK = threading.Lock()
_CACHE: dict[str, tuple[str, float]] = {}   # cache_key -> (token, expires_at)

DEFAULT_TTL = 7200.0
EXPIRY_MARGIN = 60.0


class TokenExchangeError(Exception):
    pass


@dataclass(frozen=True)
class TokenExchange:
    token_url: str
    token_pick: str
    token_method: str = "GET"
    token_query: dict[str, Any] | None = None
    token_body: dict[str, Any] | None = None
    token_headers: dict[str, str] | None = None
    expires_pick: str | None = None
    place: str = "query"
    name: str = "access_token"
    prefix: str = ""
    requires_env: tuple[str, ...] = ()
    timeout: float = 20.0


def _resolve_env_refs(obj: Any) -> Any:
    """把 ${ENV} 替换成环境变量值；缺失则抛 TokenExchangeError。"""
    import re

    if isinstance(obj, str):
        def sub(m: re.Match[str]) -> str:
            v = os.environ.get(m.group(1))
            if not v:
                raise TokenExchangeError(f"缺少环境变量 {m.group(1)}")
            return v

        return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", sub, obj)
    if isinstance(obj, dict):
        return {k: _resolve_env_refs(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_env_refs(v) for v in obj]
    return obj


def _pick(data: Any, path: str) -> Any:
    cur = data
    for seg in path.split("."):
        if isinstance(cur, dict) and seg in cur:
            cur = cur[seg]
        else:
            return None
    return cur


def _cache_key(tx: TokenExchange) -> str:
    """凭据不同 → 缓存不同。只取哈希，绝不把 secret 本身放进 key。"""
    import hashlib

    parts = [tx.token_url] + [f"{e}={os.environ.get(e, '')}" for e in sorted(tx.requires_env)]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]


def get_token(tx: TokenExchange, *, force: bool = False) -> str:
    """取（必要时换取）access_token。线程安全，带过期缓存。"""
    import httpx

    missing = [e for e in tx.requires_env if not os.environ.get(e)]
    if missing:
        raise TokenExchangeError(f"缺少凭据环境变量：{', '.join(missing)}")

    key = _cache_key(tx)
    now = time.time()
    with _LOCK:
        if not force:
            hit = _CACHE.get(key)
            if hit and hit[1] > now:
                return hit[0]

    query = _resolve_env_refs(tx.token_query or {}) or None
    body = _resolve_env_refs(tx.token_body) if tx.token_body else None
    headers = _resolve_env_refs(tx.token_headers or {}) or None

    try:
        with httpx.Client(timeout=tx.timeout, follow_redirects=True) as c:
            resp = c.request(tx.token_method, tx.token_url, params=query, json=body, headers=headers)
    except httpx.HTTPError as e:
        raise TokenExchangeError(f"换取令牌失败（网络）：{type(e).__name__}") from e

    if resp.status_code >= 400:
        raise TokenExchangeError(f"换取令牌失败：上游 HTTP {resp.status_code}")

    try:
        data = resp.json()
    except ValueError as e:
        raise TokenExchangeError("换取令牌失败：上游未返回 JSON") from e

    token = _pick(data, tx.token_pick)
    if not token or not isinstance(token, str):
        # 上游常把失败原因放在 errmsg/message 里，带出来便于排查（不含 secret）
        detail = data.get("errmsg") or data.get("msg") or data.get("message") or ""
        raise TokenExchangeError(f"换取令牌失败：响应中没有 {tx.token_pick}。{detail}".strip())

    ttl = DEFAULT_TTL
    if tx.expires_pick:
        raw = _pick(data, tx.expires_pick)
        try:
            if raw is not None:
                ttl = float(raw)
        except (TypeError, ValueError):
            pass
    with _LOCK:
        _CACHE[key] = (token, now + max(30.0, ttl - EXPIRY_MARGIN))
    return token


def invalidate(tx: TokenExchange) -> None:
    with _LOCK:
        _CACHE.pop(_cache_key(tx), None)


def parse_token_exchange(raw: dict, where: str) -> TokenExchange:
    from .spec import PackError

    for k in ("token_url", "token_pick"):
        if not raw.get(k):
            raise PackError(f"{where}: auth.type=token_exchange 需要 {k}")
    url = str(raw["token_url"])
    if not url.startswith("https://"):
        raise PackError(f"{where}: token_url 必须是 https")
    place = str(raw.get("place") or "query")
    if place not in ("query", "header"):
        raise PackError(f"{where}: auth.place={place!r} 非法（query|header）")
    req_env = tuple(str(e) for e in (raw.get("requires_env") or []))
    if not req_env:
        raise PackError(f"{where}: auth.type=token_exchange 需要 requires_env 列出所需凭据变量")
    return TokenExchange(
        token_url=url,
        token_pick=str(raw["token_pick"]),
        token_method=str(raw.get("token_method") or "GET").upper(),
        token_query=dict(raw.get("token_query") or {}) or None,
        token_body=raw.get("token_body"),
        token_headers=dict(raw.get("token_headers") or {}) or None,
        expires_pick=str(raw["expires_pick"]) if raw.get("expires_pick") else None,
        place=place,
        name=str(raw.get("name") or "access_token"),
        prefix=str(raw.get("prefix") or ""),
        requires_env=req_env,
        timeout=float(raw.get("timeout") or 20.0),
    )
