# 小红书 Playwright 搜索 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在用户家用机器上集成 MediaCrawler 的 `XiaoHongShuClient`，通过 Playwright headless Chromium + 住宅 IP 提供高权重小红书搜索 MCP 工具，绕过当前 DMIT 机房 IP 被风控的问题。

**Architecture:** 走 git submodule 引入 MediaCrawler，绕过其 `main.py`，直接 import `XiaoHongShuClient`；写一层 ~200 行薄包装 `xhs_playwright.py` 负责 cookie 解析 / 浏览器启动 / 结果格式化；MCP 服务器新增 `search_xiaohongshu_playwright` 工具，旧工具保留作 fallback。

**Tech Stack:** Python 3.10+, Playwright (async API, headless Chromium), MediaCrawler (锁定 commit `f328ee35`), httpx, MCP FastMCP server, stdlib `unittest` 做单元测试。

---

## 关键执行说明（先读再开工）

- 本计划分两类任务：
  - **🏠 在家用机器上执行** ：Task 1-3, Task 9-11（需要住宅 IP / sudo / 真实 cookie）
  - **💻 任意机器上可执行**（包括当前 DMIT 服务器）：Task 4-8（纯代码、单元测试，不碰网络）
- DMIT 上现在可以先把 Task 4-8 全写完、commit 到仓库，然后整个仓库迁到家里继续 Task 1-3 和 Task 9-11。
- 但实际工作流推荐：**整个项目先 git 化（Task 1）、推到 GitHub 私有仓库或自己拉个 USB 拷过去，然后所有后续任务都在家用机器上做**。这样不用切换环境。
- 标注 `🏠` 的命令要求 `curl -s ipinfo.io | grep org` 结果是住宅 ISP，不是任何机房 ASN。先验证再继续。

## 文件结构

| 文件 | 责任 |
|---|---|
| `drama_calendar.py` | 不动。生成追剧日历图。 |
| `xhs_mcp.py` | 改。原 `search_xiaohongshu` / `publish_xiaohongshu` 保留；新增 `search_xiaohongshu_playwright`。 |
| `xhs_playwright.py` | 新。薄包装，对外暴露 `async search(keyword, page_size)`；内含 `_parse_cookie`、`_format`、CLI 调试入口。 |
| `tests/test_xhs_playwright.py` | 新。`unittest` 测试 `_parse_cookie` 和 `_format`。 |
| `vendor/MediaCrawler/` | 新。git submodule，锁定 commit `f328ee35b55e25e8aaeb9c847fe8b622e3f3447f`。 |
| `小红书Cookie.txt` | 不动。手动维护，不进 git。 |
| `.gitignore` | 新。屏蔽 cookie / 海报 / PNG / __pycache__。 |
| `CLAUDE.md` | 改尾部。补充新工具说明和家用机器部署指南。 |

---

## Task 1: 🏠 家用机器环境预检（gate）

**目的：** 在写任何代码之前，证明目标机器的出口 IP 是住宅 IP。这是整个方案的前提，前提不成立直接终止。

**Files:** 无（纯环境检查）

- [ ] **Step 1: 在家用机器上运行 IP 检查**

```bash
curl -s ipinfo.io | grep -E '"ip"|"org"|"hostname"'
```

Expected：`org` 字段是中国电信/联通/移动家用宽带（如 `AS4134 CHINANET-BACKBONE`、`AS9808 China Mobile`），**不是**：
- `AS906 DMIT`
- `AS16509 Amazon AWS`
- `AS45102 Alibaba`
- `AS45090 Tencent`
- `AS14061 DigitalOcean`

如果 `org` 显示任何机房 ASN，**停下**，先排查 VPN/代理是否在用。

- [ ] **Step 2: 检查 Python 版本**

```bash
python3 --version
```

Expected：`Python 3.10.x` 或更高。低于 3.10 先升级。

- [ ] **Step 3: 记录检查结果**

把 ipinfo.io 的输出贴回会话里确认通过这一关。无 commit。

---

## Task 2: 🏠 把项目拷到家用机器并 git 化

**目的：** 把 DMIT 上的 `drama_calendar/` 复制到家用机器（不带敏感和大文件），初始化 git。

**Files:**
- Create: `/path/to/drama_calendar/.gitignore`
- Create: `/path/to/drama_calendar/.git/`（git init）

- [ ] **Step 1: 在家用机器上准备工作目录**

