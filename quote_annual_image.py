"""年度语录报告图片（Wrapped 风格）：把 quote_insights.annual_report_sync 的数据渲染成竖版长图。"""

from __future__ import annotations

import time
from pathlib import Path

from astrbot.api import logger
from PIL import Image, ImageDraw

import quote_db
from quote_weekly_image import (
    _avatar,
    _avatar_placeholder,
    _fit,
    _font,
    _rounded,
    _text,
)

W = 1080
PAD = 56
INNER = W - PAD * 2
ANNUAL_DIR = "annual"
KEEP_IMAGES = 40

BG_TOP = "#0B1220"
BG_BOTTOM = "#17263D"
CARD = "#182740"
CARD_ALT = "#1F3250"
INK = "#F4F7FB"
MUTED = "#9FB0C7"
ACCENT = "#4DA3FF"
GOLD = "#E8B84B"
TRACK = "#25395A"


def _wrap(text: str, size: int, max_width: int, max_lines: int = 3) -> list[str]:
    text = str(text or "").strip()
    if not text:
        return []
    font = _font(size)
    lines: list[str] = []
    rest = text
    while rest and len(lines) < max_lines:
        piece = ""
        for ch in rest:
            if font.getlength(piece + ch) > max_width:
                break
            piece += ch
        if not piece:
            break
        lines.append(piece)
        rest = rest[len(piece):]
    if rest and lines:
        lines[-1] = _fit(lines[-1] + "…", size, max_width)
    return lines


def _gradient(width: int, height: int) -> Image.Image:
    top = tuple(int(BG_TOP[i : i + 2], 16) for i in (1, 3, 5))
    bottom = tuple(int(BG_BOTTOM[i : i + 2], 16) for i in (1, 3, 5))
    canvas = Image.new("RGB", (1, height))
    for y in range(height):
        ratio = y / max(1, height - 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3))
        canvas.putpixel((0, y), color)
    return canvas.resize((width, height), Image.BILINEAR)


def _stat_card(draw, box, label: str, value: str, note: str = "") -> None:
    _rounded(draw, box, 22, CARD)
    x0, y0, x1, _y1 = box
    _text(draw, (x0 + 24, y0 + 20), label, 20, MUTED)
    _text(draw, (x0 + 24, y0 + 50), value, 46, INK)
    if note:
        _text(draw, (x0 + 24, y0 + 108), note, 18, MUTED)


