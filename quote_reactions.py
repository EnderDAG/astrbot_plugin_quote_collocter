"""quote_reactions.py — 语录表情回应 / 引用评论采集与统计（v3.0.8）。

本模块负责三类数据的采集与聚合：

* ``sent_quote``：机器人发出的语录图片消息 ``message_id`` → (群号, 文件名)，
  供表情回应 / 引用评论关联到具体语录；
* ``quote_reaction``：群友对语录图片消息的表情回应，按 emoji 归并到情绪；
* ``quote_comment``：引用回复机器人语录图片消息的评论（评论人 / 内容 / 时间）；
* 对外提供周报、年度报告与管理页需要的聚合：
  「获赞最多语录」「获赞最多人物」「评论最多人物」，以及情绪分布。

设计说明：

* 只做数据库读写与纯 Python 聚合，不依赖 AstrBot 上下文，可在线程池中调用；
* 语录作者从 ``quote_meta`` 的 ``subject_user_id`` 读取（v2.6 起「语录里被拍的
  那个人」），显示名沿用 ``quote_identity.IDENTITY.summaries()`` 的称呼解析；
  旧语录没有归属人物时，人物维度不参与排名，语录维度仍正常统计；
* 表情回应的去重键是 (群号, 文件名, 用户, emoji)：同一人对同一张图反复点同一个
  表情只算一次（取消回应时删除该行）；
* 机器人发送消息时只保留最近 ``SENT_QUOTE_TTL`` 天的 message_id 映射，
  避免表无限增长。
"""

from __future__ import annotations

import time

from astrbot.api import logger

import quote_db
from quote_core import META
from quote_identity import IDENTITY, _clean_ai_name
from quote_semantic import SEMANTIC

EMOTION_OTHER = "其他"

# message_id 映射保留天数
SENT_QUOTE_TTL = 120 * 86400

# 语录内容片段在统计结果里的最大长度
CAPTION_LIMIT = 48

# 情绪展示顺序
EMOTION_ORDER = ["喜欢", "欢乐", "赞", "心动", "惊讶", "热烈", "伤感", "生气", EMOTION_OTHER]

# 完整情绪映射表：emoji → 情绪。未命中的表情统一归入「其他」。
EMOJI_EMOTION_TABLE = {
    # 喜欢
    "❤️": "喜欢",
    "❤": "喜欢",
    "💗": "喜欢",
    "💓": "喜欢",
    "💕": "喜欢",
    "💖": "喜欢",
    "💘": "喜欢",
    "💝": "喜欢",
    "🩷": "喜欢",
    "♥": "喜欢",
    # 欢乐
    "😆": "欢乐",
    "😄": "欢乐",
    "😂": "欢乐",
    "😁": "欢乐",
    "😀": "欢乐",
    "😃": "欢乐",
    "😊": "欢乐",
    "🤣": "欢乐",
    "😸": "欢乐",
    "😹": "欢乐",
    "😅": "欢乐",
    "🥳": "欢乐",
    "🤩": "欢乐",
    "🤗": "欢乐",
    "😋": "欢乐",
    "😛": "欢乐",
    "😜": "欢乐",
    "🤪": "欢乐",
    "🤭": "欢乐",
    "😏": "欢乐",
    "🙃": "欢乐",
    "😉": "欢乐",
    "😝": "欢乐",
    "🤡": "欢乐",
    # 赞
    "👍": "赞",
    "👏": "赞",
    "💯": "赞",
    "🙌": "赞",
    "👌": "赞",
    "🆗": "赞",
    "✅": "赞",
    "🫡": "赞",
    "🤝": "赞",
    "🙏": "赞",
    "🌟": "赞",
    # 心动
    "😍": "心动",
    "🥰": "心动",
    "😘": "心动",
    "😻": "心动",
    "💋": "心动",
    "💞": "心动",
    "💌": "心动",
    "😚": "心动",
    "😙": "心动",
    # 惊讶
    "😮": "惊讶",
    "😯": "惊讶",
    "😲": "惊讶",
    "😱": "惊讶",
    "😳": "惊讶",
    "🤯": "惊讶",
    # 热烈
    "🔥": "热烈",
    "💥": "热烈",
    "⚡": "热烈",
    "✨": "热烈",
    "🎉": "热烈",
    "💫": "热烈",
    # 伤感
    "😭": "伤感",
    "😢": "伤感",
    "😥": "伤感",
    "😓": "伤感",
    "🥲": "伤感",
    "💔": "伤感",
    "☹️": "伤感",
    "😔": "伤感",
    "😞": "伤感",
    "😿": "伤感",
    # 生气
    "😡": "生气",
    "😠": "生气",
    "🤬": "生气",
    "😤": "生气",
    "👿": "生气",
    "💢": "生气",
    "😾": "生气",
    "🖕": "生气",
}

