# 小红书 Playwright 搜索集成 — 设计文档

- 作者：drama_calendar 项目
- 日期：2026-05-14
- 状态：待评审 / 待实施

## 目标

在 `drama_calendar` 现有的「搜索数据」阶段补一个高权重的小红书搜索通道，使用 Playwright 真实浏览器 + WSL2 本地住宅 IP 绕过当前 `xhs` 库 HTTP API 模式下被风控拦截（错误 300011）的问题，让 Claude 能直接搜到博主实测的 VIP/SVIP 追剧日历。

**非目标：** 不动 `publish_xiaohongshu`（发布走老路），不动 `drama_calendar.py`（出图逻辑），不引入数据库/Redis/代理池。

## 背景

- 现有 `xhs_mcp.py` 用 `ReaJason/xhs` Python 库，HTTP API 调用 + 本地签名。
- 当前服务器（DMIT Cloud Services, Los Angeles）出口是机房 IP，被小红书风控拦截（错误 300011）。
- 2026-05-14 实测：即使在本机（系统报告 WSL2 内核）跑 `curl ipinfo.io`，出口 IP 依然是 `host-by.dmit.com / AS906 DMIT Cloud Services` —— 也就是说，本机不是"真正的家用 WSL2"，而是 DMIT 上的 Linux 虚拟机。Playwright 解决浏览器指纹检测，但解决不了 IP 检测，所以在这台机器上跑 Playwright 不能绕过风控。
- 现状只能退化到 WebSearch 搜小红书帖子，准确率与覆盖度都不如官方搜索接口。

## 部署前提

**本方案必须部署在用户家庭住宅网络环境下的机器上**（家用 PC 的 WSL2 / 家用 Linux / 家用 Mac 任一），出口 IP 必须实测为住宅 IP（如电信/联通/移动家用宽带），不是任何机房 IP。

判定方式：`curl -s ipinfo.io | grep -E '"ip"|"org"|"hostname"'` 的 `org` 字段是住宅 ISP（中国电信/联通/移动等），不是 `AS906 DMIT / AS16509 AWS / AS45102 Alibaba / AS45090 Tencent` 等机房 ASN。

当前 DMIT 服务器上保留旧的 `search_xiaohongshu`（WebSearch fallback）和 `publish_xiaohongshu`（手动浏览器发布兜底）作为应急。

## 决策

走 **集成 MediaCrawler（NanmiCoder/MediaCrawler）** 路线，理由：
- 上游已经处理好小红书的 `x-s` / `x-t` 签名（`sign_with_xhshow()`），不用我们维护。
- 客户端类 `XiaoHongShuClient` 接口干净：传 `cookie_dict + playwright_page`，调 `get_note_by_keyword(keyword, page, page_size, sort, note_type)`。
- 不强依赖 Redis/MySQL，可禁用持久化。
- License 是「非商业学习使用许可证」，与本项目（个人追剧群引流，非商业）相容；若未来商业化需重新评估。

否决的备选：
- **自写 Playwright + DOM 抽取**：签名/接口变动维护成本高。
- **Playwright 仅抓 cookie+签名，HTTP 继续走 xhs 库**：xhs 库与小红书更新不同步是历史风险源，不解决根本问题。

## 架构

```
WSL2 (本地 IP，无代理)
 │
 ├─ drama_calendar.py        ← 生成图，不动
 │
 ├─ xhs_mcp.py               ← MCP server，加一个工具
 │     ├─ search_xiaohongshu_playwright(keyword, page_size)  【新】
 │     ├─ search_xiaohongshu(keyword, page_size)             【旧, 保留作 fallback】
 │     └─ publish_xiaohongshu(...)                           【旧, 不动】
 │
 ├─ xhs_playwright.py        ← 新文件 ~200 行
 │     ├─ 读 小红书Cookie.txt → cookie_dict / cookie_str / playwright cookies
 │     ├─ 启动 Playwright headless Chromium
 │     ├─ 注入 cookie 到 context
 │     ├─ 调用 XiaoHongShuClient.get_note_by_keyword()
 │     └─ 格式化返回 [{title, author, likes, url}, ...]
 │
 └─ vendor/MediaCrawler/     ← git submodule (commit 锁定)
       └─ media_platform/xhs/  ← 直接 import client/field 模块，不走 main.py
```

