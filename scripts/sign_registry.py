#!/usr/bin/env python3
"""给 registry.json 做 Ed25519 签名 / 验签（对标 totalclaw-plugins 的签名方案）。

为什么要签名：agent 侧 `plugin_hub._signature_gate` 会校验索引签名。
`files[].sha256` 只能保证「下载到的文件没被中途篡改」，但如果分发点本身被替换，
攻击者可以连索引带文件一起换掉 —— 签名把信任根从传输通道挪到了私钥上。

**私钥永远不入库。** 只从环境变量或库外文件读：

    # 一次性生成密钥对（私钥自行妥善保存，公钥随 agent 分发）
    python3 scripts/sign_registry.py --keygen --out-dir ~/.totalclaw-mcp-keys

    # 签名（CI 里把私钥放 secret）
    export MCP_REGISTRY_SIGNING_KEY="$(cat ~/.totalclaw-mcp-keys/registry-ed25519.key)"
    python3 scripts/sign_registry.py --sign

    # 验签（任何人都能做，只需公钥）
    python3 scripts/sign_registry.py --verify --pubkey registry.pub

签名文件 `registry.json.sig` 的格式与 plugins 一致：base64 编码的裸签名，
签的是 `registry.json` 的原始字节。
"""
from __future__ import annotations

import argparse
import base64
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "registry.json"
SIG = ROOT / "registry.json.sig"
PUB = ROOT / "registry.pub"
KEY_ENV = "MCP_REGISTRY_SIGNING_KEY"


def _crypto():
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519
        return serialization, ed25519
    except ImportError:
        print("需要 cryptography：pip install cryptography", file=sys.stderr)
        raise SystemExit(2)


def keygen(out_dir: Path) -> int:
    serialization, ed25519 = _crypto()
    out_dir = out_dir.expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    priv_path = out_dir / "registry-ed25519.key"
    if priv_path.exists():
        print(f"✗ {priv_path} 已存在，不覆盖（换个 --out-dir，或先手动移走）", file=sys.stderr)
        return 1

    priv = ed25519.Ed25519PrivateKey.generate()
    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    priv_path.write_bytes(priv_pem)
    priv_path.chmod(0o600)

    pub_pem = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    PUB.write_bytes(pub_pem)

    print(f"✓ 私钥：{priv_path}（权限 600，**不要提交到仓库**）")
    print(f"✓ 公钥：{PUB.relative_to(ROOT)}（可以提交，随 agent 分发）")
    print(f"\n签名前先导出私钥：\n  export {KEY_ENV}=\"$(cat {priv_path})\"")
    return 0


def _load_private(key_file: Path | None):
    serialization, _ = _crypto()
    if key_file:
        pem = key_file.expanduser().read_bytes()
    else:
        raw = os.environ.get(KEY_ENV)
        if not raw:
            print(f"✗ 没有私钥：设 {KEY_ENV} 或用 --key <私钥文件>", file=sys.stderr)
            raise SystemExit(1)
        pem = raw.encode()
    return serialization.load_pem_private_key(pem, password=None)


def sign(key_file: Path | None) -> int:
    if not REGISTRY.exists():
        print("✗ registry.json 不存在，先跑 scripts/gen_registry.py", file=sys.stderr)
        return 1
    priv = _load_private(key_file)
    data = REGISTRY.read_bytes()
    sig = priv.sign(data)
    SIG.write_text(base64.b64encode(sig).decode() + "\n", encoding="utf-8")
    print(f"✓ 已签名 {REGISTRY.name} → {SIG.name}（{len(data)} 字节，签名 {len(sig)} 字节）")
    print("  提醒：registry.json 每次重新生成后都要重新签名，否则验签会失败")
    return 0


def verify(pub_file: Path) -> int:
    serialization, _ = _crypto()
    from cryptography.exceptions import InvalidSignature

    if not SIG.exists():
        print(f"✗ {SIG.name} 不存在", file=sys.stderr)
        return 1
    pub_file = pub_file.expanduser()
    if not pub_file.exists():
        print(f"✗ 公钥不存在：{pub_file}", file=sys.stderr)
        return 1
    pub = serialization.load_pem_public_key(pub_file.read_bytes())
    sig = base64.b64decode(SIG.read_text(encoding="utf-8").strip())
    try:
        pub.verify(sig, REGISTRY.read_bytes())
    except InvalidSignature:
        print("✗ 验签失败：registry.json 与签名不匹配（内容被改过，或签名是旧的）", file=sys.stderr)
        return 1
    print(f"✓ 验签通过：{REGISTRY.name} 与 {SIG.name} 匹配")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--keygen", action="store_true", help="生成 Ed25519 密钥对")
    g.add_argument("--sign", action="store_true", help="签名 registry.json")
    g.add_argument("--verify", action="store_true", help="验签")
    ap.add_argument("--key", type=Path, help="私钥文件（默认读环境变量）")
    ap.add_argument("--pubkey", type=Path, default=PUB, help="公钥文件（验签用）")
    ap.add_argument("--out-dir", type=Path, default=Path("~/.totalclaw-mcp-keys"),
                    help="keygen 的私钥输出目录（默认库外）")
    args = ap.parse_args()

    if args.keygen:
        return keygen(args.out_dir)
    if args.sign:
        return sign(args.key)
    return verify(args.pubkey)


if __name__ == "__main__":
    raise SystemExit(main())
