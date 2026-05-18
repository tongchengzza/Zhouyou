"""小红书 Playwright 搜索 — drama_calendar 项目专用。

启动 headless Chromium 访问搜索结果页，让浏览器自身计算 X-S 签名后发起
/api/sns/web/v1/search/notes，再用 page.expect_response 拦截响应体取结构化
数据。绕过 MediaCrawler 自构造请求被反爬剥空的问题。

对外只暴露 async search(keyword, page_size)。

部署前提：本机出口 IP 必须是住宅 IP，否则风控仍会拦截。
依赖：playwright（含 chromium 二进制和 Linux 系统库）
"""
from __future__ import annotations

import re
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
PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish"
PUBLISH_API_PATTERN = "/note_collection/post"
PUBLISH_UPLOAD_TIMEOUT_MS = 60000


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
        [{"title": str, "author": str, "likes": str, "url": str,
          "note_id": str, "images": list[str]}, ...]
        images 是 WB_DFT 高清图 URL 列表（xhscdn，无需登录态）。
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
        # xsec_token 在 item 顶层，下游 MCP get_note_content 必须带它，否则报"暂时无法浏览"
        xsec_token = item.get("xsec_token") or ""
        if note_id and xsec_token:
            url = f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec_token}&xsec_source=pc_search"
        elif note_id:
            url = f"https://www.xiaohongshu.com/explore/{note_id}"
        else:
            url = ""

        # 笔记所有图：image_list[*].info_list[image_scene=WB_DFT].url 是高清版
        images: list[str] = []
        for img in (note.get("image_list") or []):
            for info in (img.get("info_list") or []):
                if info.get("image_scene") == "WB_DFT" and info.get("url"):
                    images.append(info["url"])
                    break
        # 兜底：用 cover.url_default
        if not images:
            cover_url = (note.get("cover") or {}).get("url_default")
            if cover_url:
                images.append(cover_url)

        rows.append({
            "title": title,
            "author": author,
            "likes": likes,
            "url": url,
            "note_id": note_id,
            "images": images,
        })
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


def download_images(rows: list[dict], out_dir: str, max_per_note: int = 4) -> list[dict]:
    """把 search 返回里每条笔记的前 max_per_note 张图下载到 out_dir，转 JPG。

    Returns:
        [{"note_id","title","author","likes","local_paths":[...]}, ...]
        webp 会用 Pillow 转 JPG，文件命名 {idx:02d}_{note_id}_{i}.jpg
    """
    import urllib.request
    from io import BytesIO

    try:
        from PIL import Image
    except ImportError:
        return [{"error": "需要 Pillow: pip install pillow"}]

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []

    req_headers = {
        "User-Agent": USER_AGENT,
        "Referer": "https://www.xiaohongshu.com/",
    }

    for idx, row in enumerate(rows):
        local_paths: list[str] = []
        note_id = row.get("note_id") or f"row{idx}"
        for i, img_url in enumerate(row.get("images", [])[:max_per_note]):
            try:
                req = urllib.request.Request(img_url, headers=req_headers)
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = resp.read()
                img = Image.open(BytesIO(data)).convert("RGB")
                fname = f"{idx:02d}_{note_id}_{i}.jpg"
                fpath = str(Path(out_dir) / fname)
                img.save(fpath, "JPEG", quality=90)
                local_paths.append(fpath)
            except Exception as e:
                local_paths.append(f"ERR[{i}]: {type(e).__name__}: {e}")

        manifest.append({
            "note_id": note_id,
            "title": row.get("title", ""),
            "author": row.get("author", ""),
            "likes": row.get("likes", ""),
            "url": row.get("url", ""),
            "local_paths": local_paths,
        })

    return manifest


