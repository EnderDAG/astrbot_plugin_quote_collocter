"""群内命令助手：随机 / 今日 / 语义检索 / 人物 / 合集 / 周报的取数与文案。"""

from __future__ import annotations

import random
import time

import quote_db  # noqa: F401  （保证初始化数据库）
from quote_collections import pick_names as collection_pick
from quote_collections import text_list as collection_text
from quote_core import META, group_dir, list_image_files
from quote_identity import IDENTITY
from quote_recall import recall_person_quotes_sync
from quote_semantic import SEMANTIC, _cosine
from quote_weekly import report_text as weekly_text

COMMAND_HELP = """⭐ 语录指令：
/语录 —— 随机来一张
/抽语录 [N] —— 随机抽 1-3 张
/今日语录 —— 看看今天新增了哪些
/语录查 <关键词> —— 按语义搜索语录（需已语义化）
/语录人物 <昵称或QQ> —— 看某人的语录
/合集 —— 查看本群专题合集
/合集 <名称> —— 随机看几张合集语录
/语录排行 [N] —— 本群语录数量与投稿排名
/语录排行 本月 [N] —— 本月语录数量与投稿排名（也可写「上月」）
/周报 —— 本周语录周报
/年度报告 [@某人|昵称] [年份] —— 生成年度语录报告（Wrapped 风格长图）
/限制级 开 / 关 —— 本群是否允许发送限制级语录（默认关）\n/限制级 —— 随机来一张限制级（需先开启）\n/语录帮助 —— 显示本帮助"""


def help_text() -> str:
    return COMMAND_HELP


def _names(group_id: str) -> list:
    try:
        return [item["name"] for item in list_image_files(group_id)]
    except Exception:
        return []


def _existing(group_id: str, name: str) -> bool:
    try:
        return (group_dir(group_id) / name).is_file()
    except Exception:
        return False


def random_names(group_id: str, count: int = 1) -> list:
    names = _names(group_id)
    if not names:
        return []
    count = max(1, min(3, int(count or 1)))
    if len(names) <= count:
        return list(names)
    return random.sample(names, count)


def today_names(group_id: str, limit: int = 3) -> list:
    names = _names(group_id)
    if not names:
        return []
    try:
        meta_items = META.load(group_id)["items"]
    except Exception:
        meta_items = {}
    now = time.time()
    local = time.localtime(now)
    midnight = time.mktime(
        (local.tm_year, local.tm_mon, local.tm_mday, 0, 0, 0, 0, 0, -1)
    )
    rows = []
    for name in names:
        try:
            ts = float((meta_items.get(name) or {}).get("ts") or 0.0)
        except (TypeError, ValueError):
            ts = 0.0
        if ts >= midnight or _ts_from_name(name) >= midnight:
            rows.append((_ts_from_name(name) or ts, name))
    rows.sort(key=lambda pair: pair[0], reverse=True)
    return [name for _ts, name in rows[: max(1, int(limit))]]


def _ts_from_name(name: str) -> float:
    try:
        from quote_core import _ts_from_name as ts_from_name

        return float(ts_from_name(name, 0.0) or 0.0)
    except Exception:
        return 0.0


def person_quotes(group_id: str, keyword: str, limit: int = 3) -> tuple:
    keyword = str(keyword or "").strip()
    if not keyword:
        return "", []
    try:
        rows = IDENTITY.resolve_text_people(keyword, group_id, 4)
    except Exception:
        rows = []
    if not rows:
        return "", []
    summaries = {}
    try:
        summaries = IDENTITY.summaries()
    except Exception:
        summaries = {}
    person = rows[0] or {}
    uid = str(person.get("user_id") or person.get("matched_user_id") or "")
    pid = str(person.get("person_id") or "")
    name = ""
    if uid:
        name = str((summaries.get(uid) or {}).get("display_name") or "")
    if not name:
        name = str(person.get("display_name") or person.get("name") or "").strip() or "群友"
    uids = [
        row_uid
        for row_uid, row in (summaries or {}).items()
        if str((row or {}).get("person_id") or "") == pid
    ]
    if not uids and uid:
        uids = [uid]
    try:
        candidates = recall_person_quotes_sync(group_id, uids, limit=max(1, int(limit)))
    except Exception:
        candidates = []
    names = [str(row.get("id") or "") for row in candidates if row.get("id")]
    names = [name_ for name_ in names if _existing(group_id, name_)]
    return name, names


def semantic_names(group_id: str, query_vector: list, limit: int = 3, min_score: float = 0.15) -> list:
    if not query_vector:
        return []
    try:
        items = SEMANTIC.items(group_id)
    except Exception:
        items = {}
    scored = []
    for name, entry in (items or {}).items():
        if not isinstance(entry, dict):
            continue
        vector = entry.get("vector") or []
        if not vector:
            continue
        if not _existing(group_id, str(name)):
            continue
        try:
            score = _cosine(query_vector, vector)
        except Exception:
            continue
        if score >= float(min_score):
            scored.append((score, str(name)))
    scored.sort(key=lambda pair: -pair[0])
    return [name for _score, name in scored[: max(1, int(limit))]]


def collection_names(group_id: str, keyword: str, limit: int = 3) -> tuple:
    return collection_pick(group_id, keyword, limit)


def quote_caption(group_id: str, name: str) -> str:
    try:
        entry = SEMANTIC.get(group_id, name) or {}
    except Exception:
        entry = {}
    caption = str(entry.get("caption") or "").strip()
    if caption:
        return caption[:60]
    try:
        info = META.load(group_id)["items"].get(name) or {}
    except Exception:
        info = {}
    return str(info.get("nickname") or "").strip()[:30]


def weekly(group_id: str) -> str:
    return weekly_text(group_id)