```bash
mkdir -p ~/drama_calendar
cd ~/drama_calendar
```

后续所有命令默认在 `~/drama_calendar` 下跑。

- [ ] **Step 2: 从 DMIT 复制必要文件**

从 DMIT 服务器拷过来（用 scp/rsync/Git/U盘任选一种）：
- `drama_calendar.py`
- `xhs_mcp.py`
- `CLAUDE.md`
- `fonts/`（整个目录）
- `小红书Cookie.txt`
- `docs/superpowers/specs/2026-05-14-xhs-playwright-search-design.md`
- `docs/superpowers/plans/2026-05-14-xhs-playwright-search.md`

**不要带：** `poster_*.jpg`、`*_追剧日历_*.png`、`image*.png` —— 这些是历史输出，体积大且不需要。

示例 scp 一键命令（在家用机器上跑）：

```bash
scp -r dmit_user@dmit_host:/home/admin123/drama_calendar/{drama_calendar.py,xhs_mcp.py,CLAUDE.md,fonts,小红书Cookie.txt,docs} ~/drama_calendar/
```

- [ ] **Step 3: 创建 .gitignore**

Create file `~/drama_calendar/.gitignore`:

```
# 敏感
小红书Cookie.txt

# 输出物 / 中间产物
poster_*.jpg
*_追剧日历*.png
image*.png

# Python
__pycache__/
*.pyc
.venv/
venv/

# 编辑器
.vscode/
.idea/
```

- [ ] **Step 4: 初始化 git 并 stage 现有源码**

```bash
cd ~/drama_calendar
git init
git add .gitignore drama_calendar.py xhs_mcp.py CLAUDE.md fonts/ docs/
git status   # 确认 小红书Cookie.txt 不在 staged 列表
```

Expected：`git status` 输出里 `小红书Cookie.txt` 应该出现在 `Untracked files` 之外（被 ignore），或者完全不出现。绝对不能在 `Changes to be committed` 里。

- [ ] **Step 5: 首次 commit**

```bash
git commit -m "Initial commit: drama_calendar baseline before Playwright integration"
```

---

## Task 3: 🏠 安装 Playwright + Chromium + 系统库

**Files:** 无（环境装配）

- [ ] **Step 1: 安装 Python 包**

```bash
pip install --user playwright httpx
```

如果用 `venv` 而不是 `--user`，先 `python3 -m venv .venv && source .venv/bin/activate`。

- [ ] **Step 2: 下载 Chromium 浏览器二进制**

```bash
python3 -m playwright install chromium
```

Expected：会下载到 `~/.cache/ms-playwright/chromium-*` 和 `chromium_headless_shell-*`，大概 200MB。

- [ ] **Step 3: 安装 Chromium 系统依赖（需要 sudo）**

```bash
sudo python3 -m playwright install-deps chromium
```

Expected：apt 装一堆库（`libnss3`、`libnspr4`、`libatk1.0-0` 等）。Mac 上不需要这一步（系统库通常都有）。

- [ ] **Step 4: 烟雾测试 Chromium 能启动**

Create file `~/drama_calendar/_smoke_test.py`:

```python
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://example.com", timeout=10000)
        title = await page.title()
        await browser.close()
        print(f"OK title={title!r}")

asyncio.run(main())
```

Run:

```bash
cd ~/drama_calendar
python3 _smoke_test.py
```

Expected：`OK title='Example Domain'`。如果报 `libnspr4.so: cannot open shared object file`，回 Step 3 装系统库。

- [ ] **Step 5: 删除烟雾测试脚本**

```bash
rm _smoke_test.py
```

---

## Task 4: 加 MediaCrawler 作为锁定的 submodule

**Files:**
- Create: `.gitmodules`
- Create: `vendor/MediaCrawler/` (submodule)

- [ ] **Step 1: 加 submodule**

```bash
cd ~/drama_calendar
git submodule add https://github.com/NanmiCoder/MediaCrawler vendor/MediaCrawler
```

- [ ] **Step 2: 钉到指定 commit**

```bash
cd vendor/MediaCrawler
git checkout f328ee35b55e25e8aaeb9c847fe8b622e3f3447f
cd ../..
```

- [ ] **Step 3: 安装 MediaCrawler 自身依赖（仅 XHS 模块需要的部分）**