def render_report(report: dict) -> str:
    """渲染年度报告长图，返回图片路径。"""
    year = int(report.get("year") or time.localtime().tm_year)
    name = str(report.get("display_name") or "群友")
    pid = str(report.get("pid") or "")
    total = int(report.get("total") or 0)
    group_total = int(report.get("group_total") or 0)
    share = float(report.get("share") or 0) * 100
    rank = int(report.get("rank") or 0)
    ranked_total = int(report.get("ranked_total") or 0)
    months = [int(v or 0) for v in (report.get("months") or [0] * 12)][:12]
    months += [0] * (12 - len(months))
    top_month = int(report.get("top_month") or 0)
    top_hour = int(report.get("top_hour") or 0)
    tag_rows = [str(row.get("tag")) for row in (report.get("top_tags") or [])]
    tags = tag_rows[:3]
    submitters = list(report.get("submitters") or [])[:3]
    captions = list(report.get("captions") or [])[:3]
    group_label = str(report.get("group_id") or "")
    generated = time.strftime("%Y-%m-%d %H:%M")

    height = (
        170  # header
        + 150  # hero
        + 150  # stats
        + 40
        + 200  # highlights
        + 40
        + 240  # monthly chart
        + 40
        + (120 * 3 + 40 if captions else 0)  # captions cards
        + 40
        + (150 if submitters else 0)
        + 90  # footer
    )
    canvas = _gradient(W, height).convert("RGB")
    draw = ImageDraw.Draw(canvas, "RGBA")

    # 装饰圆
    draw.ellipse((W - 260, -160, W + 120, 220), fill=(77, 163, 255, 26))
    draw.ellipse((-160, height - 320, 180, height + 20), fill=(232, 184, 75, 18))

    # 顶栏
    _text(draw, (PAD, 60), f"{year} 年度语录报告", 64, INK)
    _text(draw, (PAD, 132), ("本群语录" if group_label else "全部群聊") + " · 你的年度小结", 26, MUTED)
    _text(draw, (W - PAD, 64), f"群 {group_label}" if group_label else "全部群聊", 22, MUTED, anchor="ra")
    _text(draw, (W - PAD, 96), f"生成于 {generated}", 20, MUTED, anchor="ra")

    # 头部个人信息
    y = 196
    avatar = _avatar(str(report.get("avatar_sha") or ""), 112)
    if avatar is None:
        avatar = _avatar_placeholder(112, "#2C4A70")
    canvas.paste(avatar, (PAD, y), avatar)
    _text(draw, (PAD + 136, y + 6), _fit(name, 44, INNER - 140), 44, INK)
    _text(draw, (PAD + 136, y + 62), f"{pid}", 24, ACCENT)
    summary = f"全年被拍成语录 {total} 张 · 占全群 {share:.1f}%"
    _text(draw, (PAD + 136, y + 94), summary, 22, MUTED)

    # 三张数字卡
    y = 350
    card_h = 126
    gap = 22
    card_w = (INNER - gap * 2) // 3
    _stat_card(draw, (PAD, y, PAD + card_w, y + card_h), "年度语录", f"{total} 张", f"全群 {group_total} 张")
    _stat_card(
        draw,
        (PAD + card_w + gap, y, PAD + card_w * 2 + gap, y + card_h),
        "全群排名",
        f"第 {rank} 名" if rank else "未上榜",
        f"共 {ranked_total} 人上榜" if ranked_total else "统计中",
    )
    _stat_card(
        draw,
        (PAD + card_w * 2 + gap * 2, y, PAD + card_w * 3 + gap * 2, y + card_h),
        "平均每月",
        f"{total / 12:.1f} 张",
        "按全年 12 个月计",
    )

    # 高光
    y = 520
    _rounded(draw, (PAD, y, W - PAD, y + 184), 24, CARD_ALT)
    _text(draw, (PAD + 28, y + 20), "你的高光时刻", 26, GOLD)
    hour_text = f"{top_hour} 点" if total else "暂无"
    month_text = f"{top_month + 1} 月" if total else "暂无"
    tag_text = "、".join(f"#{tag}" for tag in tags) if tags else "暂无"
    max_tag_width = INNER - 580
    while len(tag_text) > 2 and _font(22).getlength(tag_text) > max_tag_width:
        tags = tags[:-1] if len(tags) > 1 else tags
        tag_text = "、".join(f"#{tag}" for tag in tags) if tags else "暂无"
    _text(draw, (PAD + 28, y + 66), "最活跃时段", 20, MUTED)
    _text(draw, (PAD + 28, y + 92), hour_text, 34, INK)
    _text(draw, (PAD + 300, y + 66), "最活跃月份", 20, MUTED)
    _text(draw, (PAD + 300, y + 92), month_text, 34, INK)
    _text(draw, (PAD + 540, y + 66), "最爱标签", 20, MUTED)
    _text(draw, (PAD + 540, y + 92), _fit(tag_text, 22, max_tag_width), 22, ACCENT)

    # 月度柱状图
    y = 744
    _text(draw, (PAD, y), "逐月语录", 24, MUTED)
    chart_top = y + 44
    chart_h = 150
    max_month = max(months) or 1
    bar_gap = 12
    bar_w = (INNER - bar_gap * 11) // 12
    for index, count in enumerate(months):
        x = PAD + index * (bar_w + bar_gap)
        bar_h = int(chart_h * count / max_month) if count else 6
        _rounded(draw, (x, chart_top + chart_h - bar_h, x + bar_w, chart_top + chart_h), 8, ACCENT if count else TRACK)
        if count:
            _text(draw, (x + bar_w // 2, chart_top + chart_h - bar_h - 22), str(count), 16, INK, anchor="ma")
        _text(draw, (x + bar_w // 2, chart_top + chart_h + 6), str(index + 1), 16, MUTED, anchor="ma")

    # 代表语录
    y = 1000
    if captions:
        _text(draw, (PAD, y), "你的代表语录", 24, MUTED)
        card_y = y + 40
        for row in captions:
            _rounded(draw, (PAD, card_y, W - PAD, card_y + 108), 20, CARD)
            lines = _wrap(str(row.get("caption") or ""), 22, INNER - 60, max_lines=2)
            for line_index, line in enumerate(lines):
                _text(draw, (PAD + 28, card_y + 20 + line_index * 32), line, 22, INK)
            tag_line = " ".join(f"#{str(tag)}" for tag in (row.get("tags") or [])[:3])
            _text(draw, (PAD + 28, card_y + 84), tag_line, 16, ACCENT)
            _text(draw, (W - PAD - 24, card_y + 84), str(row.get("name") or ""), 14, MUTED, anchor="ra")
            card_y += 120
        y = card_y + 20

    # 投稿最多的人
    content_bottom = y + 40
    if submitters:
        _text(draw, (PAD, y + 10), "最常投稿你的人", 24, MUTED)
        row_y = y + 50
        for index, row in enumerate(submitters, 1):
            _text(draw, (PAD + 8, row_y), f"{index}", 22, GOLD)
            _text(draw, (PAD + 44, row_y), _fit(str(row.get("name") or ""), 24, INNER - 220), 24, INK)
            _text(draw, (W - PAD - 8, row_y), f"{int(row.get('count') or 0)} 张", 22, MUTED, anchor="ra")
            row_y += 40
        content_bottom = row_y

    # 页脚
    footer_y = max(content_bottom + 40, height - 64) if content_bottom + 40 > height - 64 else content_bottom + 40
    _text(
        draw,
        (PAD, footer_y),
        f"数据来源：群内语录投稿 · 统计区间 {year}-01-01 ~ {year}-12-31",
        18,
        MUTED,
    )
    _text(draw, (W - PAD, footer_y), "quote_collocter · 年度报告", 18, MUTED, anchor="ra")
    canvas = canvas.crop((0, 0, W, min(height, footer_y + 70)))

    out_dir = quote_db.plugin_data_dir() / ANNUAL_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_pid = "".join(ch for ch in pid if ch.isalnum() or ch in "-_") or "unknown"
    path = out_dir / f"annual-{safe_pid}-{year}.png"
    canvas.save(path, "PNG", optimize=True)
    try:
        files = sorted(out_dir.glob("annual-*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in files[KEEP_IMAGES:]:
            old.unlink(missing_ok=True)
    except Exception as exc:  # pragma: no cover
        logger.warning(f"[quote] 清理旧年度报告图片失败：{exc}")
    return str(path)
