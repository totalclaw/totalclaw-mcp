"""目录读取、筛选、分页与多语言取值。

数据源是**仓库本身**：`registry.json` 加 `registry/servers/**`。注册表本来就是一个
Git 仓库，读接口没有必要再往数据库里抄一份——抄了就得管同步，而同步是会错的。
M2 的平台服务接管时，接口形状不变（见 docs/API.md ①）。

`registry.json` 变了会自动重载：按 mtime 判，不用重启。
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
REGISTRY_JSON = REPO_ROOT / "registry.json"
SERVERS_DIR = REPO_ROOT / "registry" / "servers"

# 支持的语言。key 是规范化后的标签，值是匹配前缀。
LANGS = ("zh-CN", "en")
DEFAULT_LANG = "zh-CN"

# 分类的展示名。分类 id 本身是英文短词，中文界面上得给个说法。
CATEGORY_LABELS: dict[str, dict[str, str]] = {
    "biz": {"zh-CN": "业务", "en": "Business"},
    "comm": {"zh-CN": "沟通协作", "en": "Communication"},
    "creative": {"zh-CN": "创意生成", "en": "Creative"},
    "data": {"zh-CN": "数据", "en": "Data"},
    "dev": {"zh-CN": "研发", "en": "Development"},
    "hr": {"zh-CN": "人力", "en": "HR"},
    "infra": {"zh-CN": "基础设施", "en": "Infrastructure"},
    "media": {"zh-CN": "媒体", "en": "Media"},
    "misc": {"zh-CN": "其它", "en": "Misc"},
    "office": {"zh-CN": "办公", "en": "Office"},
    "social": {"zh-CN": "社交", "en": "Social"},
    "web": {"zh-CN": "网页", "en": "Web"},
}

MAX_PAGE_SIZE = 100


def normalize_lang(raw: str | None) -> str:
    """把 ``lang`` 参数或 ``Accept-Language`` 归一到支持的语言。

    认不出来的一律回落默认语言，而不是报错——语言标签写错了不该让请求失败。
    """
    if not raw:
        return DEFAULT_LANG
    # Accept-Language 可能是 "zh-CN,zh;q=0.9,en;q=0.8"，取第一段
    first = raw.split(",")[0].strip().lower()
    if first.startswith("zh"):
        return "zh-CN"
    if first.startswith("en"):
        return "en"
    return DEFAULT_LANG


@dataclass(frozen=True)
class Page:
    items: list[dict[str, Any]]
    total: int
    page: int
    page_size: int
    total_pages: int


class Catalog:
    """registry.json 的只读视图，带 mtime 缓存。"""

    def __init__(self, registry_path: Path = REGISTRY_JSON,
                 servers_dir: Path = SERVERS_DIR) -> None:
        self._path = registry_path
        self._servers_dir = servers_dir
        self._lock = threading.Lock()
        self._mtime: float | None = None
        self._data: dict[str, Any] = {}

    # ── 加载 ────────────────────────────────────────────────────────────
    def _load(self) -> dict[str, Any]:
        with self._lock:
            try:
                mtime = self._path.stat().st_mtime
            except FileNotFoundError:
                raise RuntimeError(
                    f"找不到 {self._path.name}；先跑 python3 scripts/gen_registry.py"
                )
            if self._mtime != mtime:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
                self._mtime = mtime
            return self._data

    @property
    def meta(self) -> dict[str, Any]:
        d = self._load()
        return {k: v for k, v in d.items() if k != "servers"}

    def all_servers(self) -> list[dict[str, Any]]:
        return list(self._load().get("servers") or [])

    def get(self, name: str) -> dict[str, Any] | None:
        """按 name 或完整 id 取一个条目。"""
        for s in self.all_servers():
            if s.get("name") == name or s.get("id") == name:
                return s
        return None

    # ── 多语言 ──────────────────────────────────────────────────────────
    @staticmethod
    def localize(entry: dict[str, Any], lang: str) -> dict[str, Any]:
        """按语言挑展示字段，同时保留原始字段。

        挑不到就回落另一种语言而不是留空——目录里一个没有名字的条目毫无用处。
        """
        out = dict(entry)
        zh_name = entry.get("display_name") or ""
        en_name = entry.get("display_name_en") or ""
        zh_desc = entry.get("description_zh") or ""
        en_desc = entry.get("description") or ""
        slug = entry.get("name") or ""

        # 回落顺序：本语言 → 另一语言 → slug。
        # slug 必须排最后：它是 `tencent_tchouse_c` 这种机器名，
        # 比另一种语言的正经名字难读得多，不该抢在前面。
        if lang == "en":
            out["display_name_localized"] = en_name or zh_name or slug
            out["description_localized"] = en_desc or zh_desc
        else:
            out["display_name_localized"] = zh_name or en_name or slug
            out["description_localized"] = zh_desc or en_desc

        cat = entry.get("category") or ""
        out["category_label"] = CATEGORY_LABELS.get(cat, {}).get(lang, cat)
        out["lang"] = lang
        return out

    # ── 筛选 ────────────────────────────────────────────────────────────
    @staticmethod
    def _haystack(entry: dict[str, Any]) -> str:
        """搜索面：中英文名、中英文描述、标签、工具名全都算进去。

        只搜当前语言的话，中文界面搜 "github" 会搜不到——用户输入的语言
        和界面语言本来就是两回事。
        """
        parts: list[str] = [
            str(entry.get("name") or ""),
            str(entry.get("display_name") or ""),
            str(entry.get("display_name_en") or ""),
            str(entry.get("description") or ""),
            str(entry.get("description_zh") or ""),
            str(entry.get("category") or ""),
        ]
        parts.extend(str(t) for t in (entry.get("tags") or []))
        parts.extend(str(t) for t in (entry.get("tools") or []))
        return " ".join(parts).lower()

    def search(
        self,
        *,
        q: str | None = None,
        category: str | None = None,
        transport: str | None = None,
        launcher: str | None = None,
        tag: str | None = None,
        verified: bool | None = None,
        needs_no_credentials: bool | None = None,
        page: int = 1,
        page_size: int = 24,
    ) -> Page:
        rows: Iterable[dict[str, Any]] = self.all_servers()

        if q:
            needle = q.strip().lower()
            if needle:
                rows = [r for r in rows if needle in self._haystack(r)]
        if category:
            rows = [r for r in rows if r.get("category") == category]
        if transport:
            rows = [r for r in rows if transport in (r.get("transports") or [])]
        if launcher:
            rows = [r for r in rows if launcher in (r.get("launchers") or [])]
        if tag:
            rows = [r for r in rows if tag in (r.get("tags") or [])]
        if verified is not None:
            rows = [r for r in rows if bool(r.get("verified")) is verified]
        if needs_no_credentials is not None:
            def free(r: dict[str, Any]) -> bool:
                return not (r.get("requires_env") or [])
            rows = [r for r in rows if free(r) is needs_no_credentials]

        rows = sorted(rows, key=lambda r: str(r.get("name") or ""))
        total = len(rows)

        page_size = max(1, min(int(page_size or 24), MAX_PAGE_SIZE))
        total_pages = max(1, -(-total // page_size))       # 向上取整
        page = max(1, min(int(page or 1), total_pages))
        start = (page - 1) * page_size
        return Page(
            items=rows[start:start + page_size],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def categories(self, lang: str) -> list[dict[str, Any]]:
        counts: dict[str, int] = {}
        for s in self.all_servers():
            c = s.get("category")
            if c:
                counts[c] = counts.get(c, 0) + 1
        return [
            {
                "category": c,
                "label": CATEGORY_LABELS.get(c, {}).get(lang, c),
                "count": n,
            }
            for c, n in sorted(counts.items())
        ]

    # ── 单个条目的磁盘目录 ──────────────────────────────────────────────
    def server_dir(self, entry: dict[str, Any]) -> Path:
        """条目在磁盘上的目录。

        目录取自 `category` 与 `name` 两个已校验字段，不用 entry['path']——
        那是给客户端看的字符串，不该拿来拼本地路径。
        """
        cat = str(entry.get("category") or "")
        name = str(entry.get("name") or "")
        d = (self._servers_dir / cat / name).resolve()
        root = self._servers_dir.resolve()
        if not d.is_relative_to(root) or not d.is_dir():
            raise FileNotFoundError(f"{cat}/{name} 不在 registry/servers 下")
        return d
