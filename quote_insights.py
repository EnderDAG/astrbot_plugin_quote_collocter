"""语录数据可视化：时段热力图、发帖日历、人物时间线与年度报告数据（v2.14.0）。

本模块只做纯数据聚合，不直接依赖 AstrBot 上下文，便于在后台线程中调用。
"""

from __future__ import annotations

import time

from astrbot.api import logger

from quote_core import META, group_ids, list_image_files
from quote_identity import IDENTITY
from quote_semantic import SEMANTIC

DAY = 86400
WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _iter_quotes(group_id: str = ""):
    """遍历语录，产出 (group_id, name, info, sem, ts)。"""
    groups = [group_id] if group_id else group_ids()
    for gid in groups:
        try:
            files = list_image_files(gid)
            meta = META.load(gid).get("items") or {}
            semantic = SEMANTIC.items(gid) or {}
        except Exception as exc:  # pragma: no cover - 读盘异常时跳过该群
            logger.warning(f"[quote] 可视化读取群 {gid} 失败：{exc}")
            continue
        for item in files:
            info = meta.get(item["name"]) or {}
            sem = semantic.get(item["name"]) or {}
            try:
                ts = float(info.get("ts") or item.get("ts") or 0)
            except (TypeError, ValueError):
                ts = 0.0
            yield gid, item["name"], info, sem, ts


def heatmap_sync(group_id: str = "", days: int = 365, now: float = None) -> dict:
    """按「星期 × 小时」统计语录发布分布，并给出逐日日历。"""
    current = time.time() if now is None else float(now)
    try:
        days = max(1, min(3650, int(days or 365)))
    except (TypeError, ValueError):
        days = 365
    since = current - days * DAY
    hours = [[0] * 7 for _ in range(24)]  # hours[hour][weekday], weekday 0=周一
    per_day: dict[str, int] = {}
    per_group: dict[str, int] = {}
    total = 0
    for gid, _name, _info, _sem, ts in _iter_quotes(group_id):
        if not ts or ts < since:
            continue
        local = time.localtime(ts)
        hours[local.tm_hour][local.tm_wday] += 1
        key = time.strftime("%Y-%m-%d", local)
        per_day[key] = per_day.get(key, 0) + 1
        per_group[gid] = per_group.get(gid, 0) + 1
        total += 1
    hour_sums = [sum(row) for row in hours]
    weekday_sums = [sum(hours[h][w] for h in range(24)) for w in range(7)]
    peak_hour = max(range(24), key=lambda h: hour_sums[h]) if total else 0
    peak_weekday = max(range(7), key=lambda w: weekday_sums[w]) if total else 0
    calendar = [{"date": key, "count": per_day[key]} for key in sorted(per_day)]
    return {
        "group_id": group_id,
        "days": days,
        "since": since,
        "total": total,
        "hours": hours,
        "hour_sums": hour_sums,
        "weekday_sums": weekday_sums,
        "weekdays": WEEKDAYS,
        "peak_hour": peak_hour,
        "peak_weekday": peak_weekday,
        "calendar": calendar,
        "per_group": [
            {"group_id": gid, "count": count}
            for gid, count in sorted(per_group.items(), key=lambda kv: -kv[1])
        ],
        "max_day": max((row["count"] for row in calendar), default=0),
        "avg_day": round(total / days, 3) if days else 0,
    }


def person_timeline_sync(pid: str, group_id: str = "") -> dict:
    """某个 pid 的语录时间线：逐月数量、首次/最近时间、群分布、标签。"""
    pid = str(pid or "").strip()
    if not pid:
        raise ValueError("缺少 pid")
    detail = IDENTITY.detail("", pid)
    uids = {str(row.get("user_id") or "") for row in detail.get("users") or []}
    if not uids:
        raise ValueError("该人物没有关联 QQ 号")
    display_name = ""
    avatar_sha = ""
    for row in detail.get("users") or []:
        if not avatar_sha:
            avatar_sha = str(row.get("current_avatar") or "")
    summaries = IDENTITY.summaries()
    for uid in uids:
        summary = summaries.get(uid) or {}
        if summary.get("display_name") and not display_name:
            display_name = summary["display_name"]
        if summary.get("avatar_sha") and not avatar_sha:
            avatar_sha = summary["avatar_sha"]
    months: dict[str, int] = {}
    by_group: dict[str, int] = {}
    tags: dict[str, int] = {}
    first_ts = 0.0
    last_ts = 0.0
    total = 0
    for gid, _name, info, sem, ts in _iter_quotes(group_id):
        if str(info.get("subject_user_id") or "") not in uids:
            continue
        total += 1
        if ts:
            first_ts = ts if not first_ts else min(first_ts, ts)
            last_ts = max(last_ts, ts)
            months[time.strftime("%Y-%m", time.localtime(ts))] = (
                months.get(time.strftime("%Y-%m", time.localtime(ts)), 0) + 1
            )
        by_group[gid] = by_group.get(gid, 0) + 1
        for tag in (info.get("tags") or sem.get("tags") or []):
            key = str(tag).strip()
            if key:
                tags[key] = tags.get(key, 0) + 1
    month_rows = [{"month": key, "count": months[key]} for key in sorted(months)]
    return {
        "pid": pid,
        "person_id": detail.get("person_id") or "",
        "display_name": display_name,
        "avatar_sha": avatar_sha,
        "user_ids": sorted(uids),
        "total": total,
        "first_ts": first_ts,
        "last_ts": last_ts,
        "months": month_rows,
        "by_group": [
            {"group_id": gid, "count": count}
            for gid, count in sorted(by_group.items(), key=lambda kv: -kv[1])
        ],
        "top_tags": [
            {"tag": tag, "count": count}
            for tag, count in sorted(tags.items(), key=lambda kv: -kv[1])[:8]
        ],
    }


