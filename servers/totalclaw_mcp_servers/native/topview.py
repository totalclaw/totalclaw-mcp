"""TopView（topview.ai）AI 营销视频 MCP 服务器 —— 商品链接出带货视频、公模数字人口播，
以及新版 API Router 的多模型生图 / 生视频。

TopView 有两套互不相通的 API（余额、Key 都不通用），本服务器两套都支持，配了哪套用哪套：
  - 旧版 API（api.topview.ai）：API Key + UID，按积分计费，仅 Pro / Business 会员可开通。
    提供 m2v 带货视频、公模数字人等，对应下方 get_credit … query_task 这批工具。
  - 新版 API Router（platform.topview.ai，后端 platform-backend.topview.ai）：只要一个
    Platform Key（TOPVIEW_API_PLATFORM_KEY），按美元余额计费，免费账号也能开。只有通用的
    生图 / 生视频模型（Seedance、WAN、MiniMax、GPT Image、Topview T1），没有 m2v 和数字人。
    对应 router_* 工具。

这是原生实现而非声明式 pack，原因有三：
  1. 上传是三步（取凭证 → PUT 到 S3 预签名地址 → 校验），声明式引擎表达不了二进制 PUT；
  2. 鉴权要两个头（Authorization: Bearer <key> + Topview-Uid），pack 的默认头不做 ${ENV} 代入；
  3. 生成任务是异步的，工具内要能短轮询，否则模型只能拿着 taskId 干等。

与官方 MCP（https://www.topview.ai/mcp → https://mcp.topview.ai/mcp，registry 里的
topview_official）的分工 —— 本服务器只做官方做不到的：
  - 商品链接 → 营销视频（m2v）：官方 skill 文档明确写「Marketing-video project generation
    is outside this skill's direct tools」，只能去网页端；
  - 公模数字人库口播（video_avatar，aiAvatarId）：官方的 topview_avatar_video 只收人像照片；
  - API Key 鉴权：官方只能浏览器 OAuth 登录，服务端无人值守用不了。
TTS、克隆音色、抠图、商品模特图、电商数据一律走官方 MCP，本服务器不重复实现（旧版 v1
图生视频只有 lite/pro 档，远不如官方）。图/视频生成只通过新版 API Router 提供，因为它同样是
Key 鉴权、可无人值守，官方 MCP 则必须浏览器 OAuth 登录。
官方页面注明 Unlimited 套餐不支持 MCP / Plugin / Skill；OpenAPI 是否同样受限待实测。

接口依据（2026-10 核对）：
    https://s.apifox.cn/apidoc/shared/115a0d85-28a5-479d-8b8b-83d7898a7246   旧版英文
    https://s.apifox.cn/apidoc/shared/e8e2bcff-c3c8-4f04-9b5c-465e985c31bc   旧版中文
    积分查询 /user/credit/detail 取自官方 topviewai/codex-topview-ai 客户端。
    https://platform.topview.ai/docs 与 /llms-full.txt                       新版 API Router

凭据（环境变量，两套至少配一套）：
    TOPVIEW_API_KEY            旧版：www.topview.ai/api-settings 里的 API Key
    TOPVIEW_UID                旧版：同页的 UID（或点头像复制）
    TOPVIEW_API_PLATFORM_KEY   新版：platform.topview.ai → API 密钥（需 models:generate 与 requests:read）
"""
from __future__ import annotations

import base64
import mimetypes
import os
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

BASE_URL = "https://api.topview.ai"
TIMEOUT = 30.0
POLL_INTERVAL = 5.0
# agent 侧单次工具调用超时是 120s（registry defaults.timeout），等待上限必须留出余量
MAX_WAIT = 100
MAX_UPLOAD_BYTES = 200 * 1024 * 1024
UPLOAD_FORMATS = {"mp4", "mov", "png", "jpg", "jpeg", "bmp", "webp", "mp3", "wav", "m4a"}

# 业务码 → 人话（取自官方文档的错误码表）
_CODES = {
    "401": "API Key 或 UID 无效，请到 topview.ai → API Settings 重新复制",
    "4000": "请求参数错误",
    "4003": "缺少必填参数",
    "4004": "资源不存在（taskId / fileId / 数字人 ID 不对）",
    "4007": "已有未完成的任务，请等上一个任务结束后再提交",
    "4100": "积分不足，请到 topview.ai 充值",
    "5003": "TopView 服务繁忙，请稍后重试",
    "6001": "内容触发安全审核",
}

# 各任务类型的查询端点
_QUERY = {
    "marketing_video": "/v1/m2v/task/query",
    "avatar_video": "/v1/video_avatar/task/query",
}
_DONE = {"success"}
_FAILED = {"fail", "failed"}

# ── 新版 API Router ──
ROUTER_URL = "https://platform-backend.topview.ai/api/v1"
ROUTER_MAX_UPLOAD = 20 * 1024 * 1024
ROUTER_KINDS = {"png": "image", "jpg": "image", "jpeg": "image", "webp": "image",
                "mp4": "video", "mov": "video", "webm": "video",
                "mp3": "audio", "wav": "audio", "m4a": "audio"}
