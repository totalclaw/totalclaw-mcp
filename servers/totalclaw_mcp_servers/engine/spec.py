"""Pack 规范：声明式描述一个 REST API，引擎据此生成 MCP 服务器。

一个 pack = 一个连接器 = 一个 MCP 服务器。写 pack 不写代码，是本仓能覆盖上百个
连接器的原因：它们的共性都是「带密钥调 REST API，把 N 个操作暴露成 N 个工具」。

示例（servers/totalclaw_mcp_servers/packs/*.yaml）::

    name: qcc_company
    display_name: 企查查·企业信息
    description: 查询企业工商登记、股东、风险等信息。
    base_url: https://api.qichacha.com
    auth:
      type: header            # header | bearer | query | basic | none
      name: Token             # header/query 名
      env: QCC_API_KEY        # 从该环境变量取值
    defaults:
      timeout: 30
      headers: {Accept: application/json}
    tools:
      - name: search_company
        description: 按关键词搜索企业，返回企业名与统一社会信用代码。
        read_only: true
        method: GET
        path: /FuzzySearch/GetList
        query:
          key: ${auth}
          searchKey: "{keyword}"
        params:
          type: object
          properties:
            keyword: {type: string, description: 企业名称关键词}
          required: [keyword]
        pick: Result           # 只回传响应里的这个字段（点号路径）
        max_items: 20

字段说明见 docs/PACKS.md。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
TOOL_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
AUTH_TYPES = {"none", "header", "bearer", "query", "basic", "token_exchange", "signature", "tencent_cloud"}
METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


class PackError(ValueError):
    """pack 定义非法。"""


@dataclass(frozen=True)
class Auth:
    type: str = "none"
    name: str | None = None          # header 名或 query 参数名
    env: str | None = None           # 取值的环境变量
    env_user: str | None = None      # basic: 用户名环境变量
    prefix: str = ""                 # header 值前缀，如 "Bearer "
    exchange: Any = None             # type=token_exchange 时的 TokenExchange
    signature: Any = None            # type=signature 时的 Signature
    tc3: Any = None                  # type=tencent_cloud 时的 TC3Config

    @property
    def required_env(self) -> list[str]:
        if self.type == "token_exchange" and self.exchange is not None:
            return list(self.exchange.requires_env)
        if self.type == "signature" and self.signature is not None:
            return list(self.signature.requires_env)
        if self.type == "tencent_cloud" and self.tc3 is not None:
            return list(self.tc3.requires_env)
        return [e for e in (self.env, self.env_user) if e]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    method: str
    path: str
    params: dict[str, Any] = field(default_factory=lambda: {"type": "object", "properties": {}})
    query: dict[str, Any] = field(default_factory=dict)
    body: Any = None
    headers: dict[str, str] = field(default_factory=dict)
    read_only: bool = True
    pick: str | None = None
    max_items: int | None = None
    max_chars: int = 16000
    timeout: float | None = None


@dataclass(frozen=True)
class ErrorCheck:
    """业务错误码检查。

    企业微信 / 钉钉 / 飞书 / 多数国内 API 失败时返回 HTTP 200 + errcode!=0，
    只看 HTTP 状态码会把失败当成功喂给模型。pack 里声明::

        response:
          error_field: errcode       # 点号路径
          ok_value: 0                # 该值表示成功（数字或字符串）
          message_field: errmsg      # 失败原因字段
    """

    error_field: str
    ok_value: Any = 0
    message_field: str | None = None


@dataclass(frozen=True)
class Pack:
    name: str
    display_name: str
    description: str
    base_url: str
    tools: tuple[Tool, ...]
    description_en: str = ""
    auth: Auth = Auth()
    default_headers: dict[str, str] = field(default_factory=dict)
    default_timeout: float = 30.0
    optional_env: tuple[str, ...] = ()
    docs: str | None = None
    error_check: ErrorCheck | None = None

    @property
    def required_env(self) -> list[str]:
        return self.auth.required_env


def _req(d: dict, key: str, where: str) -> Any:
    if key not in d or d[key] in (None, ""):
        raise PackError(f"{where}: 缺少必填字段 {key!r}")
    return d[key]


def _parse_auth(raw: Any, where: str) -> Auth:
    if not raw:
        return Auth()
    if not isinstance(raw, dict):
        raise PackError(f"{where}: auth 必须是对象")
    t = str(raw.get("type") or "none")
    if t not in AUTH_TYPES:
        raise PackError(f"{where}: auth.type={t!r} 非法，可选 {sorted(AUTH_TYPES)}")
    if t == "tencent_cloud":
        from .tc3 import parse_tc3

        return Auth(type=t, tc3=parse_tc3(raw, where))
    if t == "signature":
        from .signing import parse_signature

        return Auth(type=t, signature=parse_signature(raw, where))
    if t == "token_exchange":
        from .token_exchange import parse_token_exchange

        tx = parse_token_exchange(raw, where)
        return Auth(type=t, name=tx.name, prefix=tx.prefix, exchange=tx)
    if t in ("header", "query") and not raw.get("name"):
        raise PackError(f"{where}: auth.type={t} 需要 auth.name")
    if t != "none" and not raw.get("env"):
        raise PackError(f"{where}: auth.type={t} 需要 auth.env（凭据来自环境变量，不写死在 pack 里）")
    if t == "basic" and not raw.get("env_user"):
        raise PackError(f"{where}: auth.type=basic 需要 auth.env_user")
    prefix = str(raw.get("prefix") or ("Bearer " if t == "bearer" else ""))
    return Auth(
        type=t,
        name=str(raw["name"]) if raw.get("name") else ("Authorization" if t == "bearer" else None),
        env=str(raw["env"]) if raw.get("env") else None,
        env_user=str(raw["env_user"]) if raw.get("env_user") else None,
        prefix=prefix,
    )


def _parse_tool(raw: Any, where: str) -> Tool:
    if not isinstance(raw, dict):
        raise PackError(f"{where}: tools 每项必须是对象")
    name = str(_req(raw, "name", where))
    if not TOOL_NAME_RE.match(name):
        raise PackError(f"{where}: 工具名 {name!r} 非法（仅小写字母/数字/下划线，字母开头）")
    tw = f"{where}.tools[{name}]"
    method = str(raw.get("method") or "GET").upper()
    if method not in METHODS:
        raise PackError(f"{tw}: method={method!r} 非法")
    params = raw.get("params") or {"type": "object", "properties": {}}
    if not isinstance(params, dict):
        raise PackError(f"{tw}: params 必须是 JSON Schema 对象")
    params.setdefault("type", "object")
    params.setdefault("properties", {})
    max_items = raw.get("max_items")
    return Tool(
        name=name,
        description=str(_req(raw, "description", tw)),
        method=method,
        path=str(_req(raw, "path", tw)),
        params=params,
        query=dict(raw.get("query") or {}),
        body=raw.get("body"),
        headers={str(k): str(v) for k, v in (raw.get("headers") or {}).items()},
        read_only=bool(raw.get("read_only", method == "GET")),
        pick=str(raw["pick"]) if raw.get("pick") else None,
        max_items=int(max_items) if max_items is not None else None,
        max_chars=int(raw.get("max_chars") or 16000),
        timeout=float(raw["timeout"]) if raw.get("timeout") else None,
    )


def parse_pack(raw: dict, where: str = "<pack>") -> Pack:
    if not isinstance(raw, dict):
        raise PackError(f"{where}: pack 根必须是对象")
    name = str(_req(raw, "name", where))
    if not NAME_RE.match(name):
        raise PackError(f"{where}: name={name!r} 非法（仅小写字母/数字/下划线，字母开头）")
    base_url = str(_req(raw, "base_url", where)).rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        raise PackError(f"{where}: base_url 必须是 http(s) 绝对地址")
    if base_url.startswith("http://") and not base_url.startswith(("http://127.0.0.1", "http://localhost")):
        raise PackError(f"{where}: base_url 非回环地址必须用 https")

    tools_raw = raw.get("tools") or []
    if not isinstance(tools_raw, list) or not tools_raw:
        raise PackError(f"{where}: tools 至少需要 1 个")
    tools = tuple(_parse_tool(t, where) for t in tools_raw)
    seen: set[str] = set()
    for t in tools:
        if t.name in seen:
            raise PackError(f"{where}: 工具名重复 {t.name!r}")
        seen.add(t.name)

    defaults = raw.get("defaults") or {}
    resp = raw.get("response") or {}
    error_check = None
    if resp:
        if not resp.get("error_field"):
            raise PackError(f"{where}: response 块需要 error_field")
        error_check = ErrorCheck(
            error_field=str(resp["error_field"]),
            ok_value=resp.get("ok_value", 0),
            message_field=str(resp["message_field"]) if resp.get("message_field") else None,
        )
    return Pack(
        name=name,
        display_name=str(raw.get("display_name") or name),
        description=str(raw.get("description") or ""),
        description_en=str(raw.get("description_en") or ""),
        base_url=base_url,
        tools=tools,
        auth=_parse_auth(raw.get("auth"), where),
        default_headers={str(k): str(v) for k, v in (defaults.get("headers") or {}).items()},
        default_timeout=float(defaults.get("timeout") or 30.0),
        optional_env=tuple(str(e) for e in (raw.get("optional_env") or [])),
        docs=str(raw["docs"]) if raw.get("docs") else None,
        error_check=error_check,
    )


def packs_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "packs"


def load_pack_file(path: Path) -> Pack:
    import yaml

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    pack = parse_pack(raw, where=path.name)
    if pack.name != path.stem:
        raise PackError(f"{path.name}: name={pack.name!r} 与文件名 {path.stem!r} 不一致")
    return pack


def load_pack(name: str) -> Pack:
    p = packs_dir() / f"{name}.yaml"
    if not p.exists():
        raise PackError(f"找不到 pack：{name}（{p}）")
    return load_pack_file(p)


def list_packs() -> list[str]:
    d = packs_dir()
    return sorted(p.stem for p in d.glob("*.yaml")) if d.exists() else []
