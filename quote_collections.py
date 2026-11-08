"""专题合集：把语录按主题整理成合集，支持群内命令与 WebUI 管理。

合集数据存于 SQLite 表 collection，按群隔离；合集中的图片只记录文件名，
发送/展示时再校验文件仍然存在，删除语录不会破坏合集结构。
"""

from __future__ import annotations

import random
import threading
import time
import uuid

from astrbot import logger

import quote_db
from quote_core import group_dir, safe_image_name

COLLECTION_NAME_LIMIT = 30
COLLECTION_ITEMS_LIMIT = 300
COLLECTION_MAX_COUNT = 100

_LOCK = threading.RLock()


def _clean_name(raw) -> str:
    return " ".join(str(raw or "").split()).strip()[:COLLECTION_NAME_LIMIT]


def _clean_desc(raw) -> str:
    return " ".join(str(raw or "").split()).strip()[:200]


def _clean_ids(raw, group_id: str) -> list:
    directory = group_dir(group_id)
    result: list = []
    seen: set = set()
    for item in raw or []:
        try:
            name = safe_image_name(str(item))
        except ValueError:
            continue
        if name in seen:
            continue
        if not (directory / name).is_file():
            continue
        seen.add(name)
        result.append(name)
        if len(result) >= COLLECTION_ITEMS_LIMIT:
            break
    return result


def _normalize(group_id: str, collection_id: str, data) -> dict:
    data = data if isinstance(data, dict) else {}
    now = time.time()
    return {
        "collection_id": str(collection_id),
        "group_id": str(group_id),
        "name": _clean_name(data.get("name")) or "未命名合集",
        "desc": _clean_desc(data.get("desc")),
        "ids": _clean_ids(data.get("ids"), group_id),
        "creator": str(data.get("creator") or ""),
        "created_at": float(data.get("created_at") or now),
        "updated_at": float(data.get("updated_at") or now),
    }


def load_all(group_id: str) -> dict:
    gid = str(group_id or "").strip()
    if not gid:
        return {}
    try:
        raw = quote_db.load_collections(gid)
    except Exception as exc:
        logger.warning(f"[quote] 读取专题合集失败：{exc}")
        return {}
    result: dict = {}
    for collection_id, data in (raw or {}).items():
        cid = str(collection_id or "").strip()
        if not cid:
            continue
        result[cid] = _normalize(gid, cid, data)
    return result


def save(group_id: str, collection: dict) -> dict:
    gid = str(group_id or "").strip()
    cid = str((collection or {}).get("collection_id") or "").strip()
    if not gid or not cid:
        raise ValueError("缺少群号或合集 ID")
    normalized = _normalize(gid, cid, collection)
    quote_db.save_collection(gid, cid, normalized)
    return normalized


def get(group_id: str, collection_id: str):
    cid = str(collection_id or "").strip()
    if not cid:
        return None
    return load_all(group_id).get(cid)


def list_payload(group_id: str) -> list:
    rows = list(load_all(group_id).values())
    rows.sort(key=lambda row: -float(row.get("updated_at") or 0))
    payload = []
    for row in rows:
        ids = list(row.get("ids") or [])
        payload.append(
            {
                "collection_id": row["collection_id"],
                "group_id": row["group_id"],
                "name": row["name"],
                "desc": row["desc"],
                "count": len(ids),
                "cover": ids[:4],
                "creator": row.get("creator") or "",
                "created_at": row.get("created_at"),
                "updated_at": row.get("updated_at"),
            }
        )
    return payload


def find_by_name(group_id: str, keyword: str):
    keyword = str(keyword or "").strip()
    if not keyword:
        return None
    rows = list(load_all(group_id).values())
    rows.sort(key=lambda row: -float(row.get("updated_at") or 0))
    for exact in (True, False):
        for row in rows:
            if (row["name"] == keyword) if exact else (keyword in row["name"]):
                return row
    return None


def create(group_id: str, name: str, desc: str = "", ids=None, creator: str = "") -> dict:
    cleaned = _clean_name(name)
    if not cleaned:
        raise ValueError("合集名称不能为空")
    with _LOCK:
        existing = load_all(group_id)
        if len(existing) >= COLLECTION_MAX_COUNT:
            raise ValueError("合集数量已达上限")
        for row in existing.values():
            if row["name"] == cleaned:
                raise ValueError(f"合集「{cleaned}」已存在")
        collection_id = "col_" + uuid.uuid4().hex[:10]
        now = time.time()
        return save(
            group_id,
            {
                "collection_id": collection_id,
                "group_id": str(group_id),
                "name": cleaned,
                "desc": _clean_desc(desc),
                "ids": list(ids or []),
                "creator": str(creator or ""),
                "created_at": now,
                "updated_at": now,
            },
        )


def update(
    group_id: str,
    collection_id: str,
    *,
    name=None,
    desc=None,
    ids=None,
    add_ids=None,
    remove_ids=None,
) -> dict:
    with _LOCK:
        collection = get(group_id, collection_id)
        if collection is None:
            raise KeyError(collection_id)
        if name is not None:
            cleaned = _clean_name(name)
            if not cleaned:
                raise ValueError("合集名称不能为空")
            for row in load_all(group_id).values():
                if row["collection_id"] != collection["collection_id"] and row["name"] == cleaned:
                    raise ValueError(f"合集「{cleaned}」已存在")
            collection["name"] = cleaned
        if desc is not None:
            collection["desc"] = _clean_desc(desc)
        merged = list(collection.get("ids") or [])
        if ids is not None:
            merged = list(ids)
        if add_ids:
            merged.extend(list(add_ids))
        if remove_ids:
            drop = {str(item) for item in remove_ids}
            merged = [item for item in merged if item not in drop]
        collection["ids"] = _clean_ids(merged, group_id)
        collection["updated_at"] = time.time()
        return save(group_id, collection)


def delete(group_id: str, collection_id: str) -> bool:
    cid = str(collection_id or "").strip()
    if not cid:
        return False
    quote_db.delete_collection(str(group_id or ""), cid)
    return True


def valid_items(group_id: str, collection_id: str) -> list:
    collection = get(group_id, collection_id)
    if not collection:
        return []
    directory = group_dir(str(group_id))
    return [name for name in collection.get("ids") or [] if (directory / name).is_file()]


def text_list(group_id: str) -> str:
    rows = list_payload(group_id)
    if not rows:
        return "⭐本群还没有专题合集\n在管理页选中语录后点「加入合集」，即可把同类语录整理成主题合集"
    lines = ["⭐本群专题合集："]
    for index, row in enumerate(rows[:20], start=1):
        suffix = f"——{row['desc']}" if row.get("desc") else ""
        lines.append(f"{index}. {row['name']}（{row['count']} 张）{suffix}")
    lines.append("发送「/合集 名称」随机看几张，例如：/合集 乐子")
    return "\n".join(lines)


def pick_names(group_id: str, keyword: str, limit: int = 3):
    collection = find_by_name(group_id, keyword)
    if not collection:
        return "", []
    names = valid_items(group_id, collection["collection_id"])
    random.shuffle(names)
    return collection["name"], names[: max(1, int(limit))]
