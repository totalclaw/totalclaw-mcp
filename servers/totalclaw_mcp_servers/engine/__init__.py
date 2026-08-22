"""REST→MCP 引擎：把声明式 pack 装配成 MCP 服务器。"""
from .spec import Pack, PackError, Tool, list_packs, load_pack, parse_pack
from .server import build_server, run_stdio
from .client import call_tool

__all__ = ["Pack", "PackError", "Tool", "list_packs", "load_pack", "parse_pack",
           "build_server", "run_stdio", "call_tool"]
