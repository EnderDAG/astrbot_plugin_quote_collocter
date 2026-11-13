"""协作维护服务（v2.19.0）。

为不想开放完整管理页的群友提供一层独立的、邀请制的维护界面：
- 归属（把语录绑到人物档案）
- 限制级标记
- 语义管理（查看待处理/失败，重试单条或少量）
- 审计日志（谁在什么时候改了什么）

实现要点：
- 独立 aiohttp 服务，默认只监听 127.0.0.1:6190，由 nginx 反代到 /quote-collab/
- 邀请 token 绑定 QQ 与群，默认 7 天过期，可吊销；会话用 HMAC 签名 cookie
- 只暴露白名单字段与白名单动作，所有写操作记审计
- 简单限流，防止脚本刷

本模块不导入 main.py，避免循环依赖。
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any

from aiohttp import web

import quote_db
import quote_rating
from quote_core import (
    META,
    group_dir,
    group_ids,
    list_image_files,
    load_settings,
)
from quote_identity import IDENTITY
from quote_semantic import SEMANTIC, SEMANTIC_RUNNER, resolve_caption_provider_id, semantic_status_sync

from astrbot.api import logger

ROLES = ("maintainer",)
ROLE_LABELS = {"maintainer": "维护员"}
LEGACY_ROLES = ("editor", "curator")


def normalize_role(role: str) -> str:
    """v2.20.3 起「编辑」「管理」合并为「维护员」，任何输入都归一到维护员。"""
    return "maintainer"
TOKEN_HOURS = 168
SESSION_HOURS = 24
MAX_BODY = 64 * 1024
PAGE_MAX = 30
SEMANTIC_BATCH_MAX = 20

WRITE_LIMIT_PER_MIN = 40
READ_LIMIT_PER_MIN = 240

_HTML_PATH = Path(__file__).resolve().parent / "collab" / "index.html"

_ctx: Any = None
_runner: web.AppRunner | None = None
_site: web.TCPSite | None = None
_secret: str = ""
_rate: dict[str, list[float]] = {}


# --------------------------------------------------------------------------
# 数据库
# --------------------------------------------------------------------------
def _db():
    return quote_db._connect()


def _migrate_roles(conn) -> None:
    for table in ("collab_member", "collab_token"):
        conn.execute(
            f"UPDATE {table} SET role = 'maintainer' WHERE role NOT IN ('maintainer')"
        )
    conn.commit()


def ensure_tables() -> None:
    conn = _db()
    _migrate_roles(conn)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS collab_member (
            group_id TEXT NOT NULL,
            qq TEXT NOT NULL,
            role TEXT NOT NULL,
            added_by TEXT NOT NULL DEFAULT '',
            added_at REAL NOT NULL,
            PRIMARY KEY (group_id, qq)
        );
        CREATE TABLE IF NOT EXISTS collab_token (
            id TEXT PRIMARY KEY,
            group_id TEXT NOT NULL,
            qq TEXT NOT NULL,
            role TEXT NOT NULL,
            token_hash TEXT NOT NULL,
            created_by TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL,
            expires_at REAL NOT NULL,
            revoked INTEGER NOT NULL DEFAULT 0,
            last_used REAL NOT NULL DEFAULT 0,
            use_count INTEGER NOT NULL DEFAULT 0,
            note TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS collab_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            group_id TEXT NOT NULL,
            actor_qq TEXT NOT NULL,
            actor_name TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT '',
            action TEXT NOT NULL,
            target TEXT NOT NULL DEFAULT '',
            before_json TEXT NOT NULL DEFAULT '',
            after_json TEXT NOT NULL DEFAULT '',
            ip TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_collab_audit_group ON collab_audit (group_id, ts);
        """
    )
    for ddl in (
        "ALTER TABLE collab_audit ADD COLUMN undone INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE collab_audit ADD COLUMN undo_of INTEGER NOT NULL DEFAULT 0",
    ):
        try:
            conn.execute(ddl)
        except sqlite3.OperationalError:
            pass
    conn.commit()


