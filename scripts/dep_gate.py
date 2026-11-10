#!/usr/bin/env python3
"""依赖链版本黑名单门禁 —— 被投毒的包版本不许出现在任何条目的安装依赖里。

`npx -y pkg@x.y.z` / `uvx pkg==x.y.z` 只钉住顶层包，间接依赖在用户安装那一刻才按范围解析。
axios、chalk、debug、litellm 这类被广泛依赖的库都出过「劫持发布账号 → 发一个带毒版本」的事件，
顶层钉得再死，安装时也可能拉到带毒的间接依赖。这个脚本做两件事：

  python3 scripts/dep_gate.py --refresh   # 联网：解析全部条目今天安装会拉到的依赖树（npm 全树 / PyPI 全树），
                                           # 对树里出现的每个包名查 osv.dev 的恶意包记录（MAL-），
                                           # 重写 registry/malicious-versions.json；有条目解析到黑名单版本 → 退出码 1
  python3 scripts/dep_gate.py --check     # 离线（门禁）：各条目钉住的顶层包不在黑名单里，命中退出码 1
  python3 scripts/dep_gate.py --selftest  # 离线自检

--refresh 只读公开元数据（npm registry / PyPI JSON / osv.dev），不下载压缩包、不安装、不执行任何第三方代码；
npm 依赖解析由 scripts/npm_tree.mjs 完成（需要本机 node，semver 借用 npm 自带的那份）。
解析是近似的：npm 取 latest 或满足范围的最高版本；PyPI 取满足条件的最新版、忽略 extra 依赖——
与用户「今天」装到的基本一致，但不保证与某次实际安装逐个相同。
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from gen_registry import SERVERS_DIR, _require_yaml, _runtime_package  # noqa: E402

BLACKLIST = ROOT / "registry" / "malicious-versions.json"
UA = "totalclaw-mcp-dep-gate/1.0 (metadata only, no install)"
ECOS = ("npm", "PyPI")

# ── 版本比较（只为判断 osv 的 introduced / fixed / last_affected 区间，够用即可）──────────────


def _vkey(v: str):
    """1.2.3 / 1.2.3-beta.1 / 2025.4.25 / 0.1.1.dev9 → 可比较的元组。预发布排在正式版之前。"""
    v = str(v).strip().lstrip("vV")
    m = re.match(r"(\d+(?:\.\d+)*)(.*)", v)
    if not m:
        return ((0,), 0, v)
    rel = tuple(int(x) for x in m.group(1).split("."))
    rel = rel + (0,) * (4 - len(rel)) if len(rel) < 4 else rel
    rest = m.group(2).lstrip(".-+")
    return (rel, 0 if rest else 1, rest)


def in_range(version: str, events: list) -> bool:
    """osv 的 range.events：按顺序的 introduced / fixed / last_affected。"""
    k = _vkey(version)
    affected = False
    for ev in events:
        if "introduced" in ev:
            intro = ev["introduced"]
            if intro in ("0", 0) or k >= _vkey(intro):
                affected = True
        elif "fixed" in ev and affected and k >= _vkey(ev["fixed"]):
            affected = False
        elif "last_affected" in ev and affected and k > _vkey(ev["last_affected"]):
            affected = False
    return affected


def norm(eco: str, name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower() if eco == "PyPI" else name


def hits(blacklist: dict, eco: str, name: str, version: str) -> list:
    """返回命中的 osv 编号。"""
    out = []
    for vid, rec in (blacklist.get(eco, {}).get(norm(eco, name)) or {}).items():
        if version in rec.get("versions", []) or any(in_range(version, r) for r in rec.get("ranges", [])):
            out.append(vid)
    return out


# ── 清单里的顶层包 ──────────────────────────────────────────────────────────────


def pins(include_blocked: bool = False) -> list:
    """npx / uvx 顶层包：[{entry, eco, name, version, spec}]，默认只取未下架条目。git+ 来源（本仓自研）记 eco=git。"""
    yaml = _require_yaml()
    out = []
    for p in sorted(SERVERS_DIR.glob("*/*/mcp.yaml")):
        m = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        if not include_blocked and (m.get("security") or {}).get("scan_verdict") == "block":
            continue
        for rt in m.get("runtimes") or []:
            spec = _runtime_package(rt)
            launcher = rt.get("launcher") or rt.get("command")
            if not spec or launcher not in ("npx", "uvx"):
                continue
            if launcher == "npx":
                at = spec.rfind("@")
                name, ver = (spec[:at], spec[at + 1:]) if at > 0 else (spec, "")
                out.append({"entry": m["name"], "eco": "npm", "name": name, "version": ver, "spec": spec})
            elif spec.startswith("git+"):
                out.append({"entry": m["name"], "eco": "git", "name": spec, "version": "", "spec": spec})
            else:
                name, _, ver = spec.partition("==")
                out.append({"entry": m["name"], "eco": "PyPI", "name": re.sub(r"\[.*\]", "", name), "version": ver,
                            "spec": spec})
    return out


def check() -> int:
    if not BLACKLIST.exists():
        print(f"dep-gate：缺少 {BLACKLIST.relative_to(ROOT)}，先联网跑 --refresh", file=sys.stderr)
        return 1
    bl = json.loads(BLACKLIST.read_text(encoding="utf-8"))
    bad = 0
    ps = pins()
    for p in ps:
        if p["eco"] in ECOS and p["version"]:
            ids = hits(bl, p["eco"], p["name"], p["version"])
            if ids:
                bad += 1
                print(f"✗ {p['entry']}：钉住的 {p['spec']} 是恶意版本（{', '.join(ids)}）")
    n = sum(len(bl.get(k, {})) for k in ECOS)
    print(f"dep-gate --check：{len(ps)} 个顶层包，黑名单 {n} 个包名（{bl.get('generated', '?')} 刷新），{bad} 处命中")
    return 1 if bad else 0


# ── 联网：依赖树 + osv ─────────────────────────────────────────────────────────

_DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _read_all(resp, deadline: float) -> bytes:
    """分块读，超过总时长就放弃：socket 超时只管单次读，挡不住代理一点点往回挤数据。"""
    chunks = []
    while True:
        if time.monotonic() > deadline:
            raise TimeoutError("响应读取超过总时长")
        b = resp.read(256 * 1024)
        if not b:
            return b"".join(chunks)
        chunks.append(b)


def _open(url, data=None, headers=None, timeout=30, total=120):
    """先直连、失败改走系统代理，交替重试；每次请求总时长不超过 total 秒；404 返回 None。"""
    hdrs = {"User-Agent": UA, **(headers or {})}
    last = None
    for attempt in range(6):
        opener = urllib.request.build_opener() if attempt % 2 else _DIRECT
        try:
            with opener.open(urllib.request.Request(url, data=data, headers=hdrs), timeout=timeout) as r:
                return _read_all(r, time.monotonic() + total)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            last = e
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(1 + attempt)
    raise RuntimeError(f"{url}: {last}")


def _semver_path() -> str:
    if os.environ.get("NPM_SEMVER"):
        return os.environ["NPM_SEMVER"]
    npm = shutil.which("npm")
    if not npm:
        raise SystemExit("--refresh 需要 node / npm（解析 npm 依赖树），或用 NPM_SEMVER 指定 semver 模块路径")
    root = subprocess.run([npm, "root", "-g"], capture_output=True, text=True, check=True).stdout.strip()
    p = Path(root) / "npm" / "node_modules" / "semver"
    if not p.exists():
        raise SystemExit(f"找不到 npm 自带的 semver：{p}；用 NPM_SEMVER 指定")
    return str(p)


def npm_trees(ps: list) -> dict:
    tops = [{"entry": p["entry"], "pkg": p["spec"]} for p in ps if p["eco"] == "npm"]
    r = subprocess.run(["node", str(ROOT / "scripts" / "npm_tree.mjs"), _semver_path()],
                       input=json.dumps(tops), capture_output=True, text=True, timeout=3600)
    if r.returncode:
        raise SystemExit(f"npm_tree.mjs 失败：{r.stderr[-2000:]}")
    return json.loads(r.stdout)


def _self_deps() -> list:
    """本仓自研条目（uvx --from git+…#subdirectory=servers）的依赖：servers/pyproject.toml 的 dependencies。"""
    text = (ROOT / "servers" / "pyproject.toml").read_text(encoding="utf-8")
    block = re.search(r"(?ms)^dependencies\s*=\s*\[(.*?)^\]", text)
    return re.findall(r"^\s*\"([^\"]+)\"", block.group(1), re.M) if block else []


