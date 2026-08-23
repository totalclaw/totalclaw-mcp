"""按条目打包下载，以及单文件取用。

两条路都必须挡住路径穿越：URL 里的 `path` 是外部输入，`../` 或绝对路径能把
读取范围拉到仓库外面去。这里统一 resolve 之后判是不是还在条目目录内，
symlink 也一并挡掉（resolve 会跟随软链，跟出去了就不在目录内了）。
"""
from __future__ import annotations

import hashlib
import io
import tarfile
from pathlib import Path

# 打包时跳过的东西：探测缓存与临时产物没有分发价值，也不该进 sha256 校验面
SKIP_NAMES = {".DS_Store", "__pycache__", ".git"}


def safe_join(base: Path, rel: str) -> Path:
    """把相对路径接到 base 上，接不出去就抛。"""
    if not rel or rel.startswith("/") or "\x00" in rel:
        raise ValueError("非法路径")
    base = base.resolve()
    target = (base / rel).resolve()
    if not target.is_relative_to(base):
        raise ValueError("路径越出条目目录")
    if not target.is_file():
        raise FileNotFoundError(rel)
    return target


def iter_files(server_dir: Path) -> list[Path]:
    """条目目录下要分发的文件，排序后返回（排序保证打包可复现）。"""
    out: list[Path] = []
    for p in sorted(server_dir.rglob("*")):
        if not p.is_file():
            continue
        if any(part in SKIP_NAMES for part in p.parts):
            continue
        out.append(p)
    return out


def make_tar_gz(server_dir: Path, name: str) -> bytes:
    """打成 tar.gz。

    时间戳与属主一律归零：同样的内容要打出同样的字节，否则每次下载 ETag 都变，
    缓存和「有没有更新」的判断都失效。
    """
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz", format=tarfile.PAX_FORMAT,
                      compresslevel=9) as tar:
        for p in iter_files(server_dir):
            rel = p.relative_to(server_dir)
            info = tarfile.TarInfo(name=f"{name}/{rel.as_posix()}")
            data = p.read_bytes()
            info.size = len(data)
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mode = 0o644
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_digests(server_dir: Path) -> list[dict[str, object]]:
    """逐文件 sha256，形状与 registry.json 的 files[] 一致，供客户端逐条校验。"""
    out: list[dict[str, object]] = []
    for p in iter_files(server_dir):
        data = p.read_bytes()
        out.append({
            "path": p.relative_to(server_dir).as_posix(),
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
        })
    return out
