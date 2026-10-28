"""TopView 原生服务器单测。不发真实网络请求 —— httpx.Client 被换成 MockTransport。

    cd servers && python -m pytest tests -q
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from totalclaw_mcp_servers.native import topview  # noqa: E402

_RealClient = httpx.Client


@pytest.fixture
def api(monkeypatch):
    """按 (method, path) 返回预设响应，并记录全部请求。"""
    monkeypatch.setenv("TOPVIEW_API_KEY", "sk-test-key")
    monkeypatch.setenv("TOPVIEW_UID", "uid-123")
    monkeypatch.setattr(topview, "POLL_INTERVAL", 0)
    routes: dict[tuple[str, str], list] = {}
    calls: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        queue = routes.get((req.method, req.url.path))
        if not queue:
            return httpx.Response(404, text=f"no route {req.method} {req.url.path}")
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, httpx.Response):
            return item
        return httpx.Response(200, json=item)

    monkeypatch.setattr(topview.httpx, "Client",
                        lambda **kw: _RealClient(transport=httpx.MockTransport(handler), **kw))

    def route(method: str, path: str, *responses):
        routes[(method, path)] = list(responses)

    route.calls = calls
    return route


def _ok(result):
    return {"code": "200", "message": "Success", "result": result}


def test_missing_credentials_is_clean_error(monkeypatch):
    monkeypatch.delenv("TOPVIEW_API_KEY", raising=False)
    monkeypatch.delenv("TOPVIEW_UID", raising=False)
    with pytest.raises(topview.TopviewError, match="TOPVIEW_API_KEY, TOPVIEW_UID"):
        topview.get_credit()
    assert topview.TopviewError.clean is True


def test_auth_headers_and_envelope(api):
    api("GET", "/user/credit/detail", _ok({"credit": 42}))
    out = topview.get_credit()
    assert out == {"success": True, "data": {"credit": 42}}
    req = api.calls[0]
    assert req.headers["Authorization"] == "Bearer sk-test-key"
    assert req.headers["Topview-Uid"] == "uid-123"


def test_business_error_code_is_humanized(api):
    """HTTP 200 + code!=200 必须判失败，不能当成功喂给模型。"""
    api("GET", "/user/credit/detail", {"code": "4100", "message": "Credit not enough", "result": None})
    with pytest.raises(topview.TopviewError, match="积分不足"):
        topview.get_credit()


def test_http_401_does_not_leak_key(api):
    api("GET", "/user/credit/detail", httpx.Response(401, text="bad key sk-test-key"))
    with pytest.raises(topview.TopviewError) as ei:
        topview.get_credit()
    assert "sk-test-key" not in str(ei.value)


def test_marketing_video_from_link_polls_until_done(api):
    api("POST", "/v1/m2v/task/submit", _ok({"taskId": "t1", "status": "init", "errorMsg": None}))
    api("GET", "/v1/m2v/task/query",
        _ok({"taskId": "t1", "status": "running", "exportVideos": []}),
        _ok({"taskId": "t1", "status": "success", "productName": "杯子",
             "exportVideos": [{"scriptId": 0, "status": "success",
                               "videoUrl": "https://cdn/x.mp4", "coverUrl": "https://cdn/x.jpg"}]}))
    out = topview.create_marketing_video(product_link="https://shop/p/1", language="zh-CN")
    assert out["success"] is True
    assert out["data"]["state"] == "done"
    assert out["data"]["urls"] == ["https://cdn/x.mp4"]
    body = json.loads(api.calls[0].content)
    # 缺省的可选字段整项不发，而不是发 null
    assert body == {"productLink": "https://shop/p/1", "language": "zh-CN",
                    "aspectRatio": "9:16", "videoLengthType": 2}


def test_success_without_url_is_still_running(api):
    """status=success 但没有成片地址时不算完成（以产物 URL 为权威）。"""
    api("GET", "/v1/video_avatar/task/query", _ok({"taskId": "t2", "status": "success",
                                                   "outputVideoUrl": ""}))
    out = topview.query_task(kind="avatar_video", task_id="t2")
    assert out["data"]["state"] == "running"
    assert "query_task" in out["data"]["hint"]


def test_failed_task_reports_error(api):
    api("GET", "/v1/video_avatar/task/query", _ok({"taskId": "t3", "status": "fail",
                                                   "errorMsg": "face not found"}))
    out = topview.query_task(kind="avatar_video", task_id="t3")
    assert out["success"] is False
    assert out["data"]["error"] == "face not found"


def test_marketing_video_requires_name_without_link():
    with pytest.raises(topview.TopviewError, match="product_name"):
        topview.create_marketing_video(file_ids=["f1"])


def test_avatar_video_body_for_public_avatar_tts(api):
    api("POST", "/v1/video_avatar/task/submit", _ok({"taskId": "t4"}))
    api("GET", "/v1/video_avatar/task/query",
        _ok({"taskId": "t4", "status": "success", "outputVideoUrl": "https://cdn/a.mp4",
             "costCredit": 3}))
    out = topview.create_avatar_video(script="大家好", avatar_id="av1")
    assert out["data"]["urls"] == ["https://cdn/a.mp4"]
    assert out["data"]["cost_credit"] == 3
    body = json.loads(api.calls[0].content)
    assert body == {"avatarSourceFrom": 1, "aiAvatarId": "av1", "audioSourceFrom": 1,
                    "ttsText": "大家好", "voiceSpeed": 1.0, "modeType": 0}


def test_avatar_video_validation():
    with pytest.raises(topview.TopviewError, match="二选一"):
        topview.create_avatar_video(avatar_id="av1")
    with pytest.raises(topview.TopviewError, match="voice_id"):
        topview.create_avatar_video(script="hi", image_file_id="f1", mode="avatar2")
    with pytest.raises(topview.TopviewError, match="avatar1"):
        topview.create_avatar_video(script="hi", image_file_id="f1", voice_id="v1")


def test_wait_zero_returns_task_id_without_sleeping(api):
    api("POST", "/v1/video_avatar/task/submit", _ok({"taskId": "t5"}))
    api("GET", "/v1/video_avatar/task/query", _ok({"taskId": "t5", "status": "running"}))
    out = topview.create_avatar_video(script="hi", avatar_id="av1", wait_seconds=0)
    assert out["data"]["task_id"] == "t5" and out["data"]["state"] == "running"


def test_only_capabilities_missing_from_official_mcp():
    """与官方 MCP 分工：图/视频生成、TTS 走 topview_official，这里不重复实现。"""
    names = {t["name"] for t in topview.TOOLS}
    assert "create_marketing_video" in names and "create_avatar_video" in names
    assert not names & {"create_speech", "create_image_to_video"}
    assert set(topview._QUERY) == {"marketing_video", "avatar_video"}


def test_upload_three_steps(api, tmp_path):
    f = tmp_path / "cup.png"
    f.write_bytes(b"\x89PNG fake")
    api("GET", "/v1/upload/credential",
        _ok({"fileId": "fid", "fileName": "x.png", "format": "png",
             "uploadUrl": "https://s3.example.com/bucket/x.png?sig=1"}))
    api("PUT", "/bucket/x.png", httpx.Response(200))
    api("GET", "/v1/upload/check", _ok(True))
    out = topview.upload_file(path=str(f))
    assert out["data"] == {"fileId": "fid", "format": "png", "bytes": 9}
    put = api.calls[1]
    assert put.content == b"\x89PNG fake"
    # 预签名地址不能带我们的鉴权头
    assert "Authorization" not in put.headers


def test_upload_rejects_bad_format_and_private_url(tmp_path, monkeypatch):
    monkeypatch.delenv("TOTALCLAW_MCP_WEB_ALLOW_PRIVATE", raising=False)
    f = tmp_path / "a.gif"
    f.write_bytes(b"x")
    with pytest.raises(topview.TopviewError, match="不支持的格式"):
        topview.upload_file(path=str(f))
    with pytest.raises(Exception, match="内网"):
        topview.upload_file(url="http://127.0.0.1/a.png")
    with pytest.raises(topview.TopviewError, match="三选一"):
        topview.upload_file()


# ── 新版 API Router ──────────────────────────────────────────────────────

@pytest.fixture
def router(api, monkeypatch):
    monkeypatch.setenv("TOPVIEW_API_PLATFORM_KEY", "pf_test_key")
    return api


def _task(status, outputs=(), **kw):
    return {"code": 200, "message": "ok",
            "data": {"id": "pred-1", "status": status, "outputs": list(outputs), **kw}}


def test_router_needs_only_platform_key(router, monkeypatch):
    monkeypatch.delenv("TOPVIEW_API_KEY")
    monkeypatch.delenv("TOPVIEW_UID")
    router("POST", "/api/v1/models/bytedance/seedance-2.5/text-to-video/predictions",
           _task("created"))
    router("GET", "/api/v1/predictions/pred-1",
           _task("processing"), _task("completed", ["https://cdn.example.com/v.mp4"],
                                      charged_usd="0.98", billing_state="CAPTURED"))
    out = topview.router_generate(model="bytedance/seedance-2.5", mode="text-to-video",
                                  prompt="a cup", aspect_ratio="9:16", duration=5)
    assert out["data"]["state"] == "done"
    assert out["data"]["urls"] == ["https://cdn.example.com/v.mp4"]
    assert out["data"]["charged_usd"] == "0.98"
    submit = router.calls[0]
    assert submit.headers["Authorization"] == "Bearer pf_test_key"
    assert "Topview-Uid" not in submit.headers and submit.headers["Idempotency-Key"]
    # 没填的可选项不发出去
    assert json.loads(submit.content) == {
        "content": [{"type": "text", "text": "a cup"}], "ratio": "9:16", "duration": 5}


def test_router_body_formats_per_model(router):
    router("POST", "/api/v1/models/alibaba/wan-3.0/image-to-video/predictions", _task("created"))
    router("POST", "/api/v1/models/bytedance/seedance-2.0/image-to-video/predictions", _task("created"))
    router("POST", "/api/v1/models/openai/gpt-image-2/edit/predictions", _task("created"))
    router("GET", "/api/v1/predictions/pred-1", _task("processing"))
    kw = dict(mode="image-to-video", prompt="p", first_frame_url="https://x/a.png",
              resolution="720P", generate_audio=True, wait_seconds=0)
    topview.router_generate(model="alibaba/wan-3.0", extra={"seed": 7}, **kw)
    topview.router_generate(model="bytedance/seedance-2.0", **kw)
    topview.router_generate(model="openai/gpt-image-2", mode="edit", prompt="p",
                            reference_image_urls=["https://x/b.png"], wait_seconds=0)
    wan, seed, img = (json.loads(c.content) for c in router.calls if c.method == "POST")
    assert wan == {"input": {"prompt": "p", "media": [{"type": "first_frame", "url": "https://x/a.png"}]},
                   "parameters": {"resolution": "720P", "audio": True, "seed": 7}}
    assert seed["content"][1] == {"type": "image_url", "role": "first_frame",
                                  "image_url": {"url": "https://x/a.png"}}
    assert seed["generate_audio"] is True
    assert img == {"prompt": "p", "images": ["https://x/b.png"]}


def test_router_validation_and_raw_body(router):
    with pytest.raises(topview.TopviewError, match="只支持"):
        topview.router_generate(model="minimax/minimax-h3", mode="omni-reference-to-video", prompt="p")
    with pytest.raises(topview.TopviewError, match="first_frame_url"):
        topview.router_generate(model="topview/topview-t1", mode="image-to-video", prompt="p")
    with pytest.raises(topview.TopviewError, match="body"):
        topview.router_generate(model="acme/new-model", mode="text-to-video", prompt="p")
    router("POST", "/api/v1/models/acme/new-model/text-to-video/predictions", _task("created"))
    router("GET", "/api/v1/predictions/pred-1", _task("processing"))
    topview.router_generate(model="acme/new-model", mode="text-to-video",
                            body={"prompt": "p", "fps": 24}, wait_seconds=0)
    assert json.loads(router.calls[0].content) == {"prompt": "p", "fps": 24}


def test_router_payment_required_and_failed(router):
    router("GET", "/api/v1/predictions/pred-1",
           _task("payment_required", shortfall_usd="0.50"), _task("failed", error="NSFW"))
    pay = topview.query_task(kind="router", task_id="pred-1")["data"]
    assert pay["state"] == "payment_required" and pay["shortfall_usd"] == "0.50"
    assert "不要重复提交" in pay["hint"]
    bad = topview.query_task(kind="router", task_id="pred-1")
    assert bad["success"] is False and bad["data"]["error"] == "NSFW"


def test_router_http_errors_are_humanized_and_redacted(router):
    router("GET", "/api/v1/predictions/pred-1",
           httpx.Response(401, json={"error": {"code": "unauthorized", "message": "bad pf_test_key"}}))
    with pytest.raises(topview.TopviewError) as e:
        topview.query_task(kind="router", task_id="pred-1")
    assert "API 密钥" in str(e.value) and "pf_test_key" not in str(e.value)


def test_router_submit_retries_timeout_with_same_idempotency_key(router, monkeypatch):
    keys = []

    def flaky(req):
        if req.method == "GET":
            return httpx.Response(200, json=_task("processing"))
        keys.append(req.headers["Idempotency-Key"])
        if len(keys) == 1:
            raise httpx.ReadTimeout("slow", request=req)
        return httpx.Response(200, json=_task("created"))

    monkeypatch.setattr(topview.httpx, "Client",
                        lambda **kw: _RealClient(transport=httpx.MockTransport(flaky), **kw))
    out = topview.router_generate(model="bytedance/seedance-2.0-mini", mode="text-to-video",
                                  prompt="p", wait_seconds=0)
    # 超时后用同一个 key 重试，服务端据此去重，不会建出两个任务
    assert len(keys) == 2 and keys[0] == keys[1]
    assert out["data"]["task_id"] == "pred-1"


def test_router_upload_local_and_url(router, tmp_path):
    f = tmp_path / "cup.png"
    f.write_bytes(b"\x89PNG fake")
    asset = {"code": 200, "message": "ok",
             "data": {"id": "a1", "kind": "image", "content_type": "image/png", "size": 9,
                      "download_url": "https://media.example.com/a1.png"}}
    router("POST", "/api/v1/media/files", asset)
    router("POST", "/api/v1/media/imports", asset)
    out = topview.router_upload_file(path=str(f))
    assert out["data"]["url"] == "https://media.example.com/a1.png"
    assert b'name="kind"' in router.calls[0].content and b"PNG fake" in router.calls[0].content
    topview.router_upload_file(url="https://shop.example.com/cup.png")
    assert json.loads(router.calls[1].content) == {"kind": "image",
                                                   "url": "https://shop.example.com/cup.png"}
    with pytest.raises(topview.TopviewError, match="https"):
        topview.router_upload_file(url="http://shop.example.com/cup.png")
    with pytest.raises(topview.TopviewError, match="kind"):
        topview.router_upload_file(url="https://shop.example.com/file")


def test_each_api_reports_its_own_missing_credential(monkeypatch):
    for k in ("TOPVIEW_API_KEY", "TOPVIEW_UID", "TOPVIEW_API_PLATFORM_KEY"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(topview.TopviewError, match="router_"):
        topview.get_credit()
    with pytest.raises(topview.TopviewError, match="platform.topview.ai"):
        topview.query_task(kind="router", task_id="x")
    assert topview.REQUIRED_ENV == []
    assert set(topview.OPTIONAL_ENV) <= set(topview.ENV_DOCS)
    assert topview.router_list_models()["success"] is True
