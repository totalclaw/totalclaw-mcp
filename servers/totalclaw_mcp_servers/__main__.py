"""totalclaw-mcp-servers 命令行入口。

    totalclaw-mcp-server <pack>          以 stdio 运行某个连接器的 MCP 服务器
    totalclaw-mcp-server --list          列出全部可用 pack
    totalclaw-mcp-server --check [pack]  校验 pack 定义（CI 用；不发请求）
    totalclaw-mcp-server --describe <p>  打印该 pack 的工具与所需凭据

日志一律走 stderr —— stdout 是 MCP 协议通道，写任何多余内容都会破坏握手。
"""
from __future__ import annotations

import argparse
import json
import logging
import sys


def _run(name: str) -> int:
    import anyio

    from . import native
    from .engine.server import run_stdio
    from .engine.spec import PackError, load_pack

    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    if native.has_native(name):
        from .engine.native_server import run_native_stdio

        anyio.run(run_native_stdio, native.load_native(name))
        return 0
    try:
        pack = load_pack(name)
    except PackError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1
    anyio.run(run_stdio, pack)
    return 0


def _check(pack_name: str | None) -> int:
    from .engine.spec import PackError, list_packs, load_pack

    from . import native

    if pack_name and native.has_native(pack_name):
        mod = native.load_native(pack_name)
        print(f"  ✓ {pack_name:28s} {len(mod.TOOLS):3d} 个工具  凭据: {', '.join(mod.REQUIRED_ENV) or '无'}  (原生)")
        return 0
    names = [pack_name] if pack_name else list_packs()
    if not names:
        print("没有找到任何 pack", file=sys.stderr)
        return 1
    bad = 0
    for n in names:
        try:
            p = load_pack(n)
            print(f"  ✓ {n:28s} {len(p.tools):3d} 个工具  凭据: {', '.join(p.required_env) or '无'}")
        except PackError as e:
            bad += 1
            print(f"  ✗ {n:28s} {e}", file=sys.stderr)
    for n in native.list_native():
        mod = native.load_native(n)
        print(f"  ✓ {n:28s} {len(mod.TOOLS):3d} 个工具  凭据: {', '.join(mod.REQUIRED_ENV) or '无'}  (原生)")
    total = len(names) + len(native.list_native())
    print(f"\n共 {total} 个服务器（{len(names)} pack + {len(native.list_native())} 原生），{bad} 个不合法")
    return 1 if bad else 0


def _describe(pack_name: str) -> int:
    from . import native
    from .engine.spec import PackError, load_pack

    if native.has_native(pack_name):
        mod = native.load_native(pack_name)
        print(json.dumps({
            "name": mod.SERVER_NAME, "display_name": mod.DISPLAY_NAME,
            "description": mod.DESCRIPTION, "kind": "native",
            "required_env": list(mod.REQUIRED_ENV), "optional_env": list(mod.OPTIONAL_ENV),
            "tools": [{"name": t["name"], "description": t["description"],
                       "read_only": t.get("read_only", True), "params": t["schema"]}
                      for t in mod.TOOLS],
        }, ensure_ascii=False, indent=2))
        return 0
    try:
        p = load_pack(pack_name)
    except PackError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1
    print(json.dumps({
        "name": p.name,
        "display_name": p.display_name,
        "description": p.description,
        "base_url": p.base_url,
        "required_env": p.required_env,
        "optional_env": list(p.optional_env),
        "docs": p.docs,
        "tools": [
            {"name": t.name, "description": t.description, "read_only": t.read_only,
             "method": t.method, "path": t.path, "params": t.params}
            for t in p.tools
        ],
    }, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="totalclaw-mcp-server", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pack", nargs="?", help="pack 名称（见 --list）")
    ap.add_argument("--list", action="store_true", help="列出全部 pack")
    ap.add_argument("--check", action="store_true", help="校验 pack 定义")
    ap.add_argument("--describe", action="store_true", help="打印 pack 的工具与凭据")
    args = ap.parse_args(argv)

    if args.list:
        from . import native
        from .engine.spec import list_packs
        for n in list_packs():
            print(n)
        for n in native.list_native():
            print(n)
        return 0
    if args.check:
        return _check(args.pack)
    if args.describe:
        if not args.pack:
            ap.error("--describe 需要指定 pack")
        return _describe(args.pack)
    if not args.pack:
        ap.print_help(sys.stderr)
        return 2
    return _run(args.pack)


if __name__ == "__main__":
    raise SystemExit(main())
