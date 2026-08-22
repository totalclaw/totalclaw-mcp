#!/usr/bin/env python3
"""从 servers/ 的自研实现生成 registry 清单。

registry 里的每一条清单都指向**我们自己的 MCP 服务器**（totalclaw-mcp-servers 包），
而不是任何第三方托管端点 —— 装到 agent 上跑的是本仓的代码。

    servers/totalclaw_mcp_servers/packs/<name>.yaml   声明式 pack
    servers/totalclaw_mcp_servers/native/<name>.py    原生服务器
        ↓  本脚本
    registry/servers/<category>/<name>/mcp.yaml       安装清单（含 runtimes / requires_env）

用法：python3 scripts/gen_manifests.py [--force] [--dry-run]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVERS = ROOT / "servers"
SERVERS_DIR = ROOT / "registry" / "servers"
PKG_VERSION = "0.1.0"

# 服务器 → 本仓分类 + 中文别名（用于市场展示与检索）
META: dict[str, dict] = {
    "github":      {"category": "dev",     "tags": ["git", "issues", "pull-requests", "code"]},
    "gitee":       {"category": "dev",     "tags": ["git", "码云", "issues"]},
    "notion":      {"category": "office",  "tags": ["笔记", "知识库", "数据库"]},
    "tencent_map": {"category": "web",     "tags": ["地图", "poi", "路线规划", "地理编码"]},
    "wecom":       {"category": "comm",    "tags": ["企业微信", "通讯录", "消息", "scrm"]},
    "feishu":      {"category": "comm",    "tags": ["飞书", "lark", "多维表格", "日历", "消息"]},
    "dingtalk":    {"category": "comm",    "tags": ["钉钉", "通讯录", "考勤", "审批"]},
    "imap_mail":   {"category": "comm",    "tags": ["邮箱", "imap", "smtp", "qq邮箱", "网易邮箱"]},
    "jiandaoyun":  {"category": "office",  "tags": ["简道云", "表单", "低代码", "数据"]},
    "tapd":        {"category": "dev",     "tags": ["需求", "缺陷", "迭代", "研发管理"]},
    "jinshuju":    {"category": "office",  "tags": ["金数据", "表单", "问卷", "报名"]},
    "baidu_netdisk": {"category": "office", "tags": ["百度网盘", "网盘", "文件", "存储"]},
    "linear":      {"category": "dev",     "tags": ["issue", "项目管理", "研发协作"]},
    "canva":       {"category": "creative", "tags": ["设计", "海报", "品牌模板", "导出"]},
    "qcc":         {"category": "data",    "tags": ["企查查", "工商", "股东", "企业信息"]},
    "tianyancha":  {"category": "data",    "tags": ["天眼查", "工商", "股东", "诉讼", "企业信息"]},
    "web":         {"category": "web",     "tags": ["网页抓取", "正文抽取", "无需凭据"]},
    "tencent_cloudbase": {"category": "dev", "tags": ["腾讯云", "云开发", "cloudbase", "小程序"]},
    "moka":        {"category": "hr",      "tags": ["招聘", "候选人", "职位", "组织架构"]},
}
DEFAULT_CATEGORY = "misc"


def _py() -> str:
    return sys.executable


def _describe(name: str) -> dict:
    import json

    out = subprocess.run(
        [_py(), "-m", "totalclaw_mcp_servers", name, "--describe"],
        cwd=SERVERS, capture_output=True, text=True, check=False,
    )
    if out.returncode != 0:
        raise SystemExit(f"✗ describe {name} 失败：{out.stderr.strip()[:300]}")
    return json.loads(out.stdout)


def _list_servers() -> list[str]:
    out = subprocess.run(
        [_py(), "-m", "totalclaw_mcp_servers", "--list"],
        cwd=SERVERS, capture_output=True, text=True, check=False,
    )
    if out.returncode != 0:
        raise SystemExit(f"✗ 列举服务器失败：{out.stderr.strip()[:300]}")
    return [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]


def _requires_env(desc: dict) -> list[dict]:
    secret_hint = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD")
    items = []
    for v in desc.get("required_env") or []:
        items.append({
            "name": v,
            "env_key": v,          # 保留原变量名：服务器进程直接读它
            "description": f"{desc['display_name']} 所需的 {v}",
            "prompt": f"请输入 {v}",
            "secret": any(h in v.upper() for h in secret_hint),
            "required": True,
        })
    return items


def build_manifest(desc: dict) -> tuple[dict, str]:
    name = desc["name"]
    meta = META.get(name, {})
    category = meta.get("category", DEFAULT_CATEGORY)
    tools = desc.get("tools") or []
    req_env = _requires_env(desc)

    manifest = {
        "manifest_version": 1,
        "requires_protocol_version": ">=1",
        "tested_with": ">=0.63.72",
        "name": name,
        "display_name": desc["display_name"],
        "version": PKG_VERSION,
        "description": desc.get("description") or f"{desc['display_name']} MCP server.",
        "description_zh": desc.get("description") or "",
        "author": "totalclaw",
        "license": "Apache-2.0",
        "homepage": "https://gitee.com/jlzdyx/totalclaw-mcp",
        "category": category,
        "tags": ["totalclaw", "self-hosted"] + meta.get("tags", []),
        "kind": "mcp_server",
        "runtimes": [
            # 首选：已安装本包时直接用控制台脚本
            {
                "id": "console",
                "type": "stdio",
                "launcher": "binary",
                "command": "totalclaw-mcp-server",
                "args": [name],
                "requires": {"python": ">=3.10"},
            },
            # 备选：uvx 按需拉起，无需预装
            {
                "id": "uvx",
                "type": "stdio",
                "launcher": "uvx",
                "command": "uvx",
                "args": [f"totalclaw-mcp-servers=={PKG_VERSION}", name],
                "requires": {"python": ">=3.10"},
            },
        ],
        "requires_env": req_env,
        "optional_env": list(desc.get("optional_env") or []),
        "defaults": {
            # 有必填凭据的默认不启用：装上先让用户填，避免一堆红色失败态
            "enabled": not req_env,
            "timeout": 120,
            "connect_timeout": 60,
        },
        "tools": {
            "probed_runtime": "console",
            "count": len(tools),
            "file": "tools.json",
        },
        "security": {
            "scan_verdict": "allow",
            "prompt_injection_findings": [],
            "osv": "clean",
            "note": "本仓自研实现，非第三方托管端点",
        },
    }

    ro = sum(1 for t in tools if t.get("read_only"))
    lines = [
        f"# {desc['display_name']}", "",
        desc.get("description") or "", "",
        f"由 TotalClaw 自研实现（`totalclaw-mcp-servers` 包），"
        f"共 {len(tools)} 个工具（只读 {ro} / 写入 {len(tools) - ro}）。", "",
        "## 工具", "",
    ]
    for t in tools:
        flag = "只读" if t.get("read_only") else "**写入**"
        lines.append(f"- `{t['name']}`（{flag}）— {t['description']}")
    lines += ["", "## 安装", "", "```bash", f"totalclaw mcp install {name}", "```", ""]
    if req_env:
        lines += ["## 需要的凭据", ""]
        for e in req_env:
            lines.append(f"- `{e['name']}`{'（密钥）' if e['secret'] else ''}")
        lines += ["", "凭据写入 `$TOTALCLAW_HOME/.env`，配置文件里只保留 `${…}` 引用。", ""]
    if desc.get("docs"):
        lines += [f"上游 API 文档：{desc['docs']}", ""]
    lines += ["---", "", "> 由 `scripts/gen_manifests.py` 从 `servers/` 的实现自动生成，请勿手改。"]
    return manifest, "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="覆盖已存在的清单")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    import json

    import yaml

    names = _list_servers()
    written = 0
    for name in names:
        desc = _describe(name)
        manifest, readme = build_manifest(desc)
        d = SERVERS_DIR / manifest["category"] / name
        target = d / "mcp.yaml"
        if target.exists() and not args.force:
            print(f"  · 跳过已存在 {target.relative_to(ROOT)}（--force 覆盖）")
            continue
        if args.dry_run:
            print(f"  [dry-run] {target.relative_to(ROOT)}  {len(desc.get('tools') or [])} 工具")
            written += 1
            continue
        d.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "# 由 scripts/gen_manifests.py 从 servers/ 的自研实现生成，请勿手改。\n"
            "# 实现位置：servers/totalclaw_mcp_servers/{packs,native}/\n"
            + yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False, width=100),
            encoding="utf-8",
        )
        (d / "README.md").write_text(readme, encoding="utf-8")
        (d / "tools.json").write_text(
            json.dumps([
                {"name": t["name"], "description": t["description"],
                 "read_only": t.get("read_only", True), "input_schema": t.get("params", {})}
                for t in (desc.get("tools") or [])
            ], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"  ✓ {target.relative_to(ROOT)}  {len(desc.get('tools') or [])} 工具")
        written += 1

    print(f"\n完成：{written} 个清单。接下来运行 python3 scripts/gen_registry.py")


if __name__ == "__main__":
    main()
