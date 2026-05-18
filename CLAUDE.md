# 小红书追剧日历 — 项目说明

## 项目目标
为当季热播国剧生成小红书追剧日历图（1080×1440），引流到追剧打卡群。

## 文件结构
```
drama_calendar.py           # 主生成脚本
fonts/NotoSansSC-Bold.ttf   # 中文字体
poster_*.jpg                # 各剧海报（本地缓存）
{剧名}_追剧日历.png          # 输出图片（≤12行时单张）
{剧名}_追剧日历_1.png        # 分页输出（>12行时自动分张）
{剧名}_追剧日历_2.png
```

---

## 每次换新剧的标准流程

### 第一步：搜数据（用户在终端直接跑，不经过 Claude）

**首选数据源（权重最高）：小红书追剧日历博主图 → Claude 多模态识图**

```bash
# 用户自己在终端运行（Claude Code 里用 ! 前缀），图下载完后再告诉 Claude 路径
unset ALL_PROXY HTTP_PROXY HTTPS_PROXY all_proxy http_proxy https_proxy
python3 /home/admin123/drama_calendar/xhs_playwright.py "{剧名} 追剧日历" 5 \
    --download /tmp/xhs_{剧名}/ --max-per-note 5
```
- 此命令**由用户直接执行**，JSON 输出留在终端，不进 Claude 上下文（省 token）
- 下载完成后，告诉 Claude："图在 `/tmp/xhs_{剧名}/`，请识别日历数据"
- Claude 用 `Read` 工具逐张看图（多模态识图），交叉对比≥2-3 个博主的日历贴
- 优先看**赞数高 + 标题含"追剧日历"** 的笔记；忽略月历视图日期错乱的劣质图
- `xhs_playwright.py` 从 `image_list[*].info_list[WB_DFT].url` 拉高清图（xhscdn，**无需登录态**），webp 自动转 JPG

**搜索关键词模板：**
```
{剧名} 追剧日历                  # 找博主自制日历贴（首选）
{剧名} {当前日期} 几集 更新       # 找当日实测
```

**Fallback 数据源（仅在小红书图全是劣质或缺当日数据时用）：**
- 平台官方追剧日历（官微/官网截图）
- 新浪/搜狐/网易开播报道（注意：163.com/新浪写的"更新至 X 集"通常是 SVIP 数字，不是 VIP）
- 数学推算（**不可单独使用，必须有≥1 个图源印证**）

**踩坑案例（2026-05-16 主角）：** 之前只用 sina/163 二手新闻 + 数学推算（"4 集首播+周日休更"），结果首播集数错（实际 VIP=3 不是 4）、节奏错（周日不休更）、5/14 减速没察觉、5/15 SVIP 双时段没察觉。三家小红书博主日历图交叉对比后才修正。**长剧（≥40 集）节奏不规则，必须看图。**

### 第二步：更新脚本配置
只改 `drama_calendar.py` 顶部 `DRAMA = {...}` 这一块：

```python
DRAMA = {
    "title":       "剧名",
    "en_title":    "英文名或空字符串",      # 海报上的英文名；没有填 ""
    "platform":    "优酷",                  # 主平台
    "platform2":   "酷喵TV",               # 联播平台（没有填 ""）
    "status":      "热播中",
    "total_eps":   28,                      # 总集数
    "vip_note":    "每日12:00更新",         # 注意：不含 "VIP" 前缀，badge 已显示
    "svip_note":   "比VIP多看1集",          # 没有 SVIP 超前则填 ""（自动隐藏SVIP列）
    "poster_path": "/home/admin123/drama_calendar/poster_{剧名}.jpg",
    "poster_url":  "",
    "schedule": [
        # 格式：
        # {"date":"X月X日","day":"周X","vip":"第X-X集","svip":"第X-X集","done":True/False,"current":True/False}
        #
        # vip/svip 字段：当日新增集数（非累计），SVIP始终领先VIP 1集
        #   单集日：vip="第16集"，svip="第17集"
        #   多集日：vip="第1-2集"，svip="第1-3集"（首日SVIP+1建立优势）
        #         或 vip="第3-4集"，svip="第4-5集"（后续同步平移）
        #   末集日：svip 封顶于总集数，如 svip="第28集"（无第29集）
        #
        # done=True  → 已更新（灰色）
        # current=True → 今日更新（金色高亮，只有一行）
        # 不确定的集数填 "待更新"；不确定的日期不填
    ]
}
```

