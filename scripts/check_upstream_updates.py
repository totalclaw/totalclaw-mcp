#!/usr/bin/env python3
"""比对注册表里 npx/uvx 钉的版本与 npm/PyPI 上游最新稳定版。只读元数据，不安装、不运行任何包。

  python scripts/check_upstream_updates.py [输出.json]     # 默认写到当前目录 upstream-updates.json

每条结果 status：up_to_date | outdated | pinned_missing | pkg_404 | error；
另标 current_deprecated / latest_deprecated / current_yanked / latest_yanked。
"""
import sys, json, glob, re, ssl, urllib.request, urllib.parse, concurrent.futures as cf, datetime as dt
from pathlib import Path
import yaml
ROOT = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "upstream-updates.json")
sys.path.insert(0, str(ROOT / "scripts"))
from gen_registry import _package_arg  # noqa
try:
    import certifi; CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    CTX = ssl.create_default_context()
DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=CTX))
PROXY = urllib.request.build_opener(urllib.request.HTTPSHandler(context=CTX))
def get(url):
    last = None
    for op in (DIRECT, PROXY, DIRECT):
        try:
            with op.open(urllib.request.Request(url, headers={"User-Agent": "registry-update-check", "Accept": "application/json"}), timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404: return {"__404__": True}
            last = e
        except Exception as e:
            last = e
    raise last

def split(launcher, pkg):
    if launcher == "npx":
        body = pkg[1:] if pkg.startswith("@") else pkg
        name, ver = body.rsplit("@", 1)
        return ("@" + name if pkg.startswith("@") else name), ver
    name, ver = pkg.split("==", 1)
    name = re.sub(r"\[.*\]", "", name)
    return name, ver

def check(item):
    f, name, launcher, pkg = item
    try:
        pname, cur = split(launcher, pkg)
    except Exception:
        return dict(name=name, file=f, launcher=launcher, pkg=pkg, status="unparsed")
    r = dict(name=name, file=f, launcher=launcher, package=pname, current=cur)
    try:
        if launcher == "npx":
            d = get("https://registry.npmjs.org/" + urllib.parse.quote(pname, safe="@"))
            if d.get("__404__"): r["status"] = "pkg_404"; return r
            latest = (d.get("dist-tags") or {}).get("latest")
            vers = d.get("versions") or {}
            r["latest"] = latest
            r["latest_time"] = (d.get("time") or {}).get(latest)
            r["current_time"] = (d.get("time") or {}).get(cur)
            if cur not in vers: r["status"] = "pinned_missing"; return r
            if vers[cur].get("deprecated"): r["current_deprecated"] = vers[cur]["deprecated"][:200]
            if latest and vers.get(latest, {}).get("deprecated"): r["latest_deprecated"] = vers[latest]["deprecated"][:200]
            if d.get("repository"): r["repo"] = (d["repository"] or {}).get("url") if isinstance(d["repository"], dict) else d["repository"]
        else:
            d = get(f"https://pypi.org/pypi/{pname}/json")
            if d.get("__404__"): r["status"] = "pkg_404"; return r
            latest = d["info"]["version"]; rel = d.get("releases") or {}
            r["latest"] = latest
            lf = rel.get(latest) or []; cf_ = rel.get(cur) or []
            r["latest_time"] = lf[0]["upload_time_iso_8601"] if lf else None
            r["current_time"] = cf_[0]["upload_time_iso_8601"] if cf_ else None
            if cur not in rel: r["status"] = "pinned_missing"; return r
            if cf_ and all(x.get("yanked") for x in cf_): r["current_yanked"] = True
            if lf and all(x.get("yanked") for x in lf): r["latest_yanked"] = True
        r["status"] = "up_to_date" if latest == cur else "outdated"
    except Exception as e:
        r["status"] = "error"; r["error"] = repr(e)[:200]
    return r

items = []
for f in sorted(glob.glob(str(ROOT / "registry/servers/*/*/mcp.yaml"))):
    d = yaml.safe_load(open(f))
    if (d.get("security") or {}).get("scan_verdict") == "block": continue
    for rt in d.get("runtimes") or []:
        L = rt.get("launcher")
        if L in ("npx", "uvx"):
            pkg = _package_arg(L, [str(a) for a in rt.get("args") or []])
            if pkg and "git+" not in pkg:
                items.append((str(Path(f).relative_to(ROOT)), d["name"], L, pkg))
with cf.ThreadPoolExecutor(16) as ex:
    res = list(ex.map(check, items))
OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))
from collections import Counter
print(Counter(r["status"] for r in res))
