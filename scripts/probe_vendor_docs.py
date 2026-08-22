#!/usr/bin/env python3
"""探测各厂商开放文档站，判断能否拿到可验证的接口契约。

为什么要有这个脚本：D 组还剩几十个连接器，逐个人工去翻文档很慢，而且结论
过几个月就失效（厂商随时可能开放或关闭文档）。这里把"能不能拿到端点定义"
这件事做成可重复执行的判断，免得下次又从头试一遍。

判据很粗但够用：抓首页/文档入口，看正文里有没有 `GET /`、`/api/v1`、
`access_token`、`Authorization` 这类**具体接口痕迹**。SPA 落地页与登录墙
一律零命中 —— 那正是"需要厂商账号才能继续"的信号。

    python3 scripts/probe_vendor_docs.py
    python3 scripts/probe_vendor_docs.py --json
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import ssl
import urllib.request

#: 连接器 → 其开放平台/文档入口。新增连接器时往这里补一行。
VENDOR_DOCS: dict[str, str] = {
    "tencent-weiyun": "https://www.weiyun.com/",
    "ima-mcp": "https://ima.qq.com/",
    "lexiang": "https://lexiang.tencent.com/",
    "jiushuyun": "https://www.jiushuyun.com/",
    "qingflow": "https://hc.qingflow.com/",
    "neo-crm": "https://open.neocrm.com/",
    "xiaoe-cloud-cli": "https://api-doc.xiaoe-tech.com/api_list.html",
    "pandadata": "https://www.pandadata.cn/",
    "mzl-trademark": "https://www.mozlen.com/",
    "tplus-api": "https://open.chanjet.com/",
    "h3yun-connector": "https://www.h3yun.com/",
    "morningstar": "https://developer.morningstar.com/",
    "patsnap-search": "https://open.patsnap.com/",
    "bazhuayu": "https://www.bazhuayu.com/",
    "kdocs": "https://open.wps.cn/",
    "cnb-api": "https://api.cnb.cool/openapi.json",
    "sharecrm": "https://developer.fxiaoke.com/openapi_v2/",
    "tencent-docs": "https://docs.qq.com/open/document/app/openapi/v3/",
}

#: 已逐个人工攻过、确认**具体端点页仍不可达**的。
#: 索引页会命中关键词(所以粗判据会说"可继续"),但每个接口的详情页要么 404、
#: 要么在开发者门户内 —— 记在这里，免得下一个人重复同样的试错。
KNOWN_BLOCKED: dict[str, str] = {
    "patsnap-search": "索引页可见，API reference 在开发者门户内（需注册）",
    "tencent-docs": "v3 只给三元组请求头；文件管理端点在 v2，页面 404",
    "xiaoe-cloud-cli": "文档站只暴露目录结构，端点详情页直接 404",
    "cnb-api": "openapi.json 返回 401，规范需登录",
    "sharecrm": "文档站是 SPA，抓不到端点定义",
    "h3yun-connector": "开放平台文档页报「系统加载错误」",
    "qingflow": "Open API 需先在应用内安装扩展才能看文档与取 token",
    "kdocs": "WPS 开放平台需注册为服务商才能看接口文档",
}

ENDPOINT_HINT = re.compile(
    r"(?i)(GET|POST|PUT|DELETE)\s+/|/api/v?\d|application/json|access_token|Authorization"
)
_HINT_THRESHOLD = 3


def _probe(item: tuple[str, str], timeout: float) -> dict:
    name, url = item
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            body = resp.read(200_000).decode("utf-8", "ignore")
            status: object = resp.status
    except Exception as exc:  # noqa: BLE001 - 各种网络错误一律记录不中断
        return {"name": name, "url": url, "status": type(exc).__name__,
                "hints": 0, "size_kb": 0,
                "known_blocked": KNOWN_BLOCKED.get(name), "actionable": False}
    hints = len(ENDPOINT_HINT.findall(body))
    blocked = KNOWN_BLOCKED.get(name)
    return {"name": name, "url": url, "status": status, "hints": hints,
            "size_kb": len(body) // 1024,
            "known_blocked": blocked,
            "actionable": status == 200 and hints >= _HINT_THRESHOLD and not blocked}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--timeout", type=float, default=12.0)
    args = ap.parse_args()

    with concurrent.futures.ThreadPoolExecutor(10) as ex:
        rows = sorted(ex.map(lambda i: _probe(i, args.timeout), VENDOR_DOCS.items()),
                      key=lambda r: (not r["actionable"], r["name"]))

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    actionable = [r for r in rows if r["actionable"]]
    print(f"厂商文档探测（{len(rows)} 家）\n")
    for r in rows:
        if r["actionable"]:
            mark = "→ 可继续"
        elif r["known_blocked"]:
            mark = f"  已核实受阻：{r['known_blocked']}"
        else:
            mark = "  需账号"
        print(f"  {r['name']:24s} {str(r['status']):14s} 命中 {r['hints']:3d}  {mark}")
    print(f"\n可继续 {len(actionable)} 家 · 需厂商账号 {len(rows) - len(actionable)} 家")
    if not actionable:
        print("\n判据是粗的:命中为 0 基本等于 SPA 落地页或登录墙。"
              "\n拿到任一家的开发者账号后，按 docs/PACKS.md 补 pack 即可，引擎无需改动。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