# 模型 → 请求体格式 / 支持的模式 / 取值提示。请求体有三种，各模型文档不通用：
#   content：Seedance / MiniMax / Topview T1，content[] 多模态数组 + 顶层 ratio/resolution/duration
#   wan：WAN，input{prompt, media[]} + parameters{ratio, resolution, duration, audio}
#   image：GPT Image 2，顶层 prompt / aspect_ratio / resolution / images[]
_SEEDANCE = ["text-to-video", "image-to-video", "omni-reference-to-video"]
ROUTER_MODELS: dict[str, dict[str, Any]] = {
    "bytedance/seedance-2.5": {"format": "content", "modes": _SEEDANCE,
                               "resolution": ["480p", "720p", "1080p"], "duration": "4-30 或 -1（自动）"},
    "bytedance/seedance-2.0": {"format": "content", "modes": _SEEDANCE,
                               "resolution": ["480p", "720p", "1080p"], "duration": "4-15 或 -1"},
    "bytedance/seedance-2.0-fast": {"format": "content", "modes": _SEEDANCE,
                                    "resolution": ["480p", "720p"], "duration": "4-15 或 -1"},
    "bytedance/seedance-2.0-mini": {"format": "content", "modes": _SEEDANCE,
                                    "resolution": ["480p", "720p"], "duration": "4-15 或 -1"},
    "topview/topview-t1": {"format": "content", "modes": _SEEDANCE,
                           "resolution": ["720p", "1080p"], "duration": "4-30 或 -1"},
    "minimax/minimax-h3": {"format": "content", "modes": ["text-to-video", "image-to-video"],
                           "resolution": ["768P", "2K"], "duration": "4-15"},
    "alibaba/wan-3.0": {"format": "wan",
                        "modes": ["text-to-video", "image-to-video", "reference-to-video"],
                        "resolution": ["480P", "720P", "1080P"], "duration": "2-30 或 -1"},
    "openai/gpt-image-2": {"format": "image", "modes": ["text-to-image", "edit"],
                           "resolution": ["1k", "2k", "4k"]},
}
ROUTER_DOCS = "https://platform.topview.ai/docs/models/"
# HTTP 状态 → 人话（取自 API Router 的 Authentication 文档）
_ROUTER_HTTP = {
    401: "TOPVIEW_API_PLATFORM_KEY 无效、过期或已吊销，请到 platform.topview.ai → API 密钥 重新创建",
    402: "API Router 余额不足，请到 platform.topview.ai 给该工作区充值",
    403: "这个 Key 没有所需权限（models:generate / requests:read）或没开通该模型",
    404: "任务或素材不在这个 Key 的工作区里（任务只能用创建它的那个 Key 查询）",
    429: "请求过于频繁，请稍后再试",
}


class TopviewError(Exception):
    """面向用户的错误：消息已是人话，装配层直接透出，不加类名前缀。"""

    clean = True


# ── HTTP ─────────────────────────────────────────────────────────────────

def _headers() -> dict[str, str]:
    key = os.environ.get("TOPVIEW_API_KEY", "").strip()
    uid = os.environ.get("TOPVIEW_UID", "").strip()
    missing = [k for k, v in (("TOPVIEW_API_KEY", key), ("TOPVIEW_UID", uid)) if not v]
    if missing:
        raise TopviewError(
            f"缺少凭据环境变量：{', '.join(missing)}。"
            "这个工具走旧版 API：在 www.topview.ai/api-settings 复制 API Key 与 UID"
            "（仅 Pro / Business 会员可开通）。新版 API Router 的 Key 用不了这个工具，"
            "它只能用 router_* 工具。"
        )
    return {"Authorization": f"Bearer {key}", "Topview-Uid": uid,
            "User-Agent": "totalclaw-mcp-servers/0.1"}


def _redact(text: str) -> str:
    for k in ("TOPVIEW_API_KEY", "TOPVIEW_UID", "TOPVIEW_API_PLATFORM_KEY"):
        v = os.environ.get(k, "")
        if v:
            text = text.replace(v, "***")
    return text


def _request(method: str, path: str, *, params: dict | None = None,
             body: dict | None = None) -> Any:
    """发请求并拆信封：code=="200" 返回 result，否则抛 TopviewError。"""
    headers = _headers()
    if params:
        params = {k: v for k, v in params.items() if v is not None and v != ""}
    if body is not None:
        body = {k: v for k, v in body.items() if v is not None and v != ""}
    try:
        with httpx.Client(timeout=TIMEOUT) as c:
            resp = c.request(method, BASE_URL + path, params=params or None,
                             json=body, headers=headers)
    except httpx.TimeoutException as e:
        raise TopviewError(f"请求超时（{TIMEOUT:.0f}s）：{path}") from e
    except httpx.HTTPError as e:
        raise TopviewError(_redact(f"网络错误：{type(e).__name__}: {e}")) from e
    if resp.status_code in (401, 403):
        raise TopviewError(_CODES["401"])
    if resp.status_code >= 400:
        raise TopviewError(_redact(f"TopView 返回 HTTP {resp.status_code}：{resp.text[:300]}"))
    try:
        data = resp.json()
    except ValueError as e:
        raise TopviewError(f"TopView 返回了非 JSON 响应：{resp.text[:200]}") from e
    code = str(data.get("code", ""))
    if code != "200":
        hint = _CODES.get(code, "")
        msg = data.get("message") or ""
        raise TopviewError(f"TopView 业务错误 code={code}：{msg} {hint}".strip())
    return data.get("result")


def _submit(path: str, body: dict) -> str:
    result = _request("POST", path, body=body) or {}
    task_id = result.get("taskId") if isinstance(result, dict) else None
    if not task_id:
        raise TopviewError(f"提交成功但没拿到 taskId：{result}")
    return str(task_id)


# ── 任务结果规整 ─────────────────────────────────────────────────────────

