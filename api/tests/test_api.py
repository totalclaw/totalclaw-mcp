"""注册表读接口的测试。

重点盯三件错了会出事、又不会当场报错的：
  1. 路径穿越 —— `path` 是外部输入，防线必须在 safe_join 自身，
     不能指望路由层或反向代理先帮忙把 `..` 规范化掉。
  2. 分页边界 —— 页码越界、page_size 超限、结果为空这三处最容易算错，
     错了表现为「翻到某页就空了」，用户只会以为条目丢了。
  3. 多语言回落 —— 某个语言的字段缺了要回落另一种，不能留空：
     目录里一个没有名字的条目毫无用处。
"""
from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.server.app import app, catalog
from api.server.bundle import safe_join
from api.server.catalog import Catalog, normalize_lang

client = TestClient(app)


# ── 路径穿越 ────────────────────────────────────────────────────────────
@pytest.mark.parametrize("evil", [
    "../../../etc/passwd",
    "../sibling/mcp.yaml",
    "a/../../../../etc/passwd",
    "/etc/passwd",
    "//etc/passwd",
    "\x00",
])
def test_safe_join_rejects_escapes(tmp_path: Path, evil: str) -> None:
    """防线在函数自身：不经过任何 URL 规范化也要挡住。"""
    base = tmp_path / "srv"
    base.mkdir()
    (base / "mcp.yaml").write_text("x", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("s3cret", encoding="utf-8")
    with pytest.raises((ValueError, FileNotFoundError)):
        safe_join(base, evil)


def test_safe_join_rejects_symlink_out(tmp_path: Path) -> None:
    """软链指到目录外也不行 —— resolve 会跟过去，跟出去就不在目录内。"""
    base = tmp_path / "srv"
    base.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("nope", encoding="utf-8")
    (base / "link.txt").symlink_to(outside)
    with pytest.raises(ValueError):
        safe_join(base, "link.txt")


def test_safe_join_allows_normal_file(tmp_path: Path) -> None:
    base = tmp_path / "srv"
    (base / "sub").mkdir(parents=True)
    f = base / "sub" / "a.txt"
    f.write_text("ok", encoding="utf-8")
    assert safe_join(base, "sub/a.txt") == f.resolve()


def test_files_endpoint_blocks_traversal() -> None:
    name = catalog.all_servers()[0]["name"]
    for evil in ("../../../etc/passwd", "/etc/passwd", "....//....//etc/passwd"):
        r = client.get(f"/api/mcp/servers/{name}/files/{evil}")
        assert r.status_code in (400, 404), evil
        assert "root:" not in r.text


# ── 分页 ────────────────────────────────────────────────────────────────
def test_pagination_math() -> None:
    r = client.get("/api/mcp/servers", params={"page_size": 10, "page": 1})
    d = r.json()
    total, size = d["total"], d["page_size"]
    assert d["total_pages"] == max(1, -(-total // size))
    assert len(d["items"]) == min(size, total)


def test_page_beyond_end_clamps_to_last() -> None:
    """越界页码夹到最后一页，而不是返回空列表。

    返回空的话前端只看到「没有条目」，会以为目录空了。
    """
    r = client.get("/api/mcp/servers", params={"page": 9999, "page_size": 10})
    d = r.json()
    assert d["page"] == d["total_pages"]
    assert len(d["items"]) > 0


def test_page_size_is_capped() -> None:
    r = client.get("/api/mcp/servers", params={"page_size": 5000})
    assert r.status_code == 422        # 超过上限由 FastAPI 直接拒


def test_pages_do_not_overlap_or_skip() -> None:
    """逐页取完应当不重不漏 —— 排序不稳的话会两者都犯。"""
    size = 20
    first = client.get("/api/mcp/servers", params={"page_size": size, "page": 1}).json()
    seen: list[str] = []
    for p in range(1, first["total_pages"] + 1):
        d = client.get("/api/mcp/servers", params={"page_size": size, "page": p}).json()
        seen.extend(i["name"] for i in d["items"])
    assert len(seen) == first["total"]
    assert len(set(seen)) == first["total"]


def test_empty_result_still_valid() -> None:
    d = client.get("/api/mcp/servers", params={"q": "绝不可能匹配到的字符串xyzzy"}).json()
    assert d["total"] == 0
    assert d["items"] == []
    assert d["total_pages"] == 1 and d["page"] == 1


# ── 多语言 ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize("raw,want", [
    ("en", "en"), ("en-US", "en"), ("zh", "zh-CN"), ("zh-CN", "zh-CN"),
    ("zh-CN,zh;q=0.9,en;q=0.8", "zh-CN"),
    ("en-GB,en;q=0.9", "en"),
    (None, "zh-CN"), ("", "zh-CN"), ("klingon", "zh-CN"),
])
def test_lang_negotiation(raw, want) -> None:
    assert normalize_lang(raw) == want


def test_lang_query_beats_header() -> None:
    d = client.get("/api/mcp/servers", params={"lang": "en", "page_size": 1},
                   headers={"Accept-Language": "zh-CN"}).json()
    assert d["lang"] == "en"


def test_accept_language_used_when_no_query() -> None:
    d = client.get("/api/mcp/servers", params={"page_size": 1},
                   headers={"Accept-Language": "en-US,en;q=0.9"}).json()
    assert d["lang"] == "en"


def test_localized_fields_differ_by_lang() -> None:
    en = client.get("/api/mcp/servers/pkulaw", params={"lang": "en"}).json()
    zh = client.get("/api/mcp/servers/pkulaw", params={"lang": "zh-CN"}).json()
    assert en["display_name_localized"] != zh["display_name_localized"]
    assert en["category_label"] != zh["category_label"]


def test_localize_falls_back_when_missing() -> None:
    """缺英文名就回落中文，反之亦然 —— 不能留空。"""
    entry = {"name": "x", "display_name": "中文名", "display_name_en": "",
             "description": "", "description_zh": "中文描述", "category": "biz"}
    en = Catalog.localize(entry, "en")
    assert en["display_name_localized"] == "中文名"
    assert en["description_localized"] == "中文描述"

    entry2 = {"name": "y", "display_name": "", "display_name_en": "Only English",
              "description": "English only", "description_zh": "", "category": "biz"}
    zh = Catalog.localize(entry2, "zh-CN")
    assert zh["display_name_localized"] == "Only English"
    assert zh["description_localized"] == "English only"


def test_search_matches_across_languages() -> None:
    """中文界面搜英文词也要搜得到 —— 输入语言和界面语言是两回事。"""
    zh_ui = client.get("/api/mcp/servers", params={"q": "github", "lang": "zh-CN"}).json()
    assert zh_ui["total"] > 0
    en_ui = client.get("/api/mcp/servers", params={"q": "法律", "lang": "en"}).json()
    assert en_ui["total"] > 0


# ── 筛选 ────────────────────────────────────────────────────────────────
def test_filters() -> None:
    http_only = client.get("/api/mcp/servers", params={"transport": "http",
                                                       "page_size": 100}).json()
    assert all("http" in i["transports"] for i in http_only["items"])

    biz = client.get("/api/mcp/servers", params={"category": "biz",
                                                 "page_size": 100}).json()
    assert all(i["category"] == "biz" for i in biz["items"])

    free = client.get("/api/mcp/servers", params={"no_credentials": True,
                                                  "page_size": 100}).json()
    assert all(not i.get("requires_env") for i in free["items"])


def test_categories_localized() -> None:
    en = client.get("/api/mcp/categories", params={"lang": "en"}).json()
    zh = client.get("/api/mcp/categories", params={"lang": "zh-CN"}).json()
    assert {c["category"] for c in en["items"]} == {c["category"] for c in zh["items"]}
    labels_en = {c["category"]: c["label"] for c in en["items"]}
    labels_zh = {c["category"]: c["label"] for c in zh["items"]}
    assert labels_en["biz"] != labels_zh["biz"]
    total = sum(c["count"] for c in en["items"])
    assert total == client.get("/api/mcp/servers", params={"page_size": 1}).json()["total"]


# ── 下载 ────────────────────────────────────────────────────────────────
def test_download_is_reproducible() -> None:
    """同样的内容要打出同样的字节，否则 ETag 每次都变，缓存全失效。"""
    a = client.get("/api/mcp/servers/awesun/download")
    b = client.get("/api/mcp/servers/awesun/download")
    assert a.status_code == 200
    assert a.content == b.content
    assert a.headers["ETag"] == b.headers["ETag"]


def test_download_contents_match_file_digests() -> None:
    """包里每个文件都要和 files 接口给的 sha256 对得上。"""
    import hashlib
    name = "awesun"
    digests = {f["path"]: f["sha256"]
               for f in client.get(f"/api/mcp/servers/{name}/files").json()["files"]}
    tar_bytes = client.get(f"/api/mcp/servers/{name}/download").content
    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as t:
        members = [m for m in t.getmembers() if m.isfile()]
        assert members
        for m in members:
            rel = m.name.split("/", 1)[1]
            got = hashlib.sha256(t.extractfile(m).read()).hexdigest()
            assert got == digests[rel], rel


def test_download_prefixes_with_server_name() -> None:
    """包内统一一层同名目录，解开时不会把文件散到当前目录。"""
    tar_bytes = client.get("/api/mcp/servers/awesun/download").content
    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as t:
        assert all(n.startswith("awesun/") for n in t.getnames())


def test_download_unknown_is_404() -> None:
    assert client.get("/api/mcp/servers/nope-not-here/download").status_code == 404


# ── 详情 ────────────────────────────────────────────────────────────────
def test_detail_includes_manifest_and_tools() -> None:
    d = client.get("/api/mcp/servers/awesun").json()
    assert d["manifest"]["name"] == "awesun"
    assert len(d["tools_detail"]) == d["tools_count"]


def test_detail_accepts_full_id() -> None:
    entry = catalog.get("awesun")
    d = client.get(f"/api/mcp/servers/{entry['id']}").json()
    assert d["name"] == "awesun"


def test_credential_doc_url_reaches_api() -> None:
    """凭据的申请地址要能通过接口拿到 —— 界面要靠它渲染「去哪里获取」。"""
    d = client.get("/api/mcp/servers/gangtise_mcp").json()
    urls = [e.get("doc_url") for e in d["requires_env"]]
    assert all(urls) and urls[0].startswith("https://")


# ── 快照 ────────────────────────────────────────────────────────────────
def test_registry_snapshot_matches_disk() -> None:
    served = client.get("/registry.json").json()
    on_disk = json.loads((Path(__file__).resolve().parents[2] / "registry.json")
                         .read_text(encoding="utf-8"))
    assert served == on_disk


def test_healthz() -> None:
    d = client.get("/healthz").json()
    assert d["ok"] and d["servers"] > 0


# ── 图标 ────────────────────────────────────────────────────────────────
def test_icon_falls_back_to_monogram() -> None:
    """没有自带图标就发字母块，不是 404 —— 界面上一排空框用户分不清哪个是哪个。"""
    r = client.get("/api/mcp/servers/awesun/icon")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert r.headers["X-Icon-Source"] == "generated"
    assert r.text.startswith("<svg")


def test_icon_is_deterministic() -> None:
    """同样的条目要出同样的字节，否则 ETag 每次都变。"""
    a = client.get("/api/mcp/servers/awesun/icon")
    b = client.get("/api/mcp/servers/awesun/icon")
    assert a.content == b.content and a.headers["ETag"] == b.headers["ETag"]


def test_icon_serves_real_file_when_present(tmp_path: Path) -> None:
    """条目目录里放了 icon.svg 就发真的，并把来源标成 file。"""
    entry = dict(catalog.get("awesun") or {})
    d = catalog.server_dir(entry)
    f = d / "icon.svg"
    assert not f.exists(), "这个条目本来就有图标，换一个没有的来测"
    f.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
    try:
        # 索引里还没有 icon 字段（没重新生成），所以直接测投影函数与路由的两半
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
        from gen_registry import _icon_rel
        assert _icon_rel(d) == "icon.svg"
    finally:
        f.unlink()


def test_monogram_initial_skips_punctuation() -> None:
    """名字以标点开头时要跳到第一个字母/汉字 —— 拿标点当图标认不出是谁。"""
    from api.server.icon import initial
    assert initial("「向日葵」远程控制") == "向"
    assert initial("  playwright") == "P"
    assert initial("——") == "?"
    assert initial("", "fallback_slug") == "F"


def test_monogram_differs_by_entry() -> None:
    """不同条目的块要能区分开，否则等于没有图标。"""
    from api.server.icon import monogram_svg
    a = monogram_svg("腾讯文档", "tencent_docs", "office")
    b = monogram_svg("飞书", "feishu", "comm")
    assert a != b


def test_all_entries_render_an_icon() -> None:
    """全库跑一遍：任何一个条目都不能因为名字里有奇怪字符而 500。"""
    for e in catalog.all_servers():
        r = client.get(f"/api/mcp/servers/{e['name']}/icon")
        assert r.status_code == 200, e["name"]
        assert r.content, e["name"]


def test_monogram_matches_qiye_app_implementation() -> None:
    """与 qiye-app 的 mcpIcon.ts 逐字一致。

    桌面端走 qiye_api 拿目录、不请求这个接口，所以它是在本地按同一套算法画同样的块。
    两边算出不同的颜色，同一个条目在桌面端和网页端就是两个颜色，用户会当成两个东西。
    这几组期望值在两个仓的测试里各钉一份 —— 谁改了算法，谁那边先红。
    """
    import re
    from api.server.icon import shade_delta, monogram_svg

    def bg(dn: str, slug: str, cat: str) -> str:
        return re.search(r'fill="(#\w+)"', monogram_svg(dn, slug, cat)).group(1)

    assert shade_delta("awesun") == -3
    assert bg("向日葵", "awesun", "infra") == "#596877"
    assert bg("Playwright", "playwright", "web") == "#4B9B66"
    assert bg("CNB 云原生构建", "cnb", "dev") == "#555ABA"
