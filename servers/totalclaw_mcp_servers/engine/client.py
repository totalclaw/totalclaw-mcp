"""HTTP 执行层：把一个 Tool + 入参变成一次请求，并把结果规整成统一形状。

约定（与 totalclaw-tools SPEC 一致）：处理器永不抛裸异常，一律返回
``{"success": true, ...}`` 或 ``{"success": false, "error": "<人话>"}``。
模型看到的是可读的失败原因，而不是堆栈。
"""
from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urljoin

from .render import MissingValue, clip, pick_path, render_path, render_value
from .spec import Auth, Pack, Tool

_REDACT_KEYS = ("authorization", "token", "key", "secret", "password", "cookie")


def resolve_auth_value(auth: Auth) -> str | None:
    if auth.type == "tencent_cloud":
        return None      # 签名在 build_request 里按请求体计算
    if auth.type == "signature":
        return None      # 签名在 build_request 里直接算并注入
    if auth.type == "token_exchange" and auth.exchange is not None:
        from .token_exchange import get_token

        return get_token(auth.exchange)
    if auth.type == "none" or not auth.env:
        return None
    return os.environ.get(auth.env) or None


def _redact(text: str, secrets: list[str]) -> str:
    out = text
    for s in secrets:
        if s and len(s) >= 6:
            out = out.replace(s, "***")
    return out


def build_request(pack: Pack, tool: Tool, params: dict[str, Any]) -> dict[str, Any]:
    """构造请求要素。抛 MissingValue 表示路径缺必填参数。"""
    auth_value = resolve_auth_value(pack.auth)

    path = render_path(tool.path, params, auth_value)
    url = pack.base_url + path if path.startswith("/") else urljoin(pack.base_url + "/", path)

    query = render_value(tool.query, params, auth_value) if tool.query else {}
    body = render_value(tool.body, params, auth_value) if tool.body is not None else None

    headers = {"User-Agent": "totalclaw-mcp-servers/0.1"}
    headers.update(pack.default_headers)
    headers.update(render_value(tool.headers, params, auth_value) if tool.headers else {})

    a = pack.auth
    if a.type == "tencent_cloud" and a.tc3 is not None:
        from .tc3 import build_headers, host_of

        # 云 API 恒为 POST /，动作在 X-TC-Action 头里；body 参与签名，必须先定稿
        action = headers.pop("X-TC-Action", "") or headers.pop("x-tc-action", "")
        headers.update(build_headers(a.tc3, host=host_of(pack.base_url),
                                     action=action, payload=body))
    elif a.type == "signature" and a.signature is not None:
        from .signing import compute

        signed = compute(a.signature)
        headers.update(signed["headers"])
        if signed["query"]:
            query = {**dict(query), **signed["query"]}
    elif a.type == "token_exchange" and auth_value:
        tx = a.exchange
        if tx.place == "header":
            headers[tx.name] = f"{tx.prefix}{auth_value}"
        else:
            query = dict(query)
            query.setdefault(tx.name, auth_value)
    elif a.type in ("header", "bearer") and auth_value:
        headers[a.name or "Authorization"] = f"{a.prefix}{auth_value}"
    elif a.type == "query" and auth_value and a.name:
        query = dict(query)
        query.setdefault(a.name, auth_value)
    elif a.type == "basic" and auth_value:
        import base64

        user = os.environ.get(a.env_user or "", "")
        token = base64.b64encode(f"{user}:{auth_value}".encode()).decode()
        headers["Authorization"] = f"Basic {token}"

    return {
        "method": tool.method,
        "url": url,
        "params": {k: v for k, v in query.items() if v is not None} or None,
        "json": body,
        "headers": headers,
        "timeout": tool.timeout or pack.default_timeout,
    }


def _parse_body(resp) -> Any:
    ctype = (resp.headers.get("content-type") or "").lower()
    text = resp.text
    if "json" in ctype:
        try:
            return resp.json()
        except (json.JSONDecodeError, ValueError):
            return {"_raw": text}
    # 有些 API 不设 content-type 也返回 JSON
    stripped = text.lstrip()
    if stripped[:1] in ("{", "["):
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            pass
    return {"_raw": text}


def call_tool(pack: Pack, tool: Tool, params: dict[str, Any]) -> dict[str, Any]:
    """执行一次工具调用，返回统一形状的结果。"""
    import httpx

    missing_env = [e for e in pack.required_env if not os.environ.get(e)]
    if missing_env:
        return {
            "success": False,
            "error": f"缺少凭据环境变量：{', '.join(missing_env)}。"
                     f"请在 $TOTALCLAW_HOME/.env 中设置后重新加载 MCP 服务器。",
        }

    from .signing import SigningError
    from .tc3 import TC3Error
    from .token_exchange import TokenExchangeError

    try:
        req = build_request(pack, tool, params)
    except MissingValue as e:
        return {"success": False, "error": f"缺少必填参数：{e.key}"}
    except (TokenExchangeError, SigningError, TC3Error) as e:
        return {"success": False, "error": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"success": False, "error": f"构造请求失败：{type(e).__name__}: {e}"}

    # 用于日志脱敏。token_exchange 已缓存，这里不会重复换取
    secrets = [os.environ.get(e) for e in pack.required_env]
    try:
        secrets.append(resolve_auth_value(pack.auth))
    except TokenExchangeError:
        pass
    secrets = [s for s in secrets if s]

    try:
        with httpx.Client(follow_redirects=True, timeout=req["timeout"]) as c:
            resp = c.request(
                req["method"], req["url"],
                params=req["params"], json=req["json"], headers=req["headers"],
            )
    except httpx.TimeoutException:
        return {"success": False, "error": f"请求超时（{req['timeout']}s）：{tool.name}"}
    except httpx.HTTPError as e:
        return {"success": False, "error": _redact(f"网络错误：{type(e).__name__}: {e}", secrets)}

    if resp.status_code >= 400:
        detail = _redact(resp.text[:500], secrets)
        hint = ""
        if resp.status_code in (401, 403):
            envs = "、".join(pack.required_env) or "凭据"
            hint = f" 请检查 {envs} 是否正确、是否有该接口权限。"
        elif resp.status_code == 429:
            hint = " 触发上游限流，请稍后重试。"
        return {
            "success": False,
            "error": f"上游返回 HTTP {resp.status_code}。{hint}",
            "status": resp.status_code,
            "detail": detail,
        }

    data = _parse_body(resp)

    # 业务错误码：多数国内 API 失败时仍返回 HTTP 200，必须查 errcode 才知道真假
    ec = pack.error_check
    if ec and isinstance(data, dict):
        code = pick_path(data, ec.error_field)
        # pick_path 找不到时会原样返回 data，说明该响应没有这个字段 —— 视为无错误码
        if code is not data and code is not None and str(code) != str(ec.ok_value):
            msg = ""
            if ec.message_field:
                m = pick_path(data, ec.message_field)
                if m is not data and m is not None:
                    msg = str(m)
            if msg and str(msg) == str(code):
                # 错误码字段与消息字段是同一处（GraphQL 的 errors[0].message 就是这种）
                err = f"上游返回错误：{msg}"
            else:
                err = f"上游业务错误 {ec.error_field}={code}。{msg}".strip()
            return {"success": False, "error": err, "code": code}

    data = pick_path(data, tool.pick)
    data, note = clip(data, tool.max_items, tool.max_chars)
    out: dict[str, Any] = {"success": True, "data": data}
    if note:
        out["truncated"] = note
    return out