# OneBot 表情回应里的 emoji_id 可能是 Unicode 码点字符串，先还原成 emoji 再查情绪表。
EMOJI_ID_MAP = {
    "10084": "❤️",
    "10083": "❤️",
    "128077": "👍",
    "128078": "👎",
    "128079": "👏",
    "128175": "💯",
    "128076": "👌",
    "128588": "🙌",
    "128591": "🙏",
    "128525": "😍",
    "129392": "🥰",
    "128536": "😘",
    "128514": "😂",
    "128512": "😀",
    "128513": "😁",
    "128516": "😄",
    "128517": "😆",
    "128518": "😅",
    "128521": "😉",
    "129315": "🤣",
    "129322": "🤣",
    "128557": "😭",
    "128546": "😢",
    "128545": "😠",
    "128544": "😡",
    "128548": "😤",
    "128558": "😮",
    "128559": "😯",
    "128560": "😲",
    "128561": "😱",
    "128563": "😳",
    "128293": "🔥",
    "128165": "💥",
    "127881": "🎉",
    "127775": "✨",
    "9989": "✅",
    "128064": "👀",
    "128169": "💩",
    "128148": "💔",
    "129300": "🤔",
    "128526": "😎",
    "129313": "🤡",
}


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------


def normalize_emoji(raw) -> str:
    """把 OneBot 的 emoji_id / emoji 文本规范化成可落库的 emoji 字符串。"""
    text = str(raw or "").strip()
    if not text:
        return ""
    mapped = EMOJI_ID_MAP.get(text)
    if mapped:
        return mapped
    return text


def emotion_for(emoji) -> str:
    """emoji → 情绪，未命中返回「其他」。"""
    text = normalize_emoji(emoji)
    if not text:
        return EMOTION_OTHER
    emotion = EMOJI_EMOTION_TABLE.get(text)
    if emotion:
        return emotion
    # 去掉变体选择符 FE0F 再试一次（❤️ / ❤、☹️ / ☹ 等）
    stripped = text.replace("\ufe0f", "")
    if stripped != text:
        emotion = EMOJI_EMOTION_TABLE.get(stripped)
        if emotion:
            return emotion
    return EMOTION_OTHER


def _summaries() -> dict:
    try:
        return IDENTITY.summaries() or {}
    except Exception as exc:  # pragma: no cover - 档案损坏时降级
        logger.warning(f"[quote] 读取人物称呼失败：{exc}")
        return {}


def _person_row(uid: str, summaries: dict) -> dict:
    """user_id → 统一的人物展示行。"""
    uid = str(uid or "").strip()
    who = summaries.get(uid) or {}
    person_id = str(who.get("person_id") or "") or uid
    name = _clean_ai_name(who.get("display_name")) or ""
    if not name:
        name = f"QQ {uid}" if uid else "未归属"
    return {
        "uid": uid,
        "person_id": person_id,
        "display_name": name,
        "avatar_sha": str(who.get("avatar_sha") or ""),
    }