**排版说明（当前版本）：**
- 海报占画面 40% 高度，保留更多空间给表格
- VIP 与 SVIP 说明合并在同一行显示
- **"数据来源: guangfan.top"** 紧跟在"追剧日历"标题右侧，字号 28，颜色天蓝色 `(120, 195, 218)`，垂直居中对齐标题
- 每张图最多 **12 行**，超出自动分页生成 `_1.png` / `_2.png` …
- 分页图右下角标注页码 `(1/2)`、`(2/2)` 等

### 第二·五步：核验当日集数（必须，不可跳过）

**每次更新 schedule 里 current=True 的行之前，先核实当天是否真的更新、以及实际集数：**

1. **小红书搜索**（优先）：
   ```
   mcp__xiaohongshu__search_notes 或 WebSearch:
   "{剧名} VIP 今天更新" / "{剧名} 5月X日 第几集"
   ```
2. **视频平台官方**：直接看腾讯视频/爱奇艺/优酷剧集页的集数列表
3. **第三方站辅助**（dbku.tv / 欧乐影院）：若显示"完结"须警惕，可能是盗版超点资源

只有确认了当天实际集数，才能将 `current=True` 行的 vip/svip 填为具体集数；否则保持 `"待更新"`。

### 第三步：生成图片
```bash
python3 /home/admin123/drama_calendar/drama_calendar.py
```
- ≤12 行：输出 `/home/admin123/drama_calendar/{剧名}_追剧日历.png`
- >12 行：输出 `{剧名}_追剧日历_1.png`、`{剧名}_追剧日历_2.png`……

---

## 小红书发布模板

**标题（选一个，20字内）：**
- `追《{剧名}》第X集 今晚更新`
- `《{剧名}》更新日历来了`
- `VIP今晚第X集 你跟上了吗`
- `追《{剧名}》第X集了还没破案？`（悬疑剧用）

**正文：**
```
{主演} × {主演}
今天VIP更新{第X集} SVIP{第X集}
每天12点准时更新 共{X}集

想一起追剧的来👇
每集更新我都会发日历 + 剧情讨论
评论区留言 / 私信发你入群二维码
```

**标签：** `#{剧名}` `#追剧日历` `#{主演名}` `#{平台}好剧`

**运营技巧：**
- 群二维码放评论区或私信，不放正文（规避审核）
- 每次剧集更新当天发，保持节奏感
- 固定格式发，粉丝形成认知

---

## 小红书发布（Playwright CLI）

发布走本地 CLI，不经过 MCP 或 Claude。

### 发布日历图

```bash
unset ALL_PROXY HTTP_PROXY HTTPS_PROXY all_proxy http_proxy https_proxy
python3 /home/admin123/drama_calendar/xhs_playwright.py --publish \
  --title "全集X集｜今天更新第X集" \
  --desc "（按小红书发布模板填写正文）" \
  --images /home/admin123/drama_calendar/{剧名}_追剧日历_1.png \
           /home/admin123/drama_calendar/{剧名}_追剧日历_2.png
```

输出成功：`{"note_id": "...", "url": "https://www.xiaohongshu.com/explore/..."}`

⚠️ 发布比搜索更敏感，首次建议用测试标题发布一条草稿确认流程正常。  
遇到选择器失效或验证码问题，参考 skill `xhs-publish-via-playwright`。

### 搜索 / 下载（CLI，用户直接跑）
```bash
# 搜索 + 下载图片，结果留在本地，不进 Claude 上下文
unset ALL_PROXY HTTP_PROXY HTTPS_PROXY all_proxy http_proxy https_proxy
python3 xhs_playwright.py "{关键词}" {结果数} --download {输出目录} --max-per-note {每帖图数}
```

### Cookie 更新方法
1. 浏览器打开 creator.xiaohongshu.com，F12 → Network → 任意请求 → Request Headers → 复制 cookie
2. 粘贴到 `/home/admin123/drama_calendar/小红书Cookie.txt`（整行替换）

---

## 数据准确性原则

**来源优先级（由高到低）：**
1. **WebSearch 搜小红书帖子**（关键词：`{剧名} VIP SVIP 追剧日历 小红书`，找博主实测帖）
2. 平台官方追剧日历（官微/官网截图）
3. 新浪/搜狐/中华网开播报道
4. 第三方追剧网站实测集数（dbku.tv、欧乐影院）核验
5. 数学推算：总集数 + 当前集数 + 大结局日期 → 唯一确定剩余每日集数（可用，需注释说明）