# --------------------------------------------------------------------------
# 成员 / token / 会话
# --------------------------------------------------------------------------
def list_members(group_id: str) -> list[dict]:
    rows = _db().execute(
        "SELECT qq, role, added_by, added_at FROM collab_member WHERE group_id = ? ORDER BY added_at",
        (group_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def member_role(group_id: str, qq: str) -> str:
    row = _db().execute(
        "SELECT role FROM collab_member WHERE group_id = ? AND qq = ?", (group_id, qq)
    ).fetchone()
    return str(row["role"]) if row else ""


def set_member(group_id: str, qq: str, role: str, added_by: str = "") -> None:
    role = normalize_role(role)
    _db().execute(
        "INSERT INTO collab_member (group_id, qq, role, added_by, added_at) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(group_id, qq) DO UPDATE SET role = excluded.role, added_by = excluded.added_by",
        (group_id, qq, role, added_by, time.time()),
    )
    _db().commit()


def remove_member(group_id: str, qq: str) -> bool:
    cur = _db().execute("DELETE FROM collab_member WHERE group_id = ? AND qq = ?", (group_id, qq))
    _db().commit()
    return cur.rowcount > 0


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_token(group_id: str, qq: str, role: str = "maintainer", created_by: str = "", hours: int = TOKEN_HOURS, note: str = "") -> tuple[str, dict]:
    ensure_tables()
    token = secrets.token_urlsafe(24)
    token_id = secrets.token_hex(8)
    now = time.time()
    expires = 0.0 if int(hours) <= 0 else now + int(hours) * 3600
    role = normalize_role(role)
    _db().execute(
        "INSERT INTO collab_token (id, group_id, qq, role, token_hash, created_by, created_at, expires_at, note) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (token_id, group_id, qq, role, _hash_token(token), created_by, now, expires, note),
    )
    _db().commit()
    return token, {"id": token_id, "group_id": group_id, "qq": qq, "role": role, "expires_at": expires}


def list_tokens(group_id: str) -> list[dict]:
    rows = _db().execute(
        "SELECT id, group_id, qq, role, created_by, created_at, expires_at, revoked, last_used, use_count "
        "FROM collab_token WHERE group_id = ? ORDER BY created_at DESC LIMIT 50",
        (group_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def revoke_group_tokens(group_id: str) -> int:
    cur = _db().execute("UPDATE collab_token SET revoked = 1 WHERE group_id = ? AND revoked = 0", (group_id,))
    _db().commit()
    return cur.rowcount


def revoke_token(token_id: str) -> bool:
    cur = _db().execute(
        "UPDATE collab_token SET revoked = 1 WHERE id = ? AND revoked = 0", (str(token_id),)
    )
    _db().commit()
    return cur.rowcount > 0


def member_groups(qq: str) -> list[dict]:
    valid = set(group_ids())
    rows = _db().execute(
        "SELECT group_id, role FROM collab_member WHERE qq = ? ORDER BY added_at", (str(qq),)
    ).fetchall()
    return [dict(r) for r in rows if str(r["group_id"]) in valid]


def allowed_groups(qq: str, preferred: str = "") -> list[str]:
    """该 QQ 可维护的群；旧令牌绑定的群即使成员表缺失也保留（兼容历史邀请）。"""
    valid = set(group_ids())
    groups = [str(r["group_id"]) for r in member_groups(qq)]
    preferred = str(preferred or "")
    if preferred in valid and preferred not in groups:
        groups.insert(0, preferred)
    return groups


def group_role(qq: str, group_id: str) -> str:
    return member_role(str(group_id), str(qq))


def find_token(token: str) -> dict | None:
    if not token or len(token) > 128:
        return None
    row = _db().execute(
        "SELECT * FROM collab_token WHERE token_hash = ? AND revoked = 0", (_hash_token(token),)
    ).fetchone()
    if not row:
        return None
    rec = dict(row)
    expires = float(rec.get("expires_at") or 0)
    if expires > 0 and expires < time.time():
        return None
    return rec


def _session_secret() -> str:
    global _secret
    if _secret:
        return _secret
    value = quote_db.load_doc("collab", "secret") or ""
    if not isinstance(value, str) or len(value) < 32:
        value = secrets.token_urlsafe(32)
        quote_db.save_doc("collab", "secret", value)
    _secret = value
    return _secret


def _sign(payload: str) -> str:
    return hmac.new(_session_secret().encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()[:32]


def make_session(token_id: str, qq: str, role: str, hours: int = SESSION_HOURS) -> str:
    payload = f"{token_id}.{qq}.{role}.{int(time.time() + hours * 3600)}"
    return f"{payload}.{_sign(payload)}"


def verify_session(cookie: str) -> dict | None:
    parts = (cookie or "").split(".")
    if len(parts) != 5:
        return None
    payload = ".".join(parts[:4])
    if not hmac.compare_digest(_sign(payload), parts[4]):
        return None
    token_id, qq, role, exp = parts[0], parts[1], parts[2], parts[3]
    if int(exp) < time.time():
        return None
    row = _db().execute("SELECT * FROM collab_token WHERE id = ? AND revoked = 0", (token_id,)).fetchone()
    if not row:
        return None
    rec = dict(row)
    return {"token_id": token_id, "qq": qq, "role": role, "group_id": rec["group_id"], "role_label": ROLE_LABELS.get(role, role)}


# --------------------------------------------------------------------------
# 审计
# --------------------------------------------------------------------------
def add_audit(group_id: str, actor_qq: str, actor_name: str, source: str, action: str, target: str = "", before: Any = None, after: Any = None, ip: str = "") -> None:
    try:
        _db().execute(
            "INSERT INTO collab_audit (ts, group_id, actor_qq, actor_name, source, action, target, before_json, after_json, ip) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                time.time(),
                group_id,
                actor_qq,
                actor_name,
                source,
                action,
                target,
                json.dumps(before, ensure_ascii=False) if before is not None else "",
                json.dumps(after, ensure_ascii=False) if after is not None else "",
                ip,
            ),
        )
        _db().commit()
    except Exception as exc:  # 审计失败不应阻断业务
        logger.warning(f"[quote_collab] 写审计失败：{exc}")


def list_audit(group_id: str, limit: int = 100) -> list[dict]:
    rows = _db().execute(
        "SELECT id, ts, actor_qq, actor_name, source, action, target, before_json, after_json, undone, undo_of "
        "FROM collab_audit WHERE group_id = ? ORDER BY id DESC LIMIT ?",
        (group_id, max(1, min(int(limit), 300))),
    ).fetchall()
    out = []
    for r in rows:
        item = dict(r)
        for key in ("before_json", "after_json"):
            try:
                item[key] = json.loads(item[key]) if item[key] else None
            except Exception:
                item[key] = None
        out.append(item)
    return out


def get_audit(audit_id: int) -> dict | None:
    row = _db().execute("SELECT * FROM collab_audit WHERE id = ?", (int(audit_id),)).fetchone()
    return dict(row) if row else None


_UNDO_FIELDS = {
    "restricted": ("restricted", "rating_source", "rating_reason"),
    "assign": ("subject_user_id", "subject_name", "subject_source", "subject_raw_name"),
    "tags": ("manual_tags",),
}


def undo_audit(
    audit_id: int,
    *,
    actor_qq: str,
    actor_name: str = "",
    ip: str = "",
    group_id: str = "",
) -> dict:
    rec = get_audit(audit_id)
    if not rec:
        return {"ok": False, "error": "记录不存在"}
    if group_id and str(rec.get("group_id")) != str(group_id):
        return {"ok": False, "error": "群不匹配"}
    if int(rec.get("undone") or 0):
        return {"ok": False, "error": "该操作已经撤销过了"}
    action = str(rec.get("action") or "")
    allowed = _UNDO_FIELDS.get(action)
    if not allowed:
        return {"ok": False, "error": "该类型操作不支持撤销"}
    try:
        entries = json.loads(rec.get("after_json") or "[]") or []
    except Exception:
        entries = []
    if not isinstance(entries, list):
        entries = []
    changed = 0
    for item in entries:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        before = item.get("before") if isinstance(item.get("before"), dict) else item
        if not name or not isinstance(before, dict):
            continue
        if action == "tags":
            item = META.load(str(rec["group_id"]))["items"].get(name) or {}
            if before.get("manual_tags") is None:
                item.pop("manual_tags", None)
            else:
                item["manual_tags"] = list(before.get("manual_tags") or [])
            META.save(str(rec["group_id"]))
            changed += 1
            continue
        patch = {k: before.get(k) for k in allowed if k in before}
        if not patch:
            continue
        try:
            META.update(str(rec["group_id"]), name, patch)
            changed += 1
        except Exception as exc:
            logger.warning(f"[quote_collab] 撤销写回失败 {name}：{exc}")
    _db().execute("UPDATE collab_audit SET undone = 1 WHERE id = ?", (int(audit_id),))
    _db().commit()
    add_audit(
        str(rec["group_id"]),
        actor_qq,
        actor_name,
        "web",
        "undo",
        f"audit:{audit_id}",
        {"action": action},
        {"changed": changed},
        ip,
    )
    return {"ok": True, "changed": changed, "undo_of": int(audit_id)}


def _display_name(qq: str, group_id: str = "") -> str:
    try:
        rows = IDENTITY.resolve_text_people(qq, group_id, 1)
        if rows:
            return str(rows[0].get("display_name") or "")
        summaries = IDENTITY.summaries()
        row = summaries.get(str(qq))
        if row:
            return str(row.get("display_name") or "")
    except Exception:
        pass
    return ""


# --------------------------------------------------------------------------
# 业务数据
# --------------------------------------------------------------------------
def _quote_records(group_id: str, keyword: str = "", restricted_mode: str = "all", assigned_mode: str = "all", sort_mode: str = "new") -> list[dict]:
    meta_items = (META.load(group_id) or {}).get("items") or {}
    sem_items = SEMANTIC.items(group_id) or {}
    summaries = IDENTITY.summaries() or {}
    out: list[dict] = []
    kw = (keyword or "").strip().lower()
    for entry in list_image_files(group_id):
        name = str((entry or {}).get("name") or "")
        if not name:
            continue
        info = meta_items.get(name) or {}
        sem = sem_items.get(name) or {}
        restricted = bool(info.get("restricted"))
        if restricted_mode == "0" and restricted:
            continue
        if restricted_mode == "1" and not restricted:
            continue
        caption = str(sem.get("caption") or "")
        manual_tags = info.get("manual_tags")
        if isinstance(manual_tags, list):
            tags = manual_tags
            tags_source = "manual"
        else:
            tags = sem.get("tags") or []
            tags_source = "semantic" if tags else "none"
        text = " ".join([name, caption, " ".join(map(str, tags)), str(info.get("nickname") or "")]).lower()
        if kw and kw not in text:
            continue
        uid = str(info.get("subject_user_id") or "")
        if assigned_mode == "1" and not uid:
            continue
        if assigned_mode == "0" and uid:
            continue
        person = summaries.get(uid) if uid else None
        out.append(
            {
                "group_id": group_id,
                "name": name,
                "ts": float(info.get("ts") or 0),
                "nickname": str(info.get("nickname") or ""),
                "caption": caption,
                "tags": [str(t) for t in tags][:TAGS_MAX],
                "tags_source": tags_source,
                "speaker": str(info.get("subject_name") or sem.get("speaker") or ""),
                "person_pid": str((person or {}).get("pid") or ""),
                "person_name": str((person or {}).get("display_name") or ""),
                "restricted": restricted,
                "rating_source": str(info.get("rating_source") or ""),
                "semantic": str(sem.get("status") or ""),
            }
        )
    out.sort(key=lambda item: item.get("ts") or 0, reverse=(sort_mode != "old"))
    return out


def _thumb_bytes(group_id: str, name: str) -> tuple[bytes, str]:
    from quote_views import _read_bytes, thumb_path

    names = {str((f or {}).get("name") or "") for f in list_image_files(group_id) if isinstance(f, dict)}
    if not name or name not in names:
        raise KeyError("not found")
    cache = thumb_path(group_id, name)
    if cache.is_file():
        return cache.read_bytes(), "image/webp"
    src = group_dir(group_id) / name
    return _read_bytes(src, True, cache)


def _assign_names(group_id: str, names: list[str], person_id: str) -> tuple[int, list[dict]]:
    summaries = IDENTITY.summaries() or {}
    if person_id:
        detail = IDENTITY.detail(person_id=person_id)
        uids = [str(u) for u in (detail.get("user_ids") or [])]
        if not uids:
            raise ValueError("person not found")
        actor = uids[0]
        display = str((summaries.get(actor) or {}).get("display_name") or "")
        patch = {"subject_user_id": actor, "subject_name": display, "subject_source": "manual"}
    else:
        patch = {"subject_user_id": "", "subject_name": "", "subject_source": ""}
    changed = 0
    body: list[dict] = []
    valid = {str((f or {}).get("name") or "") for f in list_image_files(group_id) if isinstance(f, dict)}
    for name in names:
        if name not in valid:
            continue
        before = dict((META.load(group_id) or {}).get("items", {}).get(name) or {})
        META.update(group_id, name, patch)
        after = dict((META.load(group_id) or {}).get("items", {}).get(name) or {})
        body.append({"name": name, "before": before, "after": after})
        changed += 1
    return changed, body


def _set_restricted(group_id: str, names: list[str], restricted: bool) -> tuple[int, list[dict]]:
    changed = 0
    body: list[dict] = []
    valid = {str((f or {}).get("name") or "") for f in list_image_files(group_id) if isinstance(f, dict)}
    for name in names:
        if name not in valid:
            continue
        before = dict((META.load(group_id) or {}).get("items", {}).get(name) or {})
        META.update(
            group_id,
            name,
            {
                "restricted": bool(restricted),
                "rating_source": "manual",
                "rating_reason": "协作页人工标记",
            },
        )
        after = dict((META.load(group_id) or {}).get("items", {}).get(name) or {})
        body.append({"name": name, "before": before, "after": after})
        changed += 1
    return changed, body


TAGS_MAX = 10
TAG_LEN_MAX = 24


def _clean_tags(raw) -> list[str]:
    out: list[str] = []
    for item in raw or []:
        text = str(item or "").strip().lstrip("#").strip()
        if not text:
            continue
        if len(text) > TAG_LEN_MAX:
            text = text[:TAG_LEN_MAX]
        if text not in out:
            out.append(text)
        if len(out) >= TAGS_MAX:
            break
    return out


def _set_tags(group_id: str, names: list[str], tags) -> tuple[int, list[dict]]:
    changed = 0
    body: list[dict] = []
    existing = {str((entry or {}).get("name") or "") for entry in list_image_files(group_id)}
    for name in names:
        if name not in existing:
            continue
        info = META.get(group_id, name)
        before = info.get("manual_tags")
        before_val = list(before) if isinstance(before, list) else None
        if tags is None:
            item = META.load(group_id)["items"].get(name) or {}
            item.pop("manual_tags", None)
            META.save(group_id)
            after_val = None
        else:
            after_val = _clean_tags(tags)
            META.update(group_id, name, {"manual_tags": after_val})
        body.append({"name": name, "before": {"manual_tags": before_val}, "after": after_val})
        changed += 1
    return changed, body


def _set_semantic_hints(group_id: str, names: list[str], hint: str, actor: str) -> int:
    hint = str(hint or "").strip()[:300]
    if not hint:
        return 0
    existing = {str((f or {}).get("name") or "") for f in list_image_files(group_id) if isinstance(f, dict)}
    changed = 0
    for name in names:
        if name not in existing:
            continue
        META.update(
            group_id,
            name,
            {
                "semantic_hint": hint,
                "semantic_hint_by": str(actor or ""),
                "semantic_hint_ts": time.time(),
            },
        )
        changed += 1
    return changed


def _semantic_pending(group_id: str, status: str = "") -> list[dict]:
    meta_items = (META.load(group_id) or {}).get("items") or {}
    out = []
    for name, sem in (SEMANTIC.items(group_id) or {}).items():
        st = str((sem or {}).get("status") or "pending")
        if status and st != status:
            continue
        info = meta_items.get(name) or {}
        out.append(
            {
                "name": name,
                "status": st,
                "caption": str((sem or {}).get("caption") or ""),
                "tags": [str(t) for t in ((sem or {}).get("tags") or [])][:4],
                "restricted": bool(info.get("restricted")),
                "ts": float(info.get("ts") or 0),
            }
        )
    out.sort(key=lambda item: item.get("ts") or 0, reverse=True)
    return out


# --------------------------------------------------------------------------
# HTTP 服务
# --------------------------------------------------------------------------
def _check_rate(key: str, limit: int) -> bool:
    now = time.time()
    window = [t for t in _rate.get(key, []) if now - t < 60]
    if len(window) >= limit:
        _rate[key] = window
        return False
    window.append(now)
    _rate[key] = window[-limit:]
    return True


def _client_ip(request: web.Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For") or ""
    if forwarded:
        return forwarded.split(",")[0].strip()
    peer = request.transport.get_extra_info("peername") if request.transport else None
    return peer[0] if peer else ""


def _require_role(session: dict, minimum: str) -> bool:
    # v2.20.3：编辑与管理权限合并，维护员拥有全部权限
    return True


def _load_session(request: web.Request) -> dict | None:
    return verify_session(request.cookies.get("qc_collab", ""))


def _session_group_ids(session: dict) -> list[str]:
    return allowed_groups(str(session.get("qq") or ""), str(session.get("group_id") or ""))


def _session_can(session: dict, group_id: str, minimum: str = "editor") -> bool:
    if str(group_id) not in _session_group_ids(session):
        return False
    role = member_role(str(group_id), str(session.get("qq") or ""))
    return _require_role({"role": role}, minimum)


@web.middleware
async def _middleware(request: web.Request, handler):
    path = request.path
    public = {"/", "/api/login", "/api/health"}
    if path in public or path.startswith("/static/"):
        return await handler(request)
    session = _load_session(request)
    if not session:
        if path.startswith("/api/"):
            return web.json_response({"error": "unauthorized"}, status=401)
        raise web.HTTPFound("/")
    request["session"] = session
    if request.method == "POST":
        if request.headers.get("X-Collab") != "1":
            return web.json_response({"error": "bad request"}, status=400)
        if not _check_rate(f"w:{session['token_id']}", WRITE_LIMIT_PER_MIN):
            return web.json_response({"error": "rate limited"}, status=429)
    elif not _check_rate(f"r:{session['token_id']}", READ_LIMIT_PER_MIN):
        return web.json_response({"error": "rate limited"}, status=429)
    return await handler(request)


async def _read_json(request: web.Request) -> dict:
    length = int(request.headers.get("Content-Length") or 0)
    if length > MAX_BODY:
        raise web.HTTPRequestEntityTooLarge(max_size=MAX_BODY, actual_size=length)
    try:
        data = await request.json()
    except Exception:
        raise web.HTTPBadRequest(text="invalid json")
    if not isinstance(data, dict):
        raise web.HTTPBadRequest(text="invalid payload")
    return data


async def handle_index(request: web.Request) -> web.Response:
    if not _HTML_PATH.is_file():
        return web.Response(text="collab page missing", status=500)
    return web.FileResponse(_HTML_PATH)


async def handle_health(request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "ts": time.time()})


async def handle_login(request: web.Request) -> web.Response:
    data = await _read_json(request)
    token = str(data.get("token") or "").strip()
    if not _check_rate(f"login:{_client_ip(request)}", 20):
        return web.json_response({"error": "too many attempts"}, status=429)
    rec = find_token(token)
    if not rec:
        return web.json_response({"error": "邀请链接无效或已过期"}, status=403)
    qq = str(rec["qq"])
    role = normalize_role(str(rec["role"]))
    groups = allowed_groups(qq, str(rec["group_id"]))
    if not groups:
        return web.json_response({"error": "没有可维护的群，请联系 AstrBot 管理员重新授权"}, status=403)
    group_id = str(rec["group_id"])
    if group_id not in groups:
        group_id = groups[0]
    _db().execute(
        "UPDATE collab_token SET last_used = ?, use_count = use_count + 1 WHERE id = ?", (time.time(), rec["id"])
    )
    _db().commit()
    cookie = make_session(str(rec["id"]), qq, role)
    add_audit(group_id, qq, _display_name(qq, group_id), "web", "login", "", None, {"role": role}, _client_ip(request))
    response = web.json_response(
        {
            "ok": True,
            "role": role,
            "role_label": ROLE_LABELS.get(role, role),
            "group_id": group_id,
            "groups": groups,
            "qq": qq,
        }
    )
    response.set_cookie("qc_collab", cookie, max_age=SESSION_HOURS * 3600, httponly=True, samesite="Lax", path="/")
    return response


async def handle_logout(request: web.Request) -> web.Response:
    response = web.json_response({"ok": True})
    response.del_cookie("qc_collab", path="/")
    return response


async def handle_me(request: web.Request) -> web.Response:
    session = request["session"]
    groups = _session_group_ids(session)
    group_id = str(session["group_id"])
    if group_id not in groups:
        group_id = groups[0] if groups else ""
    roles = {str(g): member_role(str(g), str(session["qq"])) for g in groups}
    return web.json_response(
        {
            "ok": True,
            "role": session["role"],
            "role_label": session["role_label"],
            "group_id": group_id,
            "qq": session["qq"],
            "name": _display_name(session["qq"], group_id),
            "groups": groups,
            "roles": roles,
            "group_roles": {g: ROLE_LABELS.get(r, r) for g, r in roles.items()},
        }
    )


async def handle_quotes(request: web.Request) -> web.Response:
    session = request["session"]
    group_id = str(request.query.get("group_id") or session["group_id"])
    if group_id not in _session_group_ids(session):
        return web.json_response({"error": "forbidden"}, status=403)
    if group_id not in set(group_ids()):
        return web.json_response({"error": "unknown group"}, status=400)
    try:
        page = max(1, int(request.query.get("page") or 1))
        page_size = max(1, min(PAGE_MAX, int(request.query.get("page_size") or 18)))
    except (TypeError, ValueError):
        page, page_size = 1, 18
    keyword = str(request.query.get("keyword") or "")
    restricted_mode = str(request.query.get("restricted") or "all")
    assigned_mode = str(request.query.get("assigned") or "all")
    sort_mode = str(request.query.get("sort") or "new")
    if assigned_mode not in ("0", "1", "all"):
        assigned_mode = "all"
    if sort_mode not in ("new", "old"):
        sort_mode = "new"
    rows = _quote_records(group_id, keyword, restricted_mode, assigned_mode, sort_mode)
    total = len(rows)
    start = (page - 1) * page_size
    return web.json_response(
        {
            "ok": True,
            "group_id": group_id,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": max(1, (total + page_size - 1) // page_size),
            "items": rows[start : start + page_size],
        }
    )


async def handle_thumb(request: web.Request) -> web.Response:
    session = request["session"]
    group_id = str(request.query.get("group_id") or session["group_id"])
    name = str(request.query.get("name") or "")
    if group_id not in _session_group_ids(session):
        raise web.HTTPNotFound()
    if group_id not in set(group_ids()):
        raise web.HTTPNotFound()
    full = str(request.query.get("full") or "") == "1"
    try:
        if full:
            src = group_dir(group_id) / name
            if not src.is_file() or src.stat().st_size > 16 * 1024 * 1024:
                raise KeyError("not found")
            suffix = src.suffix.lower()
            mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(suffix.lstrip("."), "application/octet-stream")
            return web.Response(body=await asyncio.to_thread(src.read_bytes), content_type=mime, headers={"Cache-Control": "private, max-age=3600"})
        payload, mime = await asyncio.to_thread(_thumb_bytes, group_id, name)
    except KeyError:
        raise web.HTTPNotFound()
    return web.Response(body=payload, content_type=mime, headers={"Cache-Control": "private, max-age=3600"})


async def handle_people(request: web.Request) -> web.Response:
    session = request["session"]
    group_id = str(request.query.get("group_id") or session["group_id"])
    if group_id not in _session_group_ids(session):
        return web.json_response({"error": "forbidden"}, status=403)
    keyword = str(request.query.get("keyword") or "")
    data = await asyncio.to_thread(IDENTITY.list_people, keyword, group_id, 1, 30)
    return web.json_response(
        {
            "ok": True,
            "total": data.get("total"),
            "items": [
                {
                    "pid": str(item.get("pid") or ""),
                    "name": str(item.get("display_name") or ""),
                    "count": int(item.get("quote_count") or 0),
                    "avatar_sha": str(item.get("avatar_sha") or ""),
                }
                for item in (data.get("items") or [])
            ],
        }
    )


async def handle_assign(request: web.Request) -> web.Response:
    session = request["session"]
    data = await _read_json(request)
    group_id = str(data.get("group_id") or session["group_id"])
    if group_id not in _session_group_ids(session):
        return web.json_response({"error": "forbidden"}, status=403)
    if group_id not in set(group_ids()):
        return web.json_response({"error": "unknown group"}, status=400)
    names = [str(n) for n in (data.get("names") or []) if isinstance(n, str)]
    if not names or len(names) > 200:
        return web.json_response({"error": "bad names"}, status=400)
    person_id = str(data.get("person_id") or "")
    try:
        changed, body = await asyncio.to_thread(_assign_names, group_id, names, person_id)
    except ValueError:
        return web.json_response({"error": "target person not found"}, status=400)
    add_audit(
        group_id,
        session["qq"],
        _display_name(session["qq"], group_id),
        "web",
        "assign",
        f"{len(names)} 张 -> {person_id or '未归属'}",
        None,
        body[:20],
        _client_ip(request),
    )
    return web.json_response({"ok": True, "updated": changed})


async def handle_restricted(request: web.Request) -> web.Response:
    session = request["session"]
    data = await _read_json(request)
    group_id = str(data.get("group_id") or session["group_id"])
    if group_id not in _session_group_ids(session):
        return web.json_response({"error": "forbidden"}, status=403)
    if group_id not in set(group_ids()):
        return web.json_response({"error": "unknown group"}, status=400)
    names = [str(n) for n in (data.get("names") or []) if isinstance(n, str)]
    if not names or len(names) > 200:
        return web.json_response({"error": "bad names"}, status=400)
    restricted = bool(data.get("restricted"))
    changed, body = await asyncio.to_thread(_set_restricted, group_id, names, restricted)
    add_audit(
        group_id,
        session["qq"],
        _display_name(session["qq"], group_id),
        "web",
        "restricted",
        f"{len(names)} 张 -> {'限制级' if restricted else '非限制级'}",
        None,
        body[:20],
        _client_ip(request),
    )
    return web.json_response({"ok": True, "updated": changed})


async def handle_tags(request: web.Request) -> web.Response:
    session = request["session"]
    data = await _read_json(request)
    group_id = str(data.get("group_id") or session["group_id"])
    if not _session_can(session, group_id):
        return web.json_response({"error": "forbidden"}, status=403)
    if group_id not in set(group_ids()):
        return web.json_response({"error": "unknown group"}, status=400)
    names = [str(n) for n in (data.get("names") or []) if isinstance(n, str)]
    if not names or len(names) > 200:
        return web.json_response({"error": "bad names"}, status=400)
    tags = data.get("tags")
    if tags is not None and not isinstance(tags, list):
        return web.json_response({"error": "bad tags"}, status=400)
    changed, body = await asyncio.to_thread(_set_tags, group_id, names, tags)
    label = "恢复语义标签" if tags is None else f"标签 -> {'、'.join(_clean_tags(tags)) or '（空）'}"
    add_audit(
        group_id, session["qq"], _display_name(session["qq"], group_id),
        "web", "tags", f"{len(names)} 张 -> {label}", None, body[:20], _client_ip(request),
    )
    return web.json_response({"ok": True, "updated": changed})


async def handle_semantic_list(request: web.Request) -> web.Response:
    session = request["session"]
    group_id = str(request.query.get("group_id") or session["group_id"])
    if not _session_can(session, group_id, "curator"):
        return web.json_response({"error": "forbidden"}, status=403)
    status = str(request.query.get("status") or "")
    rows = await asyncio.to_thread(_semantic_pending, group_id, status)
    return web.json_response({"ok": True, "total": len(rows), "items": rows[:60]})


async def handle_semantic_retry(request: web.Request) -> web.Response:
    session = request["session"]
    if _ctx is None:
        return web.json_response({"error": "semantic runner unavailable"}, status=503)
    data = await _read_json(request)
    group_id = str(data.get("group_id") or session["group_id"])
    if not _session_can(session, group_id, "curator"):
        return web.json_response({"error": "forbidden"}, status=403)
    if group_id not in set(group_ids()):
        return web.json_response({"error": "unknown group"}, status=400)
    names = [str(n) for n in (data.get("names") or []) if isinstance(n, str)]
    valid = {str((f or {}).get("name") or "") for f in list_image_files(group_id) if isinstance(f, dict)}
    names = [n for n in names if n in valid][:SEMANTIC_BATCH_MAX]
    if not names:
        return web.json_response({"error": "no valid names"}, status=400)
    hint = str(data.get("hint") or "").strip()[:300]
    if hint:
        await asyncio.to_thread(_set_semantic_hints, group_id, names, hint, session["qq"])
    try:
        status_info = await asyncio.to_thread(semantic_status_sync, _ctx, group_id=group_id)
        if not (status_info.get("embedding") or {}).get("ready"):
            return web.json_response({"error": "语义服务未就绪（需要视觉与向量模型）"}, status=503)
        await asyncio.to_thread(SEMANTIC.mark_pending, group_id, names)
        caption_id = resolve_caption_provider_id(_ctx, status_info.get("caption_provider_id") or "")
        embedding_id = str((status_info.get("embedding") or {}).get("id") or "")
        # 必须在事件循环线程里创建任务；放到 to_thread 会因没有 running loop 而报错
        SEMANTIC_RUNNER.start(
            _ctx,
            [group_id],
            scope="pending",
            caption_provider_id=caption_id,
            embedding_provider_id=embedding_id,
        )
    except Exception as exc:
        logger.warning(f"[quote_collab] 语义重试失败：{exc}")
        return web.json_response({"error": f"重试失败：{exc}"}, status=500)
    add_audit(
        group_id,
        session["qq"],
        _display_name(session["qq"], group_id),
        "web",
        "semantic_retry",
        f"{len(names)} 张" + (f" · 参考意见：{hint}" if hint else ""),
        None,
        {"names": names[:20]},
        _client_ip(request),
    )
    return web.json_response({"ok": True, "queued": len(names), "hint": hint})


async def handle_audit(request: web.Request) -> web.Response:
    session = request["session"]
    group_id = str(request.query.get("group_id") or session["group_id"])
    if group_id not in _session_group_ids(session):
        return web.json_response({"error": "forbidden"}, status=403)
    try:
        limit = max(1, min(200, int(request.query.get("limit") or 80)))
    except (TypeError, ValueError):
        limit = 80
    return web.json_response({"ok": True, "items": await asyncio.to_thread(list_audit, group_id, limit)})


async def handle_undo(request: web.Request) -> web.Response:
    session = request["session"]
    data = await _read_json(request)
    try:
        audit_id = int(data.get("id") or 0)
    except (TypeError, ValueError):
        audit_id = 0
    rec = await asyncio.to_thread(get_audit, audit_id)
    if not rec:
        return web.json_response({"error": "记录不存在"}, status=404)
    group_id = str(rec.get("group_id") or "")
    if not _session_can(session, group_id, "curator"):
        return web.json_response({"error": "forbidden"}, status=403)
    result = await asyncio.to_thread(
        undo_audit,
        audit_id,
        actor_qq=str(session["qq"]),
        actor_name=_display_name(str(session["qq"]), group_id),
        ip=_client_ip(request),
        group_id=group_id,
    )
    if not result.get("ok"):
        return web.json_response({"error": result.get("error") or "撤销失败"}, status=400)
    return web.json_response(result)


# --------------------------------------------------------------------------
# 邀请链接与登录辅助（供 main.py 群命令使用）
# --------------------------------------------------------------------------
# 默认不内置任何外网地址：请在插件管理页「协作维护 → 协作页外网地址」填写
# 反向代理后的公开地址，例如 https://example.com/quote-collab/
PUBLIC_BASE_DEFAULT = ""


def public_base() -> str:
    value = quote_db.load_doc("collab", "public_base")
    if isinstance(value, str) and value.strip():
        base = value.strip()
        if not base.endswith("/"):
            base += "/"
        return base
    return PUBLIC_BASE_DEFAULT


def set_public_base(value: str) -> str:
    """保存协作页外网地址；空串表示清除。"""
    text = str(value or "").strip()
    if text:
        if not (text.startswith("http://") or text.startswith("https://")):
            raise ValueError("外网地址需以 http:// 或 https:// 开头")
        if not text.endswith("/"):
            text += "/"
    quote_db.save_doc("collab", "public_base", text)
    return public_base()


def invite_link(token: str) -> str:
    return public_base() + "#t=" + token


def _token_row_view(row: dict) -> dict:
    expires = float(row.get("expires_at") or 0)
    now = time.time()
    row = dict(row)
    row["role_label"] = ROLE_LABELS.get(str(row.get("role")), str(row.get("role") or ""))
    row["permanent"] = expires <= 0
    row["expired"] = bool(expires > 0 and expires < now)
    row["expires_in"] = 0 if expires <= 0 else max(0, int(expires - now))
    return row


def admin_members(group_id: str) -> dict:
    items = list_members(str(group_id))
    for item in items:
        item["role_label"] = ROLE_LABELS.get(str(item.get("role")), str(item.get("role") or ""))
    return {"total": len(items), "items": items}


def admin_upsert_member(group_id: str, qq: str, role: str, actor: str = "") -> None:
    set_member(str(group_id), str(qq), role, str(actor))
    add_audit(str(group_id), str(actor), "", "dashboard", "member_set", f"qq:{qq}", None, {"role": role})


def admin_remove_member(group_id: str, qq: str, actor: str = "") -> bool:
    removed = remove_member(str(group_id), str(qq))
    add_audit(str(group_id), str(actor), "", "dashboard", "member_remove", f"qq:{qq}", None, None)
    return removed


def admin_tokens(group_id: str, include_revoked: bool = True) -> dict:
    rows = _db().execute(
        "SELECT id, group_id, qq, role, created_by, created_at, expires_at, revoked, last_used, use_count, note "
        "FROM collab_token WHERE group_id = ? ORDER BY created_at DESC LIMIT 100",
        (str(group_id),),
    ).fetchall()
    items = [_token_row_view(dict(r)) for r in rows]
    if not include_revoked:
        items = [i for i in items if not int(i.get("revoked") or 0)]
    return {"total": len(items), "items": items}


def admin_create_token(
    group_id: str, qq: str, role: str = "maintainer", hours: int = 168, actor: str = ""
) -> dict:
    if not member_role(str(group_id), str(qq)):
        set_member(str(group_id), str(qq), role, str(actor))
    token, rec = create_token(str(group_id), str(qq), role, str(actor), int(hours), "管理页生成")
    add_audit(
        str(group_id),
        str(actor),
        "",
        "dashboard",
        "token_create",
        f"qq:{qq}",
        None,
        {"role": role, "hours": int(hours), "token_id": rec.get("id")},
    )
    return {"token": token, "link": invite_link(token), "record": _token_row_view(rec)}


def admin_revoke_token(group_id: str, token_id: str, actor: str = "") -> bool:
    ok = revoke_token(str(token_id))
    if ok:
        add_audit(str(group_id), str(actor), "", "dashboard", "token_revoke", f"token:{token_id}", None, None)
    return ok


def latest_invite_for(qq: str, group_id: str = "") -> tuple[str, dict] | None:
    ensure_tables()
    sql = "SELECT * FROM collab_token WHERE qq = ? AND revoked = 0 AND (expires_at <= 0 OR expires_at > ?)"
    args: list[Any] = [str(qq), time.time()]
    if group_id:
        sql += " AND group_id = ?"
        args.append(group_id)
    sql += " ORDER BY created_at DESC LIMIT 1"
    row = _db().execute(sql, tuple(args)).fetchone()
    if not row:
        return None
    rec = dict(row)
    return str(rec["id"]), rec


def rotate_token(token_id: str, token: str) -> None:
    """登录后把令牌换成一次性（避免链接被反复使用）。"""
    _db().execute("UPDATE collab_token SET revoked = 1 WHERE id = ?", (token_id,))
    _db().commit()


def build_app() -> web.Application:
    app = web.Application(middlewares=[_middleware], client_max_size=MAX_BODY)
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/health", handle_health)
    app.router.add_post("/api/login", handle_login)
    app.router.add_post("/api/logout", handle_logout)
    app.router.add_post("/api/undo", handle_undo)
    app.router.add_get("/api/me", handle_me)
    app.router.add_get("/api/quotes", handle_quotes)
    app.router.add_get("/api/thumb", handle_thumb)
    app.router.add_get("/api/people", handle_people)
    app.router.add_post("/api/assign", handle_assign)
    app.router.add_post("/api/restricted", handle_restricted)
    app.router.add_post("/api/tags", handle_tags)
    app.router.add_get("/api/semantic", handle_semantic_list)
    app.router.add_post("/api/semantic/retry", handle_semantic_retry)
    app.router.add_get("/api/audit", handle_audit)
    return app


async def start(context: Any, host: str = "127.0.0.1", port: int = 6190) -> None:
    """启动协作服务；失败只记日志，不影响插件主体。"""
    global _ctx, _runner, _site
    _ctx = context
    ensure_tables()
    _session_secret()
    try:
        _runner = web.AppRunner(build_app(), access_log=None)
        await _runner.setup()
        _site = web.TCPSite(_runner, host, port)
        await _site.start()
        logger.info(f"[quote_collab] 协作服务已启动：http://{host}:{port}/")
    except Exception as exc:
        logger.warning(f"[quote_collab] 协作服务启动失败（不影响主功能）：{exc}")
        _runner = None
        _site = None


async def stop() -> None:
    global _runner, _site
    try:
        if _site:
            await _site.stop()
        if _runner:
            await _runner.cleanup()
    except Exception:
        pass
    _runner = None
    _site = None
