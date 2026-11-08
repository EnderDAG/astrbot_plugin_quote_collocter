"""每周语录周报：统计最近一周新增语录与排名，生成可推送到群的周报。"""

from __future__ import annotations

import time

from astrbot.api import logger

import quote_db
from quote_core import META, group_ids, list_image_files
from quote_identity import IDENTITY, _clean_ai_name
from quote_semantic import SEMANTIC

DAY = 86400
WEEKLY_SCOPE = "weekly"
WEEKLY_KEY = "settings"
WEEKLY_HOURS = 24

DEFAULT_WEEKLY_SETTINGS = {
    "enabled": False,
    "weekday": 1,
    "hour": 9,
    "groups": [],
    "last_week": "",
    "last_result": {},
}


def _week_start(now: float) -> float:
    local = time.localtime(now)
    midnight = time.mktime(
        (local.tm_year, local.tm_mon, local.tm_mday, 0, 0, 0, 0, 0, -1)
    )
    return midnight - (local.tm_wday % 7) * DAY


def week_window(now: float = None, offset: int = 0) -> tuple:
    current = time.time() if now is None else float(now)
    start = _week_start(current) + int(offset) * 7 * DAY
    end = start + 7 * DAY
    label = lambda ts: time.strftime("%m.%d", time.localtime(ts))
    return start, end, label(start), label(end - 1)


def _person_name(uid: str, summaries: dict) -> str:
    row = summaries.get(str(uid)) or {}
    return _clean_ai_name(row.get("display_name")) or "群友"


def weekly_report_sync(group_id: str, now: float = None, offset: int = 0) -> dict:
    gid = str(group_id or "").strip()
    start, end, start_label, end_label = week_window(now, offset)
    prev_start = start - 7 * DAY
    files = list_image_files(gid) if gid else []
    try:
        meta_items = META.load(gid)["items"] if gid else {}
    except Exception:
        meta_items = {}
    try:
        summaries = IDENTITY.summaries()
    except Exception:
        summaries = {}

    def scan(left: float, right: float) -> tuple:
        count = 0
        persons: dict = {}
        submitters: dict = {}
        names: list = []
        for item in files:
            try:
                ts = float(item.get("ts") or 0.0)
            except (TypeError, ValueError):
                ts = 0.0
            if not (left <= ts < right):
                continue
            count += 1
            name = str(item.get("name") or "")
            if name:
                names.append(name)
            info = meta_items.get(name) or {}
            uid = str(info.get("subject_user_id") or "").strip()
            if uid:
                persons[uid] = persons.get(uid, 0) + 1
            submitter = str(info.get("user_id") or "").strip()
            if submitter:
                submitters[submitter] = submitters.get(submitter, 0) + 1
        return count, persons, submitters, names

    count, persons, submitters, names = scan(start, end)
    hotwords = []
    try:
        semantic_items = SEMANTIC.items(gid) if gid else {}
    except Exception:
        semantic_items = {}
    word_counts: dict = {}
    for name in names:
        entry = semantic_items.get(name) or {}
        for tag in (entry.get("tags") or [])[:8]:
            word = str(tag or "").strip()
            if word and len(word) <= 12:
                word_counts[word] = word_counts.get(word, 0) + 1
        tone = str(entry.get("tone") or "").strip()
        if tone and len(tone) <= 12:
            word_counts[tone] = word_counts.get(tone, 0) + 1
    hotwords = [
        {"word": word, "count": value}
        for word, value in sorted(word_counts.items(), key=lambda pair: (-pair[1], pair[0]))[:6]
    ]
    prev_count, _prev_persons, _prev_submitters, _prev_names = scan(prev_start, start)
    top_persons = sorted(persons.items(), key=lambda pair: (-pair[1], pair[0]))[:5]
    top_submitters = sorted(submitters.items(), key=lambda pair: (-pair[1], pair[0]))[:5]
    covers = list(reversed(names[-3:]))

    def person_rows(pairs: list) -> list:
        rows = []
        for uid, value in pairs:
            info = summaries.get(str(uid)) or {}
            rows.append(
                {
                    "name": _person_name(uid, summaries),
                    "count": value,
                    "uid": str(uid),
                    "avatar_sha": str(info.get("avatar_sha") or ""),
                    "person_id": str(info.get("person_id") or ""),
                }
            )
        return rows

    person_list = person_rows(top_persons)
    submitter_list = person_rows(top_submitters)
    return {
        "group_id": gid,
        "week_start": start,
        "week_end": end,
        "week_label": f"{start_label}–{end_label}",
        "quotes": count,
        "prev_quotes": prev_count,
        "delta": count - prev_count,
        "persons": person_list,
        "submitters": submitter_list,
        "covers": covers,
        "hotwords": hotwords,
        "total": len(files),
    }


