#!/usr/bin/env python3
"""从每个条目的 homepage 抓厂商**自己的**图标，落到条目目录。

为什么可以抓：目录里展示厂商自有标识、用来识别其自有产品，是应用市场的通行做法。
为什么仍要小心：这些是第三方商标，不是我们的素材。所以这个脚本：

  * **只取厂商自己站点上的图标**，不去图标站、不去搜索引擎、更不自造；
  * 每一个都记下**来源 URL 与抓取日期**（写进 `registry/ICONS.md`），
    将来谁要求下架，能一眼查到是从哪儿来的；
  * 抓不到就留空 —— 空了会回落到「首字 + 分类取色」的字母块，界面不会开天窗。

用法：
    python3 scripts/fetch_icons.py            # 全量，跳过已有图标的条目
    python3 scripts/fetch_icons.py --force    # 连已有的也重抓
    python3 scripts/fetch_icons.py awesun cnb # 只抓这几个
    python3 scripts/fetch_icons.py --dry-run  # 只报告会抓什么

抓完记得跑 `python3 scripts/gen_registry.py` 更新索引。
"""
from __future__ import annotations

import argparse
import base64
import concurrent.futures
import datetime
import io
import json
import re
import sys
import urllib.parse
from pathlib import Path

try:
    import httpx
except ImportError:  # pragma: no cover
    sys.exit("需要 httpx：pip install httpx")
try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("需要 PyYAML：pip install pyyaml")

REPO = Path(__file__).resolve().parent.parent
SERVERS = REPO / "registry" / "servers"
ICONS_MD = REPO / "registry" / "ICONS.md"
# 来源记录必须**跨次累积**：只写本次新抓的，会把上一轮的来源冲掉。
# 图标是第三方商标，「这张是从哪儿来的」正是这个文件存在的全部理由。
ICONS_JSON = REPO / "registry" / "icons.json"

TIMEOUT = 15.0
# 图标不该有几百 KB。超过这个尺寸多半抓错了（抓到整张首页图之类）
MAX_BYTES = 512 * 1024
UA = "Mozilla/5.0 (compatible; totalclaw-mcp-icon-fetcher/1.0)"

ACCEPT = {
    "image/svg+xml": ".svg",
    "image/png": ".png",
}
# .ico 是多帧容器，直接落盘的话浏览器与 Electron 里表现不一，所以转成 PNG 再存。
# Pillow 不在就跳过这类（回落字母块），不因为少一个可选依赖让整个脚本挂掉 ——
# 国内站点用 .ico 的比例很高，实测 45 个失败里有一多半是这个原因。
ICO_TYPES = {"image/x-icon", "image/vnd.microsoft.icon", "image/ico"}
try:
    from PIL import Image                                        # noqa: F401
    _HAVE_PIL = True
except ImportError:
    _HAVE_PIL = False

# 这些站点的 favicon 是**平台自己的标识**，不是产品的。清单里不少 homepage 指的是
# 代码仓或包页面（awesun 写的是 github.com/OrayDev/awesun-mcp），照抓会给一半条目
# 贴上 GitHub 的猫 —— 那比没有图标更糟：目录看上去像所有东西都是同一家的。
# 这些一律跳过，回落字母块。
HOST_IS_NOT_THE_PRODUCT = {
    "github.com", "www.github.com", "raw.githubusercontent.com",
    "gitee.com", "www.gitee.com",
    "gitlab.com", "www.gitlab.com",
    "bitbucket.org",
    "npmjs.com", "www.npmjs.com",
    "pypi.org", "www.pypi.org",
    "cnb.cool", "www.cnb.cool",
    "hub.docker.com",
    "marketplace.visualstudio.com",
    "modelcontextprotocol.io", "www.modelcontextprotocol.io",
    "smithery.ai", "glama.ai",
}


# 顶级域回退时**不能**用的伞状域名：产品挂在大厂域名下的子域，回退到顶级域
# 拿到的是大厂 logo（stockbuddy.qq.com 的产品是腾讯自选股，qq.com 给的是 QQ 的企鹅）。
# 又是「一屏卡片长得一模一样」那个毛病，宁可回落字母块。
UMBRELLA_APEX = {
    "qq.com", "tencent.com", "aliyun.com", "alibaba.com", "taobao.com",
    "baidu.com", "bytedance.com", "163.com", "sina.com.cn", "jd.com",
    "huawei.com", "microsoft.com", "google.com", "amazonaws.com",
}


