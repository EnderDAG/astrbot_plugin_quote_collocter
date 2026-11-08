"""每周语录周报图片：把周报渲染成带头像的表格卡片，供群内推送。"""

from __future__ import annotations

import time
from pathlib import Path

from astrbot.api import logger
from PIL import Image, ImageDraw, ImageFont

import quote_db
from quote_identity import identity_avatar_dir

W = 1000
PAD = 34
INNER = W - PAD * 2

BG = "#EEF2F7"
CARD = "#FFFFFF"
INK = "#1F2A44"
MUTED = "#6B7280"
LINE = "#E3E8EF"
HEAD = "#1F3A5F"
ACCENT = "#2F5D8A"
GOLD = "#C9A227"
SILVER = "#8C96A3"
BRONZE = "#B87333"
CHIP = "#E8F0F8"

WEEKLY_IMAGE_DIR = "weekly"
KEEP_IMAGES = 30

FONT_CANDIDATES = [
    "/usr/share/fonts/google-droid/DroidSansFallback.ttf",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyhbd.ttc",
]

_FONT_CACHE: dict = {}


def _font(size: int):
    size = max(10, int(size))
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    font = None
    for path in FONT_CANDIDATES:
        try:
            if Path(path).is_file():
                font = ImageFont.truetype(path, size)
                break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()
    _FONT_CACHE[size] = font
    return font


def _text(draw, xy, text, size, fill, anchor="la"):
    draw.text(xy, str(text), font=_font(size), fill=fill, anchor=anchor)


def _fit(text, size, max_width: int) -> str:
    text = str(text or "")
    font = _font(size)
    if font.getlength(text) <= max_width:
        return text
    while text and font.getlength(text + "…") > max_width:
        text = text[:-1]
    return (text + "…") if text else "…"