def _meta_caches(gids) -> tuple:
    """按群加载一次 quote_meta / semantic_item，避免逐行查库。"""
    meta_cache: dict = {}
    sem_cache: dict = {}
    for gid in gids:
        try:
            meta_cache[gid] = META.load(gid).get("items") or {}
        except Exception:
            meta_cache[gid] = {}
        try:
            sem_cache[gid] = SEMANTIC.items(gid) or {}
        except Exception:
            sem_cache[gid] = {}
    return meta_cache, sem_cache


def _quote_author(gid: str, name: str, meta_cache: dict, sem_cache: dict) -> tuple:
    """返回 (作者 user_id, 语录内容片段)。"""
    info = (meta_cache.get(gid) or {}).get(name) or {}
    sem = (sem_cache.get(gid) or {}).get(name) or {}
    caption = str(sem.get("caption") or info.get("caption") or "").strip()
    author_uid = str(
        info.get("subject_user_id") or sem.get("user_id") or ""
    ).strip()
    return author_uid, caption


def _fetch_reactions(group_id: str = "", start=None, end=None) -> list:
    sql = (
        "SELECT group_id, filename, user_id, emoji, emotion, created_at "
        "FROM quote_reaction"
    )
    params: list = []
    where = []
    if group_id:
        where.append("group_id = ?")
        params.append(str(group_id))
    if start is not None:
        where.append("created_at >= ?")
        params.append(float(start))
    if end is not None:
        where.append("created_at < ?")
        params.append(float(end))
    if where:
        sql += " WHERE " + " AND ".join(where)
    try:
        conn = quote_db._connect()
        with quote_db._lock:
            rows = conn.execute(sql, params).fetchall()
    except Exception as exc:
        logger.warning(f"[quote] 读取表情回应失败：{exc}")
        return []
    return [dict(row) for row in rows]


def _fetch_comments(group_id: str = "", start=None, end=None) -> list:
    sql = (
        "SELECT group_id, filename, user_id, content, source, created_at "
        "FROM quote_comment"
    )
    params: list = []
    where = []
    if group_id:
        where.append("group_id = ?")
        params.append(str(group_id))
    if start is not None:
        where.append("created_at >= ?")
        params.append(float(start))
    if end is not None:
        where.append("created_at < ?")
        params.append(float(end))
    if where:
        sql += " WHERE " + " AND ".join(where)
    try:
        conn = quote_db._connect()
        with quote_db._lock:
            rows = conn.execute(sql, params).fetchall()
    except Exception as exc:
        logger.warning(f"[quote] 读取引用评论失败：{exc}")
        return []
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# 记录：message_id 映射 / 表情回应 / 引用评论
# ---------------------------------------------------------------------------


def record_sent(message_id, group_id: str, filename: str, created_at=None) -> bool:
    """记录一条机器人发出的语录消息（message_id → 群号 + 文件名）。"""
    mid = str(message_id or "").strip()
    gid = str(group_id or "").strip()
    name = str(filename or "").strip()
    if not mid or not gid or not name:
        return False
    now = float(created_at or time.time())
    try:
        conn = quote_db._connect()
        with quote_db._lock:
            conn.execute(
                "INSERT INTO sent_quote(message_id, group_id, filename, created_at) "
                "VALUES(?, ?, ?, ?) ON CONFLICT(message_id) DO NOTHING",
                (mid, gid, name, now),
            )
            conn.execute(
                "DELETE FROM sent_quote WHERE created_at < ?",
                (now - SENT_QUOTE_TTL,),
            )
            conn.commit()
    except Exception as exc:
        logger.warning(f"[quote] 记录语录消息映射失败：{exc}")
        return False
    return True


def lookup_sent(message_id) -> dict | None:
    """查询机器人发出的语录消息映射，未命中返回 None。"""
    mid = str(message_id or "").strip()
    if not mid:
        return None
    try:
        conn = quote_db._connect()
        with quote_db._lock:
            row = conn.execute(
                "SELECT message_id, group_id, filename, created_at "
                "FROM sent_quote WHERE message_id = ?",
                (mid,),
            ).fetchone()
    except Exception as exc:
        logger.warning(f"[quote] 查询语录消息映射失败：{exc}")
        return None
    return dict(row) if row else None