def pypi_trees(ps: list) -> dict:
    cache, lock = {}, threading.Lock()
    nodes, entries, errors = {}, {}, []
    done = [0]

    def meta(name, version):
        k = (norm("PyPI", name), version)
        with lock:
            if k in cache:
                return cache[k]
        raw = _open(f"https://pypi.org/pypi/{name}/{version}/json" if version else f"https://pypi.org/pypi/{name}/json")
        info = None
        if raw:
            d = json.loads(raw)
            info = {"name": norm("PyPI", d["info"]["name"]), "version": d["info"]["version"],
                    "requires": d["info"].get("requires_dist") or []}
        with lock:
            cache[k] = info
        return info

    def walk(entry, roots):
        seen, stack = set(), list(roots)
        while stack:
            name, ver = stack.pop()
            try:
                info = meta(name, ver)
            except Exception as e:  # noqa: BLE001
                errors.append(f"{entry}：{name} {e}")
                continue
            if not info:
                errors.append(f"{entry}：{name}{'==' + ver if ver else ''} 在 PyPI 上不存在")
                continue
            key = f"{info['name']}=={info['version']}"
            if key in seen:
                continue
            seen.add(key)
            nodes[key] = {"name": info["name"], "version": info["version"]}
            for req in info["requires"]:
                if re.search(r"extra\s*==", req):
                    continue
                m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", req)
                if m:
                    stack.append((m.group(1), None))
        with lock:
            entries[entry] = entries.get(entry, []) + sorted(seen)
            done[0] += 1
            if done[0] % 25 == 0 or done[0] == len(jobs):
                print(f"  PyPI 依赖树 {done[0]}/{len(jobs)}", file=sys.stderr, flush=True)

    jobs = []
    for p in ps:
        if p["eco"] == "git":
            jobs.append((p["entry"], [(re.match(r"[A-Za-z0-9._-]+", s).group(0), None) for s in _self_deps()]))
        elif p["eco"] == "PyPI":
            jobs.append((p["entry"], [(p["name"], p["version"] or None)]))
    with cf.ThreadPoolExecutor(16) as ex:
        list(ex.map(lambda j: walk(*j), jobs))
    return {"entries": entries, "nodes": nodes, "errors": errors}