def _normalize(kind: str, r: dict) -> dict[str, Any]:
    """把各任务类型五花八门的查询结果收敛成统一形状。

    完成判定以产物 URL 为准：状态字段写 success 但没有 URL 时仍视为未完成，
    避免把空结果交给模型（阿里云 DVH 踩过同类坑）。
    """
    status = str(r.get("status", "")).lower()
    out: dict[str, Any] = {"task_id": r.get("taskId"), "kind": kind, "status": status or "unknown"}
    urls: list[str] = []
    if kind == "marketing_video":
        videos = r.get("exportVideos") or r.get("previewVideos") or []
        out["videos"] = [
            {k: v.get(k) for k in ("scriptId", "status", "title", "videoUrl",
                                   "coverUrl", "videoDuration")}
            for v in videos if isinstance(v, dict)
        ]
        urls = [v["videoUrl"] for v in out["videos"] if v.get("videoUrl")]
        for k in ("productName", "productDescription"):
            if r.get(k):
                out[k] = r[k]
    elif kind == "avatar_video":
        if r.get("outputVideoUrl"):
            urls = [r["outputVideoUrl"]]
        if r.get("costCredit") is not None:
            out["cost_credit"] = r["costCredit"]
    out["urls"] = urls
    if status in _FAILED:
        out["state"] = "failed"
        out["error"] = r.get("errorMsg") or "任务失败（TopView 未给出原因）"
    elif urls and (status in _DONE or not status):
        out["state"] = "done"
    else:
        out["state"] = "running"
    return out


def _query(kind: str, task_id: str) -> dict[str, Any]:
    if kind == "router":
        d = _router_request("GET", f"/predictions/{quote(task_id, safe='')}")
        return _normalize_router(d if isinstance(d, dict) else {})
    r = _request("GET", _QUERY[kind], params={"taskId": task_id, "needCloudFrontUrl": "true"})
    return _normalize(kind, r if isinstance(r, dict) else {})


def _wait(kind: str, task_id: str, wait_seconds: int | None) -> dict[str, Any]:
    budget = MAX_WAIT if wait_seconds is None else max(0, min(int(wait_seconds), MAX_WAIT))
    deadline = time.monotonic() + budget
    while True:
        res = _query(kind, task_id)
        if res["state"] != "running" or time.monotonic() + POLL_INTERVAL > deadline:
            break
        time.sleep(POLL_INTERVAL)
    if res["state"] == "running":
        res["hint"] = (f"任务仍在生成中。稍后用 query_task(kind=\"{kind}\", "
                       f"task_id=\"{task_id}\") 继续查询，不要重复提交。")
    return {"success": res["state"] != "failed", "data": res}


# ── 新版 API Router：HTTP 与结果规整 ─────────────────────────────────────

def _router_headers() -> dict[str, str]:
    key = os.environ.get("TOPVIEW_API_PLATFORM_KEY", "").strip()
    if not key:
        raise TopviewError(
            "缺少凭据环境变量：TOPVIEW_API_PLATFORM_KEY。这个工具走新版 API Router："
            "在 platform.topview.ai → API 密钥 创建（勾选 models:generate 与 requests:read）。"
            "旧版的 API Key + UID 用不了 router_* 工具。"
        )
    return {"Authorization": f"Bearer {key}", "User-Agent": "totalclaw-mcp-servers/0.1"}


def _router_request(method: str, path: str, *, json: dict | None = None,
                    files: dict | None = None, data: dict | None = None,
                    idempotency_key: str | None = None) -> Any:
    """发请求并拆信封，返回 data。提交带 Idempotency-Key：超时后用同一个 key 重试一次，
    官方文档说明这样不会重复建任务（超时不等于失败）。"""
    headers = _router_headers()
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    attempts = 2 if idempotency_key else 1
    for i in range(attempts):
        try:
            with httpx.Client(timeout=TIMEOUT) as c:
                resp = c.request(method, ROUTER_URL + path, json=json, files=files,
                                 data=data, headers=headers)
            break
        except httpx.TimeoutException as e:
            if i + 1 < attempts:
                continue
            raise TopviewError(f"请求超时（{TIMEOUT:.0f}s）：{path}。如果是提交任务，"
                               "可能已经建好了，请到 platform.topview.ai 的用量页确认，不要直接重复提交") from e
        except httpx.HTTPError as e:
            raise TopviewError(_redact(f"网络错误：{type(e).__name__}: {e}")) from e
    try:
        body = resp.json()
    except ValueError:
        body = {}
    if resp.status_code >= 400:
        err = body.get("error") if isinstance(body, dict) else None
        detail = (err.get("message") if isinstance(err, dict) else None) \
            or (body.get("message") if isinstance(body, dict) else None) or resp.text[:300]
        hint = _ROUTER_HTTP.get(resp.status_code, "")
        raise TopviewError(_redact(f"API Router 返回 HTTP {resp.status_code}：{hint} {detail}".strip()))
    if not isinstance(body, dict) or "data" not in body:
        raise TopviewError(f"API Router 返回了意外的响应：{resp.text[:200]}")
    return body["data"]


def _normalize_router(d: dict) -> dict[str, Any]:
    """API Router 的任务状态：created / processing → 继续等；payment_required → 余额不够，
    充值后服务端自动结算，不要重复提交；completed 且有 outputs 才算完成。"""
    status = str(d.get("status", "")).lower()
    outputs = [o for o in d.get("outputs") or [] if isinstance(o, str)]
    out: dict[str, Any] = {"task_id": d.get("id"), "kind": "router", "status": status or "unknown",
                           "urls": [o for o in outputs if o.startswith("http")]}
    for k in ("charged_usd", "billing_state", "last_frame_url"):
        if d.get(k):
            out[k] = d[k]
    if status == "failed":
        out["state"] = "failed"
        out["error"] = d.get("error") or "任务失败（TopView 未给出原因）"
    elif status == "payment_required":
        out["state"] = "payment_required"
        for k in ("amount_due_usd", "shortfall_usd"):
            if d.get(k):
                out[k] = d[k]
        out["hint"] = ("余额不足以结算。到 platform.topview.ai 给同一工作区充值后会自动结算，"
                       "之后用 query_task(kind=\"router\") 取结果，不要重复提交。")
    elif status == "completed" and outputs:
        out["state"] = "done"
        if len(out["urls"]) < len(outputs):
            out["inline_outputs"] = len(outputs) - len(out["urls"])
    else:
        out["state"] = "running"
    return out


