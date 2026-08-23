#!/usr/bin/env python3
"""把厂商自有的 MCP 端点配置转成 registry 清单。

**这些端点是厂商自己的**（apim-gateway.pkulaw.com、openapi.gangtise.com、
mcp.wind.com.cn……），不是任何中间平台的网关——校验见 `--audit` 的域名归类。
厂商既然自己跑着 MCP 服务器，就没有「再实现一遍」的东西可写：REST→MCP pack
要的是底层 REST 契约，而网关正是把它包起来了。指向厂商端点是这里唯一正确的做法。

用法::

    python3 scripts/import_vendor_mcp.py --src <连接器导出目录> --audit
    python3 scripts/import_vendor_mcp.py --src <连接器导出目录> --write

导出目录需含 ``.codebuddy-connector/connectors.json``（元数据）与
``connectors/<id>/mcp.json``（端点配置）。

以下几类会被拒绝，理由写在 ``--audit`` 输出里：
  * ``sse``          —— agent 只支持 stdio 与 streamable-HTTP
  * 测试/演示主机     —— test.* / mcpdemo.* 不是生产端点
  * 平台身份鉴权     —— auth_mode 需要中间平台自己的 token，我们拿不到
  * **他方专属路由** —— URL 路径或 query 里带着别家产品名（如
    ``mcp.wind.com.cn/vserver_workbuddy/``、``?source=workbuddy``）。
    这是厂商为那个产品单开的租户入口，不是通用网关；走它等于占用别人
    谈下来的合作配额。要接得自己去和厂商申请一条路由。
  * 缺端点或缺元数据
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent

# agent 只认这两种传输（SPEC.md §runtimes）。
HTTP_TYPES = {"streamablehttp", "streamable-http", "http"}
STDIO_TYPES = {"stdio"}

# 有些上游配置省了 type，只给 url —— 按有无 command 推断，别当成缺字段拒掉。
def infer_type(cfg: dict[str, Any]) -> str:
    explicit = str(cfg.get("type") or "").lower()
    if explicit:
        return explicit
    if cfg.get("command"):
        return "stdio"
    if cfg.get("url"):
        return "streamablehttp"
    return ""


# 表明调用方身份的请求头。照抄等于冒充别的产品向厂商网关发请求，一律丢弃。
FOREIGN_IDENTITY = re.compile(r"workbuddy|codebuddy", re.I)

# 上游 id 里混进了别家产品名的，改成厂商自己的名字。
SLUG_OVERRIDE = {"wk-workbuddy": "wkinfo"}

# 上游写的是 @latest / 范围 / 干脆不写版本。装什么版本必须是确定的，
# 否则今天能用明天可能就变了。这里钉到查证过的确切版本（查证日 2026-08-22）。
PINNED_VERSIONS = {
    "@infimind-next/ai-hive-mcp": "0.2.5",
    "mcp-server-weisheng-scrm": "0.0.6",
    "dcs-cloud-mcp-server": "2.0.0",
    "@duoguan-fengchao/mcp-launcher": "1.0.8",
}

_SPEC_RE = re.compile(r"^(?P<pkg>@[^/]+/[^@]+|[^@][^@]*)@(?P<ver>.+)$")


def pin_arg(arg: str) -> str:
    """把一个 npx 包参数钉到确切版本。"""
    m = _SPEC_RE.match(arg)
    pkg = m.group("pkg") if m else arg
    if pkg in PINNED_VERSIONS:
        return f"{pkg}@{PINNED_VERSIONS[pkg]}"
    return arg


def normalize_stdio_args(args: list[str]) -> tuple[list[str], list[str]]:
    """规整 npx 参数，返回 (参数, 改动说明)。"""
    out: list[str] = []
    notes: list[str] = []
    for a in args:
        a = str(a)
        # 指向第三方镜像会把供应链信任转移到镜像方；包在 npm 官方源上有，走官方源。
        if a.startswith("--registry="):
            notes.append(f"去掉 {a}（改用 npm 官方源）")
            continue
        pinned = pin_arg(a)
        if pinned != a:
            notes.append(f"{a} → {pinned}")
        out.append(pinned)
    if "-y" not in out and out and out[0] != "-y":
        out.insert(0, "-y")
        notes.append("补 -y（免交互）")
    return out, notes

# 需要中间平台自身身份的鉴权方式：没有厂商直发的凭据，装上也是 401。
PLATFORM_AUTH = {"server-side", "oneid-token", "oneid"}

# 非生产主机。
NON_PROD = re.compile(r"(^|\.)test\.|(^|\.)mcpdemo|(^|\.)demo\.|(^|\.)staging\.", re.I)

CATEGORY_RULES: list[tuple[str, str]] = [
    (r"law|legal|fazhi|pkulaw|fyopen|yuandian|wkinfo|chineselaw|trademark|mzl", "biz"),
    (r"invoice|fssc|finance|fin-|stock|fund|wind|gildata|tdx|westock|yingmi|"
     r"eastmoney|quant|pandadata|morningstar|tonghua|gangtise|tongzhou", "data"),
    (r"hr|job|recruit|gaodun|teacher|fenbi|baokao|edu", "hr"),
    (r"crm|scrm|sales|salestouch|salesnail|xiaoshouyi|neo-crm|bd-mate|linkfox|"
     r"lingxing|chuhaijiang|proboost|tec-do", "biz"),
    (r"image|video|picset|infimind|kling|flova|camscanner|creative|design", "creative"),
    (r"doc|kdocs|wps|note|wisenote|weiyun|archive|ima", "office"),
    (r"meeting|ezjoin|shanglv|qidian|lexiang|gongyi", "comm"),
    (r"cloud|bugly|dcs|cisp|ioa|infra|zenitera", "infra"),
    (r"data|opendata|dknowc|kuaicha|qixin|qcc|sq-company|yscredit|tcredit|"
     r"microdata|chanyedata|company", "data"),
    (r"crawl|bazhuayu|spider|search", "web"),
]


def slug(name: str) -> str:
    """连接器 id → 服务器名。工具名会拼成 ``mcp__<server>__<tool>``，只留 [a-z0-9_]。"""
    if name in SLUG_OVERRIDE:
        name = SLUG_OVERRIDE[name]
    s = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return re.sub(r"_+", "_", s)


def categorize(cid: str, meta: dict[str, Any]) -> str:
    blob = " ".join(str(meta.get(k) or "") for k in
                    ("id", "name", "name_en", "description_zh")).lower()
    blob = f"{cid.lower()} {blob}"
    for pattern, cat in CATEGORY_RULES:
        if re.search(pattern, blob):
            return cat
    return "biz"


# 厂商描述里常写「在 XX 里怎么用」，XX 是别家产品。照抄到我们目录里既不准确
# 也会误导用户，替换成中性说法。
_SCRUB: list[tuple[str, str]] = [
    (r"[Ii]n WorkBuddy,?\s*", ""),
    (r"\bfor WorkBuddy\b", ""),
    (r"WorkBuddy['’]s\s*", ""),
    (r"\bvia WorkBuddy\b", ""),
    (r"在\s*WorkBuddy\s*(中|里|上)?", "在支持 MCP 的客户端中"),
    (r"(WorkBuddy|CodeBuddy)\s*(对接|平台|客户端)?", ""),
]


def scrub_foreign(text: str) -> str:
    """去掉描述里对别家产品的指名。"""
    out = text
    for pattern, repl in _SCRUB:
        out = re.sub(pattern, repl, out)
    # 收拾替换后留下的多余空格与孤立标点
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([,，。.;；:：])", r"\1", out)
    out = re.sub(r"^[\s,，:：-]+", "", out)
    # 删掉句首的「In WorkBuddy, 」后，后面那个词就落在句号后面了，补大写
    out = re.sub(r"([.!?])\s+([a-z])", lambda m: f"{m.group(1)} {m.group(2).upper()}", out)
    out = out[:1].upper() + out[1:] if out[:1].islower() else out
    return out.strip()


def env_refs(obj: Any) -> list[str]:
    """收集配置里所有 ``${VAR}`` 引用，保持出现顺序。"""
    seen: list[str] = []
    for m in re.finditer(r"\$\{(\w+)\}", json.dumps(obj, ensure_ascii=False)):
        if m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


@dataclass
class Rejected:
    cid: str
    reason: str
    detail: str = ""


@dataclass
class Result:
    manifests: dict[str, dict[str, Any]] = field(default_factory=dict)
    rejected: list[Rejected] = field(default_factory=list)


def load_source(src: Path) -> tuple[dict[str, dict], dict[str, dict]]:
    cat_file = src / ".codebuddy-connector" / "connectors.json"
    if not cat_file.exists():
        sys.exit(f"找不到元数据：{cat_file}")
    raw = json.loads(cat_file.read_text(encoding="utf-8"))
    items = raw if isinstance(raw, list) else (raw.get("connectors") or list(raw.values())[0])
    meta = {x["id"]: x for x in items if isinstance(x, dict) and x.get("id")}

    configs: dict[str, dict] = {}
    for mcp_json in sorted((src / "connectors").glob("*/mcp.json")):
        try:
            data = json.loads(mcp_json.read_text(encoding="utf-8"))
        except Exception:
            continue
        servers = data.get("mcpServers")
        if isinstance(servers, dict) and servers:
            configs[mcp_json.parent.name] = servers
    return meta, configs


def build_manifest(cid: str, cfg: dict, meta: dict) -> dict[str, Any]:
    name = slug(cid)
    ctype = infer_type(cfg)
    timeout_ms = cfg.get("timeout")
    # WorkBuddy 的 timeout 是毫秒；我们的清单是秒。个别条目本来就写的秒（如 600），
    # 用 1000 做阈值区分，再夹到 [30, 600]。
    if isinstance(timeout_ms, (int, float)) and timeout_ms > 0:
        secs = timeout_ms / 1000 if timeout_ms >= 1000 else timeout_ms
        timeout = max(30, min(600, int(secs)))
    else:
        timeout = 60

    refs = env_refs(cfg)

    if ctype in HTTP_TYPES:
        url = cfg["url"]
        runtime: dict[str, Any] = {"id": "remote", "type": "http", "url": url}
        headers: dict[str, str] = {}
        for src_key in ("staticHeaders", "headers"):
            block = cfg.get(src_key)
            if isinstance(block, dict):
                headers.update({str(k): str(v) for k, v in block.items()})
        # 丢掉标识调用方是别的产品的头 —— 照抄就是冒名请求。
        headers = {k: v for k, v in headers.items()
                   if not (FOREIGN_IDENTITY.search(k) or FOREIGN_IDENTITY.search(v))}
        if headers:
            runtime["headers"] = headers
        runtime["auth"] = "oauth" if meta.get("auth_mode") == "oauth" else "none"
        homepage = f"https://{urllib.parse.urlparse(url).netloc.split(':')[0]}"
    else:
        args, pin_notes = normalize_stdio_args(list(cfg.get("args") or []))
        runtime = {
            "id": "npx" if cfg.get("command") == "npx" else "stdio",
            "type": "stdio",
            "launcher": cfg.get("command") or "npx",
            "command": cfg.get("command") or "npx",
            "args": args,
        }
        env = {}
        env.update(cfg.get("staticEnv") or {})
        env.update(cfg.get("env") or {})
        if env:
            runtime["env"] = env
        rt = cfg.get("runtime") or {}
        if str(rt.get("type")) == "node":
            runtime["requires"] = {"node": str(rt.get("version") or ">=18")}
        if pin_notes:
            runtime["_normalized"] = pin_notes
        homepage = ""

    requires_env = [
        {
            "name": var,
            "env_key": var,          # 沿用上游原名，用户 .env 零迁移
            "description": f"{meta.get('name') or cid} 所需的 {var}",
            "prompt": f"请输入 {var}",
            "secret": True,
            "required": True,
        }
        for var in refs
    ]

    manifest: dict[str, Any] = {
        "manifest_version": 1,
        "requires_protocol_version": ">=1",
        "tested_with": ">=0.63.72",
        "name": name,
        "display_name": meta.get("name") or meta.get("name_en") or cid,
        "version": "0.1.0",
        "description": scrub_foreign(meta.get("description_en") or meta.get("description") or ""),
        "description_zh": scrub_foreign(meta.get("description_zh") or ""),
        "author": "vendor",
        "category": categorize(cid, meta),
        "tags": [categorize(cid, meta), "vendor"],
        "kind": "mcp_server",
        "runtimes": [runtime],
        "requires_env": requires_env,
        "optional_env": [],
        "defaults": {"enabled": True, "timeout": timeout},
        # 没有凭据就探测不了工具列表，也就扫不了注入。不写 allow，留给
        # scripts/probe_server.py 在有凭据的环境里补。
        "security": {"scan_verdict": "unscanned",
                     "prompt_injection_findings": [],
                     "osv": "unscanned"},
    }
    if homepage:
        manifest["homepage"] = homepage

    disabled = cfg.get("disabledTools")
    if isinstance(disabled, list) and disabled:
        manifest["tools_policy"] = {"exclude": list(disabled)}

    examples = meta.get("examples_zh") or []
    if examples:
        manifest["examples"] = [scrub_foreign(str(e)) for e in examples[:5]]
    return manifest


def convert(meta: dict[str, dict], configs: dict[str, dict],
            only: set[str] | None) -> Result:
    res = Result()
    for cid, servers in sorted(configs.items()):
        if only and cid not in only:
            continue
        m = meta.get(cid)
        if not m:
            res.rejected.append(Rejected(cid, "缺元数据", "connectors.json 里没有这个 id"))
            continue
        cfg = list(servers.values())[0]
        ctype = infer_type(cfg)
        url = cfg.get("url") or ""
        host = urllib.parse.urlparse(url).netloc

        # 厂商为某个特定产品单开的租户路由（路径或 query 里带着那个产品名）。
        # 这跟通用网关不是一回事：走它等于占用别人谈下来的合作配额。要用得自己
        # 去和厂商谈一条路由，不是把别人的地址抄过来。
        if url and FOREIGN_IDENTITY.search(urllib.parse.urlparse(url).path +
                                           "?" + (urllib.parse.urlparse(url).query or "")):
            res.rejected.append(Rejected(cid, "他方专属路由",
                                         f"{url} —— 需自行向厂商申请独立路由"))
            continue

        if ctype not in HTTP_TYPES | STDIO_TYPES:
            res.rejected.append(Rejected(cid, "传输不支持",
                                         f"type={ctype or '缺失'}；agent 只支持 stdio 与 streamable-HTTP"))
            continue
        if host and NON_PROD.search(host):
            res.rejected.append(Rejected(cid, "非生产主机", host))
            continue
        if ctype in HTTP_TYPES and not url:
            res.rejected.append(Rejected(cid, "缺端点", "http 传输但没有 url"))
            continue
        auth_mode = m.get("auth_mode")
        if auth_mode in PLATFORM_AUTH and not env_refs(cfg):
            res.rejected.append(Rejected(cid, "平台身份鉴权",
                                         f"auth_mode={auth_mode}，凭据由上游平台注入，我们拿不到"))
            continue
        if not (m.get("description_en") or m.get("description")):
            res.rejected.append(Rejected(cid, "缺描述", "没有英文描述，目录上没法读"))
            continue

        res.manifests[cid] = build_manifest(cid, cfg, m)
    return res


def audit_report(res: Result, configs: dict[str, dict]) -> None:
    print(f"可转换：{len(res.manifests)} / {len(configs)}\n")
    hosts: dict[str, int] = {}
    for cid, man in res.manifests.items():
        rt = man["runtimes"][0]
        if rt["type"] == "http":
            h = urllib.parse.urlparse(rt["url"]).netloc.split(":")[0]
        else:
            h = f"(stdio) {rt['command']}"
        hosts[h] = hosts.get(h, 0) + 1
    print("端点主机（确认都是厂商自有域名，没有任何中间平台网关）：")
    for h, n in sorted(hosts.items()):
        print(f"  {n:>2}  {h}")
    by_cat: dict[str, int] = {}
    need_cred = 0
    for man in res.manifests.values():
        by_cat[man["category"]] = by_cat.get(man["category"], 0) + 1
        if man["requires_env"]:
            need_cred += 1
    print(f"\n分类：{by_cat}")
    print(f"需要用户自备凭据：{need_cred}；配置里未声明凭据：{len(res.manifests) - need_cred}")
    if res.rejected:
        print(f"\n拒绝 {len(res.rejected)} 个：")
        for r in res.rejected:
            print(f"  {r.cid:<28} {r.reason:<12} {r.detail}")


def write_manifests(res: Result, force: bool) -> None:
    import yaml

    written = skipped = 0
    for cid, man in res.manifests.items():
        out = REPO / "registry" / "servers" / man["category"] / man["name"] / "mcp.yaml"
        if out.exists() and not force:
            skipped += 1
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        rt = man["runtimes"][0]
        notes = rt.pop("_normalized", [])
        header = (
            "# 由 scripts/import_vendor_mcp.py 生成——端点是厂商自有的 MCP 服务器，\n"
            f"# 上游连接器 id: {cid}。人工修改后请同步递增 version。\n"
        )
        if notes:
            header += "# 相对上游配置做的规整：\n"
            header += "".join(f"#   - {n}\n" for n in notes)
        out.write_text(
            header + yaml.safe_dump(man, allow_unicode=True, sort_keys=False, width=100),
            encoding="utf-8",
        )
        written += 1
    print(f"写入 {written} 份清单，跳过 {skipped} 份（已存在，加 --force 覆盖）")
    print("接下来运行：python3 scripts/gen_registry.py")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, type=Path, help="连接器导出目录")
    ap.add_argument("--audit", action="store_true", help="只报告，不写文件")
    ap.add_argument("--write", action="store_true", help="写入 registry/servers/")
    ap.add_argument("--force", action="store_true", help="覆盖已存在的清单")
    ap.add_argument("--only", help="逗号分隔的连接器 id，只处理这些")
    args = ap.parse_args()

    meta, configs = load_source(args.src)
    only = set(args.only.split(",")) if args.only else None
    res = convert(meta, configs, only)

    if args.write:
        write_manifests(res, args.force)
    else:
        audit_report(res, configs)


if __name__ == "__main__":
    main()
