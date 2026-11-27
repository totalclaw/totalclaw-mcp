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

隔离（默认开，--no-sandbox 关）：被探的是第三方包，有的一启动就往 HOME 里装东西
（往 ~/.claude/skills 装技能、起常驻守护进程、扫本机各客户端的 MCP 配置并落盘）。
所以每次运行给服务器一个临时 HOME 和临时工作目录，只把包管理器的缓存与镜像配置
软链接进去；探完列出它新写了什么（「副作用」），并结束仍在沙箱里的后台进程。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SERVERS_DIR = ROOT / "registry" / "servers"
CONNECT_TIMEOUT = 90.0

# 软链接进沙箱 HOME 的东西：包缓存（免得每条都重下）与包管理器配置（保持用户的镜像源）
_SHARED_HOME = (".npm", ".npmrc", ".cache/uv", ".local/share/uv", ".config/uv", ".config/pip", ".pip")


class _Sandbox:
    """一次运行共用的临时 HOME + 工作目录；记录每个服务器新写入的路径。"""

    def __init__(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="probe-sbx-")).resolve()
        self.home = self.root / "home"
        self.work = self.root / "work"
        self.home.mkdir()
        self.work.mkdir()
        real = Path.home()
        for rel in _SHARED_HOME:
            src = real / rel
            if src.exists():
                dst = self.home / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.symlink_to(src)
        self._seen = self._snapshot()

    def _snapshot(self) -> set[str]:
        out: set[str] = set()
        for base in (self.home, self.work):
            for dirpath, dirnames, filenames in os.walk(base):   # 不跟进软链接（共享缓存）
                for x in dirnames + filenames:
                    out.add(os.path.relpath(os.path.join(dirpath, x), self.root))
        return out

    def new_writes(self) -> list[str]:
        """自上次调用以来新出现的路径，按「home/前两级」「work/第一级」归并。"""
        now = self._snapshot()
        fresh = now - self._seen
        self._seen = now
        tops: set[str] = set()
        for p in fresh:
            parts = Path(p).parts
            keep = 3 if parts[0] == "home" else 2
            tops.add("/".join(parts[:keep]).replace("home/", "~/", 1).replace("work/", "./", 1))
        return sorted(tops)

    def kill_leftovers(self) -> list[int]:
        """结束仍在沙箱里开着文件 / 以沙箱为工作目录的进程（服务器甩出去的守护进程）。"""
        try:
            out = subprocess.run(["lsof", "-F", "pn", "+D", str(self.root)], capture_output=True,
                                 text=True, timeout=30).stdout
        except (OSError, subprocess.TimeoutExpired):
            return []
        # 只认「报出的路径就在沙箱目录里」的进程：共享缓存是软链接，别因为别的进程
        # 恰好开着 ~/.npm 里的文件就把它当成残留结束掉
        pids: set[int] = set()
        cur = None
        for ln in out.splitlines():
            if ln.startswith("p"):
                cur = int(ln[1:]) if ln[1:].isdigit() else None
            elif ln.startswith("n") and cur and cur != os.getpid() and ln[1:].startswith(str(self.root)):
                pids.add(cur)
        pids = sorted(pids)
        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
        return pids

    def close(self) -> None:
        self.kill_leftovers()
        shutil.rmtree(self.root, ignore_errors=True)   # 只删软链接本身，不碰共享缓存


_SANDBOX: _Sandbox | None = None

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
        env[str(k)] = _expand(str(v))
    cwd = None
    if _SANDBOX is not None:
        env["HOME"] = str(_SANDBOX.home)
        cwd = str(_SANDBOX.work)
    # args 也要展开 —— agent 侧 interpolate_env_vars 是对整个 server 字典递归的，
    # 参数里的 ${VAR} 一样会被代入。这里不展开就跟真实启动行为不一致，
    # 表现为「探测挂了但装上能用」，反过来更糟：探测过了但装上挂。
    return StdioServerParameters(command=str(rt["command"]),
                                 args=[_expand(str(a)) for a in (rt.get("args") or [])],
                                 env=env, cwd=cwd), rt


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
        try:
            tools, used_runtime = asyncio.run(probe_one(manifest, runtime_id))
        finally:
            side = _side_effects()
    except asyncio.TimeoutError:
        return f"✗ {name}: 连接超时（{CONNECT_TIMEOUT:.0f}s）{side}"
    except Exception as e:  # noqa: BLE001 - 上游千奇百怪，一条失败不该中断整轮
        root = _root_cause(e)
        detail = str(root).splitlines()[0][:120] if str(root) else type(root).__name__
        hint = "（可能缺凭据）" if missing else ""
        return f"✗ {name}: {type(root).__name__}: {detail}{hint}{side}"

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
    old_text = path.read_text(encoding="utf-8")
    new_text = _rewrite_probe_keys(old_text, manifest["tools"],
                                   {k: sec[k] for k in ("scan_verdict", "prompt_injection_findings", "osv")})
    # 局部改写只动 tools 块与 security 的三个键；解析结果必须与「整体重写」完全一致
    if yaml.safe_load(new_text) != manifest:
        raise RuntimeError(f"{name}: 局部改写清单后内容不一致，未写回")
    path.write_text(new_text, encoding="utf-8")

    flag = f"  ⚠ 注入嫌疑 {len(findings)} 处" if findings else ""
    ro = sum(1 for t in tools if t["read_only"])
    return f"✓ {name}: {len(tools)} 个工具（只读 {ro}）via {used_runtime}{flag}{side}"