绕开 MediaCrawler 的 `main.py`（强依赖全局 config 与 CLI 参数），直接用 `XiaoHongShuClient`。`XiaoHongShuClient` 本身只读构造器参数，可独立使用。

## 组件

### vendor/MediaCrawler/（git submodule）
- 锁定到 commit `f328ee35b55e25e8aaeb9c847fe8b622e3f3447f`（2026-05-14 HEAD）。
- 通过 `sys.path.insert(0, "<repo>/vendor/MediaCrawler")` 加进 Python 路径。
- import 范围只限：
  - `media_platform.xhs.client.XiaoHongShuClient`
  - `media_platform.xhs.field.SearchSortType, SearchNoteType`

### xhs_playwright.py（新）
对外暴露唯一 async 入口：

```python
async def search(keyword: str, page_size: int = 8) -> list[dict] | str:
    """返回结构化结果 list，或一个友好的错误字符串。"""
```

内部分工：
- `_parse_cookie(text) -> (cookie_dict, playwright_cookies, cookie_header)` —— 一次解析，三种形式派生
- `_format(items) -> list[dict]` —— 抽取 title / author / likes / url
- 启动/关闭 Playwright，注入 cookie，实例化 client，调用 `get_note_by_keyword`

文件末尾保留命令行调试入口：`python3 xhs_playwright.py "关键词"` 直接 print JSON。

### xhs_mcp.py（改）
新增 MCP 工具：

```python
@mcp.tool()
def search_xiaohongshu_playwright(keyword: str, page_size: int = 8) -> str:
    """用 Playwright 真实浏览器搜索小红书（绕过 IP 风控）。返回标题/作者/点赞数。"""
    result = asyncio.run(xhs_playwright.search(keyword, page_size))
    if isinstance(result, str):
        return result  # 错误信息原样返回
    return _format_for_claude(result)  # 沿用旧工具的展示格式
```

原 `search_xiaohongshu`、`publish_xiaohongshu` 完全不动，作为 fallback / 发布通道。

### Cookie 文件
`小红书Cookie.txt` 复用现有文件，不改格式。`_parse_cookie` 把 `a=1; b=2; c=3` 字符串派生出三种形式：
- `cookie_dict = {"a":"1","b":"2","c":"3"}` —— 喂 `XiaoHongShuClient`
- `playwright_cookies = [{"name":"a","value":"1","domain":".xiaohongshu.com","path":"/"}, ...]` —— 喂 `context.add_cookies()`
- `cookie_header = "a=1; b=2; c=3"` —— 放进 HTTP headers

## 数据流

1. Claude → MCP `search_xiaohongshu_playwright("低智商犯罪 VIP 追剧日历")`
2. `xhs_mcp.py` → `asyncio.run(xhs_playwright.search(...))`
3. 解析 cookie 三件套
4. `async_playwright()` → `chromium.launch(headless=True)` → `new_context()` → `add_cookies()` → `new_page()` → `goto("https://www.xiaohongshu.com")`
5. 构造 `XiaoHongShuClient(timeout=30, proxy=None, headers={UA, Cookie}, playwright_page=page, cookie_dict=cookie_dict)`
6. （可选）`client.pong()` 校验登录态
7. `client.get_note_by_keyword(keyword, page=1, page_size=page_size, sort=SearchSortType.GENERAL, note_type=SearchNoteType.ALL)`
8. 抽取 `result["items"]` → `[{title, author, likes, url}]`
9. 关闭 browser
10. MCP 工具序列化展示给 Claude（沿用旧工具的字符串格式）

## 错误处理

| 触发场景 | 检测点 | 用户看到的提示 |
|---|---|---|
| `小红书Cookie.txt` 不存在或空 | `_parse_cookie()` 启动校验 | `❌ Cookie 文件缺失，请按 CLAUDE.md 第三步更新` |
| Cookie 过期 | `client.pong()` 返回 False | `❌ Cookie 已过期，请重新从浏览器复制 cookie 到 小红书Cookie.txt` |
| 风控拦截（300011 等） | client 抛错或 msg 含 `300011`/`账号异常` | `❌ 仍被风控（IP={当前出口IP}）。请确认 WSL2 没走代理：curl ipinfo.io` |
| Playwright 未安装 | 顶部 try import | `❌ 缺依赖：pip install playwright && playwright install chromium` |
| Chromium 启动失败（缺系统库） | `chromium.launch()` 抛错 | `❌ Chromium 启动失败，跑 playwright install-deps chromium` |
| 关键词无结果 | items 为空 | `未找到「{keyword}」相关笔记。` |
| 单次调用超时（>30s） | `asyncio.timeout(30)` | `❌ 超时（>30s），可能是 IP 慢或被限速` |

