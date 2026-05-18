#!/usr/bin/env python3
"""
小红书追剧日历生成器 — 《主角》
换剧只改顶部 DRAMA 配置，然后 python3 drama_calendar.py
超过 ROWS_PER_PAGE 行自动分页输出多张图片
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import requests, io, os

# ================================================================
# 配置区 — 每次换剧只改这里
# ================================================================
DRAMA = {
    "title":       "爱情没有神话",
    "en_title":    "LOVE HAS NO MYTH",
    "platform":    "腾讯视频",
    "platform2":   "咪咕视频",
    "status":      "热播中",
    "total_eps":   37,
    "vip_note":    "每日19:30更新",
    "svip_note":   "比VIP多看1集",
    "poster_path": "/home/admin123/drama_calendar/poster_爱情没有神话.jpg",
    "poster_url":  "",
    # 数据来源：4/28-5/16 已实播核验（内存记录）；5/17-5/20 数学自洽推算（总集数37，VIP+SVIP各差1集）
    "schedule": [
        {"date": "4月28日", "day": "周二", "vip": "第1-3集",   "svip": "第1-4集",   "done": True,  "current": False, "badge": "开播首日"},
        {"date": "4月29日", "day": "周三", "vip": "第4-5集",   "svip": "第5-6集",   "done": True,  "current": False},
        {"date": "4月30日", "day": "周四", "vip": "第6-7集",   "svip": "第7-8集",   "done": True,  "current": False},
        {"date": "5月1日",  "day": "周五", "vip": "第8-9集",   "svip": "第9-10集",  "done": True,  "current": False},
        {"date": "5月2日",  "day": "周六", "vip": "第10-11集", "svip": "第11-12集", "done": True,  "current": False},
        {"date": "5月3日",  "day": "周日", "vip": "第12-13集", "svip": "第13-14集", "done": True,  "current": False},
        {"date": "5月4日",  "day": "周一", "vip": "第14-15集", "svip": "第15-16集", "done": True,  "current": False},
        {"date": "5月5日",  "day": "周二", "vip": "第16-17集", "svip": "第17-18集", "done": True,  "current": False},
        {"date": "5月6日",  "day": "周三", "vip": "第18-19集", "svip": "第19-20集", "done": True,  "current": False},
        {"date": "5月7日",  "day": "周四", "vip": "第20-21集", "svip": "第21-22集", "done": True,  "current": False},
        {"date": "5月8日",  "day": "周五", "vip": "第22-23集", "svip": "第23-24集", "done": True,  "current": False},
        {"date": "5月9日",  "day": "周六", "vip": "第24-25集", "svip": "第25-26集", "done": True,  "current": False},
        {"date": "5月10日", "day": "周日", "vip": "第26-27集", "svip": "第27-28集", "done": True,  "current": False},
        {"date": "5月11日", "day": "周一", "vip": "第28-29集", "svip": "第29-30集", "done": True,  "current": False},
        {"date": "5月12日", "day": "周二", "vip": "第30-31集", "svip": "第31-32集", "done": True,  "current": False},
        {"date": "5月13日", "day": "周三", "vip": "第32集",    "svip": "第33集",    "done": True,  "current": False, "badge": "大结局点映礼"},
        {"date": "5月14日", "day": "周四", "vip": "",          "svip": "",          "done": True,  "current": False, "no_update": True},
        {"date": "5月15日", "day": "周五", "vip": "",          "svip": "",          "done": True,  "current": False, "no_update": True},
        {"date": "5月16日", "day": "周六", "vip": "第33集",    "svip": "第34集",    "done": True,  "current": False, "badge": "央视收官"},
        {"date": "5月17日", "day": "周日", "vip": "第34集",    "svip": "第35集",    "done": False, "current": True},
        {"date": "5月18日", "day": "周一", "vip": "第35集",    "svip": "第36集",    "done": False, "current": False},
        {"date": "5月19日", "day": "周二", "vip": "第36集",    "svip": "第37集",    "done": False, "current": False, "badge": "SVIP大结局"},
        {"date": "5月20日", "day": "周三", "vip": "第37集",    "svip": "第37集",    "done": False, "current": False, "badge": "大结局"},
    ]
}

# ================================================================
CANVAS_W, CANVAS_H = 1080, 1440
FONT          = "/home/admin123/drama_calendar/fonts/NotoSansSC-Bold.ttf"
ROWS_PER_PAGE = 12
OUTPUT_DIR    = "/home/admin123/drama_calendar"

BG       = (8,  7, 16)
GOLD     = (215, 175, 55)
GOLD_DIM = (140, 110, 40)
WHITE    = (248, 243, 230)
DIM      = (130, 120, 100)
RED      = (240, 80, 60)
GREEN    = (70, 195, 100)
ROW_A    = (20, 17, 34)
ROW_B    = (13, 11, 22)
CURRENT  = (38, 28, 8)


def f(size):
    return ImageFont.truetype(FONT, size)


def load_poster():
    if DRAMA["poster_path"] and os.path.exists(DRAMA["poster_path"]):
        return Image.open(DRAMA["poster_path"]).convert("RGB")
    if DRAMA["poster_url"]:
        r = requests.get(DRAMA["poster_url"], timeout=10,
                         headers={"User-Agent": "Mozilla/5.0"}, verify=False)
        return Image.open(io.BytesIO(r.content)).convert("RGB")
    ph = Image.new("RGB", (CANVAS_W, 600), (20, 18, 35))
    ImageDraw.Draw(ph).text((CANVAS_W // 2, 300), DRAMA["title"],
                             font=f(90), fill=GOLD, anchor="mm")
    return ph


def draw_gradient_bg(img):
    d = ImageDraw.Draw(img)
    for y in range(CANVAS_H):
        t = y / CANVAS_H
        d.line([(0, y), (CANVAS_W, y)],
               fill=(int(8 + t * 5), int(7 + t * 4), int(16 + t * 12)))


def paste_poster(img, poster):
    POSTER_H = int(CANVAS_H * 0.40)

    pw, ph = poster.size
    target_ratio = CANVAS_W / POSTER_H
    if pw / ph > target_ratio:
        new_w = int(ph * target_ratio)
        off = (pw - new_w) // 2
        poster = poster.crop((off, 0, off + new_w, ph))
    else:
        new_h = int(pw / target_ratio)
        off = int((ph - new_h) * 0.22)
        poster = poster.crop((0, off, pw, off + new_h))

    poster = poster.resize((CANVAS_W, POSTER_H), Image.LANCZOS)
    img.paste(poster, (0, 0))

    fade = Image.new("RGB", (CANVAS_W, POSTER_H), BG)
    mask = Image.new("L",   (CANVAS_W, POSTER_H), 0)
    md   = ImageDraw.Draw(mask)
    fade_from = int(POSTER_H * 0.50)
    for y in range(fade_from, POSTER_H):
        a = int(255 * ((y - fade_from) / (POSTER_H - fade_from)) ** 1.4)
        md.line([(0, y), (CANVAS_W, y)], fill=a)
    img.paste(fade, (0, 0), mask)

    top = Image.new("RGB", (CANVAS_W, 80), BG)
    tm  = Image.new("L",   (CANVAS_W, 80), 0)
    tmd = ImageDraw.Draw(tm)
    for y in range(80):
        tmd.line([(0, y), (CANVAS_W, y)], fill=int(200 * (1 - y / 80) ** 1.2))
    img.paste(top, (0, 0), tm)

    return POSTER_H


def make_page(page_items, page_num, total_pages, poster):
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), BG)
    draw_gradient_bg(img)

    # ── 1. 海报（40% 高度）──────────────────────────────────
    POSTER_H = paste_poster(img, poster)
    draw = ImageDraw.Draw(img)

    # ── 2. 剧名叠在海报底部 ──────────────────────────────────
    ty = POSTER_H - 110
    draw.rectangle([56, ty + 4, 64, ty + 68], fill=GOLD)
    draw.text((78, ty),       DRAMA["title"],    font=f(70), fill=WHITE)
    draw.text((78, ty + 78),  DRAMA["en_title"], font=f(20), fill=DIM)

    # 平台角标（右上角）
    platforms = [p for p in [DRAMA["platform"], DRAMA["platform2"]] if p]
    for i, plat in enumerate(platforms):
        x = CANVAS_W - 56 - i * 128
        draw.rounded_rectangle([x - 108, ty + 4, x, ty + 38], radius=5, fill=(100, 50, 0))
        draw.text((x - 54, ty + 21), plat, font=f(21), fill=(255, 200, 60), anchor="mm")

    # ── 3. 追剧日历标题 ──────────────────────────────────────
    CT = POSTER_H + 16
    draw.text((60, CT), "追剧日历", font=f(44), fill=GOLD)
    title_w = int(draw.textlength("追剧日历", font=f(44)))
    draw.text((60 + title_w + 18, CT + 22), "数据来源: guangfan.top", font=f(28), fill=(120, 195, 218), anchor="lm")

    # VIP + SVIP 合并一行
    has_svip = bool(DRAMA["svip_note"])
    note_y   = CT + 54

    # VIP
    draw.rounded_rectangle([60, note_y, 168, note_y + 32], radius=4, fill=(80, 40, 0))
    draw.text((114, note_y + 16), "VIP", font=f(19), fill=(255, 200, 60), anchor="mm")
    draw.text((178, note_y + 16), DRAMA["vip_note"], font=f(19), fill=DIM, anchor="lm")

    # SVIP（同一行，右侧）
    if has_svip:
        draw.rounded_rectangle([476, note_y, 604, note_y + 32], radius=4, fill=(60, 20, 80))
        draw.text((540, note_y + 16), "SVIP", font=f(19), fill=(220, 140, 255), anchor="mm")
        draw.text((614, note_y + 16), DRAMA["svip_note"], font=f(19), fill=DIM, anchor="lm")

    sep_y = CT + 98
    draw.line([(60, sep_y), (CANVAS_W - 60, sep_y)], fill=(40, 36, 26), width=1)

    # ── 4. 表头 ──────────────────────────────────────────────
    TBL = sep_y + 12
    bot_y = CANVAS_H - 56
    remaining = bot_y - 18 - TBL
    ROW_H = min(int(remaining / (len(page_items) + 1)), 66)

    if has_svip:
        C = {"date": 60, "day": 228, "vip": 336, "svip": 580, "status": 830}
        headers = [("日期", C["date"]), ("星期", C["day"]),
                   ("VIP可看", C["vip"]), ("SVIP可看", C["svip"]), ("状态", C["status"])]
    else:
        C = {"date": 60, "day": 228, "vip": 336, "svip": 336, "status": 690}
        headers = [("日期", C["date"]), ("星期", C["day"]),
                   ("VIP可看", C["vip"]), ("状态", C["status"])]

    for txt, x in headers:
        draw.text((x, TBL), txt, font=f(21), fill=GOLD_DIM)

    # ── 5. 数据行 ────────────────────────────────────────────
    for i, item in enumerate(page_items):
        y = TBL + (i + 1) * ROW_H

        is_badge     = bool(item.get("badge"))
        is_no_update = item.get("no_update", False)
        if item["current"]:
            bg = CURRENT
        elif is_badge:
            bg = (35, 12, 4)
        elif is_no_update:
            bg = (10, 9, 18)
        else:
            bg = ROW_A if i % 2 == 0 else ROW_B
        draw.rectangle([40, y - 2, CANVAS_W - 40, y + ROW_H - 4], fill=bg)

        if item["current"]:
            draw.rectangle([40, y - 2, 45, y + ROW_H - 4], fill=GOLD)
        elif is_badge:
            draw.rectangle([40, y - 2, 45, y + ROW_H - 4], fill=RED)

        tc = (255, 225, 100) if item["current"] else \
             (DIM[0], DIM[1], DIM[2]) if item["done"] else \
             (60, 56, 46) if is_no_update else WHITE

        draw.text((C["date"], y + 5), item["date"], font=f(26), fill=tc)
        draw.text((C["day"],  y + 5), item["day"],  font=f(24), fill=tc)
        if not is_no_update:
            draw.text((C["vip"], y + 5), item["vip"], font=f(24), fill=tc)
        if has_svip and not is_no_update:
            draw.text((C["svip"], y + 5), item["svip"], font=f(24),
                      fill=(210, 130, 255) if not item["done"] else DIM)

        if is_no_update:
            bx1, bx2 = C["vip"] - 4, CANVAS_W - 40
            draw.rounded_rectangle([bx1, y + 3, bx2, y + ROW_H - 6], radius=4, fill=(18, 16, 30))
            draw.text(((bx1 + bx2) // 2, y + ROW_H // 2 - 1),
                      "本日断更", font=f(19), fill=(70, 65, 55), anchor="mm")
        elif is_badge:
            bx1, bx2 = C["status"] - 4, CANVAS_W - 40
            draw.rounded_rectangle([bx1, y + 3, bx2, y + ROW_H - 6], radius=4, fill=(185, 45, 0))
            draw.text(((bx1 + bx2) // 2, y + ROW_H // 2 - 1),
                      item["badge"], font=f(17), fill=(255, 218, 50), anchor="mm")
        elif item["done"]:
            draw.text((C["status"], y + 5), "已更新", font=f(21), fill=GREEN)
        elif item["current"]:
            draw.rounded_rectangle([C["status"], y + 3,
                                    C["status"] + 106, y + ROW_H - 6],
                                   radius=4, fill=(160, 60, 0))
            draw.text((C["status"] + 53, y + ROW_H // 2 - 1),
                      "今日更新", font=f(19), fill=WHITE, anchor="mm")
        else:
            draw.text((C["status"], y + 5), "待更新", font=f(21), fill=DIM)

    # ── 6. 底部 ──────────────────────────────────────────────
    draw.line([(60, bot_y - 10), (CANVAS_W - 60, bot_y - 10)],
              fill=(40, 36, 26), width=1)

    done_list = [x for x in DRAMA["schedule"] if x["done"] or x["current"]]
    last_vip  = done_list[-1]["vip"] if done_list else "—"

    draw.text((60, bot_y),
              f"VIP 已更新至{last_vip}",
              font=f(22), fill=RED)

    right_text = f"共{DRAMA['total_eps']}集  {DRAMA['status']}"
    if total_pages > 1:
        right_text = f"({page_num}/{total_pages})  " + right_text
    draw.text((CANVAS_W - 60, bot_y), right_text, font=f(22), fill=DIM, anchor="ra")

    # ── 7. 输出文件名 ────────────────────────────────────────
    if total_pages == 1:
        output = f"{OUTPUT_DIR}/{DRAMA['title']}_追剧日历.png"
    else:
        output = f"{OUTPUT_DIR}/{DRAMA['title']}_追剧日历_{page_num}.png"

    img.save(output, "PNG")
    print(f"生成完成: {output}")


def main():
    poster   = load_poster()
    schedule = DRAMA["schedule"]
    pages    = [schedule[i:i + ROWS_PER_PAGE]
                for i in range(0, len(schedule), ROWS_PER_PAGE)]

    for idx, page_items in enumerate(pages):
        make_page(page_items, idx + 1, len(pages), poster)


if __name__ == "__main__":
    main()