# 图标地址里出现这些字样，说明抓到的是**站点用的第三方基础设施**的标，不是产品的。
# 实例：shanglv_mcp_gateway 的网关挂着 Keycloak 登录页，favicon 是
# `.../keycloak.v2/favicon.svg` —— 挂上去等于给商旅贴了 Keycloak 的标。
THIRD_PARTY_ASSET = (
    "keycloak", "auth0", "okta", "onelogin", "casdoor", "logto",
    "wordpress", "shopify", "cloudflare", "nginx", "apache",
    "swagger", "redoc", "gitbook", "docusaurus", "vitepress",
)


def _apex_fallback(host: str) -> str:
    """把 `mcp-center.wps.cn` 这类网关主机退到产品站 `wps.cn`。

    清单里的 homepage 大多写的是 MCP 端点或文档地址，不是产品首页 —— 34 个抓不到
    的条目里绝大多数是这个原因。顶级域上通常就有产品自己的图标。
    """
    parts = host.split(".")
    if len(parts) < 3:
        return ""                       # 本来就是顶级域，没什么可退的
    # 中国域名多是三段后缀（com.cn / net.cn），apex 要多留一段
    apex = ".".join(parts[-3:]) if parts[-2] in ("com", "net", "org", "gov") \
        and parts[-1] in ("cn", "hk", "tw") else ".".join(parts[-2:])
    if apex in UMBRELLA_APEX or apex == host:
        return ""
    return apex


# <link rel=...> 里哪些算图标，按优先级排：越靠前越好
REL_PRIORITY = [
    "apple-touch-icon",        # 通常是最大最干净的那张
    "icon",
    "shortcut icon",
    "mask-icon",
]

LINK_RE = re.compile(
    r"""<link\b[^>]*?rel\s*=\s*["']([^"']+)["'][^>]*?>""", re.I | re.S)
HREF_RE = re.compile(r"""href\s*=\s*["']([^"']+)["']""", re.I)
SIZES_RE = re.compile(r"""sizes\s*=\s*["'](\d+)x\d+["']""", re.I)


class Result:
    def __init__(self, name: str) -> None:
        self.name = name
        self.status = "skip"      # ok | skip | fail
        self.detail = ""
        self.source = ""
        self.suffix = ""


def _decode_data_uri(uri: str) -> "tuple[bytes, str] | None":
    """把 `data:image/png;base64,…` 解出来。认不出的类型返回 None。"""
    m = re.match(r"data:([^;,]+)(;base64)?,(.*)$", uri, re.S)
    if not m:
        return None
    ctype, is_b64, payload = m.group(1).lower(), bool(m.group(2)), m.group(3)
    try:
        raw = (base64.b64decode(payload) if is_b64
               else urllib.parse.unquote_to_bytes(payload))
    except Exception:                                            # noqa: BLE001
        return None
    if not raw or len(raw) > MAX_BYTES:
        return None
    if ctype == "image/png" and raw.startswith(b"\x89PNG"):
        return raw, ".png"
    if ctype == "image/svg+xml" and b"<svg" in raw[:2048].lower():
        return raw, ".svg"
    if ctype in ICO_TYPES:
        png = _ico_to_png(raw)
        return (png, ".png") if png else None
    return None


def _ico_to_png(raw: bytes) -> "bytes | None":
    """.ico 转 PNG，取里面最大的一帧。Pillow 不在就返回 None。"""
    if not _HAVE_PIL or not raw:
        return None
    try:
        from PIL import Image
        with Image.open(io.BytesIO(raw)) as im:
            # ico 是多帧的，sizes() 给出全部尺寸，挑最大那张
            sizes = getattr(im, "ico", None)
            if sizes is not None:
                im = im.ico.getimage(max(im.ico.sizes()))
            out = io.BytesIO()
            im.convert("RGBA").save(out, format="PNG")
            return out.getvalue()
    except Exception:                                            # noqa: BLE001
        return None