def _rounded(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def _avatar(sha, size: int):
    key = str(sha or "").strip().lower()
    if len(key) != 16:
        return None
    path = identity_avatar_dir() / f"{key}.jpg"
    if not path.is_file():
        return None
    try:
        image = Image.open(path).convert("RGB")
    except Exception:
        return None
    w, h = image.size
    side = min(w, h)
    if side <= 0:
        return None
    image = image.crop(
        ((w - side) // 2, (h - side) // 2, (w + side) // 2, (h + side) // 2)
    ).resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(image, (0, 0), mask)
    return out


def _avatar_placeholder(size: int, color: str):
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(out)
    draw.ellipse((0, 0, size - 1, size - 1), fill=color)
    _text(draw, (size // 2, size // 2), "群", max(12, size // 3), "#FFFFFF", anchor="mm")
    return out


def _rank_color(rank: int) -> str:
    if rank == 1:
        return GOLD
    if rank == 2:
        return SILVER
    if rank == 3:
        return BRONZE
    return "#A9B4C2"


def _person_rows(report: dict) -> list:
    return list(report.get("persons") or [])


def _submitter_rows(report: dict) -> list:
    return list(report.get("submitters") or [])


def _table_height(rows: int) -> int:
    return 40 + 42 + rows * 68 + 10


def render_card(report: dict, group_label: str = "") -> str:
    """把周报数据渲染成 PNG 表格卡片，返回文件路径。"""
    persons = _person_rows(report)
    submitters = _submitter_rows(report)
    hotwords = [str(row.get("word") or "") for row in (report.get("hotwords") or [])][:3]
    hotwords = [word for word in hotwords if word]

    height = (
        132
        + 18
        + 104
        + 26
        + _table_height(len(persons))
        + 22
        + _table_height(len(submitters))
        + 46
        + PAD
    )
    canvas = Image.new("RGB", (W, height), BG)
    draw = ImageDraw.Draw(canvas)

    # 顶部标题
    _rounded(draw, (PAD, 26, W - PAD, 26 + 132), 20, HEAD)
    _text(draw, (PAD + 30, 26 + 30), "语录周报", 36, "#FFFFFF")
    _text(draw, (PAD + 30, 26 + 86), "本群语录 · 每周新增与人气排行", 15, "#C7D3E3")
    label = _fit(group_label or f"群 {report.get('group_id', '')}", 15, 300)
    week = str(report.get("week_label") or "")
    _text(draw, (W - PAD - 30, 26 + 30), label, 15, "#C7D3E3", anchor="ra")
    _text(draw, (W - PAD - 30, 26 + 62), week, 26, "#FFFFFF", anchor="ra")
    _text(draw, (W - PAD - 30, 26 + 100), f"生成于 {time.strftime('%Y-%m-%d %H:%M')}", 13, "#9FB0C7", anchor="ra")

    y = 26 + 132 + 18

    # 概览卡片
    gap = 16
    card_w = (INNER - gap * 2) // 3
    cards = [
        ("本周新增", f"{int(report.get('quotes') or 0)} 张", f"较上周 {int(report.get('delta') or 0):+d} 张"),
        ("群内累计", f"{int(report.get('total') or 0)} 张", f"本周占 {int(report.get('quotes') or 0)} 张"),
        ("本周热词", " / ".join(hotwords) or "暂无", "来自语义标签与语气"),
    ]
    for index, (title, value, sub) in enumerate(cards):
        x0 = PAD + index * (card_w + gap)
        _rounded(draw, (x0, y, x0 + card_w, y + 104), 16, CARD)
        _text(draw, (x0 + 20, y + 16), title, 14, MUTED)
        size = 27 if font_ok(value, 27, card_w - 40) else 20
        _text(draw, (x0 + 20, y + 40), _fit(value, size, card_w - 40), size, INK)
        _text(draw, (x0 + 20, y + 80), sub, 12, MUTED)
    y += 104 + 26

    y = _draw_rank_table(
        canvas,
        draw,
        y,
        "语录最多 · TOP",
        persons,
        ["排名", "语录人物", "本周语录"],
        "暂无归属人物的语录",
    )
    y += 22
    y = _draw_rank_table(
        canvas,
        draw,
        y,
        "投稿最多 · TOP",
        submitters,
        ["排名", "投稿人", "投稿数"],
        "本周暂无投稿记录",
    )

    # 页脚
    _text(draw, (PAD, height - 40), "数据来自群内投稿语录 · 同一人物的多个昵称已合并统计", 12, MUTED)
    _text(draw, (W - PAD, height - 40), "quote_collocter 周报", 12, "#A9B4C2", anchor="ra")

    out_dir = quote_db.plugin_data_dir() / WEEKLY_IMAGE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    gid = str(report.get("group_id") or "all")
    week = time.strftime("%Y%m%d", time.localtime(float(report.get("week_start") or time.time())))
    path = out_dir / f"weekly-{gid}-{week}.png"
    canvas.save(path, "PNG", optimize=True)
    _cleanup(out_dir)
    return str(path)


def font_ok(text, size, max_width) -> bool:
    return _font(size).getlength(str(text)) <= max_width


def _cleanup(out_dir: Path) -> None:
    try:
        files = sorted(out_dir.glob("weekly-*.png"), key=lambda item: item.stat().st_mtime)
        for old in files[:-KEEP_IMAGES]:
            old.unlink(missing_ok=True)
    except Exception as exc:
        logger.warning(f"[quote] 清理周报图片失败：{exc}")


def _draw_rank_table(canvas, draw, top_y: int, title: str, rows: list, headers: list, empty_text: str) -> int:
    _text(draw, (PAD + 4, top_y), title, 20, HEAD)
    y = top_y + 40
    _rounded(draw, (PAD, y, W - PAD, y + 42), 12, HEAD)
    _text(draw, (PAD + 26, y + 10), headers[0], 13, "#C7D3E3")
    _text(draw, (PAD + 96, y + 10), headers[1], 13, "#C7D3E3")
    _text(draw, (W - PAD - 30, y + 10), headers[2], 13, "#C7D3E3", anchor="ra")
    y += 42

    if not rows:
        _rounded(draw, (PAD, y, W - PAD, y + 68), 12, CARD)
        _text(draw, (PAD + 26, y + 24), empty_text, 15, MUTED)
        return y + 68 + 10

    max_count = max(int(row.get("count") or 0) for row in rows) or 1
    for index, row in enumerate(rows):
        top = y + index * 68
        if index % 2 == 0:
            _rounded(draw, (PAD, top, W - PAD, top + 68), 10, CARD)
        accent = _rank_color(index + 1)
        draw.rounded_rectangle((PAD + 16, top + 18, PAD + 50, top + 52), radius=8, fill=accent)
        _text(draw, (PAD + 33, top + 35), str(index + 1), 16, "#FFFFFF", anchor="mm")

        size = 46
        avatar = _avatar(row.get("avatar_sha"), size) or _avatar_placeholder(size, accent)
        canvas.paste(avatar, (PAD + 66, top + 11), avatar)
        name = _fit(row.get("name") or "群友", 17, 300)
        _text(draw, (PAD + 126, top + 14), name, 17, INK)
        person_id = str(row.get("person_id") or "")
        if person_id:
            _text(draw, (PAD + 126, top + 38), person_id, 12, MUTED)

        count = int(row.get("count") or 0)
        count_x = W - PAD - 20
        bar_w = 170
        bar_right = count_x - 54
        bar_x = bar_right - bar_w
        draw.rounded_rectangle((bar_x, top + 30, bar_right, top + 42), radius=6, fill="#E7EDF5")
        filled = max(6, int(bar_w * count / max_count))
        draw.rounded_rectangle((bar_x, top + 30, bar_x + filled, top + 42), radius=6, fill=ACCENT)
        _text(draw, (count_x, top + 14), f"{count}", 20, ACCENT, anchor="ra")
        _text(draw, (count_x, top + 42), f"{count / max_count * 100:.0f}%", 12, MUTED, anchor="ra")
    return y + len(rows) * 68 + 10


def render_for_group(group_id: str, offset: int = 0) -> tuple:
    """生成指定群当前周（offset=0）或上一周（offset=-1）的周报图片。"""
    import quote_weekly

    report = quote_weekly.weekly_report_sync(group_id, offset=offset)
    path = render_card(report, group_label=f"群 {group_id}")
    return path, report