**填写规则：**
- 每行来源标注在代码注释里
- 集数不确定时，vip/svip 填 `"待更新"`，不猜
- 日期不确定时，整行不填，等官方公布
- SVIP 末集封顶于总集数（不存在 `总集数+1` 集）
- **SVIP 超前不能靠规则推算**：即使 `svip_note` 写"比VIP多看1集"，平台也可能某天 VIP/SVIP 集数齐平。当天必须实测，不能机械套 VIP+1

**⚠️ 高频易错：追剧日历文章里的集数 = SVIP 数字，不是 VIP**
> 二手来源（163.com、新浪追剧日历等）写"更新至 X 集"，指的通常是 SVIP 最新集号（或平台最高可看集号），不是普通 VIP。
> - 判断方法：`该数字 - 1 = VIP当日集数`，在此基础上做数学推算
> - 反例：163.com 写"5月12日更新至25集" → 实际 VIP=24，SVIP=25
> - 直接用这个数字填 VIP 会整体多算1集，所有后续行全部错位

**SVIP 齐平后的处理：**
> 典型场景：平台某日 SVIP 未出超前集，VIP/SVIP 追平至同一集。
- 当天 SVIP 填实测值（如 `"第22集"`），不填 `"第22-23集"`
- 之后各天 SVIP 一律填 `"待更新"`，直到当天实测确认
- VIP 若仍可数学唯一推算（剩余集数 ÷ 剩余天数整除），继续填入并在注释说明

**核验方式（每次生成追剧日历前必须执行，不可跳过）：**

**第一步：小红书实时搜索（最高优先级）**
```
WebSearch 或 mcp__xiaohongshu__search_notes 搜索：
  "{剧名} 今天更新 第几集"
  "{剧名} VIP 5月X日"
  "{剧名} 追剧 更新"
目标：找到当天博主实测帖，确认 VIP / SVIP 今日实际集数
```

**第二步：视频平台官方页面**
```
腾讯视频 / 爱奇艺 / 优酷 对应剧集页 → 看集数列表最新一集编号
注意：平台显示的"最新X集"通常是 SVIP 最高集号，VIP = 该数字 - 1
```

**第三步：第三方核验（辅助，注意陷阱）**
```
dbku.tv 搜剧名 → 看已上线集数
欧乐影院 搜剧名 → 交叉确认
⚠️ 警告：dbku.tv / 欧乐影院等第三方站经常提前显示"完结 X 集"
  → 因为它们抓取的是盗版超点/SVIP 资源，不代表官方 VIP 当前进度
  → 若第三方显示"已完结"而今日日程显示只到第 X 集，以日程为准，不要改集数
```

**⚠️ 结论：只有小红书实测帖或平台官方数据才能确认当天集数；第三方站仅供参考。**

---

## 家用机器部署指南（Playwright CLI 专用）

`xhs_playwright.py` 必须在家庭住宅网络环境直接运行，机房 IP 会被风控（300011）。

### 一次性安装

```bash
# 1. 装 Python 依赖
pip install --user playwright pillow

# 2. 装 Chromium 浏览器和 Linux 系统库
python3 -m playwright install chromium
sudo python3 -m playwright install-deps chromium   # Linux 需要，Mac 不需要

# 3. 把 小红书Cookie.txt 拷到项目根（不进 git）
cp /path/to/your/小红书Cookie.txt ./

# 4. 验证出口 IP 是住宅，且当前 shell 不走代理
unset ALL_PROXY HTTP_PROXY HTTPS_PROXY all_proxy http_proxy https_proxy
curl -s ipinfo.io | grep -E '"ip"|"org"'
# org 不能是 DMIT/AWS/Alibaba/Tencent 等机房 ASN，必须是住宅 ISP

# 5. 烟雾测试
python3 xhs_playwright.py "追剧日历 VIP" 3
# 期望：JSON 数组，≥1 条结果
```

### ⚠️ SOCKS5/HTTP 代理注意

WSL 经 Windows 宿主机走 Clash/V2Ray 等代理时，`ALL_PROXY` / `HTTPS_PROXY` 环境变量会被 Chromium 继承，导致出口变成机房 IP 被风控。跑脚本前必须先 `unset` 这几个变量。

### Cookie 失效时

浏览器 F12 复制 cookie 字符串覆盖 `小红书Cookie.txt`。从 `www.xiaohongshu.com` 或 `creator.xiaohongshu.com` 任意子域复制均可（小红书 SSO 跨子域下发），关键字段：`a1`、`web_session`、`webId`、`xsecappid`。

### License 说明

`vendor/MediaCrawler/` 采用「非商业学习使用许可证」，本项目当前作为个人追剧群引流的学习用途。如未来涉及商业化，需重新评估合规性。