def _year_of(ts: float) -> int:
    return time.localtime(ts).tm_year if ts else 0


def annual_report_sync(pid: str, year: int = 0, group_id: str = "") -> dict:
    """生成某个人的年度报告数据（默认最近一年）。"""
    pid = str(pid or "").strip()
    if not pid:
        raise ValueError("缺少 pid")
    detail = IDENTITY.detail("", pid)
    uids = {str(row.get("user_id") or "") for row in detail.get("users") or []}
    summaries = IDENTITY.summaries()
    display_name = ""
    avatar_sha = ""
    for uid in sorted(uids):
        summary = summaries.get(uid) or {}
        display_name = display_name or summary.get("display_name") or ""
        avatar_sha = avatar_sha or summary.get("avatar_sha") or ""
    now = time.time()
    year = int(year or time.localtime(now).tm_year)
    start = time.mktime((year, 1, 1, 0, 0, 0, 0, 0, -1))
    end = time.mktime((year + 1, 1, 1, 0, 0, 0, 0, 0, -1))

    per_person_year: dict[str, int] = {}
    total_year = 0
    mine_month = [0] * 12
    mine_hour = [0] * 24
    mine_weekday = [0] * 7
    tags: dict[str, int] = {}
    submitters: dict[str, int] = {}
    groups: dict[str, int] = {}
    captions: list[dict] = []
    mine_total = 0
    mine_first = 0.0
    mine_last = 0.0
    subject_by_pid: dict[str, str] = {}
    for uid, summary in summaries.items():
        person_id = str(summary.get("person_id") or "")
        if person_id:
            subject_by_pid[uid] = person_id

    for gid, _name, info, sem, ts in _iter_quotes(group_id):
        if not ts or ts < start or ts >= end:
            continue
        total_year += 1
        subject_uid = str(info.get("subject_user_id") or "")
        if subject_uid:
            key = subject_by_pid.get(subject_uid) or subject_uid
            per_person_year[key] = per_person_year.get(key, 0) + 1
        if subject_uid not in uids:
            continue
        mine_total += 1
        local = time.localtime(ts)
        mine_month[local.tm_mon - 1] += 1
        mine_hour[local.tm_hour] += 1
        mine_weekday[local.tm_wday] += 1
        mine_first = ts if not mine_first else min(mine_first, ts)
        mine_last = max(mine_last, ts)
        groups[gid] = groups.get(gid, 0) + 1
        for tag in (info.get("tags") or sem.get("tags") or []):
            key = str(tag).strip()
            if key:
                tags[key] = tags.get(key, 0) + 1
        submitter = str(info.get("nickname") or "").strip()
        if submitter:
            submitters[submitter] = submitters.get(submitter, 0) + 1
        caption = str(sem.get("caption") or info.get("caption") or "").strip()
        if caption:
            captions.append(
                {
                    "name": _name,
                    "group_id": gid,
                    "caption": caption[:120],
                    "tags": list((info.get("tags") or sem.get("tags") or []))[:3],
                    "ts": ts,
                }
            )

    ranked = sorted(per_person_year.items(), key=lambda kv: -kv[1])
    rank = 0
    for index, (key, _count) in enumerate(ranked, 1):
        if key == pid or key == str(detail.get("person_id") or ""):
            rank = index
            break
    top_month = max(range(12), key=lambda m: mine_month[m]) if mine_total else 0
    top_hour = max(range(24), key=lambda h: mine_hour[h]) if mine_total else 0
    top_tag_rows = [
        {"tag": tag, "count": count}
        for tag, count in sorted(tags.items(), key=lambda kv: -kv[1])[:5]
    ]
    submitter_rows = [
        {"name": name, "count": count}
        for name, count in sorted(submitters.items(), key=lambda kv: -kv[1])[:5]
    ]
    captions.sort(key=lambda row: (row["ts"], -len(row["caption"])))
    highlights = captions[-3:] if len(captions) > 3 else captions
    return {
        "pid": pid,
        "person_id": detail.get("person_id") or "",
        "year": year,
        "display_name": display_name,
        "avatar_sha": avatar_sha,
        "group_id": group_id,
        "total": mine_total,
        "group_total": total_year,
        "share": round(mine_total / total_year, 4) if total_year else 0,
        "rank": rank,
        "ranked_total": len(ranked),
        "months": mine_month,
        "hours": mine_hour,
        "weekdays": mine_weekday,
        "top_month": top_month,
        "top_hour": top_hour,
        "top_tags": top_tag_rows,
        "submitters": submitter_rows,
        "groups": [
            {"group_id": gid, "count": count}
            for gid, count in sorted(groups.items(), key=lambda kv: -kv[1])
        ],
        "first_ts": mine_first,
        "last_ts": mine_last,
        "captions": highlights,
    }