统一原则：所有错误返回字符串给 MCP，不抛异常，让 Claude 直接读到原因。

## 安装步骤（一次性）

```bash
cd /home/admin123/drama_calendar

# 1. 初始化 git 仓库
git init
cat > .gitignore <<'EOF'
poster_*.jpg
*_追剧日历*.png
小红书Cookie.txt
image*.png
__pycache__/
*.pyc
.venv/
EOF

# 2. 加 MediaCrawler 作为锁定的 submodule
git submodule add https://github.com/NanmiCoder/MediaCrawler vendor/MediaCrawler
cd vendor/MediaCrawler
git checkout f328ee35b55e25e8aaeb9c847fe8b622e3f3447f
cd ../..

# 3. 装 Python / 浏览器依赖
pip install playwright httpx
playwright install chromium
playwright install-deps chromium  # WSL2 需要系统库

# 4. 首次首验证（重要）
curl -s ipinfo.io | grep -E '"ip"|"org"'   # 必须是住宅 IP，不能是机房
python3 xhs_playwright.py "低智商犯罪 VIP 追剧日历"
```

## 验证清单（实施完成判定）

1. `curl -s ipinfo.io` 显示住宅 IP（非 DMIT / 阿里云 / 腾讯云 / AWS 等机房 ORG）。
2. `python3 xhs_playwright.py "低智商犯罪"` 返回至少 1 条非空结果。
3. MCP 调用 `search_xiaohongshu_playwright` 时 Claude 拿到结构化展示。
4. 故意把 `小红书Cookie.txt` 改坏 → 工具返回友好的「Cookie 已过期」提示，不是 traceback。
5. 旧工具 `search_xiaohongshu` 调用不被破坏（依然能被调用，依然能正确报机房 IP 错误，作 fallback）。

## 文件改动总结

| 文件 | 操作 |
|---|---|
| `/home/admin123/drama_calendar/.git/` | 新建（`git init`） |
| `/home/admin123/drama_calendar/.gitignore` | 新建 |
| `/home/admin123/drama_calendar/.gitmodules` | 新建（`git submodule add` 自动生成） |
| `/home/admin123/drama_calendar/vendor/MediaCrawler/` | submodule，锁 `f328ee35` |
| `/home/admin123/drama_calendar/xhs_playwright.py` | 新建，~200 行 |
| `/home/admin123/drama_calendar/xhs_mcp.py` | 改：新增 `search_xiaohongshu_playwright` 工具 |
| `/home/admin123/drama_calendar/CLAUDE.md` | 改：新工具的使用说明 + 安装步骤指引 |

## 风险与限制

1. **License**：MediaCrawler 是非商业学习许可。当前用途（个人追剧群引流）属于个人学习范畴；商业化前需重新评估。
2. **出口 IP 必须实测**：部署的目标机器必须实测 `curl ipinfo.io` 为住宅 IP；若家里走了 VPN/代理出去，仍可能被风控。
3. **MediaCrawler 上游变动**：锁定 commit `f328ee35` 对抗。需要时再手动 bump。
4. **Chromium 系统依赖**：首次 `playwright install chromium` 后还要 `sudo playwright install-deps chromium`（或 apt 装 libnspr3/libnss3 等），否则 launch 时会报缺 .so。
5. **Headless 检测**：当前不加 `playwright-stealth`，留作未来如果被检测的退路。
6. **MediaCrawler 内部依赖膨胀风险**：直接 import 可能链式拉入它内部模块（如 `tools`、`config`）。实施时若遇到 ImportError 需逐个补 stub 或 monkey-patch。
7. **跨机器迁移**：项目需要从 DMIT 服务器迁移到家用机器。`小红书Cookie.txt` 是敏感文件，迁移时手动复制，不进 git。海报/PNG 等大文件可以不带，跟着以后实际使用再下载。