def record_reaction(
    group_id: str,
    filename: str,
    user_id: str,
    emoji: str,
    is_add: bool = True,
    emotion: str = "",
    created_at=None,
) -> bool:
    """写入 / 取消一条表情回应，返回是否产生实际变化。"""
    gid = str(group_id or "").strip()
    name = str(filename or "").strip()
    uid = str(user_id or "").strip()
    text = normalize_emoji(emoji)
    if not gid or not name or not uid or not text:
        return False
    mood = str(emotion or "").strip() or emotion_for(text)
    try:
        conn = quote_db._connect()
        with quote_db._lock:
            if is_add:
                cursor = conn.execute(
                    "INSERT INTO quote_reaction"
                    "(group_id, filename, user_id, emoji, emotion, created_at) "
                    "VALUES(?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(group_id, filename, user_id, emoji) DO NOTHING",
                    (gid, name, uid, text, mood, float(created_at or time.time())),
                )
            else:
                cursor = conn.execute(
                    "DELETE FROM quote_reaction WHERE group_id = ? AND filename = ? "
                    "AND user_id = ? AND emoji = ?",
                    (gid, name, uid, text),
                )
            conn.commit()
            changed = cursor.rowcount > 0
    except Exception as exc:
        logger.warning(f"[quote] 记录表情回应失败：{exc}")
        return False
    if changed:
        logger.debug(
            f"[quote] 表情回应{'新增' if is_add else '取消'}：群 {gid} / {name} / "
            f"{uid} / {text}（{mood}）"
        )
    return changed


def record_comment(
    group_id: str,
    filename: str,
    user_id: str,
    content: str,
    source: str = "reply",
    created_at=None,
) -> int:
    """记录一条引用评论，返回新行 id（重复 / 空内容返回 0）。"""
    gid = str(group_id or "").strip()
    name = str(filename or "").strip()
    uid = str(user_id or "").strip()
    text = str(content or "").strip()
    if not gid or not name or not uid or not text:
        return 0
    now = float(created_at or time.time())
    try:
        conn = quote_db._connect()
        with quote_db._lock:
            # 同一个人 30 秒内对同一条语录的相同内容只记一次，避免协议端重发。
            row = conn.execute(
                "SELECT id FROM quote_comment WHERE group_id = ? AND filename = ? "
                "AND user_id = ? AND content = ? AND created_at >= ?",
                (gid, name, uid, text, now - 30),
            ).fetchone()
            if row:
                return 0
            cursor = conn.execute(
                "INSERT INTO quote_comment"
                "(group_id, filename, user_id, content, source, created_at) "
                "VALUES(?, ?, ?, ?, ?, ?)",
                (gid, name, uid, text, str(source or "reply"), now),
            )
            conn.commit()
            new_id = int(cursor.lastrowid or 0)
    except Exception as exc:
        logger.warning(f"[quote] 记录引用评论失败：{exc}")
        return 0
    if new_id:
        logger.info(f"[quote] 收到语录评论：群 {gid} / {name} / {uid} / {text[:40]}")
    return new_id


# ---------------------------------------------------------------------------
# OneBot 事件解析（main.py 群消息处理器调用）
# ---------------------------------------------------------------------------


