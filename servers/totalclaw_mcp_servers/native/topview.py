"""TopView（topview.ai）AI 营销视频 MCP 服务器 —— 商品链接出带货视频、公模数字人口播。

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
图/视频生成（Seedance / Kling / Veo 等多模型）、TTS、克隆音色、抠图、商品模特图、电商数据
一律走官方 MCP，本服务器不重复实现（旧版 v1 图生视频只有 lite/pro 档，远不如官方）。
官方页面注明 Unlimited 套餐不支持 MCP / Plugin / Skill；OpenAPI 是否同样受限待实测。

接口依据（2026-10 核对）：
    https://s.apifox.cn/apidoc/shared/115a0d85-28a5-479d-8b8b-83d7898a7246   英文版
    https://s.apifox.cn/apidoc/shared/e8e2bcff-c3c8-4f04-9b5c-465e985c31bc   中文版
    积分查询 /user/credit/detail 取自官方 topviewai/codex-topview-ai 客户端。

凭据（环境变量）：
    TOPVIEW_API_KEY   topview.ai → API Settings 里的 API Key
    TOPVIEW_UID       同页的 UID（或点头像复制）
"""
from __future__ import annotations

import base64
import os
import time
from pathlib import Path
from typing import Any

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
            "在 topview.ai 登录后打开 API Settings，复制 API Key 与 UID。"
        )
    return {"Authorization": f"Bearer {key}", "Topview-Uid": uid,
            "User-Agent": "totalclaw-mcp-servers/0.1"}


def _redact(text: str) -> str:
    for k in ("TOPVIEW_API_KEY", "TOPVIEW_UID"):
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
    if kind not in _QUERY:
        raise TopviewError(f"kind 只能是 {', '.join(_QUERY)}")
    return _wait(kind, task_id, 0)


# ── 工具清单 ─────────────────────────────────────────────────────────────

_WAIT_PROP = {"type": "integer",
              "description": f"提交后在工具内等待结果的秒数，0-{MAX_WAIT}，默认 {MAX_WAIT}。"
                             "超时未完成会返回 taskId，之后用 query_task 继续查"}

TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_credit",
        "description": "查询 TopView 账户剩余积分。生成任务前可先查，避免积分不足（code 4100）。",
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
                       "state=running 请稍后再查，不要重复提交任务。",
        "read_only": True,
        "handler": query_task,
        "schema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": list(_QUERY),
                         "description": "任务类型，与提交时用的工具对应"},
                "task_id": {"type": "string", "description": "提交时返回的 task_id"},
            },
            "required": ["kind", "task_id"],
        },
    },
]

SERVER_NAME = "topview"
DISPLAY_NAME = "TopView AI 营销视频"
DESCRIPTION = ("用 TopView 把商品链接一键做成带货短视频，并支持公模数字人口播（API Key 鉴权，可无人值守）。"
               "生图生视频、配音、电商数据请用官方的 topview_official。")
DESCRIPTION_EN = ("TopView AI marketing video via the OpenAPI (API key, works unattended): product "
                  "link to UGC-style ad video and stock-avatar talking-head video. For image/video "
                  "generation, TTS and e-commerce data use topview_official.")
REQUIRED_ENV = ["TOPVIEW_API_KEY", "TOPVIEW_UID"]
ENV_DOCS = {
    "TOPVIEW_API_KEY": {
        "description": "TopView OpenAPI 的 API Key，在 topview.ai 登录后的 API Settings 页复制",
        "prompt": "请粘贴 TopView API Settings 页里的 API Key",
        "doc_url": "https://www.topview.ai/openapi",
        "doc_label": "前往 TopView 开通 API 并复制 API Key",
    },
    "TOPVIEW_UID": {
        "description": "TopView 账号 UID，与 API Key 在同一页（API Settings），也可点右上角头像复制",
        "prompt": "请粘贴 TopView API Settings 页里的 UID",
        "doc_url": "https://www.topview.ai/openapi",
        "doc_label": "前往 TopView 复制 UID",
    },
}
OPTIONAL_ENV: list[str] = []
