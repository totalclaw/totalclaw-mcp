"""模板渲染与响应裁剪。

pack 里三种占位符：
  {param}      工具入参。整串就是一个占位符时保留原始类型（数字/布尔/数组不被强转成字符串）
  ${auth}      鉴权凭据（auth.env 的值）——用于少数把 key 放在 query 里的 API
  ${ENV_VAR}   任意环境变量

未提供且非必填的参数：其所在的 query 项/ body 字段会被整条丢弃，而不是发送空串
（空串对多数 API 意味着「显式传空」，与「不传」语义不同）。
"""
from __future__ import annotations

import os
import re
from typing import Any

_WHOLE_PARAM_RE = re.compile(r"^\{([A-Za-z_][A-Za-z0-9_]*)\}$")
_PARAM_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
_ENV_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class MissingValue(Exception):
    """占位符没有对应的值 —— 调用方据此丢弃该项。"""

    def __init__(self, key: str):
        super().__init__(key)
        self.key = key


def render_value(value: Any, params: dict[str, Any], auth_value: str | None = None) -> Any:
    """渲染任意结构。字符串里的占位符被替换；缺值抛 MissingValue。"""
    if isinstance(value, str):
        return _render_str(value, params, auth_value)
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            try:
                out[k] = render_value(v, params, auth_value)
            except MissingValue:
                continue  # 缺值 → 整项丢弃
        return out
    if isinstance(value, list):
        out_list = []
        for v in value:
            try:
                out_list.append(render_value(v, params, auth_value))
            except MissingValue:
                continue
        return out_list
    return value


def _lookup_env(name: str, auth_value: str | None) -> str:
    if name == "auth":
        if auth_value is None:
            raise MissingValue("${auth}")
        return auth_value
    v = os.environ.get(name)
    if v is None or v == "":
        raise MissingValue(f"${{{name}}}")
    return v


def _render_str(s: str, params: dict[str, Any], auth_value: str | None) -> Any:
    # 整串即单个参数占位符 → 保留原始类型
    m = _WHOLE_PARAM_RE.match(s)
    if m:
        if m.group(1) not in params or params[m.group(1)] is None:
            raise MissingValue(m.group(1))
        return params[m.group(1)]

    m = re.fullmatch(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", s)
    if m:
        return _lookup_env(m.group(1), auth_value)

    def sub_param(mo: re.Match[str]) -> str:
        key = mo.group(1)
        if key not in params or params[key] is None:
            raise MissingValue(key)
        return str(params[key])

    def sub_env(mo: re.Match[str]) -> str:
        return _lookup_env(mo.group(1), auth_value)

    out = _ENV_RE.sub(sub_env, s)
    out = _PARAM_RE.sub(sub_param, out)
    return out


def render_path(path: str, params: dict[str, Any], auth_value: str | None = None) -> str:
    """路径必须完整渲染 —— 缺值直接报错，绝不容忍 /repos//issues 这种畸形路径。"""
    from urllib.parse import quote

    def sub(mo: re.Match[str]) -> str:
        key = mo.group(1)
        if key not in params or params[key] in (None, ""):
            raise MissingValue(key)
        return quote(str(params[key]), safe="")

    out = _ENV_RE.sub(lambda mo: quote(_lookup_env(mo.group(1), auth_value), safe=""), path)
    return _PARAM_RE.sub(sub, out)


def pick_path(data: Any, path: str | None) -> Any:
    """按点号路径取值：``a.b.0.c``。任一层不存在则返回原数据（宁可多给，不可静默丢空）。"""
    if not path:
        return data
    cur = data
    for seg in path.split("."):
        if isinstance(cur, dict) and seg in cur:
            cur = cur[seg]
        elif isinstance(cur, list) and seg.isdigit() and int(seg) < len(cur):
            cur = cur[int(seg)]
        else:
            return data
    return cur


def clip(data: Any, max_items: int | None, max_chars: int) -> tuple[Any, dict[str, Any]]:
    """裁剪过长响应，返回 (数据, 裁剪说明)。说明为空 dict 表示未裁剪。"""
    import json

    note: dict[str, Any] = {}
    if max_items is not None and isinstance(data, list) and len(data) > max_items:
        note["truncated_items"] = {"returned": max_items, "total": len(data)}
        data = data[:max_items]
    try:
        s = json.dumps(data, ensure_ascii=False)
    except (TypeError, ValueError):
        return data, note
    if len(s) > max_chars:
        note["truncated_chars"] = {"returned": max_chars, "total": len(s)}
        return {"_truncated_text": s[:max_chars]}, note
    return data, note
