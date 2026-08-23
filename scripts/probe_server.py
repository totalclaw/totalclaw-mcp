#!/usr/bin/env python3
"""探测注册表里的 MCP 服务器：真实启动 → list_tools → 写回 tools.json 与 security 块。

为什么要探测：
  * `tools.json` 让 agent 安装时预填 schema-cache，**装完立刻能看到工具**，
    不必等首次连接（配合 TOTALCLAW_MCP_LAZY_START 尤其明显）。
  * 工具描述是模型唯一的判断依据，也是提示词注入的入口。上游随时可能改描述，
    所以每次探测都重跑一遍注入扫描，把结论钉进 `security.scan_verdict`。

用法：
  python3 scripts/probe_server.py --all                 # 探测全部（慢，会真的下载包）
  python3 scripts/probe_server.py mcp_fetch playwright  # 只探测指定的
  python3 scripts/probe_server.py --all --skip-auth     # 跳过需要凭据的（CI 用）
  python3 scripts/probe_server.py mcp_fetch --dry-run   # 只打印将要执行的命令

需要凭据的服务器在没配好环境变量时会连接失败 —— 这是预期的，用 --skip-auth 跳过。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SERVERS_DIR = ROOT / "registry" / "servers"
CONNECT_TIMEOUT = 90.0

# 与 agent totalclaw_core/tools/mcp_tool/helpers.py 同一组模式：
# 工具描述里出现这些，说明上游试图在描述里给模型下指令
INJECTION_PATTERNS = [
    (r"(?i)ignore\s+(all\s+)?(previous|prior|above)\s+instructions", "要求忽略先前指令"),
    (r"(?i)disregard\s+(all\s+)?(previous|prior|your)\s+", "要求无视先前内容"),
    (r"(?i)you\s+are\s+now\s+", "试图重设角色"),
    (r"(?i)new\s+(system\s+)?(prompt|instructions?)\s*:", "试图注入新系统提示"),
    (r"(?i)</?(system|assistant|user)>", "伪造对话角色标签"),
    (r"(?i)\bdo\s+not\s+tell\s+the\s+user\b", "要求对用户隐瞒"),
    (r"(?i)\bwithout\s+(asking|informing|telling)\s+the\s+user\b", "要求绕过用户确认"),
    (r"(?i)(exfiltrat|send\s+(all\s+)?(the\s+)?(data|files|secrets|credentials))", "疑似外传数据"),
    (r"(?i)(cat|read)\s+.*\.env\b", "疑似读取 .env"),
    (r"(?i)\b(curl|wget)\s+http", "描述里带出网命令"),
]


def _yaml():
    import yaml
    return yaml


def scan_tools(tools: list[dict]) -> list[dict]:
    """扫描工具名与描述里的提示词注入痕迹。"""
    findings = []
    for t in tools:
        blob = f"{t.get('name', '')}\n{t.get('description', '')}"
        for pattern, label in INJECTION_PATTERNS:
            m = re.search(pattern, blob)
            if m:
                findings.append({
                    "tool": t.get("name", "?"),
                    "pattern": label,
                    "excerpt": blob[max(0, m.start() - 40):m.start() + 80].strip()[:160],
                })
    return findings


def _root_cause(exc: BaseException) -> BaseException:
    """扒出 ExceptionGroup 里真正的错误。

    MCP SDK 用 TaskGroup 跑连接，任何失败都被包成
    ``ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)`` ——
    那句话对排查毫无帮助：分不清是缺凭据（401）、端点没了（404）还是网络不通。
    """
    seen = 0
    while seen < 10:
        subs = getattr(exc, "exceptions", None)
        if not subs:
            break
        exc = subs[0]
        seen += 1
    return exc


def _expand(value: str) -> str:
    """把 ``${VAR}`` 展开成真实环境变量；展不开就原样留着，让上游自己报错。"""
    return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}",
                  lambda m: os.environ.get(m.group(1), m.group(0)), str(value))


def _pick_runtime(manifest: dict, runtime_id: str | None) -> dict:
    """挑一个可探测的 runtime。stdio 优先——不用凭据就能连上。"""
    runtimes = [r for r in (manifest.get("runtimes") or [])
                if r.get("type") in ("stdio", "http")]
    if runtime_id:
        runtimes = [r for r in runtimes if r.get("id") == runtime_id]
        if not runtimes:
            raise RuntimeError(f"清单里没有 runtime {runtime_id!r}")
    if not runtimes:
        raise RuntimeError("清单里没有 stdio 或 http runtime")
    runtimes.sort(key=lambda r: 0 if r.get("type") == "stdio" else 1)
    return runtimes[0]


def _server_params(manifest: dict, runtime_id: str | None):
    """从清单里挑一个 stdio runtime，转成 StdioServerParameters。"""
    from mcp import StdioServerParameters

    runtimes = [r for r in (manifest.get("runtimes") or []) if r.get("type") == "stdio"]
    if runtime_id:
        runtimes = [r for r in runtimes if r.get("id") == runtime_id]
    if not runtimes:
        raise RuntimeError("没有可探测的 stdio runtime")
    rt = runtimes[0]

    env = {k: os.environ.get(k, "") for k in
           ("PATH", "HOME", "USER", "LANG", "LC_ALL", "TERM", "SHELL", "TMPDIR")}
    env = {k: v for k, v in env.items() if v}
    for e in manifest.get("requires_env") or []:
        key = e.get("env_key") or e.get("name")
        if key and os.environ.get(key):
            env[key] = os.environ[key]
    for k, v in (rt.get("env") or {}).items():
        # 清单里的 ${VAR} 要用真实环境变量展开，展不开就原样留着让上游自己报错
        env[str(k)] = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}",
                             lambda m: os.environ.get(m.group(1), m.group(0)), str(v))
    return StdioServerParameters(command=str(rt["command"]),
                                 args=[str(a) for a in (rt.get("args") or [])],
                                 env=env), rt


async def _collect(session, tools_out: list) -> None:
    await asyncio.wait_for(session.initialize(), timeout=CONNECT_TIMEOUT)
    listed = await asyncio.wait_for(session.list_tools(), timeout=CONNECT_TIMEOUT)
    tools_out.extend(listed.tools)


async def probe_one(manifest: dict, runtime_id: str | None) -> tuple[list[dict], str]:
    """连接服务器并拉取工具清单。返回 (tools, runtime_id)。"""
    from mcp import ClientSession

    rt = _pick_runtime(manifest, runtime_id)
    raw: list = []

    if rt.get("type") == "http":
        # http 型要真实端点；带 ${VAR} 的头展不开就会被服务端拒（401），
        # 那正是我们要如实记下的结果 —— 不能假装探过。
        from mcp.client.streamable_http import streamablehttp_client

        headers = {str(k): _expand(v) for k, v in (rt.get("headers") or {}).items()}
        kwargs: dict = {"timeout": CONNECT_TIMEOUT}
        if headers:
            kwargs["headers"] = headers
        async with streamablehttp_client(_expand(str(rt["url"])), **kwargs) as transport:
            read, write = transport[0], transport[1]
            async with ClientSession(read, write) as session:
                await _collect(session, raw)
    else:
        from mcp.client.stdio import stdio_client

        params, rt = _server_params(manifest, runtime_id)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await _collect(session, raw)

    listed = type("L", (), {"tools": raw})()
    tools = []
    for t in listed.tools:
        ann = t.annotations
        tools.append({
            "name": t.name,
            "description": t.description or "",
            "read_only": bool(getattr(ann, "readOnlyHint", False)) if ann else False,
            "input_schema": t.inputSchema or {"type": "object", "properties": {}},
        })
    return tools, str(rt.get("id") or "stdio")


def probe(name: str, *, runtime_id: str | None, dry_run: bool, skip_auth: bool) -> str:
    """探测一个服务器，写回 tools.json 与 security 块。返回状态字符串。"""
    yaml = _yaml()
    matches = list(SERVERS_DIR.glob(f"*/{name}/mcp.yaml"))
    if not matches:
        return f"✗ {name}: 找不到清单"
    path = matches[0]
    manifest = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    # 自研服务器的 tools.json 由 gen_manifests.py 从实现直接生成（--describe 就是活的实现），
    # 探测它们纯属多此一举，而且写进去的 probed_at 会被下次 gen_manifests 抹掉
    if "totalclaw" in (manifest.get("tags") or []):
        return f"· {name}: 跳过（自研服务器，tools.json 由 gen_manifests.py 生成）"

    # 指向 localhost 的条目要用户先在本机把那个服务跑起来。探它只会拿到
    # 连接错误，说明不了条目本身有没有问题 —— 跳过，别混进失败计数里。
    for rt in manifest.get("runtimes") or []:
        url = str(rt.get("url") or "")
        if url and re.search(r"//(localhost|127\.0\.0\.1|\[::1\])\b", url):
            return f"· {name}: 跳过（{url} 是本机端点，需用户自行启动该服务）"

    req_env = [e.get("env_key") or e.get("name") for e in (manifest.get("requires_env") or [])]
    missing = [e for e in req_env if e and not os.environ.get(e)]
    if missing and skip_auth:
        return f"· {name}: 跳过（缺凭据 {', '.join(missing)}）"

    if dry_run:
        try:
            params, rt = _server_params(manifest, runtime_id)
        except RuntimeError as e:
            return f"✗ {name}: {e}"
        return f"[dry-run] {name}: {params.command} {' '.join(params.args)}"

    try:
        tools, used_runtime = asyncio.run(probe_one(manifest, runtime_id))
    except asyncio.TimeoutError:
        return f"✗ {name}: 连接超时（{CONNECT_TIMEOUT:.0f}s）"
    except Exception as e:  # noqa: BLE001 - 上游千奇百怪，一条失败不该中断整轮
        root = _root_cause(e)
        detail = str(root).splitlines()[0][:120] if str(root) else type(root).__name__
        hint = "（可能缺凭据）" if missing else ""
        return f"✗ {name}: {type(root).__name__}: {detail}{hint}"

    findings = scan_tools(tools)
    verdict = "warn" if findings else "allow"

    (path.parent / "tools.json").write_text(
        json.dumps(tools, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    manifest["tools"] = {
        "probed_at": _now(),
        "probed_runtime": used_runtime,
        "count": len(tools),
        "file": "tools.json",
    }
    sec = dict(manifest.get("security") or {})
    sec.update({
        "scan_verdict": verdict,
        "prompt_injection_findings": findings,
        "osv": sec.get("osv", "unscanned"),
    })
    manifest["security"] = sec
    head = "".join(l for l in path.read_text(encoding="utf-8").splitlines(keepends=True)
                   if l.startswith("#"))
    path.write_text(head + yaml.safe_dump(manifest, allow_unicode=True,
                                          sort_keys=False, width=100), encoding="utf-8")

    flag = f"  ⚠ 注入嫌疑 {len(findings)} 处" if findings else ""
    ro = sum(1 for t in tools if t["read_only"])
    return f"✓ {name}: {len(tools)} 个工具（只读 {ro}）via {used_runtime}{flag}"


def _now() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _all_names() -> list[str]:
    return sorted(p.parent.name for p in SERVERS_DIR.glob("*/*/mcp.yaml"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="*", help="要探测的服务器名；留空需配 --all")
    ap.add_argument("--all", action="store_true", help="探测全部")
    ap.add_argument("--runtime", help="指定 runtime id（默认取第一个 stdio）")
    ap.add_argument("--skip-auth", action="store_true", help="跳过缺凭据的服务器")
    ap.add_argument("--dry-run", action="store_true", help="只打印将执行的命令")
    args = ap.parse_args()

    names = _all_names() if args.all else args.names
    if not names:
        ap.error("给出服务器名，或用 --all")

    ok = warn = fail = skip = 0
    for n in names:
        line = probe(n, runtime_id=args.runtime, dry_run=args.dry_run, skip_auth=args.skip_auth)
        print(" ", line)
        if line.startswith("✓"):
            ok += 1
            if "⚠" in line:
                warn += 1
        elif line.startswith("✗"):
            fail += 1
        elif line.startswith("·"):
            skip += 1
    print(f"\n探测完成：成功 {ok}（其中 {warn} 个有注入嫌疑）· 失败 {fail} · 跳过 {skip}")
    if ok and not args.dry_run:
        print("接下来运行 python3 scripts/gen_registry.py 更新索引")
    return 1 if fail and not ok else 0


if __name__ == "__main__":
    raise SystemExit(main())
