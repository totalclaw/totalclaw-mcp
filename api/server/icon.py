"""条目图标：有就发真的，没有就发一个确定性的字母块。

厂商 logo 有商标，不自造 —— 所以这里**不生成假 logo**，生成的是一个字母块：
首字 + 按分类取色。它一眼就能看出不是官方图标，但比空白强：115 个条目里目前
一个都没有自带图标，界面上会是一排空框，用户分不清哪个是哪个。

真图标什么时候有：把 `icon.svg` 或 `icon.png` 放进条目目录即可，索引会带上
（gen_registry 的 `icon` 字段），这里也会优先发它。响应头 `X-Icon-Source`
区分 `file` 与 `generated`，客户端要区别对待时有据可依。
"""
from __future__ import annotations

import unicodedata

# 分类底色。取自同一套色相环，饱和度压低 —— 这是背景块，不该比条目名更抢眼。
CATEGORY_COLORS: dict[str, str] = {
    "biz":      "#3B6FB6",
    "comm":     "#2E8B7A",
    "creative": "#B5539C",
    "data":     "#2F7D8C",
    "dev":      "#5A5FBF",
    "hr":       "#9A6B3F",
    "infra":    "#5C6B7A",
    "media":    "#C0603A",
    "misc":     "#6E6E6E",
    "office":   "#4A7BA7",
    "social":   "#A84B6B",
    "web":      "#3F8F5A",
}
FALLBACK_COLOR = "#6E6E6E"


def initial(display_name: str, slug: str = "") -> str:
    """取用来显示的首字。

    拉丁字母取大写首字母；中文取第一个汉字（不做转拼音——转错了比不转更难认）。
    名字以标点或空白开头时跳过，那种字符做图标认不出是谁。
    """
    for ch in (display_name or slug or "?"):
        cat = unicodedata.category(ch)
        if cat[0] in ("L", "N"):          # 字母或数字
            return ch.upper()
    return "?"


def shade_delta(name: str) -> int:
    """明度微调量。

    刻意用「字符码求和」而不是 sha256：qiye-app 那边要用同一套算法在本地画同样的
    块（它走 qiye_api 拿目录，不请求这个接口），字符码求和两边都能一行写对，
    换成 sha256 就得在 TS 里再引一个哈希，两边算出不一样的颜色只是时间问题。
    """
    return (sum(ord(c) for c in name) % 25) - 12          # ±12：够区分，又不会糊掉字


def _shade(hex_color: str, name: str) -> str:
    """同分类内按名字微调明度，相邻两块不至于糊成一片。"""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    delta = shade_delta(name)
    r, g, b = (max(0, min(255, c + delta)) for c in (r, g, b))
    return f"#{r:02X}{g:02X}{b:02X}"


def monogram_svg(display_name: str, slug: str, category: str, size: int = 128) -> str:
    """确定性的字母块 SVG。同样的入参永远出同样的字节（ETag 才稳）。"""
    bg = _shade(CATEGORY_COLORS.get(category, FALLBACK_COLOR), slug or display_name)
    ch = initial(display_name, slug)
    # 汉字比拉丁字母占得满，字号要小一档，否则会顶到圆角外面
    font_size = size * (0.44 if ord(ch) > 0x2E80 else 0.52)
    safe = ch.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
        f'width="{size}" height="{size}" role="img" aria-label="{safe}">'
        f'<rect width="{size}" height="{size}" rx="{size * 0.22:.0f}" fill="{bg}"/>'
        f'<text x="50%" y="50%" dy="0.35em" text-anchor="middle" fill="#FFFFFF" '
        f'font-family="-apple-system,BlinkMacSystemFont,\'PingFang SC\','
        f'\'Microsoft YaHei\',\'Segoe UI\',sans-serif" '
        f'font-size="{font_size:.1f}" font-weight="600">{safe}</text>'
        f'</svg>'
    )