def _compact(v: Any) -> Any:
    """递归去掉 None / 空串 / 空容器，避免把没填的可选项发给模型校验。"""
    if isinstance(v, dict):
        v = {k: _compact(x) for k, x in v.items()}
        return {k: x for k, x in v.items() if x not in (None, "", [], {})}
    if isinstance(v, list):
        return [x for x in (_compact(i) for i in v) if x not in (None, "", [], {})]
    return v


# ── 工具：账户与素材库 ───────────────────────────────────────────────────

def get_credit() -> dict[str, Any]:
    return {"success": True, "data": _request("GET", "/user/credit/detail")}


def list_avatars(*, gender: str | None = None, custom: bool = False,
                 page: int = 1, page_size: int = 20) -> dict[str, Any]:
    r = _request("GET", "/v1/aiavatar/query", params={
        "pageNo": page, "pageSize": min(max(page_size, 1), 50), "gender": gender,
        "isCustom": "true" if custom else None,
    }) or {}
    items = [
        {k: a.get(k) for k in ("aiavatarId", "aiavatarName", "gender", "coverUrl",
                               "previewVideoUrl", "voiceoverIdDefault")}
        for a in r.get("data") or []
    ]
    return {"success": True, "data": {"total": r.get("total"), "page": r.get("pageNo"),
                                      "avatars": items}}


def list_voices(*, language: str | None = None, gender: str | None = None,
                style: str | None = None, custom: bool = False,
                page: int = 1, page_size: int = 20) -> dict[str, Any]:
    r = _request("GET", "/v1/voice/query", params={
        "pageNo": page, "pageSize": min(max(page_size, 1), 50), "language": language,
        "gender": gender, "style": style, "isCustom": "true" if custom else None,
    }) or {}
    return {"success": True, "data": {"total": r.get("total"), "page": r.get("pageNo"),
                                      "voices": r.get("data") or []}}


def list_captions() -> dict[str, Any]:
    r = _request("GET", "/v1/caption/list")
    return {"success": True, "data": r}


# ── 工具：上传 ───────────────────────────────────────────────────────────

def _fmt_of(name: str, explicit: str | None) -> str:
    fmt = (explicit or Path(name).suffix.lstrip(".")).lower()
    if fmt not in UPLOAD_FORMATS:
        raise TopviewError(f"不支持的格式 {fmt or '（无扩展名）'}；"
                           f"支持：{', '.join(sorted(UPLOAD_FORMATS))}")
    return fmt


def upload_file(*, path: str | None = None, url: str | None = None,
                base64_data: str | None = None, format: str | None = None) -> dict[str, Any]:
    given = [x for x in (path, url, base64_data) if x]
    if len(given) != 1:
        raise TopviewError("path / url / base64_data 三选一，且只能给一个")
    if path:
        p = Path(path).expanduser()
        if not p.is_file():
            raise TopviewError(f"找不到文件：{path}")
        if p.stat().st_size > MAX_UPLOAD_BYTES:
            raise TopviewError(f"文件超过 {MAX_UPLOAD_BYTES // 1024 // 1024} MB 上限")
        fmt = _fmt_of(p.name, format)
        content = p.read_bytes()
    elif url:
        from .web import _check_url  # 复用网页抓取的 SSRF 防护：拒绝内网/回环地址

        _check_url(url)
        fmt = _fmt_of(url.split("?")[0], format)
        try:
            with httpx.Client(timeout=120, follow_redirects=False) as c:
                resp = c.get(url)
        except httpx.HTTPError as e:
            raise TopviewError(f"下载素材失败：{type(e).__name__}: {e}") from e
        if resp.status_code != 200:
            raise TopviewError(f"下载素材失败：HTTP {resp.status_code}")
        content = resp.content
        if len(content) > MAX_UPLOAD_BYTES:
            raise TopviewError(f"素材超过 {MAX_UPLOAD_BYTES // 1024 // 1024} MB 上限")
    else:
        if not format:
            raise TopviewError("base64_data 上传必须同时给 format（如 png / mp3）")
        fmt = _fmt_of("", format)
        try:
            content = base64.b64decode(base64_data or "", validate=True)
        except ValueError as e:
            raise TopviewError("base64_data 不是合法的 base64") from e

    cred = _request("GET", "/v1/upload/credential", params={"format": fmt}) or {}
    file_id, upload_url = cred.get("fileId"), cred.get("uploadUrl")
    if not file_id or not upload_url:
        raise TopviewError(f"上传凭证不完整：{cred}")
    try:
        with httpx.Client(timeout=300) as c:
            put = c.put(upload_url, content=content)  # 预签名地址，不带鉴权头
    except httpx.HTTPError as e:
        raise TopviewError(f"上传到存储失败：{type(e).__name__}") from e
    if put.status_code >= 300:
        raise TopviewError(f"上传到存储失败：HTTP {put.status_code}")
    ok = _request("GET", "/v1/upload/check", params={"fileId": file_id})
    if ok is not True and str(ok).lower() != "true":
        raise TopviewError("上传校验未通过，请重试")
    return {"success": True, "data": {"fileId": file_id, "format": fmt, "bytes": len(content)}}


# ── 工具：生成 ───────────────────────────────────────────────────────────

