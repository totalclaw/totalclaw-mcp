#!/usr/bin/env python3
"""生成 registry.json —— 本仓唯一的索引生成入口（对标 totalclaw-plugins/scripts/gen_registry.py）。

遍历 registry/servers/<category>/<name>/，读取每个 mcp.yaml，按 SPEC.md §4 校验，
计算逐文件 sha256 与 bundle_sha256（与 agent 侧 plugin_hub._verify_files 同构），
输出 schema_version=1 的 registry.json。

用法：
  python3 scripts/gen_registry.py            # 生成
  python3 scripts/gen_registry.py --check    # CI：只校验现有 registry.json 与磁盘一致，不一致退出码 1
  python3 scripts/gen_registry.py --strict   # 把「包未 pin 版本」等警告升级为错误
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVERS_DIR = ROOT / "registry" / "servers"
REGISTRY = ROOT / "registry.json"
REGISTRY_NAME = "totalclaw-mcp"
REPO_RAW_BASE = "https://gitee.com/jlzdyx/totalclaw-mcp/raw/master"
REPO_GIT = "https://gitee.com/jlzdyx/totalclaw-mcp.git"
API_BASE = "https://mcp.taituai.com/api"
SKIP_NAMES = {"_TEMPLATE"}
SKIP_FILES = {".DS_Store"}
SKIP_DIRS = {"__pycache__"}
SKIP_SUFFIXES = {".pyc", ".pyo"}

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
CATEGORY_RE = re.compile(r"^[a-z0-9][a-z0-9_]*$")
ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
TRANSPORTS = {"stdio", "http"}
AUTH_MODES = {"none", "header", "oauth"}
PIN_LAUNCHERS = {"npx", "uvx", "pipx", "bunx", "pnpx"}
DEFAULTS_ALLOWED = {
    "enabled", "timeout", "connect_timeout", "keepalive_interval",
    "supports_parallel_tool_calls", "tools", "sampling", "elicitation", "apps", "identity",
}
SHELLS = {"bash", "sh", "zsh", "dash", "fish", "ksh", "cmd", "cmd.exe",
          "powershell", "powershell.exe", "pwsh", "pwsh.exe"}
EGRESS_RE = re.compile(r"\b(curl|wget|nc|ncat|socat|telnet)\b|/dev/tcp/|Invoke-WebRequest|Invoke-RestMethod")

WARNINGS: list[str] = []


def _require_yaml():
    try:
        import yaml  # type: ignore
        return yaml
    except ImportError:
        print("需要 PyYAML：pip install pyyaml", file=sys.stderr)
        raise SystemExit(2)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _bundle_hash(files: list[dict]) -> str:
    """排序遍历的确定性 bundle 摘要：sha256(rel + ':' + file_sha256 换行拼接)。"""
    h = hashlib.sha256()
    for f in sorted(files, key=lambda x: x["path"]):
        h.update(f"{f['path']}:{f['sha256']}\n".encode("utf-8"))
    return h.hexdigest()


def _fail(msg: str) -> None:
    raise SystemExit(f"✗ {msg}")


def _warn(msg: str, strict: bool) -> None:
    if strict:
        _fail(msg)
    WARNINGS.append(msg)


# ── 包版本 pin 检查（与 totalclaw_cli/mcp_catalog.package_pin_problem 同规则） ──

# 哪个选项后面跟的是**包名**、哪个后面跟的是别的东西，按 launcher 分：
#   npx -p / --package <包> <bin名>    -p 后面是包，再后面那个是要跑的可执行名
#   uvx --from <包> <bin名>            同理
#   uvx -p / --python 3.12 <包>        -p 后面是 Python 版本，不是包
#   uvx --with <额外依赖> <包>          --with 后面是附加依赖，不是主包
# 混起来处理就会查错对象：npx 的 -p 被当成「跳过下一个」的话，
# 真包被跳过、bin 名被当成包，于是报「未 pin 版本」——但那个位置本来就不该有版本。
_PKG_AFTER = {
    "npx": ("-p", "--package"),
    "bunx": ("-p", "--package"),
    "pnpx": ("-p", "--package"),
    "uvx": ("--from",),
    "pipx": ("--spec",),
}
_SKIP_AFTER = {
    "uvx": ("-p", "--python", "--with"),
    "pipx": ("-p", "--python"),
}


def _package_arg(launcher: str, args: list[str]) -> str | None:
    """从启动参数里挑出真正的包名。"""
    pkg_after = _PKG_AFTER.get(launcher, ())
    skip_after = _SKIP_AFTER.get(launcher, ())
    skip_next = False
    for i, a in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if a in pkg_after:
            return args[i + 1] if i + 1 < len(args) else None
        if a in skip_after:
            skip_next = True
            continue
        if a.startswith("-"):
            continue
        return a          # 没有显式选项时，第一个位置参数就是包
    return None


def _pin_problem(launcher: str, args: list[str]) -> str | None:
    if launcher not in PIN_LAUNCHERS:
        if launcher == "docker":
            for a in args:
                if "/" in a and ":" not in a.split("/")[-1] and "@sha256" not in a and not a.startswith("-"):
                    return f"docker 镜像未带 tag：{a}"
        return None
    pkg = _package_arg(launcher, args)
    if not pkg:
        return "找不到包名"
    if launcher in ("npx", "bunx", "pnpx"):
        # @scope/name@1.2.3 | name@1.2.3
        body = pkg[1:] if pkg.startswith("@") else pkg
        if "@" not in body:
            return f"npm 包未 pin 版本：{pkg}"
        ver = body.rsplit("@", 1)[1]
        if ver in ("latest", "") or not re.match(r"^\d", ver):
            return f"npm 包版本非精确：{pkg}"
    else:  # uvx / pipx
        if "==" not in pkg:
            return f"PyPI 包未 pin 版本：{pkg}"
    return None


def _validate_runtime(rt: dict, where: str, strict: bool) -> dict:
    rid = str(rt.get("id") or "").strip()
    rtype = str(rt.get("type") or "").strip()
    if not rid:
        _fail(f"{where}: runtime 缺 id")
    if rtype not in TRANSPORTS:
        _fail(f"{where}: runtime {rid} type={rtype!r} 非法（只能 stdio|http；agent 不支持 sse/websocket）")
    has_cmd, has_url = bool(rt.get("command")), bool(rt.get("url"))
    if rtype == "stdio" and not has_cmd:
        _fail(f"{where}: runtime {rid} 是 stdio 但缺 command")
    if rtype == "http" and not has_url:
        _fail(f"{where}: runtime {rid} 是 http 但缺 url")
    if has_cmd and has_url:
        _fail(f"{where}: runtime {rid} 不得同时有 command 与 url（agent 以 url 优先并丢弃 command）")
    args = rt.get("args") or []
    if not isinstance(args, list):
        _fail(f"{where}: runtime {rid} args 必须是列表")
    args = [str(a) for a in args]
    if rtype == "stdio":
        base = Path(str(rt["command"])).name.lower()
        if base in SHELLS and EGRESS_RE.search(" ".join(args)):
            _fail(f"{where}: runtime {rid} 使用 shell + 出网命令，agent mcp_security 会拒绝连接")
        launcher = str(rt.get("launcher") or base)
        prob = _pin_problem(launcher, args)
        if prob:
            _warn(f"{where}: runtime {rid}: {prob}", strict)
        rt.setdefault("launcher", launcher)
    else:
        auth = str(rt.get("auth") or "none")
        if auth not in AUTH_MODES:
            _fail(f"{where}: runtime {rid} auth={auth!r} 非法")
        url = str(rt["url"])
        if "{org}" in url and not rt.get("hosted"):
            _fail(f"{where}: runtime {rid} url 含 {{org}} 但未标 hosted: true")
        if auth == "oauth":
            oa = rt.get("oauth") or {}
            for k in ("authorize_endpoint", "token_endpoint"):
                if k in oa and not str(oa[k]).startswith("https://"):
                    _fail(f"{where}: runtime {rid} oauth.{k} 必须 https")
    return rt


def _validate_env_list(items, where: str, key: str) -> list[dict]:
    out = []
    for it in items or []:
        if isinstance(it, str):
            it = {"name": it}
        if not isinstance(it, dict) or not it.get("name"):
            _fail(f"{where}: {key} 每项需有 name")
        if not ENV_NAME_RE.match(str(it["name"])):
            _fail(f"{where}: {key} 变量名非法：{it['name']}")
        out.append(it)
    return out


def _icon_rel(server_dir: Path) -> str:
    """条目自带图标的相对路径；没有就空串（由客户端回落到生成的字母块）。"""
    for fn in ("icon.svg", "icon.png"):
        if (server_dir / fn).is_file():
            return fn
    return ""


def _collect_server(server_dir: Path, category: str, strict: bool) -> dict:
    yaml = _require_yaml()
    manifest_path = server_dir / "mcp.yaml"
    where = manifest_path.relative_to(ROOT).as_posix()
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}

    name = str(manifest.get("name") or "").strip()
    if not name:
        _fail(f"{where}: 缺 name")
    if name != server_dir.name:
        _fail(f"{where}: name={name!r} 与目录名 {server_dir.name!r} 不一致")
    if not NAME_RE.match(name):
        _fail(f"{where}: name={name!r} 不合法（仅 [a-z0-9_-]，字母数字开头）")
    if not CATEGORY_RE.match(category):
        _fail(f"registry/servers/{category}: 品类目录名不合法（仅 [a-z0-9_]）")
    if manifest.get("manifest_version") != 1:
        _fail(f"{where}: manifest_version 必须为 1")
    if manifest.get("kind") != "mcp_server":
        _fail(f"{where}: kind 必须为 mcp_server")
    if not manifest.get("version"):
        _fail(f"{where}: 缺 version")
    if str(manifest.get("category") or category) != category:
        _fail(f"{where}: category={manifest.get('category')!r} 与目录 {category!r} 不一致")

    runtimes = manifest.get("runtimes") or []
    if not isinstance(runtimes, list) or not runtimes:
        _fail(f"{where}: runtimes 至少需要 1 个")
    rids = []
    runtimes = [_validate_runtime(dict(rt), where, strict) for rt in runtimes]
    for rt in runtimes:
        if rt["id"] in rids:
            _fail(f"{where}: runtime id 重复：{rt['id']}")
        rids.append(rt["id"])

    requires_env = _validate_env_list(manifest.get("requires_env"), where, "requires_env")
    optional_env = _validate_env_list(manifest.get("optional_env"), where, "optional_env")

    defaults = manifest.get("defaults") or {}
    bad = set(defaults) - DEFAULTS_ALLOWED
    if bad:
        _fail(f"{where}: defaults 含 agent 不支持的键：{sorted(bad)}")

    # tools 快照
    tools_meta = manifest.get("tools") or {}
    tool_names: list[str] = []
    if tools_meta.get("file"):
        tf = server_dir / str(tools_meta["file"])
        if not tf.exists():
            _fail(f"{where}: tools.file={tools_meta['file']} 不存在")
        try:
            tool_items = json.loads(tf.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            _fail(f"{where}: {tools_meta['file']} 不是合法 JSON：{e}")
        if not isinstance(tool_items, list):
            _fail(f"{where}: {tools_meta['file']} 必须是 JSON 数组")
        tool_names = [str(t.get("name")) for t in tool_items if isinstance(t, dict) and t.get("name")]
    elif isinstance(tools_meta.get("items"), list):
        tool_names = [str(t.get("name")) for t in tools_meta["items"] if isinstance(t, dict) and t.get("name")]

    security = dict(manifest.get("security") or {})
    security.setdefault("scan_verdict", "allow" if tools_meta else "unscanned")

    rel_root = server_dir.relative_to(ROOT).as_posix()
    files = []
    for p in sorted(server_dir.rglob("*")):
        if not p.is_file() or p.name in SKIP_FILES or p.suffix in SKIP_SUFFIXES:
            continue
        if SKIP_DIRS & set(p.relative_to(server_dir).parts[:-1]):
            continue
        rel = p.relative_to(server_dir).as_posix()
        files.append({"path": rel, "sha256": _sha256(p), "size": p.stat().st_size})

    entry = {
        # ── 市场 schema v1 兼容字段（agent plugin_hub.is_hub_entry 需要 path + files） ──
        "name": name,
        "id": f"{REGISTRY_NAME}/{category}/{name}",
        "display_name": manifest.get("display_name") or name,
        # 中英各存一份，接口按 lang 挑。少了它，英文界面上 84 个条目只能显示中文名。
        "display_name_en": manifest.get("display_name_en") or "",
        "description": manifest.get("description") or "",
        **({"description_zh": manifest["description_zh"]} if manifest.get("description_zh") else {}),
        "version": str(manifest["version"]),
        "author": manifest.get("author") or "",
        **({"license": manifest["license"]} if manifest.get("license") else {}),
        **({"homepage": manifest["homepage"]} if manifest.get("homepage") else {}),
        "verified": bool(manifest.get("verified", True)),  # 官方仓内置即 verified；第三方 PR 由维护者审后置位
        **({"tested_with": manifest["tested_with"]} if manifest.get("tested_with") else {}),
        "category": category,
        # 条目目录里有 icon.svg/png 就把相对路径挂出来。此前 SPEC 写了这个可选文件，
        # 但索引里根本没有这个字段 —— 也就是说就算真放了图标，客户端也找不到它。
        # 目前一个都没有（厂商 logo 有商标，不自造），字段先备好，放进去即刻生效。
        "icon": _icon_rel(server_dir),
        "tags": [str(t) for t in (manifest.get("tags") or [])],
        "kind": "mcp_server",
        "platforms": manifest.get("platforms") or ["darwin", "linux", "win32"],
        # ── MCP 专属摘要（市场列表 / 安装器选 runtime 用，详情仍以 mcp.yaml 为准） ──
        "transports": sorted({rt["type"] for rt in runtimes}),
        "launchers": sorted({str(rt.get("launcher")) for rt in runtimes if rt["type"] == "stdio"}),
        "runtimes": [
            {k: v for k, v in {
                "id": rt["id"], "type": rt["type"], "launcher": rt.get("launcher"),
                "auth": rt.get("auth"), "hosted": rt.get("hosted"),
                # 客户端拿它去重（与内置目录、与已添加的连接器比包名 / 地址），不必为每条再拉 mcp.yaml
                "package": _runtime_package(rt), "url": rt.get("url") if rt["type"] == "http" else None,
            }.items() if v is not None}
            for rt in runtimes
        ],
        "requires_env": [
            {k: v for k, v in {
                "name": e["name"], "description": e.get("description"), "prompt": e.get("prompt"),
                "secret": e.get("secret"), "required": e.get("required", True), "runtimes": e.get("runtimes"),
                # doc_url/doc_label 必须进索引：qiye-app 的安装向导读的是索引，
                # 不是清单文件。漏掉它们，用户在凭据那一步只看得到「请输入 XXX_KEY」，
                # 不知道去哪儿申请——凭据填不上，条目就等于装不了。
                "doc_url": e.get("doc_url"), "doc_label": e.get("doc_label"),
            }.items() if v is not None}
            for e in requires_env
        ],
        "optional_env": [e["name"] for e in optional_env],
        "tools_count": len(tool_names),
        "tools": tool_names,
        "security": security,
        # ── 分发字段（与 plugins/tools 完全一致；agent 侧可直接复用下载/校验） ──
        "path": rel_root,
        "raw_base": f"{REPO_RAW_BASE}/{rel_root}",
        "git_sparse": {"repo": REPO_GIT, "subdir": rel_root},
        "files": files,
        "bundle_sha256": _bundle_hash(files),
    }
    return entry


_UVX_VALUE_FLAGS = {"--with", "-w", "--python", "-p", "--index-url", "--extra-index-url", "--with-editable",
                    "--with-requirements", "--refresh-package", "--index", "--default-index"}


def _runtime_package(rt: dict) -> str | None:
    """npx / uvx 运行时的包规格（含钉住的版本），其它启动方式返回 None。"""
    launcher = rt.get("launcher") or rt.get("command")
    args = [str(a) for a in rt.get("args") or []]
    if launcher == "npx":
        i = 0
        while i < len(args):
            a = args[i]
            if a in ("-p", "--package") and i + 1 < len(args):
                return args[i + 1]
            if not a.startswith("-"):
                return a
            i += 1
        return None
    if launcher == "uvx":
        if "--from" in args:
            i = args.index("--from")
            return args[i + 1] if i + 1 < len(args) else None
        i = 0
        while i < len(args):
            a = args[i]
            if a in _UVX_VALUE_FLAGS:
                i += 2
                continue
            if not a.startswith("-"):
                return a
            i += 1
    return None


def build(strict: bool = False) -> dict:
    entries = []
    if not SERVERS_DIR.exists():
        _fail(f"{SERVERS_DIR} 不存在")
    for category_dir in sorted(SERVERS_DIR.iterdir()):
        if not category_dir.is_dir() or category_dir.name in SKIP_NAMES:
            continue
        for server_dir in sorted(category_dir.iterdir()):
            if not server_dir.is_dir() or server_dir.name in SKIP_NAMES:
                continue
            if not (server_dir / "mcp.yaml").exists():
                _fail(f"{server_dir}: 缺 mcp.yaml")
            entries.append(_collect_server(server_dir, category_dir.name, strict))
    names = [e["name"] for e in entries]
    if len(names) != len(set(names)):
        _fail(f"服务器 name 重复：{sorted(n for n in names if names.count(n) > 1)}")
    # 热度（npm 周下载 / PyPI 周下载 / GitHub 星标）单独放一份文件：定期刷新不必改各条清单的版本号。
    # 客户端按 score 排「热门常用」；没有数据的条目记 0。
    pop_file = ROOT / "registry" / "popularity.json"
    popularity = json.loads(pop_file.read_text(encoding="utf-8")) if pop_file.exists() else {}
    for e in entries:
        e["popularity"] = popularity.get(e["name"]) or {"score": 0}
    return {
        "schema_version": 1,
        "registry": REGISTRY_NAME,
        "id_scheme": "<registry>/<category>/<name>",
        "source": REPO_GIT,
        "api_base": API_BASE,
        "servers": entries,
    }


def _stable_dump(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def main() -> None:
    strict = "--strict" in sys.argv
    data = build(strict=strict)
    for w in WARNINGS:
        print(f"⚠ {w}", file=sys.stderr)
    if "--check" in sys.argv:
        if not REGISTRY.exists():
            _fail("registry.json 不存在，先运行 gen_registry.py")
        current = json.loads(REGISTRY.read_text(encoding="utf-8"))
        current.pop("generated_at", None)
        if current != data:
            _fail("registry.json 与磁盘不一致，请重新运行 scripts/gen_registry.py")
        print(f"✓ registry.json 一致（{len(data['servers'])} 个服务器）")
        return
    data_out = dict(data)
    data_out["generated_at"] = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # generated_at 放在 servers 之前，便于阅读
    ordered = {k: data_out[k] for k in ("schema_version", "registry", "id_scheme", "source", "api_base", "generated_at")}
    ordered["servers"] = data_out["servers"]
    REGISTRY.write_text(_stable_dump(ordered), encoding="utf-8")
    print(f"✓ 已生成 {REGISTRY.relative_to(ROOT)}：{len(data['servers'])} 个服务器，{len(WARNINGS)} 条警告")


if __name__ == "__main__":
    main()