def osv_malicious(eco: str, names: list) -> dict:
    """对每个包名（不带版本）查 osv，留下 MAL- 记录的受影响版本与区间。"""
    ids_by_name = {}
    for i in range(0, len(names), 800):
        chunk = names[i:i + 800]
        body = json.dumps({"queries": [{"package": {"name": n, "ecosystem": eco}} for n in chunk]}).encode()
        res = json.loads(_open("https://api.osv.dev/v1/querybatch", data=body,
                               headers={"Content-Type": "application/json"}, total=300))["results"]
        for n, item in zip(chunk, res):
            mal = [v["id"] for v in item.get("vulns") or [] if v["id"].startswith("MAL-")]
            if mal:
                ids_by_name[n] = mal
    out = {}

    def detail(pair):
        name, vid = pair
        return name, vid, json.loads(_open(f"https://api.osv.dev/v1/vulns/{vid}") or b"{}")

    pairs = [(n, v) for n, ids in ids_by_name.items() for v in ids]
    with cf.ThreadPoolExecutor(12) as ex:
        for name, vid, d in ex.map(detail, pairs):
            if d.get("withdrawn"):
                continue
            rec = {"versions": [], "ranges": [], "summary": (d.get("summary") or "")[:160]}
            for a in d.get("affected") or []:
                if norm(eco, a.get("package", {}).get("name", "")) != norm(eco, name):
                    continue
                rec["versions"] += a.get("versions") or []
                rec["ranges"] += [r["events"] for r in a.get("ranges") or [] if r.get("events")]
            rec["versions"] = sorted(set(rec["versions"]), key=_vkey)
            out.setdefault(norm(eco, name), {})[vid] = rec
    return out