def create_marketing_video(*, product_link: str | None = None,
                           file_ids: list[str] | None = None,
                           product_name: str | None = None,
                           product_description: str | None = None,
                           custom_script: str | None = None,
                           target_audience: str | None = None,
                           language: str = "en", aspect_ratio: str = "9:16",
                           video_length_type: int = 2,
                           avatar_id: str | None = None, voice_id: str | None = None,
                           caption_id: str | None = None, logo_file_id: str | None = None,
                           wait_seconds: int | None = None) -> dict[str, Any]:
    if not product_link and not file_ids:
        raise TopviewError("product_link 与 file_ids 至少给一个")
    if not product_link and not product_name:
        raise TopviewError("没有商品链接时必须给 product_name")
    if not product_link and not custom_script and not product_description:
        raise TopviewError("没有商品链接且不用自定义脚本时，必须给 product_description")
    task_id = _submit("/v1/m2v/task/submit", {
        "productLink": product_link,
        "fileIds": file_ids or None,
        "productName": product_name,
        "productDescription": product_description,
        "isDiyScript": True if custom_script else None,
        "diyScriptDescription": custom_script,
        "targetAudience": target_audience,
        "language": language,
        "aspectRatio": aspect_ratio,
        "videoLengthType": video_length_type,
        "aiavatarId": avatar_id,
        "voiceId": voice_id,
        "captionId": caption_id,
        "logoFileId": logo_file_id,
    })
    return _wait("marketing_video", task_id, wait_seconds)


def create_avatar_video(*, script: str | None = None, audio_file_id: str | None = None,
                        avatar_id: str | None = None, custom_avatar: bool = False,
                        image_file_id: str | None = None, video_file_id: str | None = None,
                        voice_id: str | None = None, mode: str = "avatar1",
                        voice_speed: float = 1.0, caption_id: str | None = None,
                        wait_seconds: int | None = None) -> dict[str, Any]:
    if bool(script) == bool(audio_file_id):
        raise TopviewError("script（文本转语音）与 audio_file_id（已上传音频）二选一")
    sources = [x for x in (avatar_id, image_file_id, video_file_id) if x]
    if len(sources) != 1:
        raise TopviewError("avatar_id / image_file_id / video_file_id 三选一")
    if avatar_id:
        avatar_from = 2 if custom_avatar else 1
    else:
        avatar_from = 3 if image_file_id else 0
    # 公模用 TTS 时可省略音色（用数字人默认音色）；其余 TTS 组合必须给音色
    if script and not voice_id and avatar_from != 1:
        raise TopviewError("用自定义数字人 / 图片 / 视频配合文本时，必须给 voice_id（见 list_voices）")
    modes = {"avatar1": 0, "avatar2": 1, "avatar4": 2, "avatar4_fast": 3}
    if mode not in modes:
        raise TopviewError(f"mode 只能是 {', '.join(modes)}")
    if mode == "avatar1" and image_file_id:
        raise TopviewError("avatar1 只改口型、不支持图片输入；图片请用 avatar2 / avatar4")
    task_id = _submit("/v1/video_avatar/task/submit", {
        "avatarSourceFrom": avatar_from,
        "aiAvatarId": avatar_id,
        "imageFileId": image_file_id,
        "videoFileId": video_file_id,
        "audioSourceFrom": 1 if script else 0,
        "ttsText": script,
        "audioFileId": audio_file_id,
        "voiceoverId": voice_id,
        "voiceSpeed": min(max(float(voice_speed), 0.8), 1.2),
        "modeType": modes[mode],
        "captionId": caption_id,
    })
    return _wait("avatar_video", task_id, wait_seconds)


def query_task(*, kind: str, task_id: str) -> dict[str, Any]:
    if kind not in TASK_KINDS:
        raise TopviewError(f"kind 只能是 {', '.join(TASK_KINDS)}")
    return _wait(kind, task_id, 0)


# ── 工具：新版 API Router ────────────────────────────────────────────────

def router_list_models() -> dict[str, Any]:
    models = [{"model": m, "modes": spec["modes"], "resolution": spec.get("resolution"),
               "duration": spec.get("duration"), "doc": ROUTER_DOCS + m}
              for m, spec in ROUTER_MODELS.items()]
    return {"success": True, "data": {
        "models": models,
        "note": "价格见 https://platform.topview.ai/pricing，按美元余额计费。"
                "列表外的新模型可在 router_generate 里用 body 原样提交（参数以模型文档为准）。",
    }}


def _router_body(fmt: str, mode: str, *, prompt: str, first_frame_url: str | None,
                 last_frame_url: str | None, reference_image_urls: list[str],
                 reference_video_urls: list[str], reference_audio_urls: list[str],
                 aspect_ratio: str | None, resolution: str | None, duration: int | None,
                 generate_audio: bool | None, extra: dict) -> dict[str, Any]:
    if fmt == "image":
        if mode == "edit" and not reference_image_urls:
            raise TopviewError("edit 模式必须给 reference_image_urls（要编辑的图）")
        return {"prompt": prompt, "aspect_ratio": aspect_ratio, "resolution": resolution,
                "images": reference_image_urls if mode == "edit" else None, **extra}
    if mode == "image-to-video" and not first_frame_url:
        raise TopviewError("image-to-video 必须给 first_frame_url（首帧图）")
    if fmt == "wan":
        media = ([{"type": "first_frame", "url": first_frame_url},
                  {"type": "last_frame", "url": last_frame_url}]
                 + [{"type": "reference_image", "url": u} for u in reference_image_urls]
                 + [{"type": "reference_video", "url": u} for u in reference_video_urls]
                 + [{"type": "reference_audio", "url": u} for u in reference_audio_urls])
        return {"input": {"prompt": prompt, "media": [m for m in media if m["url"]]},
                "parameters": {"ratio": aspect_ratio, "resolution": resolution,
                               "duration": duration, "audio": generate_audio, **extra}}
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for role, url in (("first_frame", first_frame_url), ("last_frame", last_frame_url)):
        if url:
            content.append({"type": "image_url", "role": role, "image_url": {"url": url}})
    for typ, role, urls in (("image_url", "reference_image", reference_image_urls),
                            ("video_url", "reference_video", reference_video_urls),
                            ("audio_url", "reference_audio", reference_audio_urls)):
        content += [{"type": typ, "role": role, typ: {"url": u}} for u in urls]
    return {"content": content, "ratio": aspect_ratio, "resolution": resolution,
            "duration": duration, "generate_audio": generate_audio, **extra}


