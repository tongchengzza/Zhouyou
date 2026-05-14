"""小红书 Playwright 搜索 — drama_calendar 项目专用。

集成 MediaCrawler 的 XiaoHongShuClient，通过真实浏览器 + 住宅 IP 绕过风控。
对外只暴露 async search(keyword, page_size)。
"""
from __future__ import annotations


def _parse_cookie(text: str) -> tuple[dict[str, str], list[dict], str]:
    """把浏览器复制的 cookie 字符串解析成三种形式。

    Returns:
        (cookie_dict, playwright_cookies, cookie_header)
        - cookie_dict: {"a": "1", ...}，喂 XiaoHongShuClient
        - playwright_cookies: [{name,value,domain,path}]，喂 context.add_cookies()
        - cookie_header: 规整后的 "a=1; b=2" 字符串，喂 HTTP headers

    Raises:
        ValueError: 输入为空或纯空白
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("cookie 为空")

    cookie_dict: dict[str, str] = {}
    for part in text.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, _, v = part.partition("=")
        cookie_dict[k.strip()] = v.strip()

    playwright_cookies = [
        {"name": k, "value": v, "domain": ".xiaohongshu.com", "path": "/"}
        for k, v in cookie_dict.items()
    ]
    cookie_header = "; ".join(f"{k}={v}" for k, v in cookie_dict.items())
    return cookie_dict, playwright_cookies, cookie_header


def _format(result: dict | None) -> list[dict]:
    """把 XiaoHongShuClient.get_note_by_keyword 的原始返回拍平成展示行。

    Returns:
        [{"title": str, "author": str, "likes": str, "url": str}, ...]
    """
    if not result or not isinstance(result, dict):
        return []
    items = result.get("items") or []

    rows: list[dict] = []
    for item in items:
        note = item.get("note_card") or item
        title = note.get("display_title") or note.get("title") or "（无标题）"
        author = (note.get("user") or {}).get("nickname") or "未知"
        likes = (note.get("interact_info") or {}).get("liked_count")
        likes = str(likes) if likes is not None else "?"
        note_id = item.get("id") or note.get("note_id") or note.get("id") or ""
        url = f"https://www.xiaohongshu.com/explore/{note_id}" if note_id else ""
        rows.append({"title": title, "author": author, "likes": likes, "url": url})
    return rows