MediaCrawler 自带 `requirements.txt`，里面包含很多平台的依赖。我们只需 XHS 模块的运行时依赖。先尝试只装 httpx（已装）、parsel、execjs、tenacity 这几个 XHS 直接用的：

```bash
pip install --user parsel PyExecJS tenacity
```

如果后续 import 时报缺其他模块，再单独装。

- [ ] **Step 4: 验证 MediaCrawler 关键模块能 import**

Run:

```bash
cd ~/drama_calendar
python3 -c "
import sys
sys.path.insert(0, 'vendor/MediaCrawler')
from media_platform.xhs.client import XiaoHongShuClient
from media_platform.xhs.field import SearchSortType, SearchNoteType
print('MediaCrawler XHS imports OK')
print('  XiaoHongShuClient =', XiaoHongShuClient)
print('  SearchSortType.GENERAL =', SearchSortType.GENERAL)
print('  SearchNoteType.ALL =', SearchNoteType.ALL)
"
```

Expected：`MediaCrawler XHS imports OK` 和三个对象的 repr。如果报 `ModuleNotFoundError`，pip 装那个模块再试一次（最常见的是缺 `parsel` 或 `execjs`）。

- [ ] **Step 5: Commit submodule**

```bash
cd ~/drama_calendar
git add .gitmodules vendor/MediaCrawler
git commit -m "Add MediaCrawler submodule pinned to f328ee35"
```

---

## Task 5: TDD 实现 `_parse_cookie`

**Files:**
- Create: `tests/__init__.py`（空文件，让 tests 成包）
- Create: `tests/test_xhs_playwright.py`
- Create: `xhs_playwright.py`（仅 `_parse_cookie` 部分）

- [ ] **Step 1: 写失败的测试**

Create file `~/drama_calendar/tests/__init__.py` 为空文件：

```bash
mkdir -p ~/drama_calendar/tests
touch ~/drama_calendar/tests/__init__.py
```

Create file `~/drama_calendar/tests/test_xhs_playwright.py`:

```python
import unittest

from xhs_playwright import _parse_cookie


class ParseCookieTest(unittest.TestCase):
    def test_basic_three_forms(self):
        raw = "a=1; b=2; c=3"
        cookie_dict, pw_cookies, cookie_header = _parse_cookie(raw)

        self.assertEqual(cookie_dict, {"a": "1", "b": "2", "c": "3"})
        self.assertEqual(cookie_header, "a=1; b=2; c=3")
        self.assertEqual(len(pw_cookies), 3)
        self.assertEqual(
            pw_cookies[0],
            {"name": "a", "value": "1", "domain": ".xiaohongshu.com", "path": "/"},
        )

    def test_value_with_equals_sign(self):
        # 真实 cookie 里值可能包含 =（base64 之类）
        raw = "token=abc==; web_session=xyz"
        cookie_dict, _, _ = _parse_cookie(raw)
        self.assertEqual(cookie_dict["token"], "abc==")
        self.assertEqual(cookie_dict["web_session"], "xyz")

    def test_trailing_semicolon_and_whitespace(self):
        raw = "  a=1;  b=2;  "
        cookie_dict, _, _ = _parse_cookie(raw)
        self.assertEqual(cookie_dict, {"a": "1", "b": "2"})

    def test_empty_input(self):
        with self.assertRaises(ValueError):
            _parse_cookie("")
        with self.assertRaises(ValueError):
            _parse_cookie("   ")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```bash
cd ~/drama_calendar
python3 -m unittest tests.test_xhs_playwright -v
```

Expected：4 个测试全部 FAIL 或 ERROR，原因是 `ImportError: cannot import name '_parse_cookie' from 'xhs_playwright'`（因为文件还不存在）。

- [ ] **Step 3: 写最小实现**

Create file `~/drama_calendar/xhs_playwright.py`:

```python
"""小红书 Playwright 搜索 — drama_calendar 项目专用。

集成 MediaCrawler 的 XiaoHongShuClient，通过真实浏览器 + 住宅 IP 绕过风控。
对外只暴露 async search(keyword, page_size)。
"""
from __future__ import annotations


