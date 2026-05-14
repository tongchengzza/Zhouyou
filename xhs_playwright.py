"""小红书 Playwright 搜索 — drama_calendar 项目专用。

集成 MediaCrawler 的 XiaoHongShuClient，通过真实浏览器 + 住宅 IP 绕过风控。
对外只暴露 async search(keyword, page_size)。

部署前提：本机出口 IP 必须是住宅 IP，否则风控仍会拦截。
依赖：playwright, httpx, parsel, PyExecJS, tenacity, pyhumps, xhshow
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
COOKIE_FILE = PROJECT_ROOT / "小红书Cookie.txt"
MEDIA_CRAWLER_PATH = PROJECT_ROOT / "vendor" / "MediaCrawler"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


def _install_mediacrawler_path() -> None:
    """让 import 能找到 MediaCrawler 的 client.py / field.py。

    MediaCrawler 的 media_platform/xhs/__init__.py 会 eagerly import
    XiaoHongShuCrawler，那条路径会拉 redis / aiomysql / proxy_pool 等重依赖。
    我们只需要 client 和 field，所以预注册空的 package modules 跳过 __init__.py。
    """
    if str(MEDIA_CRAWLER_PATH) not in sys.path:
        sys.path.insert(0, str(MEDIA_CRAWLER_PATH))
    for pkg_name, pkg_path in [
        ("media_platform", MEDIA_CRAWLER_PATH / "media_platform"),
        ("media_platform.xhs", MEDIA_CRAWLER_PATH / "media_platform" / "xhs"),
    ]:
        if pkg_name not in sys.modules:
            mod = types.ModuleType(pkg_name)
            mod.__path__ = [str(pkg_path)]
            sys.modules[pkg_name] = mod


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


def _friendly_error(stage: str, e: Exception) -> str:
    msg = str(e)
    if "300011" in msg or "账号异常" in msg:
        return (
            f"❌ {stage}：被小红书风控拦截（300011）。\n"
            "   当前出口 IP 可能仍是机房 / VPN 出口。\n"
            "   排查：curl -s ipinfo.io | grep org"
        )
    if "登录已过期" in msg or "-100" in msg:
        return f"❌ {stage}：登录已过期，请更新 {COOKIE_FILE}"
    return f"❌ {stage}：{type(e).__name__}: {msg}"


async def search(keyword: str, page_size: int = 8) -> list[dict] | str:
    """用 Playwright + MediaCrawler 在小红书搜索。

    Returns:
        成功：list[{"title","author","likes","url"}]
        失败：str（友好错误信息，不抛异常）
    """
    if not COOKIE_FILE.exists():
        return f"❌ Cookie 文件不存在：{COOKIE_FILE}"
    try:
        cookie_dict, pw_cookies, cookie_header = _parse_cookie(
            COOKIE_FILE.read_text(encoding="utf-8")
        )
    except ValueError as e:
        return f"❌ Cookie 解析失败：{e}"

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return "❌ 缺依赖：pip install playwright && python3 -m playwright install chromium"

    if not MEDIA_CRAWLER_PATH.exists():
        return (
            f"❌ MediaCrawler 不存在：{MEDIA_CRAWLER_PATH}\n"
            "   请先 git submodule update --init --recursive"
        )
    _install_mediacrawler_path()
    try:
        from media_platform.xhs.client import XiaoHongShuClient
        from media_platform.xhs.field import SearchSortType, SearchNoteType
    except ImportError as e:
        return (
            f"❌ MediaCrawler 模块加载失败：{e}\n"
            "   缺依赖时装：pip install --user parsel PyExecJS tenacity pyhumps xhshow"
        )

    try:
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=True)
            except Exception as e:
                return (
                    f"❌ Chromium 启动失败：{e}\n"
                    "   尝试：sudo python3 -m playwright install-deps chromium"
                )

            context = await browser.new_context(user_agent=USER_AGENT)
            await context.add_cookies(pw_cookies)
            page = await context.new_page()

            try:
                await page.goto(
                    "https://www.xiaohongshu.com",
                    timeout=15000,
                    wait_until="domcontentloaded",
                )
            except Exception as e:
                await browser.close()
                return f"❌ 打开小红书首页失败：{e}"

            client = XiaoHongShuClient(
                timeout=30,
                proxy=None,
                headers={
                    "User-Agent": USER_AGENT,
                    "Cookie": cookie_header,
                    "Origin": "https://www.xiaohongshu.com",
                    "Referer": "https://www.xiaohongshu.com/",
                    "Content-Type": "application/json;charset=UTF-8",
                },
                playwright_page=page,
                cookie_dict=cookie_dict,
            )

            try:
                if not await client.pong():
                    await browser.close()
                    return (
                        "❌ Cookie 已过期或登录态失效。\n"
                        f"   重新从浏览器复制 cookie 到 {COOKIE_FILE}"
                    )
            except Exception as e:
                await browser.close()
                return _friendly_error("登录检查失败", e)

            try:
                result = await client.get_note_by_keyword(
                    keyword,
                    page=1,
                    page_size=page_size,
                    sort=SearchSortType.GENERAL,
                    note_type=SearchNoteType.ALL,
                )
            except Exception as e:
                await browser.close()
                return _friendly_error("搜索接口失败", e)

            await browser.close()
            return _format(result)
    except Exception as e:
        return _friendly_error("Playwright 异常", e)


if __name__ == "__main__":
    import asyncio
    import json

    kw = sys.argv[1] if len(sys.argv) > 1 else "低智商犯罪 VIP 追剧日历"
    size = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    out = asyncio.run(search(kw, size))
    if isinstance(out, str):
        print(out)
    else:
        print(json.dumps(out, ensure_ascii=False, indent=2))
