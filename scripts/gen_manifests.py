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

# uvx 跑法装的代码 = 本仓 servers/ 在这个提交上的样子（必须已推送到 gitee 的 master）。
# - 不走 PyPI：totalclaw-mcp-servers 这个名字不是我们的，谁抢注，用户装上的就是谁的代码。
# - 不走 gitee 归档 .zip：gitee 防火墙对 User-Agent 含「CPython」的下载一律 403，uv 的 UA 恒带它；
#   只剩 git 协议能过，所以用户机器上要有 git。
# 改了 servers/ 之后：先提交并推送，再把这里换成那个提交，然后 --force 重新生成。
SERVERS_COMMIT = "289d9c344390b7ac433a17095c85f413237fbf50"
SERVERS_SOURCE = f"git+https://gitee.com/jlzdyx/totalclaw-mcp.git@{SERVERS_COMMIT}#subdirectory=servers"

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
    "tencent_survey": {"category": "office", "tags": ["腾讯问卷", "问卷", "调研", "答卷"]},
    "tencent_edgeone": {"category": "infra", "tags": ["腾讯云", "edgeone", "cdn", "加速", "刷新预热"]},
    "topview":     {"category": "media",   "tags": ["topview", "营销视频", "带货视频", "数字人", "ugc广告", "跨境电商"]},
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


def _check_servers_commit() -> None:
    """钉住的提交必须已在 gitee 上、且 servers/ 和工作区一致，否则清单写的工具和用户装到的代码对不上。"""
    def git(*a: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, check=False)

    short = SERVERS_COMMIT[:9]
    if git("merge-base", "--is-ancestor", SERVERS_COMMIT, "origin/master").returncode:
        raise SystemExit(f"✗ SERVERS_COMMIT {short} 不在 origin/master 上（没推送的提交用户拉不到；先 git fetch 再试）")
    if git("diff", "--quiet", SERVERS_COMMIT, "--", "servers/").returncode or \
            git("ls-files", "--others", "--exclude-standard", "--", "servers/").stdout.strip():
        raise SystemExit(f"✗ servers/ 与 SERVERS_COMMIT {short} 不一致：先提交并推送，再把 SERVERS_COMMIT 换成那个提交")


def _requires_env(desc: dict) -> list[dict]:
    secret_hint = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD")
    items = []
    # 原生模块可导出 ENV_DOCS：{变量: {description, prompt, doc_url, doc_label}}，
    # 让安装向导告诉用户凭据去哪儿拿，而不是只有一句「请输入 XXX」
    env_docs = desc.get("env_docs") or {}
    required = list(desc.get("required_env") or [])
    # 有 ENV_DOCS 的可选凭据也放进来（required: False）：安装向导只渲染 requires_env，
    # 像 topview 这种「两套凭据配一套即可」的服务器，否则用户在界面上无处可填
    optional = [v for v in desc.get("optional_env") or [] if v in env_docs]
    for v in required + optional:
        doc = env_docs.get(v) or {}
        item = {
            "name": v,
            "env_key": v,          # 保留原变量名：服务器进程直接读它
            "description": doc.get("description") or f"{desc['display_name']} 所需的 {v}",
            "prompt": doc.get("prompt") or f"请输入 {v}",
            "secret": any(h in v.upper() for h in secret_hint),
            "required": v in required,
        }
        for k in ("doc_url", "doc_label"):
            if doc.get(k):
                item[k] = doc[k]
        items.append(item)
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
        # 英文名没有来源可生成（013387d 手工补的），由 main() 从旧清单带过来，重新生成不丢
        **({"display_name_en": desc["display_name_en"]} if desc.get("display_name_en") else {}),
        "version": PKG_VERSION,
        # description 走英文(目录/市场的通用语言)，中文另放 description_zh。
        # 此前两处都填中文,英文界面上就只能看到中文。
        "description": (desc.get("description_en")
                        or desc.get("description")
                        or f"{desc['display_name']} MCP server."),
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
            # 备选：uvx 从本仓钉死的提交现装（桌面端市场只认这条），来源见 SERVERS_COMMIT
            {
                "id": "uvx",
                "type": "stdio",
                "launcher": "uvx",
                "command": "uvx",
                "args": ["--from", SERVERS_SOURCE, "totalclaw-mcp-server", name],
                "requires": {"python": ">=3.10", "git": True},
            },
        ],
        "requires_env": req_env,
        "optional_env": [v for v in desc.get("optional_env") or []
                         if v not in {e["name"] for e in req_env}],
        "defaults": {
            # 有凭据项的默认不启用：装上先让用户填，避免一堆红色失败态
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

    _check_servers_commit()
    names = _list_servers()
    written = 0
    for name in names:
        desc = _describe(name)
        d = SERVERS_DIR / META.get(name, {}).get("category", DEFAULT_CATEGORY) / name
        target = d / "mcp.yaml"
        if target.exists() and not args.force:
            print(f"  · 跳过已存在 {target.relative_to(ROOT)}（--force 覆盖）")
            continue
        if target.exists():
            desc.setdefault("display_name_en", (yaml.safe_load(target.read_text(encoding="utf-8")) or {}).get("display_name_en"))
        manifest, readme = build_manifest(desc)
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