def handle_emoji_notice(raw_message) -> int:
    """处理 OneBot ``group_msg_emoji_like`` notice，返回写入 / 删除的条数。"""
    if not isinstance(raw_message, dict):
        return 0
    if str(raw_message.get("notice_type") or "") != "group_msg_emoji_like":
        return 0
    message_id = str(raw_message.get("message_id") or "").strip()
    user_id = str(raw_message.get("user_id") or "").strip()
    self_id = str(raw_message.get("self_id") or "").strip()
    if not message_id or not user_id or user_id == self_id:
        return 0
    sent = lookup_sent(message_id)
    if not sent:
        return 0
    gid = str(sent.get("group_id") or raw_message.get("group_id") or "").strip()
    filename = str(sent.get("filename") or "").strip()
    if not gid or not filename:
        return 0
    is_add = bool(raw_message.get("is_add", True))
    likes = raw_message.get("likes") or raw_message.get("like") or []
    if isinstance(likes, dict):
        likes = [likes]
    changed = 0
    for like in likes:
        if not isinstance(like, dict):
            continue
        emoji = normalize_emoji(like.get("emoji_id") or like.get("emoji") or "")
        if not emoji:
            continue
        if record_reaction(gid, filename, user_id, emoji, is_add=is_add):
            changed += 1
    return changed


def extract_reply_quote(message_obj) -> tuple:
    """从消息组件里取出 (被引用消息 id, 纯文本内容)，无引用返回 ("", "")。"""
    target = ""
    parts: list = []
    components = getattr(message_obj, "message", None) or []
    for component in components:
        kind = type(component).__name__
        if kind == "Reply" and not target:
            target = str(getattr(component, "id", "") or "").strip()
        elif kind == "Plain":
            parts.append(str(getattr(component, "text", "") or ""))
    return target, "".join(parts).strip()


def handle_reply_message(message_obj, user_id: str) -> bool:
    """命中「引用回复机器人语录图片消息」时记录评论，返回是否命中。"""
    target, text = extract_reply_quote(message_obj)
    if not target:
        return False
    sent = lookup_sent(target)
    if not sent:
        return False
    gid = str(sent.get("group_id") or "").strip()
    filename = str(sent.get("filename") or "").strip()
    if not gid or not filename:
        return False
    if text:
        record_comment(gid, filename, user_id, text, "reply")
    return True


# ---------------------------------------------------------------------------
# 聚合统计（周报 / 年度报告 / 管理页共用）
# ---------------------------------------------------------------------------


