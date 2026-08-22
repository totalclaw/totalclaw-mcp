"""原生 MCP 服务器：声明式 pack 表达不了的连接器。

每个原生模块导出：
    SERVER_NAME / DISPLAY_NAME / DESCRIPTION / REQUIRED_ENV / OPTIONAL_ENV
    TOOLS: list[{name, description, read_only, handler, schema}]
handler 是普通同步函数，只接受关键字参数，返回 {"success": bool, ...}。
"""
from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType

_MODULES = ("imap_mail", "web")


def list_native() -> list[str]:
    names = []
    for m in _MODULES:
        try:
            names.append(load_native(m).SERVER_NAME)
        except Exception:  # noqa: BLE001
            continue
    return sorted(names)


def load_native(name: str) -> ModuleType:
    """按 SERVER_NAME 或模块名加载。"""
    for m in _MODULES:
        mod = importlib.import_module(f".{m}", __package__)
        if m == name or getattr(mod, "SERVER_NAME", None) == name:
            return mod
    raise KeyError(name)


def has_native(name: str) -> bool:
    try:
        load_native(name)
        return True
    except KeyError:
        return False


__all__ = ["list_native", "load_native", "has_native"]
