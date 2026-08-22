"""把一个 Pack 装配成 MCP 服务器（stdio）。

用 MCP 低层 ``Server`` 而非 FastMCP：pack 的入参本来就是 JSON Schema，低层 API
可以直接声明，不必像 FastMCP 那样反过来用函数签名去合成 schema。
"""
from __future__ import annotations

import logging
from typing import Any

from .client import call_tool
from .spec import Pack

logger = logging.getLogger("totalclaw_mcp_servers")


def build_server(pack: Pack):
    """返回一个已注册好全部工具的 mcp.server.Server 实例。"""
    import mcp.types as types
    from mcp.server import Server

    server = Server(pack.name)
    by_name = {t.name: t for t in pack.tools}

    @server.list_tools()
    async def _list_tools() -> list[types.Tool]:
        out = []
        for t in pack.tools:
            out.append(
                types.Tool(
                    name=t.name,
                    description=t.description,
                    inputSchema=t.params,
                    annotations=types.ToolAnnotations(
                        readOnlyHint=t.read_only,
                        # 只读工具不具破坏性；写工具不声明幂等，交由 agent 审批层处理
                        destructiveHint=not t.read_only,
                    ),
                )
            )
        return out

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any] | None) -> list[types.ContentBlock]:
        import json

        import anyio

        tool = by_name.get(name)
        if tool is None:
            payload = {"success": False, "error": f"未知工具：{name}"}
        else:
            # httpx 同步客户端跑在工作线程，避免阻塞 stdio 事件循环
            payload = await anyio.to_thread.run_sync(call_tool, pack, tool, arguments or {})
        return [types.TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))]

    return server


async def run_stdio(pack: Pack) -> None:
    from mcp.server.stdio import stdio_server

    server = build_server(pack)
    opts = server.create_initialization_options()
    async with stdio_server() as (read, write):
        await server.run(read, write, opts)
