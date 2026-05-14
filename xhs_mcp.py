"""小红书 MCP 服务器 — 供 drama_calendar 查询剧情数据 & 发布日历图"""
import asyncio
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from xhs import XhsClient
from xhs.help import sign

import xhs_playwright

COOKIE_FILE = Path(__file__).parent / "小红书Cookie.txt"

mcp = FastMCP("xiaohongshu-drama")


def _external_sign(url, data=None, a1="", web_session="", **kwargs):
    return sign(url, data, a1=a1)


def _client():
    cookie = COOKIE_FILE.read_text(encoding="utf-8").strip()
    return XhsClient(cookie=cookie, sign=_external_sign)


def _cookie_expired_msg():
    return (
        "❌ 小红书 cookie 已过期。\n"
        "请在浏览器登录小红书后，用开发者工具复制完整 cookie，更新到：\n"
        f"{COOKIE_FILE}\n"
        "然后重试。"
    )


@mcp.tool()
def search_xiaohongshu(keyword: str, page_size: int = 8) -> str:
    """搜索小红书笔记，用于查询追剧博主的VIP/SVIP更新日历。返回标题、作者、点赞数，优先参考高点赞笔记。

    Args:
        keyword: 搜索关键词，如「低智商犯罪 追剧日历 VIP」
        page_size: 返回条数，默认8
    """
    try:
        result = _client().get_note_by_keyword(keyword, page_size=page_size)
        items = result.get("items", []) if isinstance(result, dict) else []
        if not items:
            return f"未找到「{keyword}」相关笔记。"

        lines = [f"小红书搜索「{keyword}」，共 {len(items)} 条：\n"]
        for i, item in enumerate(items, 1):
            note = item.get("note_card", item)
            title = note.get("display_title") or note.get("title", "（无标题）")
            author = note.get("user", {}).get("nickname", "未知")
            likes = note.get("interact_info", {}).get("liked_count", "?")
            note_id = note.get("id") or note.get("note_id", "")
            url = f"https://www.xiaohongshu.com/explore/{note_id}" if note_id else ""
            lines.append(f"{i}. 【{title}】 作者:{author} 点赞:{likes}")
            if url:
                lines.append(f"   {url}")
        return "\n".join(lines)

    except Exception as e:
        msg = str(e)
        if "登录已过期" in msg or "-100" in msg:
            return _cookie_expired_msg()
        if "300011" in msg or "账号异常" in msg:
            return (
                "❌ 请求被小红书拦截（错误 300011）\n"
                "原因：当前服务器 IP 是机房 IP，小红书对机房 IP 触发反爬。\n"
                "替代方案：用 WebSearch 工具搜「小红书 {剧名} VIP 追剧日历」"
            )
        return f"搜索失败: {msg}"


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
        return result
    if not result:
        return f"未找到「{keyword}」相关笔记。"

    lines = [f"小红书 Playwright 搜索「{keyword}」，共 {len(result)} 条：\n"]
    for i, row in enumerate(result, 1):
        lines.append(f"{i}. 【{row['title']}】 作者:{row['author']} 点赞:{row['likes']}")
        if row["url"]:
            lines.append(f"   {row['url']}")
    return "\n".join(lines)


@mcp.tool()
def publish_xiaohongshu(title: str, desc: str, image_paths: list[str]) -> str:
    """发布图文笔记到小红书，用于发布追剧日历图片。

    Args:
        title: 笔记标题（20字以内）
        desc: 正文内容
        image_paths: 本地图片路径列表
    """
    missing = [p for p in image_paths if not Path(p).exists()]
    if missing:
        return f"图片文件不存在: {missing}"

    try:
        result = _client().create_image_note(title=title, desc=desc, files=image_paths)
        note_id = result.get("note_id", "") if isinstance(result, dict) else ""
        url = f"https://www.xiaohongshu.com/explore/{note_id}" if note_id else ""
        return (
            f"✅ 发布成功！\n标题: {title}\n图片数: {len(image_paths)}"
            + (f"\n链接: {url}" if url else "")
        )
    except Exception as e:
        msg = str(e)
        if "登录已过期" in msg or "-100" in msg:
            return _cookie_expired_msg()
        if "300011" in msg or "账号异常" in msg:
            return (
                "❌ 发布被小红书拦截（错误 300011）\n"
                "原因：当前服务器 IP 是机房 IP（DMIT Cloud Services），小红书拒绝机房 IP 的请求。\n"
                "解决方案：在本地居民网络环境下配置代理后运行，或手动复制内容在浏览器中发布。"
            )
        return f"发布失败: {msg}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
