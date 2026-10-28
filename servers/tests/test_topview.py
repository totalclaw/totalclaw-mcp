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
    api("POST", "/v1/voice/text2voice/task/submit", _ok({"taskId": "t5"}))
    api("GET", "/v1/voice/text2voice/task/query", _ok({"taskId": "t5", "status": "running"}))
    out = topview.create_speech(text="hi", voice_id="v1", wait_seconds=0)
    assert out["data"]["task_id"] == "t5" and out["data"]["state"] == "running"


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