async def publish(title: str, desc: str, image_paths: list[str]) -> dict | str:
    """Playwright 浏览器自动化在 creator.xiaohongshu.com 发布图文笔记。

    Returns:
        成功: {"note_id": str, "url": str}
        失败: str（❌ 开头为错误，⚠️ 开头为发布成功但未拿到 note_id）
    """
    missing = [p for p in image_paths if not Path(p).exists()]
    if missing:
        return f"❌ 图片文件不存在: {missing}"
    abs_paths = [str(Path(p).resolve()) for p in image_paths]

    if not COOKIE_FILE.exists():
        return f"❌ Cookie 文件不存在：{COOKIE_FILE}"
    try:
        _, pw_cookies, _ = _parse_cookie(COOKIE_FILE.read_text(encoding="utf-8"))
    except ValueError as e:
        return f"❌ Cookie 解析失败：{e}"

    try:
        from playwright.async_api import async_playwright, TimeoutError as PWTimeout
    except ImportError:
        return "❌ 缺依赖：pip install playwright && python3 -m playwright install chromium"

    try:
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=True)
            except Exception as e:
                return (
                    f"❌ Chromium 启动失败：{e}\n"
                    "   尝试：sudo python3 -m playwright install-deps chromium"
                )

            try:
                context = await browser.new_context(user_agent=USER_AGENT)
                await context.add_cookies(pw_cookies)
                page = await context.new_page()
            except Exception as e:
                await browser.close()
                return _friendly_error("初始化浏览器上下文失败", e)

            try:
                await page.goto(
                    PUBLISH_URL,
                    timeout=PAGE_LOAD_TIMEOUT_MS,
                    wait_until="domcontentloaded",
                )
            except PWTimeout:
                await browser.close()
                return "❌ 打开发布页超时"

            if "login" in page.url or "signin" in page.url:
                await browser.close()
                return f"❌ 跳转到登录页，cookie 已失效，请更新 {COOKIE_FILE}"

            # 上传图片（必须绝对路径）
            try:
                await page.wait_for_selector('input[type="file"]', timeout=10000)
                await page.locator('input[type="file"]').first.set_input_files(abs_paths)
            except PWTimeout:
                await browser.close()
                return (
                    "❌ 上传控件未出现（10s 超时）。\n"
                    "   可能页面选择器已变更，参考 xhs-publish-via-playwright skill 排查。"
                )
            except Exception as e:
                await browser.close()
                return _friendly_error("上传图片失败", e)

            # 等待所有缩略图渲染完成（否则提交时图片未绑定）
            n = len(abs_paths)
            try:
                await page.wait_for_function(
                    f"document.querySelectorAll('.preview-item').length >= {n}",
                    timeout=PUBLISH_UPLOAD_TIMEOUT_MS,
                )
            except PWTimeout:
                await browser.close()
                return (
                    f"❌ 图片缩略图超时：等待 {n} 个 .preview-item 超过 60s。\n"
                    "   可能选择器已变更，参考 xhs-publish-via-playwright skill。"
                )

            # 填写标题
            try:
                await page.locator('input[placeholder*="标题"]').first.fill(
                    title, timeout=5000
                )
            except Exception as e:
                await browser.close()
                return _friendly_error("填写标题失败（选择器可能变更）", e)

            # 填写正文（富文本编辑器）
            try:
                editor = page.locator('[contenteditable="true"]').first
                await editor.click(timeout=5000)
                await editor.fill(desc)
            except Exception as e:
                await browser.close()
                return _friendly_error("填写正文失败（选择器可能变更）", e)

            # 点击发布并拦截 API 响应
            note_id = ""
            try:
                async with page.expect_response(
                    lambda r: PUBLISH_API_PATTERN in r.url and r.status == 200,
                    timeout=30000,
                ) as resp_ctx:
                    await page.locator('button:has-text("发布")').first.click(
                        timeout=5000
                    )
                resp = await resp_ctx.value
                payload = await resp.json()
                data = payload.get("data") or {}
                note_id = (
                    (data.get("note") or {}).get("note_id")
                    or data.get("note_id")
                    or ""
                )
            except PWTimeout:
                # 兜底：等 URL 跳转，从 /explore/{note_id} 提取
                try:
                    await page.wait_for_url("**/explore/**", timeout=15000)
                    m = re.search(r"/explore/([a-zA-Z0-9]+)", page.url)
                    if m:
                        note_id = m.group(1)
                except PWTimeout:
                    pass
            except Exception as e:
                await browser.close()
                return _friendly_error("发布请求失败", e)

            await browser.close()

            if not note_id:
                return (
                    "⚠️ 发布操作已执行，但未自动获取 note_id。\n"
                    "请登录 creator.xiaohongshu.com 确认笔记是否发布成功。\n"
                    "若持续出现，可能发布 API 路径已变更（见 xhs-publish-via-playwright skill）。"
                )

            return {
                "note_id": note_id,
                "url": f"https://www.xiaohongshu.com/explore/{note_id}",
            }

    except Exception as e:
        return _friendly_error("Playwright 发布异常", e)


if __name__ == "__main__":
    import asyncio
    import json

    args = sys.argv[1:]

    if "--publish" in args:
        pub_title = ""
        pub_desc = ""
        pub_images: list[str] = []
        i = 0
        while i < len(args):
            if args[i] == "--publish":
                i += 1
            elif args[i] == "--title" and i + 1 < len(args):
                pub_title = args[i + 1]
                i += 2
            elif args[i] == "--desc" and i + 1 < len(args):
                pub_desc = args[i + 1]
                i += 2
            elif args[i] == "--images":
                i += 1
                while i < len(args) and not args[i].startswith("--"):
                    pub_images.append(args[i])
                    i += 1
            else:
                i += 1

        if not pub_title:
            print("❌ --publish 模式需要 --title", file=sys.stderr)
            sys.exit(1)
        if not pub_images:
            print("❌ --publish 模式需要至少一张 --images", file=sys.stderr)
            sys.exit(1)

        result = asyncio.run(publish(pub_title, pub_desc, pub_images))
        if isinstance(result, str):
            print(result)
            sys.exit(1 if result.startswith("❌") else 0)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        # 搜索模式（现有逻辑不变）
        download_dir: str | None = None
        max_per_note = 4
        positional: list[str] = []
        i = 0
        while i < len(args):
            if args[i] == "--download" and i + 1 < len(args):
                download_dir = args[i + 1]
                i += 2
            elif args[i] == "--max-per-note" and i + 1 < len(args):
                max_per_note = int(args[i + 1])
                i += 2
            else:
                positional.append(args[i])
                i += 1

        kw = positional[0] if positional else "低智商犯罪 VIP 追剧日历"
        size = int(positional[1]) if len(positional) > 1 else 5

        out = asyncio.run(search(kw, size))
        if isinstance(out, str):
            print(out)
            sys.exit(1)

        if download_dir:
            manifest = download_images(out, download_dir, max_per_note=max_per_note)
            print(json.dumps(manifest, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(out, ensure_ascii=False, indent=2))
