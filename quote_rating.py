"""限制级语录识别：按关键词给语录打「限制级 / 非限制级」标记。"""

from __future__ import annotations

from typing import Iterable

from quote_core import META, group_ids, list_image_files
from quote_semantic import SEMANTIC

from astrbot.api import logger

RESTRICTED_VERSION = 2

# 高置信度：出现即判为限制级
STRONG_WORDS: tuple[str, ...] = (
    "露骨", "擦边", "色情", "黄图", "裸", "乳头", "奶子", "下体",
    "裆", "丁丁", "阴茎", "阴道", "射精", "撸", "手淫", "自慰", "做爱",
    "约炮", "性交", "性行为", "肛", "调教", "舔", "淫", "骚", "妓",
    "强奸", "轮奸", "精液", "前列腺", "排泄", "黄腔", "荤段子", "文爱",
)

# 中置信度：出现两个及以上才判为限制级
MEDIUM_WORDS: tuple[str, ...] = (
    "变态", "恶心", "恶臭", "臭", "屁", "光着", "脱", "屎", "尿", "胸部",
    "勾引", "发情", "欲望", "骚气", "污", "荤", "开车", "涩",
)

STRONG_WEIGHT = 2
MEDIUM_WEIGHT = 1
RESTRICTED_THRESHOLD = 2


def _hits(text: str, words: Iterable[str]) -> list[str]:
    return [w for w in words if w and w in text]


def classify(
    caption: str = "",
    tags: Iterable[str] | None = None,
    visible_text: str = "",
    tone: str = "",
) -> dict:
    """根据文案/标签/可见文字判断是否限制级。"""
    parts = [str(caption or ""), str(visible_text or ""), str(tone or "")]
    parts.extend(str(tag) for tag in (tags or []))
    text = " ".join(parts)
    strong = _hits(text, STRONG_WORDS)
    medium = _hits(text, MEDIUM_WORDS)
    score = len(strong) * STRONG_WEIGHT + len(medium) * MEDIUM_WEIGHT
    restricted = score >= RESTRICTED_THRESHOLD
    reason = ""
    if strong:
        reason = "命中：" + "、".join(strong[:3])
    elif medium:
        reason = "疑似：" + "、".join(medium[:3])
    return {
        "restricted": restricted,
        "score": score,
        "reason": reason,
        "strong": strong[:5],
        "medium": medium[:5],
    }


def classify_meta(info: dict, sem: dict) -> dict:
    info = info or {}
    sem = sem or {}
    tags = info.get("tags") or sem.get("tags") or []
    return classify(
        caption=str(info.get("caption") or sem.get("caption") or ""),
        tags=tags,
        visible_text=str(sem.get("visible_text") or ""),
        tone=str(sem.get("tone") or ""),
    )


def rating_map_sync(group_id: str) -> dict:
    """返回 {文件名: 是否限制级}。"""
    try:
        meta = (META.load(group_id) or {}).get("items") or {}
    except Exception:
        return {}
    result = {}
    for name, info in meta.items():
        if isinstance(info, dict) and info.get("restricted"):
            result[str(name)] = True
    return result


def public_names_sync(group_id: str) -> list:
    """本群所有非限制级语录文件名。"""
    restricted = rating_map_sync(group_id)
    return [
        str(item.get("name"))
        for item in list_image_files(group_id)
        if not restricted.get(str(item.get("name") or ""))
    ]


def restricted_names_sync(group_id: str) -> list:
    """本群所有限制级语录文件名。"""
    restricted = rating_map_sync(group_id)
    return [
        str(item.get("name"))
        for item in list_image_files(group_id)
        if restricted.get(str(item.get("name") or ""))
    ]


def apply_auto_rating_sync(group_id: str = "", overwrite: bool = False) -> dict:
    """批量识别未标记语录；manual 标记默认不覆盖。"""
    targets = [str(group_id)] if group_id else list(group_ids())
    scanned = updated = restricted_count = 0
    per_group: dict = {}
    for gid in targets:
        try:
            files = list_image_files(gid)
            meta = (META.load(gid) or {}).get("items") or {}
            semantic = SEMANTIC.items(gid) or {}
        except Exception as exc:
            logger.warning(f"[quote] 限制级识别读取群 {gid} 失败：{exc}")
            continue
        g_updated = g_restricted = 0
        for item in files:
            name = str(item.get("name") or "")
            scanned += 1
            info = meta.get(name) or {}
            sem = semantic.get(name) or {}
            if str(info.get("rating_source") or "") == "manual" and not overwrite:
                if info.get("restricted"):
                    restricted_count += 1
                    g_restricted += 1
                continue
            verdict = classify_meta(info, sem)
            new_value = bool(verdict["restricted"])
            if new_value:
                restricted_count += 1
                g_restricted += 1
            if bool(info.get("restricted")) != new_value or "restricted" not in info:
                try:
                    META.update(
                        gid,
                        name,
                        {
                            "restricted": new_value,
                            "rating_source": "auto",
                            "rating_reason": str(verdict["reason"])[:80],
                        },
                    )
                    updated += 1
                    g_updated += 1
                except Exception as exc:
                    logger.warning(f"[quote] 写入限制级标记失败 {gid}/{name}：{exc}")
        per_group[gid] = {
            "updated": g_updated,
            "restricted": g_restricted,
            "total": len(files),
        }
    logger.info(
        f"[quote] 限制级识别完成：扫描 {scanned}、更新 {updated}、限制级 {restricted_count}"
    )
    return {
        "scanned": scanned,
        "updated": updated,
        "restricted": restricted_count,
        "unrestricted": max(0, scanned - restricted_count),
        "groups": per_group,
    }


def stats_sync(group_id: str = "") -> dict:
    targets = [str(group_id)] if group_id else list(group_ids())
    groups = []
    total = total_restricted = 0
    for gid in targets:
        try:
            files = list_image_files(gid)
            meta = (META.load(gid) or {}).get("items") or {}
        except Exception:
            continue
        count = len(files)
        restricted = sum(
            1
            for item in files
            if (meta.get(str(item.get("name") or "")) or {}).get("restricted")
        )
        total += count
        total_restricted += restricted
        groups.append(
            {
                "group_id": gid,
                "total": count,
                "restricted": restricted,
                "unrestricted": count - restricted,
            }
        )
    return {
        "total": total,
        "restricted": total_restricted,
        "unrestricted": max(0, total - total_restricted),
        "groups": groups,
    }
