"""腾讯云 TC3-HMAC-SHA256 签名。

腾讯云所有云 API（CloudBase / EdgeOne / Bugly / TCHouse / 营销投放 / SMS / OCR …）
共用这一套签名，实现一次即可覆盖整片服务。签名分四步（官方文档《签名方法 v3》）：

  1. 拼接规范请求串 CanonicalRequest
  2. 拼接待签名字符串 StringToSign（含 CredentialScope = date/service/tc3_request）
  3. 逐级 HMAC 派生签名密钥：SecretKey → date → service → "tc3_request"
  4. 组装 Authorization 头

云 API 的形状是固定的：POST /，动作放在 X-TC-Action 头里，入参是 JSON body。
所以 pack 里 path 恒为 "/"，用 tools[].headers 指定 X-TC-Action 即可。
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

ALGORITHM = "TC3-HMAC-SHA256"


class TC3Error(Exception):
    """面向用户的错误。"""

    clean = True


@dataclass(frozen=True)
class TC3Config:
    service: str                      # 如 tcb / teo / sms
    secret_id_env: str
    secret_key_env: str
    version: str                      # 如 2018-06-08
    region: str = ""                  # 部分接口不需要地域
    region_env: str | None = None     # 允许用环境变量覆盖地域

    @property
    def requires_env(self) -> tuple[str, ...]:
        return (self.secret_id_env, self.secret_key_env)


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def build_headers(cfg: TC3Config, *, host: str, action: str,
                  payload: Any, extra_headers: dict[str, str] | None = None) -> dict[str, str]:
    """算出一次调用所需的全部腾讯云头（含 Authorization）。"""
    secret_id = os.environ.get(cfg.secret_id_env, "")
    secret_key = os.environ.get(cfg.secret_key_env, "")
    missing = [e for e, v in ((cfg.secret_id_env, secret_id), (cfg.secret_key_env, secret_key)) if not v]
    if missing:
        raise TC3Error(f"缺少凭据环境变量：{', '.join(missing)}")
    if not action:
        raise TC3Error("腾讯云调用缺少 X-TC-Action（pack 的 tools[].headers 里要指定）")

    body = json.dumps(payload if payload is not None else {},
                      ensure_ascii=False, separators=(",", ":"))
    ts = int(time.time())
    date = time.strftime("%Y-%m-%d", time.gmtime(ts))
    ctype = "application/json; charset=utf-8"

    # 1) 规范请求串。云 API 恒为 POST /，无 query
    canonical_headers = f"content-type:{ctype}\nhost:{host}\nx-tc-action:{action.lower()}\n"
    signed_headers = "content-type;host;x-tc-action"
    hashed_payload = hashlib.sha256(body.encode("utf-8")).hexdigest()
    canonical_request = "\n".join(
        ["POST", "/", "", canonical_headers, signed_headers, hashed_payload]
    )

    # 2) 待签名字符串
    scope = f"{date}/{cfg.service}/tc3_request"
    string_to_sign = "\n".join([
        ALGORITHM, str(ts), scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ])

    # 3) 逐级派生签名密钥
    k_date = _sign(f"TC3{secret_key}".encode("utf-8"), date)
    k_service = _sign(k_date, cfg.service)
    k_signing = _sign(k_service, "tc3_request")
    signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    headers = {
        "Authorization": (
            f"{ALGORITHM} Credential={secret_id}/{scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        ),
        "Content-Type": ctype,
        "Host": host,
        "X-TC-Action": action,
        "X-TC-Timestamp": str(ts),
        "X-TC-Version": cfg.version,
    }
    region = os.environ.get(cfg.region_env or "", "") or cfg.region
    if region:
        headers["X-TC-Region"] = region
    if extra_headers:
        headers.update(extra_headers)
    return headers


def host_of(base_url: str) -> str:
    h = urlparse(base_url).hostname
    if not h:
        raise TC3Error(f"base_url 里取不到主机名：{base_url}")
    return h


def parse_tc3(raw: dict, where: str) -> TC3Config:
    from .spec import PackError

    for k in ("service", "version", "secret_id_env", "secret_key_env"):
        if not raw.get(k):
            raise PackError(f"{where}: auth.type=tencent_cloud 需要 {k}")
    return TC3Config(
        service=str(raw["service"]),
        version=str(raw["version"]),
        secret_id_env=str(raw["secret_id_env"]),
        secret_key_env=str(raw["secret_key_env"]),
        region=str(raw.get("region") or ""),
        region_env=str(raw["region_env"]) if raw.get("region_env") else None,
    )