def report_text(group_id: str, report: dict = None, now: float = None) -> str:
    report = report or weekly_report_sync(group_id, now)
    lines = [f"📅 本群语录周报（{report['week_label']}）"]
    if report["prev_quotes"] or report["delta"]:
        trend = f"（较上周 {report['delta']:+d}）"
    else:
        trend = ""
    lines.append(f"本周新增 {report['quotes']} 张{trend}")
    if report["persons"]:
        top = "、".join(
            f"{row['name']} {row['count']} 张" for row in report["persons"][:3]
        )
        lines.append(f"🔥 本周语录最多：{top}")
    if report.get("hotwords"):
        hot = "、".join(row["word"] for row in report["hotwords"][:5])
        lines.append(f"🏷️ 本周热词：{hot}")
    if report["submitters"]:
        top = "、".join(
            f"{row['name']} {row['count']} 张" for row in report["submitters"][:3]
        )
        lines.append(f"✍️ 本周投稿最多：{top}")
    lines.append(f"📊 群内累计 {report['total']} 张")
    return "\n".join(lines)


def load_weekly_settings() -> dict:
    settings = dict(DEFAULT_WEEKLY_SETTINGS)
    try:
        raw = quote_db.load_doc(WEEKLY_SCOPE, WEEKLY_KEY)
    except Exception as exc:
        logger.warning(f"[quote] 读取周报设置失败：{exc}")
        raw = None
    if isinstance(raw, dict):
        settings.update({key: value for key, value in raw.items() if key in DEFAULT_WEEKLY_SETTINGS})
    groups: list = []
    for item in settings.get("groups") or []:
        if isinstance(item, dict):
            gid = str(item.get("group_id") or "").strip()
        else:
            gid = str(item or "").strip()
        if gid and gid not in groups:
            groups.append(gid)
    settings["groups"] = groups
    try:
        settings["weekday"] = max(1, min(7, int(settings.get("weekday") or 1)))
    except (TypeError, ValueError):
        settings["weekday"] = 1
    try:
        settings["hour"] = max(0, min(23, int(settings.get("hour") or 9)))
    except (TypeError, ValueError):
        settings["hour"] = 9
    settings["enabled"] = bool(settings.get("enabled"))
    settings["last_week"] = str(settings.get("last_week") or "")
    if not isinstance(settings.get("last_result"), dict):
        settings["last_result"] = {}
    return settings


def save_weekly_settings(patch) -> dict:
    settings = load_weekly_settings()
    patch = patch if isinstance(patch, dict) else {}
    if "enabled" in patch:
        settings["enabled"] = bool(patch.get("enabled"))
    if "weekday" in patch:
        try:
            settings["weekday"] = max(1, min(7, int(patch.get("weekday"))))
        except (TypeError, ValueError):
            raise ValueError("推送星期必须是 1-7")
    if "hour" in patch:
        try:
            settings["hour"] = max(0, min(23, int(patch.get("hour"))))
        except (TypeError, ValueError):
            raise ValueError("推送小时必须是 0-23")
    if "groups" in patch:
        raw = patch.get("groups")
        if not isinstance(raw, list):
            raise ValueError("groups 必须是数组")
        groups: list = []
        valid = set(group_ids())
        for item in raw:
            if isinstance(item, dict):
                gid = str(item.get("group_id") or "").strip()
            else:
                gid = str(item or "").strip()
            if not gid or gid not in valid or gid in groups:
                continue
            groups.append(gid)
        settings["groups"] = groups
    if "last_week" in patch:
        settings["last_week"] = str(patch.get("last_week") or "")
    if "last_result" in patch and isinstance(patch.get("last_result"), dict):
        settings["last_result"] = patch["last_result"]
    try:
        quote_db.save_doc(WEEKLY_SCOPE, WEEKLY_KEY, settings)
    except Exception as exc:
        logger.warning(f"[quote] 保存周报设置失败：{exc}")
    return settings


def week_key(now: float = None) -> str:
    start, _end, _label_start, _label_end = week_window(now)
    return time.strftime("%Y-W%W", time.localtime(start))


def due_groups(now: float = None) -> list:
    settings = load_weekly_settings()
    if not settings.get("enabled") or not settings.get("groups"):
        return []
    current = time.time() if now is None else float(now)
    local = time.localtime(current)
    if (local.tm_wday + 1) != settings["weekday"] or local.tm_hour < settings["hour"]:
        return []
    if settings.get("last_week") == week_key(current):
        return []
    return list(settings["groups"])