def _side_effects() -> str:
    """沙箱里这个服务器新写的路径 + 甩出去的后台进程，拼成状态行后缀；没开沙箱 / 没有则为空。"""
    if _SANDBOX is None:
        return ""
    writes = _SANDBOX.new_writes()
    pids = _SANDBOX.kill_leftovers()
    bits = []
    if writes:
        bits.append("写入 " + "、".join(writes[:6]) + (f" 等 {len(writes)} 处" if len(writes) > 6 else ""))
    if pids:
        bits.append(f"留下后台进程 {len(pids)} 个（已结束）")
    return f"  ⚑ 副作用：{'；'.join(bits)}" if bits else ""


def _block_span(lines: list[str], key: str) -> tuple[int, int] | None:
    """顶层 `key:` 块在行列表里的 [起, 止)；块体是其后所有缩进行 / 空行 / 缩进注释。"""
    for i, ln in enumerate(lines):
        if re.match(rf"{re.escape(key)}:\s*(#.*)?$", ln.rstrip("\n")):
            j = i + 1
            while j < len(lines) and (lines[j].startswith((" ", "\t")) or not lines[j].strip()):
                j += 1
            while j > i + 1 and not lines[j - 1].strip():   # 尾部空行留给块外
                j -= 1
            return i, j
    return None


def _rewrite_probe_keys(text: str, tools: dict, sec_updates: dict) -> str:
    """只改写顶层 `tools:` 块与 `security:` 里探测负责的键，其余文本（含注释）原样保留。

    以前是整份 yaml.safe_dump 重写：缩进注释全丢、文件中部的顶格注释被挪到文件头。
    """
    yaml = _yaml()

    def dump(obj: dict, indent: str = "") -> list[str]:
        out = yaml.safe_dump(obj, allow_unicode=True, sort_keys=False, width=100)
        return [indent + ln + "\n" for ln in out.splitlines()]

    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"

    # security：按两格缩进的键切段，只替换（或追加）探测负责的键；注释与其它键原样保留
    span = _block_span(lines, "security")
    if span is None:
        lines += dump({"security": sec_updates})
    else:
        i, j = span
        body = lines[i + 1:j]
        segs: list[tuple[str | None, list[str]]] = []
        for ln in body:
            m = re.match(r"  ([A-Za-z_][\w-]*):", ln)
            if m:
                segs.append((m.group(1), [ln]))
            elif segs and segs[-1][0] is not None and (ln.startswith("   ") or ln.startswith("  - ")):
                segs[-1][1].append(ln)          # 上一个键的续行（嵌套映射 / 列表）
            else:
                segs.append((None, [ln]))       # 注释、空行
        done = set()
        for k, (key, _) in enumerate(segs):
            if key in sec_updates:
                segs[k] = (key, dump({key: sec_updates[key]}, "  "))
                done.add(key)
        for key, val in sec_updates.items():
            if key not in done:
                segs.append((key, dump({key: val}, "  ")))
        lines[i + 1:j] = [ln for _, seg in segs for ln in seg]

    # tools：整块替换；没有就放在 security 之前（与旧版整体重写的键顺序一致）
    new_tools = dump({"tools": tools})
    span = _block_span(lines, "tools")
    if span is not None:
        lines[span[0]:span[1]] = new_tools
    else:
        sec = _block_span(lines, "security")
        at = sec[0] if sec else len(lines)
        lines[at:at] = new_tools
    return "".join(lines)


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
    ap.add_argument("--no-sandbox", action="store_true",
                    help="不隔离：服务器用真实 HOME 与当前目录（会让它往本机写东西，慎用）")
    args = ap.parse_args()

    names = _all_names() if args.all else args.names
    if not names:
        ap.error("给出服务器名，或用 --all")

    global _SANDBOX
    if not args.no_sandbox and not args.dry_run:
        _SANDBOX = _Sandbox()
    ok = warn = fail = skip = side = 0
    try:
        for n in names:
            line = probe(n, runtime_id=args.runtime, dry_run=args.dry_run, skip_auth=args.skip_auth)
            print(" ", line, flush=True)
            if line.startswith("✓"):
                ok += 1
                if "注入嫌疑" in line:
                    warn += 1
            elif line.startswith("✗"):
                fail += 1
            elif line.startswith("·"):
                skip += 1
            if "⚑ 副作用" in line:
                side += 1
    finally:
        if _SANDBOX is not None:
            _SANDBOX.close()
    print(f"\n探测完成：成功 {ok}（其中 {warn} 个有注入嫌疑）· 失败 {fail} · 跳过 {skip}"
          + (f" · 有副作用 {side} 个（见 ⚑）" if side else ""))
    if ok and not args.dry_run:
        print("接下来运行 python3 scripts/gen_registry.py 更新索引")
    return 1 if fail and not ok else 0


if __name__ == "__main__":
    raise SystemExit(main())
