#!/usr/bin/env python3
"""从 totalclaw-agent 内置目录导入种子清单（一次性 / 可重复执行）。

来源：
  * totalclaw_core/tools/mcp_presets.py  PRESETS（24 条，含 __meta__）
  * totalclaw_cli/mcp_catalog.py         CURATED_CATALOG（2 条）

输出：registry/servers/<category>/<name>/mcp.yaml (+ README.md)
保持 name 与 agent preset 名完全一致（mcp_fetch / playwright / wechat-desktop …），
并通过 requires_env[].env_key 保留上游原始环境变量名，保证既有用户 .env 零迁移。

用法：python3 scripts/import_presets.py --agent ../totalclaw-agent [--force]
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVERS_DIR = ROOT / "registry" / "servers"

ENV_REF_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")
SECRET_RE = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|PASSWD|AUTH|COOKIE|CREDENTIAL)", re.I)
CJK_RE = re.compile(r"[一-鿿]")

# preset 名 → 分类（来源：mcp_presets.BUNDLES + 人工补齐）
CATEGORY_MAP = {
    "chrome_devtools": "web", "playwright": "web", "playwright-py": "web", "mcp_fetch": "web",
    "mcp_brave_search": "web",
    "xiaohongshu": "social", "dy_xhs": "social", "matrixmedia": "social", "socialcrawl": "social",
    "aitoearn": "social",
    "mcp_git": "dev", "mcp_github": "dev", "mcp_everything": "dev", "sentry": "dev", "linear": "dev",
    "docker": "infra",
    "mcp_filesystem": "media",
    "composio": "biz", "mcp_memory": "biz", "mcp_sequential_thinking": "biz", "notion": "biz",
    "mcp_postgres": "data", "mcp_sqlite": "data",
    "mcp_time": "office",
    "wechat-desktop": "comm",
    "unreal_engine": "creative", "blender": "creative",
}
DISPLAY_MAP = {
    "mcp_fetch": "Fetch", "mcp_filesystem": "Filesystem", "mcp_git": "Git", "mcp_github": "GitHub",
    "mcp_memory": "Memory", "mcp_sequential_thinking": "Sequential Thinking", "mcp_time": "Time",
    "mcp_postgres": "PostgreSQL", "mcp_sqlite": "SQLite", "mcp_brave_search": "Brave Search",
    "mcp_everything": "Everything (reference)", "chrome_devtools": "Chrome DevTools",
    "playwright": "Playwright", "playwright-py": "Playwright (built-in Python)",
    "wechat-desktop": "WeChat Desktop (built-in)", "unreal_engine": "Unreal Engine",
    "dy_xhs": "抖音 / 小红书", "xiaohongshu": "小红书", "matrixmedia": "MatrixMedia 媒体矩阵",
    "socialcrawl": "SocialCrawl", "aitoearn": "AiToEarn", "composio": "Composio", "notion": "Notion",
    "linear": "Linear", "sentry": "Sentry", "docker": "Docker", "blender": "Blender",
}


def _load_module(path: Path, name: str, agent_root: Path):
    if str(agent_root) not in sys.path:
        sys.path.insert(0, str(agent_root))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[name] = mod  # dataclass 装饰器需要在 sys.modules 中找到宿主模块
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _yaml():
    try:
        import yaml  # type: ignore
        return yaml
    except ImportError:
        print("需要 PyYAML：pip install pyyaml", file=sys.stderr)
        raise SystemExit(2)


def _launcher_of(command: str) -> str:
    base = Path(command).name.lower()
    if base in {"npx", "uvx", "pipx", "docker", "node", "bunx", "pnpx"}:
        return base
    if base.startswith("python"):
        return "python"
    if base == "totalclaw":
        return "totalclaw"
    return "binary"


def _collect_env_refs(*values) -> dict[str, str | None]:
    """返回 {VAR: default_or_None}，按出现顺序。"""
    found: dict[str, str | None] = {}

    def walk(v):
        if isinstance(v, str):
            for m in ENV_REF_RE.finditer(v):
                found.setdefault(m.group(1), m.group(2))
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, (list, tuple)):
            for x in v:
                walk(x)

    for v in values:
        walk(v)
    return found


def _env_items(refs: dict[str, str | None], name: str) -> tuple[list[dict], list[dict]]:
    required, optional = [], []
    for var, default in refs.items():
        item = {
            "name": var,
            "env_key": var,  # 保留上游原始变量名（不做 MCP_<NAME>_ 命名空间化），兼容既有 .env
            "description": f"{var} for {name}",
            "prompt": f"请输入 {var}",
            "secret": bool(SECRET_RE.search(var)),
        }
        if default is not None:
            item["default"] = default
            item["required"] = False
            optional.append(item)
        else:
            item["required"] = True
            required.append(item)
    return required, optional


def _runtime_from_preset(name: str, cfg: dict) -> dict:
    if "url" in cfg:
        rt = {"id": "remote", "type": "http", "url": cfg["url"]}
        if cfg.get("headers"):
            rt["headers"] = dict(cfg["headers"])
            if any("Bearer" in str(v) for v in cfg["headers"].values()):
                rt["auth"] = "header"
        if cfg.get("auth"):
            rt["auth"] = cfg["auth"]
        return rt
    command = str(cfg.get("command") or "")
    args = [str(a) for a in (cfg.get("args") or [])]
    # 内置 Python 服务器：sys.executable -m totalclaw_core.tools.xxx → totalclaw __mcp-server <name>
    if command == sys.executable or command.endswith("python") or command.endswith("python3"):
        if any(a.startswith("totalclaw_core.") for a in args) or "__mcp-server" in args:
            command, args = "totalclaw", ["__mcp-server", name]
    launcher = _launcher_of(command)
    rt = {"id": launcher, "type": "stdio", "launcher": launcher, "command": command, "args": args}
    if cfg.get("env"):
        rt["env"] = {str(k): str(v) for k, v in cfg["env"].items()}
    if launcher in ("npx", "bunx", "pnpx"):
        rt["requires"] = {"node": ">=18"}
    elif launcher in ("uvx", "pipx"):
        rt["requires"] = {"python": ">=3.10"}
    elif launcher == "docker":
        rt["requires"] = {"docker": True}
    return rt


def _manifest_from_preset(name: str, cfg: dict, meta: dict) -> tuple[dict, str]:
    category = CATEGORY_MAP.get(name, "misc")
    purpose = str(meta.get("purpose") or "").strip()
    setup = str(meta.get("setup") or "").strip()
    source = str(meta.get("source") or "").strip()
    auth_required = str(meta.get("auth_required") or "").strip()
    runtime = _runtime_from_preset(name, cfg)
    refs = _collect_env_refs(cfg.get("args"), cfg.get("env"), cfg.get("headers"), cfg.get("url"))
    required, optional = _env_items(refs, name)

    defaults: dict = {"enabled": True}
    for k in ("timeout", "connect_timeout", "supports_parallel_tool_calls", "keepalive_interval"):
        if k in cfg:
            defaults[k] = cfg[k]
    if isinstance(cfg.get("tools"), dict):
        defaults["tools"] = cfg["tools"]

    desc_en = purpose if purpose and not CJK_RE.search(purpose) else f"{DISPLAY_MAP.get(name, name)} MCP server."
    desc_zh = purpose if CJK_RE.search(purpose) else ""
    manifest = {
        "manifest_version": 1,
        "requires_protocol_version": ">=1",
        "tested_with": ">=0.63.72",
        "name": name,
        "display_name": DISPLAY_MAP.get(name, name),
        "version": "0.1.0",
        "description": desc_en,
        **({"description_zh": desc_zh} if desc_zh else {}),
        "author": "totalclaw" if runtime.get("launcher") == "totalclaw" else "upstream",
        **({"homepage": source} if source.startswith("http") else {}),
        "category": category,
        "tags": [category, "preset"],
        "kind": "mcp_server",
        "runtimes": [runtime],
        "requires_env": required,
        "optional_env": optional,
        "defaults": defaults,
    }
    readme = f"# {manifest['display_name']}\n\n{purpose}\n\n"
    if setup:
        readme += f"## 安装前置\n\n{setup}\n\n"
    if auth_required:
        readme += f"**鉴权**：{auth_required}\n\n"
    if source:
        readme += f"来源：{source}\n"
    readme += "\n> 由 scripts/import_presets.py 从 totalclaw-agent mcp_presets 导入，名称与 preset 保持一致。\n"
    return manifest, readme


def _manifest_from_catalog(entry) -> tuple[dict, str]:
    name = entry.key.replace("-", "_") if entry.key == "unreal-engine" else entry.key
    category = CATEGORY_MAP.get(name, entry.category or "misc")
    if entry.transport == "http":
        runtime = {"id": "remote", "type": "http", "url": entry.url,
                   **({"auth": "header"} if entry.requires_auth else {})}
    else:
        launcher = _launcher_of(entry.command or "")
        runtime = {"id": launcher, "type": "stdio", "launcher": launcher,
                   "command": entry.command, "args": list(entry.args)}
        if entry.env:
            runtime["env"] = dict(entry.env)
    refs = _collect_env_refs(list(entry.args), dict(entry.env), entry.url)
    for hint in entry.env_hints:
        refs.setdefault(hint, None)
    required, optional = _env_items(refs, name)
    defaults: dict = {"enabled": True}
    if entry.tools_include:
        defaults["tools"] = {"include": list(entry.tools_include)}
    manifest = {
        "manifest_version": 1,
        "requires_protocol_version": ">=1",
        "tested_with": ">=0.63.72",
        "name": name,
        "display_name": entry.title,
        "version": "0.1.0",
        "description": entry.summary,
        "author": "upstream",
        "category": category,
        "tags": [category, "catalog"],
        "kind": "mcp_server",
        "runtimes": [runtime],
        "requires_env": required,
        "optional_env": optional,
        "defaults": defaults,
    }
    readme = f"# {entry.title}\n\n{entry.summary}\n\n> 由 scripts/import_presets.py 从 totalclaw_cli/mcp_catalog 导入。\n"
    return manifest, readme


def _write(manifest: dict, readme: str, force: bool) -> bool:
    yaml = _yaml()
    d = SERVERS_DIR / manifest["category"] / manifest["name"]
    target = d / "mcp.yaml"
    if target.exists() and not force:
        print(f"  · 跳过已存在 {target.relative_to(ROOT)}（--force 覆盖）")
        return False
    d.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "# 由 scripts/import_presets.py 生成；人工维护时请同步递增 version。\n"
        + yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
    )
    (d / "README.md").write_text(readme, encoding="utf-8")
    print(f"  ✓ {target.relative_to(ROOT)}")
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default="../totalclaw-agent", help="totalclaw-agent 仓库根目录")
    ap.add_argument("--force", action="store_true", help="覆盖已存在的清单")
    args = ap.parse_args()
    agent_root = (ROOT / args.agent).resolve() if not Path(args.agent).is_absolute() else Path(args.agent)
    presets_py = agent_root / "totalclaw_core" / "tools" / "mcp_presets.py"
    catalog_py = agent_root / "totalclaw_cli" / "mcp_catalog.py"
    if not presets_py.exists():
        raise SystemExit(f"找不到 {presets_py}")

    presets = _load_module(presets_py, "tc_mcp_presets", agent_root)
    written = 0
    print(f"导入 presets（{len(presets.PRESETS)} 条）…")
    seen = set()
    for name, raw in presets.PRESETS.items():
        cfg = {k: v for k, v in raw.items() if k != "__meta__"}
        meta = raw.get("__meta__") or {}
        manifest, readme = _manifest_from_preset(name, cfg, meta)
        seen.add(manifest["name"])
        written += _write(manifest, readme, args.force)

    if catalog_py.exists():
        catalog = _load_module(catalog_py, "tc_mcp_catalog", agent_root)
        entries = getattr(catalog, "CURATED_CATALOG", [])
        print(f"导入 catalog（{len(entries)} 条）…")
        for entry in entries:
            manifest, readme = _manifest_from_catalog(entry)
            if manifest["name"] in seen:
                print(f"  · 跳过 {entry.key}（与 preset {manifest['name']} 重复）")
                continue
            written += _write(manifest, readme, args.force)

    print(f"完成：写入 {written} 个清单。接下来运行 python3 scripts/gen_registry.py")


if __name__ == "__main__":
    main()