def _parse_cookie(text: str) -> tuple[dict[str, str], list[dict], str]:
    """把浏览器复制的 cookie 字符串解析成三种形式。

    Args:
        text: 原始 cookie，形如 "a=1; b=2; c=3"

    Returns:
        (cookie_dict, playwright_cookies, cookie_header)
        - cookie_dict: {"a": "1", ...}，喂 XiaoHongShuClient
        - playwright_cookies: [{name,value,domain,path}]，喂 context.add_cookies()
        - cookie_header: 原始字符串规整版，喂 HTTP headers

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
```

- [ ] **Step 4: 跑测试确认通过**

Run:

```bash
cd ~/drama_calendar
python3 -m unittest tests.test_xhs_playwright -v
```

Expected：`OK`，4 tests passed。

- [ ] **Step 5: Commit**

```bash
git add xhs_playwright.py tests/
git commit -m "feat(xhs): add _parse_cookie with three output forms"
```

---

## Task 6: TDD 实现 `_format`

**Files:**
- Modify: `tests/test_xhs_playwright.py` (append)
- Modify: `xhs_playwright.py` (append)

- [ ] **Step 1: 追加失败的测试**

在 `~/drama_calendar/tests/test_xhs_playwright.py` 末尾追加（在 `if __name__` 之前）：

```python


class FormatTest(unittest.TestCase):
    def test_extracts_fields_from_api_response(self):
        from xhs_playwright import _format

        api_response = {
            "items": [
                {
                    "id": "abc123",
                    "note_card": {
                        "display_title": "低智商犯罪 VIP 更新日历",
                        "user": {"nickname": "追剧博主小红"},
                        "interact_info": {"liked_count": "1.2万"},
                    },
                },
                {
                    "note_id": "def456",
                    "title": "fallback 标题字段",
                    "user": {"nickname": "另一个博主"},
                    "interact_info": {"liked_count": "234"},
                },
            ]
        }
        rows = _format(api_response)
        self.assertEqual(len(rows), 2)

        self.assertEqual(rows[0]["title"], "低智商犯罪 VIP 更新日历")
        self.assertEqual(rows[0]["author"], "追剧博主小红")
        self.assertEqual(rows[0]["likes"], "1.2万")
        self.assertEqual(rows[0]["url"], "https://www.xiaohongshu.com/explore/abc123")

        self.assertEqual(rows[1]["title"], "fallback 标题字段")
        self.assertEqual(rows[1]["url"], "https://www.xiaohongshu.com/explore/def456")

    def test_empty_items(self):
        from xhs_playwright import _format
        self.assertEqual(_format({"items": []}), [])
        self.assertEqual(_format({}), [])
        self.assertEqual(_format(None), [])

    def test_missing_optional_fields(self):
        from xhs_playwright import _format
        api_response = {"items": [{"id": "x", "note_card": {}}]}
        rows = _format(api_response)
        self.assertEqual(rows[0]["title"], "（无标题）")
        self.assertEqual(rows[0]["author"], "未知")
        self.assertEqual(rows[0]["likes"], "?")
```

- [ ] **Step 2: 跑测试确认 3 个新测试失败**

Run:

```bash
cd ~/drama_calendar
python3 -m unittest tests.test_xhs_playwright -v
```

Expected：原 4 个 PASS，新 3 个 FAIL 报 `cannot import name '_format'`。

- [ ] **Step 3: 在 `xhs_playwright.py` 末尾追加实现**

```python


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
```

- [ ] **Step 4: 跑测试确认全部通过**

Run:

```bash
cd ~/drama_calendar
python3 -m unittest tests.test_xhs_playwright -v
```

Expected：`OK`，7 tests passed。

- [ ] **Step 5: Commit**

```bash
git add xhs_playwright.py tests/test_xhs_playwright.py
git commit -m "feat(xhs): add _format to flatten search API response"
```

---

## Task 7: 实现 `async search()` + CLI 入口

> **TDD 注：** 这一步包含真实 Playwright + 真实网络 + 真实 cookie，不写自动化单元测试（会泄漏 cookie / 触发风控 / 不稳定）。我们用**手动 CLI 烟雾测试**验证。这是合理偏离 TDD 的场景：与外部活体服务集成的边界，自动测试价值低、风险高。

**Files:**
- Modify: `xhs_playwright.py`（追加 `search`、`_friendly_error`、`__main__` 入口）

- [ ] **Step 1: 在 `xhs_playwright.py` 顶部 imports 处追加**

把文件开头的 import 区改成：

```python
"""小红书 Playwright 搜索 — drama_calendar 项目专用。

