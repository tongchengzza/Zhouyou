"""小红书 Playwright 搜索 — drama_calendar 项目专用。

启动 headless Chromium 访问搜索结果页，让浏览器自身计算 X-S 签名后发起
/api/sns/web/v1/search/notes，再用 page.expect_response 拦截响应体取结构化
数据。绕过 MediaCrawler 自构造请求被反爬剥空的问题。

对外只暴露 async search(keyword, page_size)。

部署前提：本机出口 IP 必须是住宅 IP，否则风控仍会拦截。
依赖：playwright（含 chromium 二进制和 Linux 系统库）
"""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import quote

PROJECT_ROOT = Path(__file__).parent
COOKIE_FILE = PROJECT_ROOT / "小红书Cookie.txt"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

SEARCH_API_FRAGMENT = "/api/sns/web/v1/search/notes"
PAGE_LOAD_TIMEOUT_MS = 20000
RESPONSE_WAIT_TIMEOUT_MS = 25000


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
    """启动浏览器访问搜索结果页，拦截 /search/notes 响应取结果。

    Returns:
        成功：list[{"title","author","likes","url"}]
        失败：str（友好错误信息，不抛异常）
    """
    if not COOKIE_FILE.exists():
        return f"❌ Cookie 文件不存在：{COOKIE_FILE}"
    try:
        _, pw_cookies, _ = _parse_cookie(COOKIE_FILE.read_text(encoding="utf-8"))
    except ValueError as e:
        return f"❌ Cookie 解析失败：{e}"

    try:
        from playwright.async_api import (
            async_playwright,
            TimeoutError as PWTimeout,
        )
    except ImportError:
        return "❌ 缺依赖：pip install playwright && python3 -m playwright install chromium"

    search_url = (
        f"https://www.xiaohongshu.com/search_result?"
        f"keyword={quote(keyword)}&source=web_explore_feed"
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
                async with page.expect_response(
                    lambda r: SEARCH_API_FRAGMENT in r.url and r.status == 200,
                    timeout=RESPONSE_WAIT_TIMEOUT_MS,
                ) as resp_ctx:
                    try:
                        await page.goto(
                            search_url,
                            timeout=PAGE_LOAD_TIMEOUT_MS,
                            wait_until="domcontentloaded",
                        )
                    except PWTimeout as e:
                        await browser.close()
                        return f"❌ 打开搜索页超时：{e}"
                resp = await resp_ctx.value
            except PWTimeout:
                await browser.close()
                return (
                    "❌ 搜索 API 响应超时，浏览器没发出搜索请求。\n"
                    "   可能 cookie 已失效跳到登录页，请用最新 cookie 覆盖 "
                    f"{COOKIE_FILE}"
                )
            except Exception as e:
                await browser.close()
                return _friendly_error("拦截搜索响应失败", e)

            try:
                payload = await resp.json()
            except Exception as e:
                await browser.close()
                return _friendly_error("解析搜索响应失败", e)

            await browser.close()

            if not isinstance(payload, dict):
                return "❌ 搜索响应不是合法 JSON"
            code = payload.get("code")
            if code not in (0, None):
                msg = payload.get("msg") or payload.get("message") or "未知"
                if code in (-100, 300011):
                    return _friendly_error("搜索接口失败", Exception(f"code={code} {msg}"))
                return f"❌ 搜索接口返回错误：code={code} msg={msg}"

            data = payload.get("data") or payload
            rows = _format(data)
            return rows[:page_size]
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