def router_generate(*, model: str, mode: str, prompt: str | None = None,
                    first_frame_url: str | None = None, last_frame_url: str | None = None,
                    reference_image_urls: list[str] | None = None,
                    reference_video_urls: list[str] | None = None,
                    reference_audio_urls: list[str] | None = None,
                    aspect_ratio: str | None = None, resolution: str | None = None,
                    duration: int | None = None, generate_audio: bool | None = None,
                    extra: dict | None = None, body: dict | None = None,
                    wait_seconds: int | None = None) -> dict[str, Any]:
    model, mode = model.strip().strip("/"), mode.strip()
    spec = ROUTER_MODELS.get(model)
    if body is None:
        if not spec:
            raise TopviewError(f"未内置的模型 {model}；已内置：{', '.join(ROUTER_MODELS)}。"
                               "新模型请按其文档用 body 原样提交")
        if mode not in spec["modes"]:
            raise TopviewError(f"{model} 只支持 {', '.join(spec['modes'])}")
        if not prompt:
            raise TopviewError("prompt 必填")
        body = _router_body(spec["format"], mode, prompt=prompt, first_frame_url=first_frame_url,
                            last_frame_url=last_frame_url,
                            reference_image_urls=reference_image_urls or [],
                            reference_video_urls=reference_video_urls or [],
                            reference_audio_urls=reference_audio_urls or [],
                            aspect_ratio=aspect_ratio, resolution=resolution, duration=duration,
                            generate_audio=generate_audio, extra=extra or {})
    d = _router_request("POST", f"/models/{model}/{mode}/predictions", json=_compact(body),
                        idempotency_key=str(uuid.uuid4())) or {}
    task_id = d.get("id") if isinstance(d, dict) else None
    if not task_id:
        raise TopviewError(f"提交成功但没拿到任务 id：{d}")
    return _wait("router", str(task_id), wait_seconds)


def router_upload_file(*, path: str | None = None, url: str | None = None,
                       kind: str | None = None) -> dict[str, Any]:
    if bool(path) == bool(url):
        raise TopviewError("path 与 url 二选一，且只能给一个")
    if kind and kind not in ("image", "video", "audio"):
        raise TopviewError("kind 只能是 image / video / audio")
    name = Path(path).name if path else (url or "").split("?")[0]
    kind = kind or ROUTER_KINDS.get(Path(name).suffix.lstrip(".").lower())
    if not kind:
        raise TopviewError(f"无法从扩展名判断素材类型，请给 kind；支持：{', '.join(sorted(ROUTER_KINDS))}")
    if url:
        # 由 TopView 服务端去抓，官方只收公网 https、拒绝跳转与内网，这里提前挡掉明显不合规的
        if not url.startswith("https://"):
            raise TopviewError("url 必须是公网 https 直链")
        d = _router_request("POST", "/media/imports", json={"kind": kind, "url": url})
    else:
        p = Path(path or "").expanduser()
        if not p.is_file():
            raise TopviewError(f"找不到文件：{path}")
        if p.stat().st_size > ROUTER_MAX_UPLOAD:
            raise TopviewError("文件超过 20 MiB 上限（API Router 限制）")
        mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        d = _router_request("POST", "/media/files", data={"kind": kind},
                            files={"file": (p.name, p.read_bytes(), mime)})
    d = d if isinstance(d, dict) else {}
    return {"success": True, "data": {
        "asset_id": d.get("id"), "kind": d.get("kind"), "content_type": d.get("content_type"),
        "size": d.get("size"), "url": d.get("download_url"),
        "note": "url 是临时签名地址，尽快填进 router_generate 的图片 / 参考素材字段",
    }}


# ── 工具清单 ─────────────────────────────────────────────────────────────

TASK_KINDS = [*_QUERY, "router"]

_WAIT_PROP = {"type": "integer",
              "description": f"提交后在工具内等待结果的秒数，0-{MAX_WAIT}，默认 {MAX_WAIT}。"
                             "超时未完成会返回 taskId，之后用 query_task 继续查"}

TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_credit",
        "description": "查询 TopView 旧版 API 的剩余积分（需 API Key + UID）。生成任务前可先查，"
                       "避免积分不足（code 4100）。新版 API Router 的美元余额不在这里。",
        "read_only": True,
        "handler": get_credit,
        "schema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_avatars",
        "description": "列出可用的数字人（公模或自己的私模），返回 aiavatarId、名称、性别、封面、"
                       "预览视频与默认音色 voiceoverIdDefault。用于 create_marketing_video / "
                       "create_avatar_video 的 avatar_id。",
        "read_only": True,
        "handler": list_avatars,
        "schema": {
            "type": "object",
            "properties": {
                "gender": {"type": "string", "enum": ["male", "female"]},
                "custom": {"type": "boolean", "description": "true 只看自己的私模，默认 false（公模）"},
                "page": {"type": "integer", "description": "页码，默认 1"},
                "page_size": {"type": "integer", "description": "每页条数，1-50，默认 20"},
            },
        },
    },
    {
        "name": "list_voices",
        "description": "列出可用音色，返回 voiceId、名称、擅长语言、口音、性别、年龄、风格与试听地址。",
        "read_only": True,
        "handler": list_voices,
        "schema": {
            "type": "object",
            "properties": {
                "language": {"type": "string", "description": "语言代码，如 en、zh-CN、ja，默认 en"},
                "gender": {"type": "string", "enum": ["male", "female"]},
                "style": {"type": "string", "enum": ["UGC", "Advertisement"]},
                "custom": {"type": "boolean", "description": "true 只看自己克隆的音色"},
                "page": {"type": "integer", "description": "页码，默认 1"},
                "page_size": {"type": "integer", "description": "每页条数，1-50，默认 20"},
            },
        },
    },
    {
        "name": "list_captions",
        "description": "列出可用的字幕样式，返回 captionId 与预览图。不传 caption_id 时 TopView 随机选一个。",
        "read_only": True,
        "handler": list_captions,
        "schema": {"type": "object", "properties": {}},
    },
    {
        "name": "upload_file",
        "description": "把素材上传到 TopView，返回 fileId 供生成工具使用。三种来源三选一："
                       "path（本机文件）、url（公网直链，拒绝内网地址）、base64_data（需同时给 format）。"
                       "支持 mp4/mov/png/jpg/jpeg/bmp/webp/mp3/wav/m4a，单个不超过 200 MB。",
        "read_only": False,
        "handler": upload_file,
        "schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "本机文件绝对路径"},
                "url": {"type": "string", "description": "公网 http(s) 直链"},
                "base64_data": {"type": "string", "description": "文件内容的 base64，适合 10 MB 以内"},
                "format": {"type": "string", "description": "文件格式，如 png、mp4；path/url 可按扩展名推断"},
            },
        },
    },
    {
        "name": "create_marketing_video",
        "description": "【核心】商品链接一键出带货短视频：TopView 自动解析商品、写脚本、选数字人与配音、"
                       "剪辑成片。也可不给链接，改用 file_ids（上传的商品图/视频）+ 商品名与描述。"
                       "custom_script 给了就按你的脚本念（适合先让 LLM 写好文案）。"
                       "这会消耗 TopView 积分。返回任务状态与成片 videoUrl。",
        "read_only": False,
        "handler": create_marketing_video,
        "schema": {
            "type": "object",
            "properties": {
                "product_link": {"type": "string",
                                 "description": "商品页链接（Shopify / Amazon / TikTok Shop / 独立站等），优先于 file_ids"},
                "file_ids": {"type": "array", "items": {"type": "string"},
                             "description": "upload_file 返回的商品图/视频 fileId"},
                "product_name": {"type": "string", "description": "商品名；无链接时必填"},
                "product_description": {"type": "string",
                                        "description": "商品卖点描述；无链接且不用 custom_script 时必填"},
                "custom_script": {"type": "string", "description": "自定义口播脚本；给了就不让 AI 写"},
                "target_audience": {"type": "string", "description": "目标人群，帮助 AI 写脚本"},
                "language": {"type": "string", "description": "成片语言代码，如 en、zh-CN、ja、es，默认 en"},
                "aspect_ratio": {"type": "string", "enum": ["9:16", "3:4", "1:1", "4:3", "16:9"],
                                 "description": "画幅，默认 9:16（竖屏）"},
                "video_length_type": {"type": "integer", "enum": [1, 2, 3, 4],
                                      "description": "时长档：1=30-50s，2=15-30s，3=30-45s，4=45-60s；默认 2"},
                "avatar_id": {"type": "string", "description": "数字人 ID（list_avatars），不填由 AI 选"},
                "voice_id": {"type": "string", "description": "音色 ID（list_voices），不填由 AI 选"},
                "caption_id": {"type": "string", "description": "字幕样式 ID（list_captions）"},
                "logo_file_id": {"type": "string", "description": "品牌 logo 的 fileId"},
                "wait_seconds": _WAIT_PROP,
            },
        },
    },
    {
        "name": "create_avatar_video",
        "description": "数字人口播：让数字人念一段文本（或对上一段音频的口型）。数字人来源三选一："
                       "avatar_id（公模/私模）、image_file_id（一张人像图）、video_file_id（一段人像视频）。"
                       "这会消耗 TopView 积分。返回成片 videoUrl。",
        "read_only": False,
        "handler": create_avatar_video,
        "schema": {
            "type": "object",
            "properties": {
                "script": {"type": "string", "description": "口播文本（走 TTS）；与 audio_file_id 二选一"},
                "audio_file_id": {"type": "string", "description": "已上传音频的 fileId"},
                "avatar_id": {"type": "string", "description": "数字人 ID（list_avatars）"},
                "custom_avatar": {"type": "boolean", "description": "avatar_id 是否为私模，默认 false"},
                "image_file_id": {"type": "string", "description": "人像图片 fileId（需 avatar2/avatar4 模式）"},
                "video_file_id": {"type": "string", "description": "人像视频 fileId"},
                "voice_id": {"type": "string",
                             "description": "音色 ID；公模 + 文本时可不填（用数字人默认音色），其余文本场景必填"},
                "mode": {"type": "string", "enum": ["avatar1", "avatar2", "avatar4", "avatar4_fast"],
                         "description": "avatar1 只改口型（默认）；avatar2/avatar4 以首帧驱动全身动作，支持图片"},
                "voice_speed": {"type": "number", "description": "语速 0.8-1.2，默认 1"},
                "caption_id": {"type": "string", "description": "字幕样式 ID，仅公模支持"},
                "wait_seconds": _WAIT_PROP,
            },
        },
    },
    {
        "name": "query_task",
        "description": "查询生成任务的进度与结果。state=done 时 urls 里是成片地址；"
                       "state=running 请稍后再查，不要重复提交任务；"
                       "state=payment_required 表示 API Router 余额不足，充值后自动结算。",
        "read_only": True,
        "handler": query_task,
        "schema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": TASK_KINDS,
                         "description": "任务类型：marketing_video / avatar_video 对应旧版工具，"
                                        "router 对应 router_generate"},
                "task_id": {"type": "string", "description": "提交时返回的 task_id"},
            },
            "required": ["kind", "task_id"],
        },
    },
    {
        "name": "router_list_models",
        "description": "【新版 API Router】列出可用的生图 / 生视频模型、各自支持的模式、分辨率与时长取值。"
                       "不联网、不需要凭据。",
        "read_only": True,
        "handler": router_list_models,
        "schema": {"type": "object", "properties": {}},
    },
    {
        "name": "router_generate",
        "description": "【新版 API Router】用 Seedance / WAN / MiniMax / Topview T1 生视频，或 GPT Image 2 "
                       "生图、改图（需 TOPVIEW_API_PLATFORM_KEY）。按美元余额计费，会花钱。"
                       "图片 / 参考素材填公网 URL，本地文件先用 router_upload_file 换成 URL。"
                       "返回任务状态与产物 urls。",
        "read_only": False,
        "handler": router_generate,
        "schema": {
            "type": "object",
            "properties": {
                "model": {"type": "string",
                          "description": "模型，如 bytedance/seedance-2.5、alibaba/wan-3.0、openai/gpt-image-2"
                                         "（见 router_list_models）"},
                "mode": {"type": "string",
                         "description": "text-to-video / image-to-video / omni-reference-to-video / "
                                        "reference-to-video（WAN）/ text-to-image / edit（GPT Image）"},
                "prompt": {"type": "string", "description": "画面描述；不用 body 时必填"},
                "first_frame_url": {"type": "string", "description": "首帧图 URL；image-to-video 必填"},
                "last_frame_url": {"type": "string", "description": "尾帧图 URL（可选）"},
                "reference_image_urls": {"type": "array", "items": {"type": "string"},
                                         "description": "参考图 URL；GPT Image 的 edit 模式里是要编辑的图"},
                "reference_video_urls": {"type": "array", "items": {"type": "string"},
                                         "description": "参考视频 URL（omni / reference 模式）"},
                "reference_audio_urls": {"type": "array", "items": {"type": "string"},
                                         "description": "参考音频 URL（omni / reference 模式）"},
                "aspect_ratio": {"type": "string",
                                 "description": "画幅，如 16:9、9:16、1:1、adaptive；不填用模型默认"},
                "resolution": {"type": "string",
                               "description": "分辨率，大小写按模型：Seedance 720p、WAN 720P、MiniMax 768P、GPT Image 1k"},
                "duration": {"type": "integer", "description": "视频秒数，-1 为自动；范围见 router_list_models"},
                "generate_audio": {"type": "boolean", "description": "是否同时生成声音（视频模型）"},
                "extra": {"type": "object",
                          "description": "其余模型参数原样并入请求（WAN 并入 parameters），如 seed、quality、n"},
                "body": {"type": "object",
                         "description": "完整请求体，给了就原样提交、忽略上面的字段；用于未内置的新模型"},
                "wait_seconds": _WAIT_PROP,
            },
            "required": ["model", "mode"],
        },
    },
    {
        "name": "router_upload_file",
        "description": "【新版 API Router】把本地文件或公网 https 链接存入 API Router 素材库，返回可填进 "
                       "router_generate 的临时 url。单个不超过 20 MiB，音视频不超过 300 秒；图片仅 PNG/JPEG/WebP。",
        "read_only": False,
        "handler": router_upload_file,
        "schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "本机文件绝对路径"},
                "url": {"type": "string", "description": "公网 https 直链（由 TopView 服务端拉取）"},
                "kind": {"type": "string", "enum": ["image", "video", "audio"],
                         "description": "素材类型；不填按扩展名推断"},
            },
        },
    },
]