集成 MediaCrawler 的 XiaoHongShuClient，通过真实浏览器 + 住宅 IP 绕过风控。
对外只暴露 async search(keyword, page_size)。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
COOKIE_FILE = PROJECT_ROOT / "小红书Cookie.txt"
MEDIA_CRAWLER_PATH = PROJECT_ROOT / "vendor" / "MediaCrawler"
if str(MEDIA_CRAWLER_PATH) not in sys.path:
    sys.path.insert(0, str(MEDIA_CRAWLER_PATH))

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
```

（保留下面已有的 `_parse_cookie` 和 `_format`，不动。）

- [ ] **Step 2: 在 `xhs_playwright.py` 末尾追加 `search` 和 CLI 入口**

```python


async def search(keyword: str, page_size: int = 8) -> list[dict] | str:
    """用 Playwright + MediaCrawler 在小红书搜索。

    Returns:
        成功：list[{"title","author","likes","url"}]
        失败：str（友好错误信息，不抛异常）
    """
    # 1. cookie 校验
    if not COOKIE_FILE.exists():
        return f"❌ Cookie 文件不存在：{COOKIE_FILE}"
    try:
        cookie_dict, pw_cookies, cookie_header = _parse_cookie(
            COOKIE_FILE.read_text(encoding="utf-8")
        )
    except ValueError as e:
        return f"❌ Cookie 解析失败：{e}"

    # 2. import Playwright 和 MediaCrawler（运行时校验依赖）
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return "❌ 缺依赖：pip install playwright && python3 -m playwright install chromium"
    try:
        from media_platform.xhs.client import XiaoHongShuClient
        from media_platform.xhs.field import SearchSortType, SearchNoteType
    except ImportError as e:
        return (
            f"❌ MediaCrawler 模块加载失败：{e}\n"
            f"   检查 vendor/MediaCrawler 是否存在、submodule 是否 init"
        )

    # 3. 启动浏览器
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
                    "https://www.xiaohongshu.com", timeout=15000, wait_until="domcontentloaded"
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
```

- [ ] **Step 3: 重跑单元测试，确认不被破坏**

Run:

```bash
cd ~/drama_calendar
python3 -m unittest tests.test_xhs_playwright -v
```

Expected：`OK`，7 tests passed（新增 imports 不应影响原测试）。

- [ ] **Step 4: 🏠 真实烟雾测试（需要住宅 IP + 有效 cookie）**

Run：

```bash
cd ~/drama_calendar
python3 xhs_playwright.py "低智商犯罪 VIP" 5
```

Expected：JSON 数组打印出来，至少 1 条结果，每条有 `title/author/likes/url` 字段。

如果输出是 `❌` 开头的错误：
- "Cookie 已过期" → 重新从浏览器复制 cookie 到 `小红书Cookie.txt`
- "Chromium 启动失败" → 回 Task 3 Step 3 装系统库
- "300011" → 检查 `curl ipinfo.io`，IP 不对就退回 Task 1 排查
- "MediaCrawler 模块加载失败：缺 XXX" → `pip install --user XXX`，回 Step 3 重测

- [ ] **Step 5: Commit**

```bash
git add xhs_playwright.py
git commit -m "feat(xhs): add async search() with Playwright + MediaCrawler"
```

---

## Task 8: 把新工具挂到 MCP 服务器

**Files:**
- Modify: `xhs_mcp.py`

- [ ] **Step 1: 在 `xhs_mcp.py` 顶部 imports 处追加**

打开 `~/drama_calendar/xhs_mcp.py`，在文件顶部 `from xhs.help import sign` 之后追加：

```python
import asyncio
import xhs_playwright
```

- [ ] **Step 2: 在 `search_xiaohongshu` 工具下方追加新工具**

在 `@mcp.tool() def publish_xiaohongshu(...)` **之前**插入：

```python
@mcp.tool()
def search_xiaohongshu_playwright(keyword: str, page_size: int = 8) -> str:
    """[推荐] 用 Playwright 真实浏览器搜索小红书，绕过机房 IP 风控。

    需要部署在家庭住宅网络的机器上才有效。比 search_xiaohongshu 权重更高、覆盖更全。

    Args:
        keyword: 搜索关键词，如「低智商犯罪 追剧日历 VIP」
        page_size: 返回条数，默认 8
    """
    result = asyncio.run(xhs_playwright.search(keyword, page_size))
    if isinstance(result, str):
        return result  # 友好错误信息原样返回
    if not result:
        return f"未找到「{keyword}」相关笔记。"

    lines = [f"小红书 Playwright 搜索「{keyword}」，共 {len(result)} 条：\n"]
    for i, row in enumerate(result, 1):
        lines.append(f"{i}. 【{row['title']}】 作者:{row['author']} 点赞:{row['likes']}")
        if row["url"]:
            lines.append(f"   {row['url']}")
    return "\n".join(lines)