def _entries(only: list[str]) -> list[tuple[str, str, Path, dict]]:
    out = []
    for mf in sorted(SERVERS.glob("*/*/mcp.yaml")):
        d = mf.parent
        name, category = d.name, d.parent.name
        if only and name not in only:
            continue
        try:
            m = yaml.safe_load(mf.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        out.append((name, category, d, m))
    return out


def _candidates(html: str, page_url: str) -> list[str]:
    """从首页 HTML 里挑出候选图标 URL，按「好用程度」排序。"""
    found: list[tuple[int, int, str]] = []      # (rel 优先级, -尺寸, url)
    for tag_match in re.finditer(r"<link\b[^>]*?>", html, re.I | re.S):
        tag = tag_match.group(0)
        rel_m = re.search(r"""rel\s*=\s*["']([^"']+)["']""", tag, re.I)
        href_m = HREF_RE.search(tag)
        if not rel_m or not href_m:
            continue
        rel = rel_m.group(1).strip().lower()
        if not any(r in rel for r in ("icon",)):
            continue
        try:
            prio = next(i for i, r in enumerate(REL_PRIORITY) if r in rel)
        except StopIteration:
            prio = len(REL_PRIORITY)
        size_m = SIZES_RE.search(tag)
        size = int(size_m.group(1)) if size_m else 0
        href = href_m.group(1).strip()
        # data: URI 不能 urljoin，会被拼坏
        full = href if href.startswith("data:") else urllib.parse.urljoin(page_url, href)
        found.append((prio, -size, full))
    found.sort()
    urls = [u for _, _, u in found]
    # 兜底：约定俗成的位置
    urls.append(urllib.parse.urljoin(page_url, "/favicon.svg"))
    urls.append(urllib.parse.urljoin(page_url, "/favicon.png"))
    urls.append(urllib.parse.urljoin(page_url, "/favicon.ico"))
    # 去重保序
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _try_one(c, url: str, d: Path, res: "Result", page) -> bool:
    """试一个候选地址；成功就落盘并填好 res，返回 True。"""
    # 有的站把图标直接内联成 data: URI（bugly 就是），没有可请求的地址
    if url.startswith("data:"):
        blob = _decode_data_uri(url)
        if not blob:
            return False
        payload, suffix = blob
        _write_icon(d, suffix, payload)
        res.status, res.suffix = "ok", suffix
        res.source = f"{page.url}（页面内联 data: URI）"
        res.detail = f"{len(payload) // 1024 or 1} KB（内联）"
        return True
    if any(k in url.lower() for k in THIRD_PARTY_ASSET):
        return False
    try:
        r = c.get(url)
    except Exception:                                            # noqa: BLE001
        return False
    if r.status_code != 200 or not r.content or len(r.content) > MAX_BYTES:
        return False
    ctype = r.headers.get("content-type", "").split(";")[0].strip().lower()
    if ctype in ICO_TYPES or url.lower().split("?")[0].endswith(".ico"):
        png = _ico_to_png(r.content)
        if not png:
            return False
        _write_icon(d, ".png", png)
        res.status, res.source, res.suffix = "ok", url, ".png"
        res.detail = f"{len(png) // 1024 or 1} KB（ico→png）"
        return True
    suffix = ACCEPT.get(ctype)
    if not suffix:
        return False
    # 有些站把 404 页当 200 返回，内容是 HTML —— 按魔数再核一次
    if suffix == ".png" and not r.content.startswith(b"\x89PNG"):
        return False
    if suffix == ".svg" and b"<svg" not in r.content[:2048].lower():
        return False
    _write_icon(d, suffix, r.content)
    res.status, res.source, res.suffix = "ok", url, suffix
    res.detail = f"{len(r.content) // 1024 or 1} KB"
    return True


def _write_icon(d: Path, suffix: str, payload: bytes) -> None:
    for old in (d / "icon.svg", d / "icon.png"):
        old.unlink(missing_ok=True)
    (d / f"icon{suffix}").write_bytes(payload)


def fetch_one(name: str, category: str, d: Path, manifest: dict,
              *, force: bool, dry_run: bool) -> "Result":
    res = Result(name)
    existing = [p for p in (d / "icon.svg", d / "icon.png") if p.is_file()]
    if existing and not force:
        res.detail = f"已有 {existing[0].name}"
        return res

    home = str(manifest.get("homepage") or "").strip()
    if not home.startswith("http"):
        res.detail = "清单没有 homepage"
        return res
    host = (urllib.parse.urlparse(home).hostname or "").lower()
    if host in HOST_IS_NOT_THE_PRODUCT:
        res.detail = f"homepage 指向 {host}，抓到的会是平台图标不是产品图标"
        return res
    if dry_run:
        res.status = "ok"
        res.detail = f"会从 {home} 抓"
        return res

    try:
        with httpx.Client(timeout=TIMEOUT, follow_redirects=True,
                          headers={"User-Agent": UA}, verify=True) as c:
            # 主页 →（不行的话）顶级域。clean 里绝大多数 homepage 写的是 MCP 端点
            # 或文档地址，不是产品首页，所以顶级域这一跳很值钱。
            tried = []
            for base in (home, ):
                tried.append(base)
            apex = _apex_fallback(host)
            if apex:
                tried.append(f"https://{apex}")
            for base in tried:
                try:
                    page = c.get(base)
                except Exception:                                # noqa: BLE001
                    continue
                html = (page.text if "html" in
                        page.headers.get("content-type", "") else "")
                for url in _candidates(html, str(page.url)):
                    if _try_one(c, url, d, res, page):
                        return res
        res.status = "fail"
        res.detail = "站点与其顶级域上都没有 svg/png/ico 图标"
    except Exception as exc:                                     # noqa: BLE001
        res.status = "fail"
        res.detail = f"{type(exc).__name__}: {exc}"[:90]
    return res


def _load_provenance() -> dict:
    if ICONS_JSON.is_file():
        try:
            return json.loads(ICONS_JSON.read_text(encoding="utf-8"))
        except Exception:                                        # noqa: BLE001
            return {}
    return {}


def write_provenance(new_rows: list[tuple[str, str, str]]) -> int:
    """把「哪个条目的图标从哪儿来的」写下来（累积，不覆盖）。

    这些是第三方商标，不是我们的素材。将来谁要求下架，得能一眼查到来源。
    磁盘上已经没有图标的条目会从记录里剔掉，免得留下查不到实物的幽灵行。
    """
    today = datetime.date.today().isoformat()
    store = _load_provenance()
    for name, suffix, source in new_rows:
        store[name] = {"file": f"icon{suffix}", "source": source, "fetched_at": today}

    # 与磁盘对账：图标被删了，记录也该走
    on_disk = {}
    for icon in SERVERS.glob("*/*/icon.*"):
        if icon.suffix in (".svg", ".png"):
            on_disk[icon.parent.name] = icon.name
    store = {k: v for k, v in store.items() if k in on_disk}
    for name, fname in on_disk.items():
        if name not in store:
            # 有图标却没有来源记录：标出来，别装作知道它从哪儿来
            store[name] = {"file": fname, "source": "（来源未记录，重跑 --force 补）",
                           "fetched_at": ""}
        else:
            store[name]["file"] = fname

    ICONS_JSON.write_text(json.dumps(store, ensure_ascii=False, indent=2,
                                     sort_keys=True) + "\n", encoding="utf-8")
    rows = [(k, v["file"], v["source"], v.get("fetched_at", "")) for k, v in store.items()]
    lines = [
        "# 条目图标来源",
        "",
        "目录里的图标**一律取自厂商自己的站点**（清单里的 `homepage`），",
        "用于在目录中识别其自有产品。不自造、不改画、不从第三方图标站取。",
        "",
        "抓取脚本：`scripts/fetch_icons.py`。抓不到的条目没有图标文件，",
        "客户端会回落到「首字 + 分类取色」的字母块。",
        "",
        "这些图标**不在**本仓库 LICENSE（Apache-2.0）的授权范围内 —— 见根目录 `NOTICE`。",
        "商标归各自厂商所有，本仓库不主张任何权利、也不转授权。",
        "如需下架某个图标，删掉对应条目目录下的 `icon.svg`/`icon.png`，"
        "再跑 `scripts/fetch_icons.py`（会同步剔掉记录）与 `scripts/gen_registry.py`。",
        "",
        f"最后更新：{today}",
        "",
        "| 条目 | 文件 | 来源 URL | 抓取日期 |",
        "|---|---|---|---|",
    ]
    for name, fname, source, when in sorted(rows):
        lines.append(f"| `{name}` | `{fname}` | {source} | {when or '—'} |")
    lines.append("")
    ICONS_MD.write_text("\n".join(lines), encoding="utf-8")
    return len(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="*", help="只抓这几个条目；留空为全量")
    ap.add_argument("--force", action="store_true", help="连已有图标的条目也重抓")
    ap.add_argument("--dry-run", action="store_true", help="只报告，不下载")
    ap.add_argument("--jobs", type=int, default=8, help="并发数（默认 8）")
    args = ap.parse_args()

    entries = _entries(args.names)
    if not entries:
        print("没有匹配的条目")
        return 1
    print(f"共 {len(entries)} 个条目，并发 {args.jobs}\n")

    results: list[Result] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futs = {pool.submit(fetch_one, n, c, d, m,
                            force=args.force, dry_run=args.dry_run): n
                for n, c, d, m in entries}
        for fut in concurrent.futures.as_completed(futs):
            r = fut.result()
            results.append(r)
            mark = {"ok": "✓", "skip": "·", "fail": "✗"}[r.status]
            print(f"  {mark} {r.name:32} {r.detail}")

    ok = [r for r in results if r.status == "ok" and r.source]
    print(f"\n抓到 {len(ok)} · 跳过 {sum(1 for r in results if r.status == 'skip')}"
          f" · 失败 {sum(1 for r in results if r.status == 'fail')}")

    if not args.dry_run:
        # 累积写：本次结果并进已有记录，再与磁盘对账。只抓几个也安全。
        total = write_provenance([(r.name, r.suffix, r.source) for r in ok])
        print(f"来源表已更新：{ICONS_MD.relative_to(REPO)}（共 {total} 条）")
        if ok:
            print("接下来跑 python3 scripts/gen_registry.py 更新索引")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