SERVER_NAME = "topview"
DISPLAY_NAME = "TopView AI 营销视频"
DESCRIPTION = ("用 TopView 把商品链接一键做成带货短视频、公模数字人口播（旧版 API：API Key + UID），"
               "或用新版 API Router 调 Seedance / WAN / MiniMax / GPT Image 生视频生图（一个 Platform Key）。"
               "两套凭据至少配一套，都可无人值守。配音、电商数据请用官方的 topview_official。")
DESCRIPTION_EN = ("TopView AI via API keys (works unattended). Legacy OpenAPI (API key + UID): product "
                  "link to UGC-style ad video and stock-avatar talking-head video. New API Router "
                  "(one platform key): Seedance / WAN / MiniMax / GPT Image video and image generation. "
                  "Configure at least one. For TTS and e-commerce data use topview_official.")
# 两套 API 互不相通、各自独立可用，所以都不是必填；缺哪套，对应工具会报出该去哪里拿凭据
REQUIRED_ENV: list[str] = []
ENV_DOCS = {
    "TOPVIEW_API_KEY": {
        "description": "旧版 API 的 API Key（带货视频、数字人），仅 Pro / Business 会员可在 API 设置页看到；"
                       "与 UID 成对填写。只用新版 API Router 可留空",
        "prompt": "旧版 API Key（可选）",
        "doc_url": "https://www.topview.ai/api-settings",
        "doc_label": "前往 TopView 旧版 API 设置",
    },
    "TOPVIEW_UID": {
        "description": "旧版 API 的 UID，与 API Key 在同一页，也可点右上角头像复制。只用新版 API Router 可留空",
        "prompt": "旧版 UID（可选）",
        "doc_url": "https://www.topview.ai/api-settings",
        "doc_label": "前往 TopView 旧版 API 设置",
    },
    "TOPVIEW_API_PLATFORM_KEY": {
        "description": "新版 API Router 的 Platform Key（生图生视频，按美元余额计费，免费账号也能开），"
                       "创建时勾选 models:generate 与 requests:read。只用旧版可留空",
        "prompt": "新版 API Router Key（可选）",
        "doc_url": "https://platform.topview.ai/api-keys",
        "doc_label": "前往 platform.topview.ai 创建 Key",
    },
}
OPTIONAL_ENV = ["TOPVIEW_API_KEY", "TOPVIEW_UID", "TOPVIEW_API_PLATFORM_KEY"]