```

- [ ] **Step 3: 不改 `search_xiaohongshu` 和 `publish_xiaohongshu`**

确认原 `search_xiaohongshu`（基于 xhs lib HTTP API）和 `publish_xiaohongshu` 完全不动 —— 它们是 fallback 通道。

- [ ] **Step 4: 静态语法检查**

Run：

```bash
cd ~/drama_calendar
python3 -c "import xhs_mcp; print('xhs_mcp imports OK')"
```

Expected：`xhs_mcp imports OK`。

- [ ] **Step 5: 🏠 通过 MCP 工具的命令行（FastMCP 自带）调一次**

FastMCP 工具一般通过 MCP 客户端调用。最简单的端到端验证：直接调用工具函数（绕过 MCP 协议）：

```bash
cd ~/drama_calendar
python3 -c "
from xhs_mcp import search_xiaohongshu_playwright
print(search_xiaohongshu_playwright('低智商犯罪 VIP', 3))
"
```

Expected：人类可读的多行字符串，列出 3 条小红书笔记。

- [ ] **Step 6: Commit**

```bash
git add xhs_mcp.py
git commit -m "feat(mcp): add search_xiaohongshu_playwright tool"
```

---

## Task 9: 更新 CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: 在「小红书 MCP 工具」节中替换 `search_xiaohongshu` 段，并新增 Playwright 工具段**

打开 `~/drama_calendar/CLAUDE.md`，找到这一段：

```markdown
### `search_xiaohongshu` — 查询数据
```

把它替换为：

```markdown
### `search_xiaohongshu_playwright` — 查询数据【推荐，仅家用机器可用】
```
keyword: "{剧名} 追剧日历 VIP SVIP 更新"
keyword: "{剧名} VIP 几集 更新时间"
```
- 用 Playwright 真实浏览器 + 住宅 IP 搜，比 WebSearch 准
- 返回标题、作者、点赞数、笔记链接
- **优先点赞数高的博主笔记**，实测准确率高
- 必须部署在家庭住宅网络环境，机房 IP 一样会被风控

### `search_xiaohongshu` — 查询数据【fallback】
```
keyword: "{剧名} 追剧日历 VIP SVIP 更新"
```
- 基于 xhs Python 库的 HTTP API + 本地签名
- 当前 DMIT 机房 IP 下被小红书风控拦截，返回 300011 错误
- 仅在家用机器上的 Playwright 工具不可用时退而求其次，或仍走 WebSearch
```

- [ ] **Step 2: 在文件末尾追加部署说明**

把下面这段追加到 CLAUDE.md 最后：

```markdown

---

## 家用机器部署指南（Playwright 搜索专用）

`search_xiaohongshu_playwright` 工具必须部署在家庭住宅网络环境，否则 IP 仍会被风控。

### 一次性安装

```bash
# 1. 复制项目（不带 cookie 和大文件）
git clone <仓库地址> ~/drama_calendar
cd ~/drama_calendar
git submodule update --init --recursive
cd vendor/MediaCrawler && git checkout f328ee35b55e25e8aaeb9c847fe8b622e3f3447f && cd ../..

# 2. 装 Python 依赖
pip install --user playwright httpx parsel PyExecJS tenacity
python3 -m playwright install chromium
sudo python3 -m playwright install-deps chromium   # Linux 需要，Mac 不需要

# 3. 把 小红书Cookie.txt 拷到项目根（不进 git）
cp /path/to/your/小红书Cookie.txt ./

# 4. 验证出口 IP 是住宅
curl -s ipinfo.io | grep -E '"ip"|"org"'
# org 不能是 DMIT/AWS/Alibaba/Tencent 等机房 ASN

# 5. 烟雾测试
python3 xhs_playwright.py "低智商犯罪 VIP" 3
```

### Cookie 失效时

跟原来一样，在浏览器 F12 复制 cookie 字符串覆盖 `小红书Cookie.txt`。

### License 说明