def _aggregate(
    group_id: str = "",
    start=None,
    end=None,
    limit: int = 5,
) -> dict:
    """聚合表情回应与评论数据，产出三项排行与情绪分布。"""
    gid_filter = str(group_id or "").strip()
    try:
        limit = max(1, min(50, int(limit or 5)))
    except (TypeError, ValueError):
        limit = 5
    reaction_rows = _fetch_reactions(gid_filter, start, end)
    comment_rows = _fetch_comments(gid_filter, start, end)

    by_quote: dict = {}
    by_emoji: dict = {}
    by_emotion: dict = {}
    for row in reaction_rows:
        gid = str(row.get("group_id") or "")
        name = str(row.get("filename") or "")
        if not gid or not name:
            continue
        key = (gid, name)
        by_quote[key] = by_quote.get(key, 0) + 1
        emoji = str(row.get("emoji") or "") or EMOTION_OTHER
        by_emoji[emoji] = by_emoji.get(emoji, 0) + 1
        emotion = str(row.get("emotion") or "") or EMOTION_OTHER
        by_emotion[emotion] = by_emotion.get(emotion, 0) + 1

    comment_by_user: dict = {}
    comment_by_quote: dict = {}
    for row in comment_rows:
        gid = str(row.get("group_id") or "")
        name = str(row.get("filename") or "")
        uid = str(row.get("user_id") or "").strip()
        if gid and name:
            key = (gid, name)
            comment_by_quote[key] = comment_by_quote.get(key, 0) + 1
        if uid:
            comment_by_user[uid] = comment_by_user.get(uid, 0) + 1

    gids = {key[0] for key in by_quote} | {key[0] for key in comment_by_quote}
    meta_cache, sem_cache = _meta_caches(sorted(gids))
    summaries = _summaries()

    # 获赞最多语录（附带作者与内容片段）
    quote_rows: list = []
    author_counts: dict = {}
    for (gid, name), count in sorted(
        by_quote.items(), key=lambda kv: (-kv[1], kv[0])
    )[:limit]:
        author_uid, caption = _quote_author(gid, name, meta_cache, sem_cache)
        author = _person_row(author_uid, summaries) if author_uid else {
            "uid": "",
            "person_id": "",
            "display_name": "未归属",
            "avatar_sha": "",
        }
        quote_rows.append(
            {
                "group_id": gid,
                "filename": name,
                "caption": caption[:CAPTION_LIMIT],
                "count": count,
                "author": author["display_name"],
                "person_id": author["person_id"],
                "avatar_sha": author["avatar_sha"],
            }
        )
    for (gid, name), count in by_quote.items():
        author_uid, _caption = _quote_author(gid, name, meta_cache, sem_cache)
        if author_uid:
            author_counts[author_uid] = author_counts.get(author_uid, 0) + count

    # 获赞最多人物：按「语录归属人物」聚合，同一人的多个 QQ 号合并
    by_person: dict = {}
    for uid, count in author_counts.items():
        person = _person_row(uid, summaries)
        pid = person["person_id"] or uid
        row = by_person.setdefault(
            pid,
            {
                "person_id": pid,
                "display_name": person["display_name"],
                "avatar_sha": person["avatar_sha"],
                "count": 0,
            },
        )
        row["count"] += count
        if not row.get("avatar_sha"):
            row["avatar_sha"] = person["avatar_sha"]
    person_rows = sorted(
        by_person.values(), key=lambda item: (-item["count"], item["display_name"])
    )[:limit]

    # 评论最多人物
    commenter_rows = []
    for uid, count in comment_by_user.items():
        person = _person_row(uid, summaries)
        commenter_rows.append(
            {
                "uid": uid,
                "person_id": person["person_id"],
                "display_name": person["display_name"],
                "avatar_sha": person["avatar_sha"],
                "count": count,
            }
        )
    commenter_rows.sort(key=lambda item: (-item["count"], item["display_name"]))
    commenter_rows = commenter_rows[:limit]

    emotion_rows = [
        {"emotion": emotion, "count": by_emotion[emotion]}
        for emotion in EMOTION_ORDER
        if by_emotion.get(emotion)
    ]
    emoji_rows = [
        {"emoji": emoji, "emotion": emotion_for(emoji), "count": count}
        for emoji, count in sorted(
            by_emoji.items(), key=lambda kv: (-kv[1], kv[0])
        )[: max(limit, 8)]
    ]
    commented_rows = [
        {
            "group_id": gid,
            "filename": name,
            "count": count,
        }
        for (gid, name), count in sorted(
            comment_by_quote.items(), key=lambda kv: (-kv[1], kv[0])
        )[:limit]
    ]

    return {
        "reactions": len(reaction_rows),
        "comments": len(comment_rows),
        "emotions": emotion_rows,
        "emoji": emoji_rows,
        "top_quotes": quote_rows,
        "top_persons": person_rows,
        "top_commenters": commenter_rows,
        "top_commented_quotes": commented_rows,
    }


def stats_sync(group_id: str = "", top: int = 5) -> dict:
    """管理页 / 群统计：全部时间范围的表情回应与评论聚合。"""
    return _aggregate(group_id, None, None, top)


def window_summary_sync(
    group_id: str, start: float, end: float, limit: int = 3
) -> dict:
    """周报：指定时间窗口内的表情回应与评论聚合。"""
    return _aggregate(group_id, start, end, limit)


def annual_summary_sync(year: int = 0, group_id: str = "", limit: int = 3) -> dict:
    """年度报告：指定年份内的表情回应与评论聚合。"""
    try:
        year = int(year or time.localtime().tm_year)
    except (TypeError, ValueError):
        year = time.localtime().tm_year
    start = time.mktime((year, 1, 1, 0, 0, 0, 0, 0, -1))
    end = time.mktime((year + 1, 1, 1, 0, 0, 0, 0, 0, -1))
    result = _aggregate(group_id, start, end, limit)
    result["year"] = year
    return result
