"""MCP 注册表读接口 —— 分页查询（多语言）+ 逐条目下载。

形状与 `docs/API.md` ① 的平台接口一致，但实现是直接读仓库，不依赖数据库。
M2 的 NestJS 平台接管时前端不用改。

跑起来：

    pip install fastapi 'uvicorn[standard]' pyyaml
    python3 -m uvicorn api.server.app:app --port 3101 --reload

Swagger 在 /api/docs。
"""
from __future__ import annotations

import mimetypes
from typing import Any

import yaml
from fastapi import FastAPI, Header, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .bundle import file_digests, make_tar_gz, safe_join, sha256_bytes
from .catalog import Catalog, normalize_lang
from .icon import monogram_svg

app = FastAPI(
    title="TotalClaw MCP Registry API",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    description="MCP 注册表的只读接口：分页查询（中/英）与逐条目下载。",
)

# 目录是公开可读的，客户端可能是桌面端、网页或别的 agent
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

catalog = Catalog()


def _lang(lang: str | None, accept_language: str | None) -> str:
    """显式 lang 优先；没给就按 Accept-Language 协商。"""
    return normalize_lang(lang or accept_language)


def _entry_or_404(name: str) -> dict[str, Any]:
    entry = catalog.get(name)
    if not entry:
        raise HTTPException(status_code=404, detail=f"没有名为 {name!r} 的 MCP 服务器")
    return entry


@app.get("/healthz", summary="存活检查")
def healthz() -> dict[str, Any]:
    try:
        n = len(catalog.all_servers())
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"ok": True, "servers": n}


@app.get("/registry.json", summary="完整索引快照")
def registry_snapshot() -> Response:
    data = catalog.meta | {"servers": catalog.all_servers()}
    return JSONResponse(data, headers={"Cache-Control": "public, max-age=300"})


@app.get("/api/mcp/servers", summary="分页查询 MCP 服务器（多语言）")
def list_servers(
    q: str | None = Query(None, description="关键词。中英文名、描述、标签、工具名一起搜"),
    category: str | None = Query(None),
    transport: str | None = Query(None, description="stdio | http"),
    launcher: str | None = Query(None, description="npx | uvx | docker | binary …"),
    tag: str | None = Query(None),
    verified: bool | None = Query(None),
    free: bool | None = Query(None, alias="no_credentials",
                              description="true 只看不需要预置凭据的"),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    lang: str | None = Query(None, description="zh-CN | en；不传按 Accept-Language"),
    accept_language: str | None = Header(None, alias="Accept-Language"),
) -> dict[str, Any]:
    lg = _lang(lang, accept_language)
    result = catalog.search(
        q=q, category=category, transport=transport, launcher=launcher,
        tag=tag, verified=verified, needs_no_credentials=free,
        page=page, page_size=page_size,
    )
    return {
        "items": [catalog.localize(e, lg) for e in result.items],
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size,
        "total_pages": result.total_pages,
        "lang": lg,
    }


@app.get("/api/mcp/categories", summary="分类与条目数（多语言）")
def list_categories(
    lang: str | None = Query(None),
    accept_language: str | None = Header(None, alias="Accept-Language"),
) -> dict[str, Any]:
    lg = _lang(lang, accept_language)
    return {"items": catalog.categories(lg), "lang": lg}


@app.get("/api/mcp/servers/{name}/files", summary="条目文件清单与逐文件摘要")
def list_files(name: str) -> dict[str, Any]:
    entry = _entry_or_404(name)
    return {
        "name": entry["name"],
        "files": file_digests(catalog.server_dir(entry)),
        # 索引里那个 bundle_sha256 是「文件清单」的摘要，不是压缩包的摘要。
        # 客户端要按 files[] 逐条校验，别拿它去比 tar.gz 的哈希。
        "bundle_sha256": entry.get("bundle_sha256"),
    }


@app.get("/api/mcp/servers/{name}/files/{path:path}", summary="取条目里的单个文件")
def get_file(name: str, path: str) -> Response:
    entry = _entry_or_404(name)
    try:
        target = safe_join(catalog.server_dir(entry), path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"{name} 里没有 {path}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    if target.suffix in (".yaml", ".yml", ".md", ".json"):
        ctype = {"": "text/plain"}.get("", ctype)
    return Response(
        target.read_bytes(),
        media_type=ctype,
        headers={"Cache-Control": "public, max-age=300"},
    )


@app.get("/api/mcp/servers/{name}/download", summary="下载整个条目（tar.gz）")
def download(name: str) -> Response:
    entry = _entry_or_404(name)
    data = make_tar_gz(catalog.server_dir(entry), entry["name"])
    digest = sha256_bytes(data)
    return Response(
        data,
        media_type="application/gzip",
        headers={
            "Content-Disposition": f'attachment; filename="{entry["name"]}.tar.gz"',
            # 打包是可复现的（时间戳与属主归零），所以 ETag 稳定，能走缓存
            "ETag": f'"{digest}"',
            "X-Bundle-Sha256": entry.get("bundle_sha256") or "",
            "X-Archive-Sha256": digest,
            "Cache-Control": "public, max-age=300",
        },
    )


@app.get("/api/mcp/servers/{name}/icon", summary="条目图标（没有自带图标就发字母块）")
def get_icon(name: str) -> Response:
    entry = _entry_or_404(name)
    rel = entry.get("icon") or ""
    if rel:
        try:
            target = safe_join(catalog.server_dir(entry), rel)
        except (ValueError, FileNotFoundError):
            target = None            # 索引与磁盘不同步时不 500，回落生成
        if target is not None:
            ctype = "image/svg+xml" if target.suffix == ".svg" else "image/png"
            return Response(target.read_bytes(), media_type=ctype, headers={
                "X-Icon-Source": "file",
                "Cache-Control": "public, max-age=300",
            })

    # 厂商 logo 有商标，不自造 —— 生成的是字母块，一眼看得出不是官方图标，
    # 但比一排空白强：目前 115 个条目自带图标数为 0。
    svg = monogram_svg(entry.get("display_name") or "", entry.get("name") or "",
                       entry.get("category") or "")
    return Response(svg, media_type="image/svg+xml", headers={
        "X-Icon-Source": "generated",
        "ETag": f'"{sha256_bytes(svg.encode())}"',
        "Cache-Control": "public, max-age=300",
    })


# 详情路由声明在最后：{name:path} 是贪婪的，放前面会把 `awesun/download`
# 整个吞成 name，下载与取文件两条路就都进不来了。
# 用 :path 是为了让完整 id（totalclaw-mcp/<cat>/<name>，带斜杠）也能取详情；
# 下载与取文件仍只认短名（name 在全库唯一，SPEC §1 有保证）。
@app.get("/api/mcp/servers/{name:path}", summary="条目详情（含清单全文与工具清单）")
def get_server(
    name: str,
    lang: str | None = Query(None),
    accept_language: str | None = Header(None, alias="Accept-Language"),
) -> dict[str, Any]:
    lg = _lang(lang, accept_language)
    entry = _entry_or_404(name)
    out = catalog.localize(entry, lg)

    d = catalog.server_dir(entry)
    manifest_path = d / "mcp.yaml"
    if manifest_path.is_file():
        out["manifest"] = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    tools_path = d / "tools.json"
    if tools_path.is_file():
        import json
        raw = json.loads(tools_path.read_text(encoding="utf-8"))
        out["tools_detail"] = raw if isinstance(raw, list) else raw.get("tools", [])
    readme = d / "README.md"
    if readme.is_file():
        out["readme_md"] = readme.read_text(encoding="utf-8")
    return out