`vendor/MediaCrawler/` 采用「非商业学习使用许可证」，本项目当前作为个人追剧群引流的学习用途。如未来涉及商业化，需重新评估合规性。
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add Playwright search workflow and deployment guide"
```

---

## Task 10: 🏠 端到端验证清单

**目的：** 集中跑完所有验收项，把结果记录到 PR 或会话里。

**Files:** 无

- [ ] **Step 1: 出口 IP 是住宅**

Run:

```bash
curl -s ipinfo.io | grep -E '"ip"|"org"|"hostname"'
```

Expected：`org` 是住宅 ISP，不是机房 ASN。

- [ ] **Step 2: 单元测试全通过**

Run:

```bash
cd ~/drama_calendar
python3 -m unittest tests.test_xhs_playwright -v
```

Expected：`OK`，7 tests。

- [ ] **Step 3: CLI 烟雾测试**

Run:

```bash
python3 xhs_playwright.py "低智商犯罪 VIP" 5
```

Expected：JSON 数组，≥1 条结果。

- [ ] **Step 4: MCP 工具端到端**

Run:

```bash
python3 -c "
from xhs_mcp import search_xiaohongshu_playwright
print(search_xiaohongshu_playwright('黑夜告白 VIP 更新', 3))
"
```

Expected：人类可读的多行字符串。

- [ ] **Step 5: 错误路径手测 —— cookie 失效**

```bash
mv 小红书Cookie.txt 小红书Cookie.txt.bak
echo "fake=invalid; cookie=string" > 小红书Cookie.txt
python3 xhs_playwright.py "测试" 1
# 看到 "❌ Cookie 已过期或登录态失效" 之类的友好提示，不应该是 traceback
mv 小红书Cookie.txt.bak 小红书Cookie.txt
```

Expected：友好错误，不是 Python traceback。

- [ ] **Step 6: 错误路径手测 —— cookie 文件不存在**

```bash
mv 小红书Cookie.txt 小红书Cookie.txt.bak
python3 xhs_playwright.py "测试" 1
# 看到 "❌ Cookie 文件不存在" 提示
mv 小红书Cookie.txt.bak 小红书Cookie.txt
```

Expected：友好错误，明确指出 cookie 文件路径。

- [ ] **Step 7: 旧工具未被破坏**

```bash
python3 -c "
from xhs_mcp import search_xiaohongshu
print(search_xiaohongshu('低智商犯罪', 2))
"
```

Expected：要么返回正常结果（家用机器上 xhs lib 也能用），要么返回原有的 300011 / 登录过期错误提示，**不应该报 ImportError 或 NameError**。

- [ ] **Step 8: 旧出图脚本未被破坏**

```bash
python3 drama_calendar.py
```

Expected：生成当前 `DRAMA` 配置对应的 PNG 文件，正常退出。（如果 `DRAMA["poster_path"]` 指向的海报文件不在家用机器上，先 scp 过来或临时改个本地存在的海报。）

---

## Task 11: 最终 commit + push

**Files:** 无

- [ ] **Step 1: 确认无未提交改动**

```bash
cd ~/drama_calendar
git status
```

Expected：`nothing to commit, working tree clean`。

- [ ] **Step 2: 看 commit 历史**

```bash
git log --oneline
```

Expected：~7-8 个 commit，按顺序：
- Initial commit
- Add MediaCrawler submodule
- feat(xhs): add _parse_cookie
- feat(xhs): add _format
- feat(xhs): add async search()
- feat(mcp): add search_xiaohongshu_playwright tool
- docs: add Playwright search workflow

- [ ] **Step 3: 推到远端（如果有）**

```bash
git remote add origin <你的仓库地址>
git push -u origin main
```

或暂时不推也行 —— 本地 git 历史已经完整。

---

## 备注

- 实施过程中如果遇到 MediaCrawler 内部 import 链报错（如缺 `tools.utils` 或 `base.base_crawler`），最简单的解法是把那些模块也 `pip install --user` 或者临时塞个 stub。具体错误请贴回会话里再处理。
- `xhs_playwright.py` 没有用 `playwright-stealth`，理由是 MediaCrawler 内部已通过签名 + cookie 验证身份，住宅 IP 已经是最强信号。如果未来被检测，再加 stealth。
- 整个项目跟 DMIT 上的旧副本应当**并存而非互相替代**：DMIT 留着方便 SSH 进去查日志 / 远程出图；家用机器上跑 Playwright 搜索。如果想完全迁走，DMIT 上 `rm -rf drama_calendar` 即可。
