"""把一个原生模块装配成 MCP 服务器 —— 与 pack 走同一套对外形状。"""
from __future__ import annotations

from types import ModuleType
from typing import Any


def build_native_server(mod: ModuleType):
    import mcp.types as types
    from mcp.server import Server

    server = Server(mod.SERVER_NAME)
    by_name = {t["name"]: t for t in mod.TOOLS}

    @server.list_tools()
    async def _list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["schema"],
                annotations=types.ToolAnnotations(
                    readOnlyHint=t.get("read_only", True),
                    destructiveHint=not t.get("read_only", True),
                ),
            )
            for t in mod.TOOLS
        ]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any] | None) -> list[types.ContentBlock]:
        import json

        import anyio

        spec = by_name.get(name)
        if spec is None:
            payload = {"success": False, "error": f"未知工具：{name}"}
        else:
            def run() -> dict[str, Any]:
                try:
                    return spec["handler"](**(arguments or {}))
                except Exception as e:  # noqa: BLE001 - 绝不把堆栈抛给模型
                    if getattr(e, "clean", False):
                        return {"success": False, "error": str(e)}
                    return {"success": False, "error": f"{type(e).__name__}: {e}"}

            payload = await anyio.to_thread.run_sync(run)
        return [types.TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))]

    return server


async def run_native_stdio(mod: ModuleType) -> None:
    from mcp.server.stdio import stdio_server

    server = build_native_server(mod)
    opts = server.create_initialization_options()
    async with stdio_server() as (read, write):
        await server.run(read, write, opts)