def refresh() -> int:
    ps = pins()
    print(f"顶层包 {len(ps)} 个，解析依赖树 …", file=sys.stderr)
    trees = {"npm": npm_trees(ps)}
    print(f"  npm 依赖树完成：{len(trees['npm']['entries'])} 条 / {len(trees['npm']['nodes'])} 个包版本", file=sys.stderr, flush=True)
    trees["PyPI"] = pypi_trees(ps)
    old = json.loads(BLACKLIST.read_text(encoding="utf-8")) if BLACKLIST.exists() else {}
    bl = {"generated": dt.date.today().isoformat(),
          "source": "osv.dev 恶意包记录（MAL-）；查询范围：全部未下架条目依赖树里出现过的包名，加上已下架条目的顶层包名。由 scripts/dep_gate.py --refresh 生成，勿手改。"}
    for eco in ECOS:
        # 已下架条目的顶层包名也查：恢复上架时若钉到带毒版本，--check 能拦住
        names = sorted({n["name"] for n in trees[eco]["nodes"].values()}
                       | {p["name"] for p in pins(include_blocked=True) if p["eco"] == eco})
        print(f"{eco}：{len(trees[eco]['nodes'])} 个包版本 / {len(names)} 个包名，查 osv …", file=sys.stderr)
        fresh = osv_malicious(eco, names)
        # 只增不减：这次依赖树里不再出现的包名，旧记录照留（条目换版本后又可能引回来）
        merged = {**(old.get(eco) or {}), **fresh}
        bl[eco] = {k: merged[k] for k in sorted(merged)}
    BLACKLIST.write_text(json.dumps(bl, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    bad = 0
    for eco in ECOS:
        t = trees[eco]
        for entry, keys in sorted(t["entries"].items()):
            for k in keys:
                n = t["nodes"][k]
                ids = hits(bl, eco, n["name"], n["version"])
                if ids:
                    bad += 1
                    print(f"✗ {entry}：依赖树里有 {k}（{', '.join(ids)}）")
        for e in t["errors"]:
            print(f"  ! {eco} 解析告警：{e}", file=sys.stderr)
    print(f"dep-gate --refresh：npm {len(trees['npm']['entries'])} 条 / {len(trees['npm']['nodes'])} 个包版本，"
          f"PyPI {len(trees['PyPI']['entries'])} 条 / {len(trees['PyPI']['nodes'])} 个包版本；"
          f"黑名单 npm {len(bl['npm'])} / PyPI {len(bl['PyPI'])} 个包名；{bad} 处命中")
    return 1 if bad else 0


def selftest() -> int:
    assert _vkey("1.2.3") < _vkey("1.10.0") and _vkey("1.2.3-beta.1") < _vkey("1.2.3") and _vkey("2025.4.25") > _vkey("1.0")
    assert in_range("1.1.5", [{"introduced": "1.0.0"}, {"fixed": "1.2.11"}])
    assert not in_range("2.3.3", [{"introduced": "1.0.0"}, {"fixed": "1.2.11"}])
    assert in_range("9.9.9", [{"introduced": "0"}])
    assert not in_range("1.3.0", [{"introduced": "1.0.0"}, {"last_affected": "1.2.0"}])
    bl = {"npm": {"axios": {"MAL-X": {"versions": ["1.14.1"], "ranges": []}}},
          "PyPI": {"some-pkg": {"MAL-Y": {"versions": [], "ranges": [[{"introduced": "0"}]]}}}}
    assert hits(bl, "npm", "axios", "1.14.1") == ["MAL-X"] and not hits(bl, "npm", "axios", "1.14.0")
    assert hits(bl, "PyPI", "Some_Pkg", "0.0.1") == ["MAL-Y"]
    print("✓ dep-gate selftest")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--refresh", action="store_true", help="联网解析依赖树、刷新黑名单（命中退出码 1）")
    g.add_argument("--check", action="store_true", help="离线门禁：顶层钉住的包不在黑名单里（命中退出码 1）")
    g.add_argument("--selftest", action="store_true", help="离线自检")
    a = ap.parse_args()
    sys.exit(selftest() if a.selftest else check() if a.check else refresh())


if __name__ == "__main__":
    main()
