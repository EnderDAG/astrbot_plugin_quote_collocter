"""quote_db.py — 语录插件的 SQLite 存储层。

v2.11.0 起，插件的历史数据（群设置、语录元数据、语义索引、人物档案、
发送记忆、自动同步设置、更新推送设置）统一存放在 plugin_data/quote_collocter/quote.db。

设计原则：
  * 图片、头像等二进制文件仍然保留在磁盘上，数据库只存元数据；
  * 首次启动时如果发现旧版 JSON/YAML 数据文件，自动迁移进数据库，
    旧文件原样保留（作为只读备份），之后读写只走数据库；
  * 所有读写都经过一个进程内连接 + 全局锁，AstrBot 插件的线程模型足够安全；
  * WAL 模式，单文件即可备份（连同 -wal/-shm 一起），支持增量写入。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import threading
import time
from pathlib import Path

try:
    import yaml
except Exception:  # pragma: no cover - 仅在没有 PyYAML 的本地测试环境走降级解析
    yaml = None
from typing import Any

PLUGIN_NAME = "quote_collocter"

SCHEMA_VERSION = 1

DB_FILE = "quote.db"

_lock = threading.RLock()

_conn: sqlite3.Connection | None = None

_initialized = False

# v3.0.1 媒体目录迁移结果（只用于日志展示，空串表示尚未执行）
_media_migration = ""

# 旧版数据文件位置（只用于迁移；迁移后不再读写）
LEGACY_DATA_ROOT = Path("data") / "quotes_data"

LEGACY_PLUGIN_DIR = Path("data") / "plugin_data" / PLUGIN_NAME

LEGACY_META_FILE = "quotes_meta.json"

LEGACY_SETTINGS_FILE = "admin_settings.yml"

LEGACY_SEMANTIC_FILE = "quotes_semantic.json"

LEGACY_IDENTITY_FILE = "identities.json"

LEGACY_SENT_FILE = "quotes_sent.json"

LEGACY_SYNC_FILE = "identity_sync.json"

LEGACY_ANNOUNCE_FILE = "update_announce.json"


def plugin_data_dir() -> Path:
    override = os.environ.get("QUOTE_DB_DIR")
    if override:
        return Path(override)
    return LEGACY_PLUGIN_DIR


def db_path() -> Path:
    return plugin_data_dir() / DB_FILE


def _connect() -> sqlite3.Connection:
    global _conn, _initialized
    with _lock:
        if _conn is not None:
            return _conn
        path = db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA foreign_keys=OFF")
        _conn = conn
        _create_schema(conn)
        if not _initialized:
            _initialized = True
            _migrate_legacy(conn)
        _migrate_legacy_media_root()
        return conn


def ensure_initialized() -> None:
    """主动初始化数据库（含旧版 JSON / 媒体目录迁移），供插件启动时调用。"""
    _connect()


def media_migration_result() -> str:
    """返回旧媒体目录迁移结果，供插件启动日志展示。"""
    return _media_migration


def _merge_move_tree(src: Path, dst: Path) -> int:
    """把 src 目录内容递归并入 dst（目标已存在的文件保留，不覆盖）。返回移动的文件数。"""
    moved = 0
    dst.mkdir(parents=True, exist_ok=True)
    try:
        children = list(src.iterdir())
    except OSError:
        return moved
    for child in children:
        target = dst / child.name
        try:
            if child.is_dir():
                if target.is_dir():
                    moved += _merge_move_tree(child, target)
                elif not target.exists():
                    shutil.move(str(child), str(target))
                    moved += 1
            elif not target.exists():
                shutil.move(str(child), str(target))
                moved += 1
        except OSError:
            continue
    return moved


def _prune_empty_dirs(root: Path) -> None:
    """删除 root 下所有空目录（自底向上），最后尝试删除 root 本身。"""
    try:
        entries = sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True)
    except OSError:
        return
    for path in entries:
        if not path.is_dir():
            continue
        try:
            path.rmdir()
        except OSError:
            continue
    try:
        root.rmdir()
    except OSError:
        pass


def _migrate_legacy_media_root() -> None:
    """v3.0.1：把旧版 data/quotes_data/ 下的图片、缩略图并入 plugin_data/quote_collocter/quotes_data/。

    幂等：每次启动检查一次；目标目录已存在的文件不覆盖，迁移完删除空的旧目录。
    迁移失败不抛异常，不影响插件运行，下次启动会重试。
    """
    global _media_migration
    if _media_migration:
        return
    legacy = LEGACY_DATA_ROOT
    target = LEGACY_PLUGIN_DIR / "quotes_data"
    if not legacy.is_dir():
        _media_migration = "no legacy media directory"
        return
    moved = 0
    try:
        target.mkdir(parents=True, exist_ok=True)
        for child in list(legacy.iterdir()):
            dest = target / child.name
            if child.is_dir():
                if not dest.exists():
                    # 目标不存在时整目录一步搬走（同盘 rename，最快）
                    shutil.move(str(child), str(dest))
                    moved += 1
                else:
                    moved += _merge_move_tree(child, dest)
            elif not dest.exists():
                shutil.move(str(child), str(dest))
                moved += 1
        _prune_empty_dirs(legacy)
        _media_migration = f"moved {moved} file(s) to {target}"
    except Exception as exc:  # pragma: no cover - 迁移失败只记状态，下次启动重试
        _media_migration = f"failed: {exc}"


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS group_settings (
            group_id TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS quote_meta (
            group_id TEXT NOT NULL,
            name TEXT NOT NULL,
            data TEXT NOT NULL,
            updated_at REAL NOT NULL,
            PRIMARY KEY (group_id, name)
        );
        CREATE INDEX IF NOT EXISTS idx_quote_meta_group ON quote_meta(group_id);
        CREATE TABLE IF NOT EXISTS semantic_index (
            group_id TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS semantic_item (
            group_id TEXT NOT NULL,
            name TEXT NOT NULL,
            data TEXT NOT NULL,
            updated_at REAL NOT NULL,
            PRIMARY KEY (group_id, name)
        );
        CREATE INDEX IF NOT EXISTS idx_semantic_item_group ON semantic_item(group_id);
        CREATE TABLE IF NOT EXISTS identity_user (
            user_id TEXT PRIMARY KEY,
            data TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS identity_person (
            person_key TEXT PRIMARY KEY,
            data TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS identity_alias (
            alias_key TEXT PRIMARY KEY,
            data TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS identity_blocked (
            blocked_key TEXT PRIMARY KEY,
            data TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS trash (
            group_id TEXT NOT NULL,
            name TEXT NOT NULL,
            data TEXT NOT NULL,
            deleted_at REAL NOT NULL,
            PRIMARY KEY (group_id, name)
        );
        CREATE TABLE IF NOT EXISTS tag_queue (
            group_id TEXT NOT NULL,
            name TEXT NOT NULL,
            status TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            error TEXT NOT NULL DEFAULT '',
            updated_at REAL NOT NULL,
            PRIMARY KEY (group_id, name)
        );
        CREATE TABLE IF NOT EXISTS alias_candidate (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id TEXT NOT NULL DEFAULT '',
            alias_key TEXT NOT NULL,
            alias_name TEXT NOT NULL,
            target_pid TEXT NOT NULL DEFAULT '',
            target_user_id TEXT NOT NULL DEFAULT '',
            display_name TEXT NOT NULL DEFAULT '',
            evidence TEXT NOT NULL DEFAULT '',
            evidence_user TEXT NOT NULL DEFAULT '',
            confidence REAL NOT NULL DEFAULT 0.5,
            occurrences INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_alias_candidate_status ON alias_candidate(status, created_at);
        CREATE VIRTUAL TABLE IF NOT EXISTS quote_fts USING fts5(
            group_id UNINDEXED,
            name UNINDEXED,
            text,
            tokens,
            tokenize='unicode61'
        );
        CREATE TABLE IF NOT EXISTS identity_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sent_session (
            umo TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS doc (
            scope TEXT NOT NULL,
            key TEXT NOT NULL,
            data TEXT NOT NULL,
            updated_at REAL NOT NULL,
            PRIMARY KEY (scope, key)
        );
        CREATE TABLE IF NOT EXISTS collection (
            group_id TEXT NOT NULL,
            collection_id TEXT NOT NULL,
            data TEXT NOT NULL,
            updated_at REAL NOT NULL,
            PRIMARY KEY (group_id, collection_id)
        );
        """
    )
    conn.commit()
    _ensure_alias_candidate_columns(conn)


def _ensure_alias_candidate_columns(conn: sqlite3.Connection) -> None:
    """v3.0.5：旧库补 alias_candidate.occurrences 列（幂等，失败不影响启动）。"""
    try:
        columns = {str(row["name"]) for row in conn.execute("PRAGMA table_info(alias_candidate)")}
    except sqlite3.Error:
        return
    if "occurrences" in columns:
        return
    try:
        conn.execute(
            "ALTER TABLE alias_candidate ADD COLUMN occurrences INTEGER NOT NULL DEFAULT 0"
        )
        conn.commit()
    except sqlite3.Error:
        pass


def _get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return str(row["value"]) if row else None


def _set_meta(conn: sqlite3.Connection, key: str, value: Any) -> None:
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )


# ---------------------------------------------------------------------------
# 旧版 JSON/YAML 数据迁移
# ---------------------------------------------------------------------------


def _load_legacy_yaml(path: Path) -> Any:
    text = ""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if yaml is not None:
        try:
            return yaml.safe_load(text) or {}
        except Exception:
            pass
    data: dict = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if value.lower() in ("true", "false"):
            data[key.strip()] = value.lower() == "true"
        else:
            try:
                data[key.strip()] = int(value)
            except ValueError:
                try:
                    data[key.strip()] = float(value)
                except ValueError:
                    data[key.strip()] = value
    return data


def _load_json(path: Path, encoding: str = "utf-8") -> Any:
    try:
        return json.loads(path.read_text(encoding=encoding))
    except (OSError, ValueError):
        return None


def _migrate_legacy(conn: sqlite3.Connection) -> None:
    """把旧版散落的 JSON/YAML 数据导入数据库。

    只导入一次：meta 里记录 migrated_at。即使导入失败，也会在下次启动重试，
    因为失败时不会写入 migrated_at 标记。
    """
    if _get_meta(conn, "migrated_at"):
        return
    now = time.time()
    migrated: list[str] = []
    try:
        # ---- 群数据：设置、语录元数据、语义索引 ----
        if LEGACY_DATA_ROOT.is_dir():
            for directory in sorted(LEGACY_DATA_ROOT.iterdir()):
                if not directory.is_dir() or directory.name.startswith("."):
                    continue
                gid = directory.name
                settings_path = directory / LEGACY_SETTINGS_FILE
                if settings_path.is_file():
                    try:
                        raw = _load_legacy_yaml(settings_path)
                        if isinstance(raw, dict) and raw:
                            _save_group_settings_row(conn, gid, raw, now)
                            migrated.append(f"settings:{gid}")
                    except Exception:
                        pass
                meta_path = directory / LEGACY_META_FILE
                if meta_path.is_file():
                    raw = _load_json(meta_path)
                    if isinstance(raw, dict) and isinstance(raw.get("items"), dict):
                        for name, item in raw["items"].items():
                            if isinstance(item, dict):
                                _save_quote_meta_row(conn, gid, str(name), item, now)
                        migrated.append(f"meta:{gid}")
                semantic_path = directory / LEGACY_SEMANTIC_FILE
                if semantic_path.is_file():
                    raw = _load_json(semantic_path)
                    if isinstance(raw, dict):
                        index = {
                            "version": raw.get("version"),
                            "signature": raw.get("signature") or "",
                            "provider": raw.get("provider") or {},
                            "updated_at": raw.get("updated_at") or 0,
                        }
                        _save_semantic_index_row(conn, gid, index, now)
                        items = raw.get("items")
                        if isinstance(items, dict):
                            for name, item in items.items():
                                if isinstance(item, dict):
                                    _save_semantic_item_row(
                                        conn, gid, str(name), item, now
                                    )
                        migrated.append(f"semantic:{gid}")
        # ---- 插件级数据：人物档案 / 发送记忆 / 同步设置 / 更新推送 ----
        identity_raw = _load_json(LEGACY_PLUGIN_DIR / LEGACY_IDENTITY_FILE)
        if isinstance(identity_raw, dict) and identity_raw:
            _import_identity_raw(conn, identity_raw, now)
            migrated.append("identity")
        sent_raw = _load_json(LEGACY_PLUGIN_DIR / LEGACY_SENT_FILE)
        if isinstance(sent_raw, dict):
            sessions = sent_raw.get("sessions")
            if isinstance(sessions, dict):
                for umo, items in sessions.items():
                    if isinstance(items, list):
                        _save_sent_session_row(conn, str(umo), items, now)
                migrated.append("sent")
        sync_raw = _load_json(LEGACY_PLUGIN_DIR / LEGACY_SYNC_FILE)
        if isinstance(sync_raw, dict) and sync_raw:
            _save_doc_row(conn, "sync", "settings", sync_raw, now)
            migrated.append("sync")
        announce_raw = _load_json(LEGACY_PLUGIN_DIR / LEGACY_ANNOUNCE_FILE)
        if isinstance(announce_raw, dict) and announce_raw:
            _save_doc_row(conn, "announce", "settings", announce_raw, now)
            migrated.append("announce")

        _set_meta(conn, "schema_version", SCHEMA_VERSION)
        _set_meta(conn, "migrated_at", f"{now:.3f}")
        _set_meta(conn, "migrated_sources", ",".join(migrated))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _import_identity_raw(conn: sqlite3.Connection, raw: dict, now: float) -> None:
    users = raw.get("users") or {}
    persons = raw.get("persons") or {}
    aliases = raw.get("aliases") or {}
    blocked = raw.get("blocked") or {}
    if isinstance(users, dict):
        for user_id, data in users.items():
            if isinstance(data, dict):
                conn.execute(
                    "INSERT OR REPLACE INTO identity_user(user_id, data) VALUES(?, ?)",
                    (str(user_id), json.dumps(data, ensure_ascii=False)),
                )
    if isinstance(persons, dict):
        for key, data in persons.items():
            if isinstance(data, dict):
                conn.execute(
                    "INSERT OR REPLACE INTO identity_person(person_key, data) VALUES(?, ?)",
                    (str(key), json.dumps(data, ensure_ascii=False)),
                )
    if isinstance(aliases, dict):
        for key, data in aliases.items():
            if isinstance(data, dict):
                conn.execute(
                    "INSERT OR REPLACE INTO identity_alias(alias_key, data) VALUES(?, ?)",
                    (str(key), json.dumps(data, ensure_ascii=False)),
                )
    if isinstance(blocked, dict):
        for key, data in blocked.items():
            if isinstance(data, dict):
                conn.execute(
                    "INSERT OR REPLACE INTO identity_blocked(blocked_key, data) VALUES(?, ?)",
                    (str(key), json.dumps(data, ensure_ascii=False)),
                )
    for key in ("version", "next_pid", "updated_at"):
        if key in raw:
            conn.execute(
                "INSERT OR REPLACE INTO identity_meta(key, value) VALUES(?, ?)",
                (key, json.dumps(raw[key], ensure_ascii=False)),
            )


# ---------------------------------------------------------------------------
# 行级写入辅助（迁移与保存共用）
# ---------------------------------------------------------------------------


def _save_group_settings_row(conn, group_id: str, data: dict, now: float) -> None:
    conn.execute(
        "INSERT INTO group_settings(group_id, data, updated_at) VALUES(?, ?, ?) "
        "ON CONFLICT(group_id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at",
        (str(group_id), json.dumps(data, ensure_ascii=False), now),
    )


def _save_quote_meta_row(conn, group_id: str, name: str, data: dict, now: float) -> None:
    conn.execute(
        "INSERT INTO quote_meta(group_id, name, data, updated_at) VALUES(?, ?, ?, ?) "
        "ON CONFLICT(group_id, name) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at",
        (str(group_id), str(name), json.dumps(data, ensure_ascii=False), now),
    )


def _save_semantic_index_row(conn, group_id: str, data: dict, now: float) -> None:
    conn.execute(
        "INSERT INTO semantic_index(group_id, data, updated_at) VALUES(?, ?, ?) "
        "ON CONFLICT(group_id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at",
        (str(group_id), json.dumps(data, ensure_ascii=False), now),
    )


def _save_semantic_item_row(conn, group_id: str, name: str, data: dict, now: float) -> None:
    conn.execute(
        "INSERT INTO semantic_item(group_id, name, data, updated_at) VALUES(?, ?, ?, ?) "
        "ON CONFLICT(group_id, name) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at",
        (str(group_id), str(name), json.dumps(data, ensure_ascii=False), now),
    )


def _save_sent_session_row(conn, umo: str, items: list, now: float) -> None:
    conn.execute(
        "INSERT INTO sent_session(umo, data, updated_at) VALUES(?, ?, ?) "
        "ON CONFLICT(umo) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at",
        (str(umo), json.dumps(items, ensure_ascii=False), now),
    )


def _save_doc_row(conn, scope: str, key: str, data: Any, now: float) -> None:
    conn.execute(
        "INSERT INTO doc(scope, key, data, updated_at) VALUES(?, ?, ?, ?) "
        "ON CONFLICT(scope, key) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at",
        (scope, key, json.dumps(data, ensure_ascii=False), now),
    )


# ---------------------------------------------------------------------------
# 群设置
# ---------------------------------------------------------------------------


def load_group_settings(group_id: str) -> dict | None:
    conn = _connect()
    with _lock:
        row = conn.execute(
            "SELECT data FROM group_settings WHERE group_id = ?", (str(group_id),)
        ).fetchone()
    if not row:
        return None
    try:
        data = json.loads(row["data"])
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def save_group_settings(group_id: str, data: dict) -> None:
    conn = _connect()
    with _lock:
        _save_group_settings_row(conn, str(group_id), data, time.time())
        conn.commit()


def load_all_group_settings() -> dict[str, dict]:
    conn = _connect()
    with _lock:
        rows = conn.execute("SELECT group_id, data FROM group_settings").fetchall()
    result: dict[str, dict] = {}
    for row in rows:
        try:
            data = json.loads(row["data"])
        except ValueError:
            continue
        if isinstance(data, dict):
            result[str(row["group_id"])] = data
    return result


# ---------------------------------------------------------------------------
# 语录元数据（原 quotes_meta.json）
# ---------------------------------------------------------------------------


def load_quote_meta(group_id: str) -> dict:
    conn = _connect()
    with _lock:
        rows = conn.execute(
            "SELECT name, data FROM quote_meta WHERE group_id = ?", (str(group_id),)
        ).fetchall()
    items: dict[str, dict] = {}
    for row in rows:
        try:
            data = json.loads(row["data"])
        except ValueError:
            continue
        if isinstance(data, dict):
            items[str(row["name"])] = data
    return {"version": 1, "items": items}


def save_quote_meta(group_id: str, payload: dict) -> None:
    conn = _connect()
    gid = str(group_id)
    items = payload.get("items") if isinstance(payload, dict) else None
    items = items if isinstance(items, dict) else {}
    now = time.time()
    with _lock:
        existing = {
            str(row["name"])
            for row in conn.execute(
                "SELECT name FROM quote_meta WHERE group_id = ?", (gid,)
            ).fetchall()
        }
        for name, item in items.items():
            if isinstance(item, dict):
                _save_quote_meta_row(conn, gid, str(name), item, now)
        stale = existing - {str(name) for name in items.keys()}
        if stale:
            conn.executemany(
                "DELETE FROM quote_meta WHERE group_id = ? AND name = ?",
                [(gid, name) for name in stale],
            )
        conn.commit()
    _fts_mark_dirty(gid)


# ---------------------------------------------------------------------------
# 语义索引（原 quotes_semantic.json）
# ---------------------------------------------------------------------------


def load_semantic(group_id: str) -> dict:
    conn = _connect()
    gid = str(group_id)
    with _lock:
        index_row = conn.execute(
            "SELECT data FROM semantic_index WHERE group_id = ?", (gid,)
        ).fetchone()
        rows = conn.execute(
            "SELECT name, data FROM semantic_item WHERE group_id = ?", (gid,)
        ).fetchall()
    index: dict = {}
    if index_row:
        try:
            raw = json.loads(index_row["data"])
        except ValueError:
            raw = None
        if isinstance(raw, dict):
            index = raw
    items: dict[str, dict] = {}
    for row in rows:
        try:
            data = json.loads(row["data"])
        except ValueError:
            continue
        if isinstance(data, dict):
            items[str(row["name"])] = data
    payload = dict(index)
    payload.setdefault("version", 2)
    payload.setdefault("signature", "")
    payload.setdefault("provider", {})
    payload.setdefault("updated_at", 0)
    payload["items"] = items
    return payload


def save_semantic(group_id: str, data: dict) -> None:
    conn = _connect()
    gid = str(group_id)
    now = time.time()
    index = {
        "version": data.get("version"),
        "signature": data.get("signature") or "",
        "provider": data.get("provider") or {},
        "updated_at": data.get("updated_at") or now,
    }
    items = data.get("items") if isinstance(data, dict) else None
    items = items if isinstance(items, dict) else {}
    with _lock:
        _save_semantic_index_row(conn, gid, index, now)
        existing = {
            str(row["name"])
            for row in conn.execute(
                "SELECT name FROM semantic_item WHERE group_id = ?", (gid,)
            ).fetchall()
        }
        for name, item in items.items():
            if isinstance(item, dict):
                _save_semantic_item_row(conn, gid, str(name), item, now)
        stale = existing - {str(name) for name in items.keys()}
        if stale:
            conn.executemany(
                "DELETE FROM semantic_item WHERE group_id = ? AND name = ?",
                [(gid, name) for name in stale],
            )
        conn.commit()
    _fts_mark_dirty(gid)


# ---------------------------------------------------------------------------
# 人物档案（原 identities.json）
# ---------------------------------------------------------------------------


def load_identity_state() -> dict | None:
    conn = _connect()
    with _lock:
        user_rows = conn.execute("SELECT user_id, data FROM identity_user").fetchall()
        person_rows = conn.execute(
            "SELECT person_key, data FROM identity_person"
        ).fetchall()
        alias_rows = conn.execute("SELECT alias_key, data FROM identity_alias").fetchall()
        blocked_rows = conn.execute(
            "SELECT blocked_key, data FROM identity_blocked"
        ).fetchall()
        meta_rows = conn.execute("SELECT key, value FROM identity_meta").fetchall()
    if not user_rows and not person_rows:
        return None

    def _decode(rows, key_field: str) -> dict:
        result: dict = {}
        for row in rows:
            try:
                data = json.loads(row["data"])
            except ValueError:
                continue
            if isinstance(data, dict):
                result[str(row[key_field])] = data
        return result

    state: dict = {
        "users": _decode(user_rows, "user_id"),
        "persons": _decode(person_rows, "person_key"),
        "aliases": _decode(alias_rows, "alias_key"),
        "blocked": _decode(blocked_rows, "blocked_key"),
        "version": 1,
        "updated_at": 0.0,
        "next_pid": 1,
    }
    for row in meta_rows:
        try:
            value = json.loads(row["value"])
        except ValueError:
            continue
        key = str(row["key"])
        if key in ("version", "next_pid", "updated_at"):
            state[key] = value
    if "next_pid" not in state or not isinstance(state.get("next_pid"), int):
        state["next_pid"] = 1
    return state


def save_identity_state(state: dict) -> None:
    conn = _connect()
    now = time.time()
    users = state.get("users") or {}
    persons = state.get("persons") or {}
    aliases = state.get("aliases") or {}
    blocked = state.get("blocked") or {}
    with _lock:
        _sync_rows(conn, "identity_user", "user_id", users)
        _sync_rows(conn, "identity_person", "person_key", persons)
        _sync_rows(conn, "identity_alias", "alias_key", aliases)
        _sync_rows(conn, "identity_blocked", "blocked_key", blocked)
        for key in ("version", "next_pid", "updated_at"):
            if key in state:
                conn.execute(
                    "INSERT OR REPLACE INTO identity_meta(key, value) VALUES(?, ?)",
                    (key, json.dumps(state[key], ensure_ascii=False)),
                )
        conn.commit()
    del now


def _sync_rows(conn: sqlite3.Connection, table: str, key_field: str, rows: dict) -> None:
    existing = {
        str(row[0])
        for row in conn.execute(f"SELECT {key_field} FROM {table}").fetchall()
    }
    target = {str(key) for key in rows.keys()}
    for key, data in rows.items():
        if isinstance(data, dict):
            conn.execute(
                f"INSERT INTO {table}({key_field}, data) VALUES(?, ?) "
                f"ON CONFLICT({key_field}) DO UPDATE SET data = excluded.data",
                (str(key), json.dumps(data, ensure_ascii=False)),
            )
    stale = existing - target
    if stale:
        conn.executemany(
            f"DELETE FROM {table} WHERE {key_field} = ?", [(key,) for key in stale]
        )


# ---------------------------------------------------------------------------
# 发送记忆（原 quotes_sent.json）
# ---------------------------------------------------------------------------


def load_sent() -> dict:
    conn = _connect()
    with _lock:
        rows = conn.execute("SELECT umo, data FROM sent_session").fetchall()
    sessions: dict[str, list] = {}
    for row in rows:
        try:
            data = json.loads(row["data"])
        except ValueError:
            continue
        if isinstance(data, list):
            sessions[str(row["umo"])] = data
    return {"version": 1, "sessions": sessions}


def save_sent(payload: dict) -> None:
    conn = _connect()
    sessions = payload.get("sessions") if isinstance(payload, dict) else None
    sessions = sessions if isinstance(sessions, dict) else {}
    now = time.time()
    with _lock:
        _sync_sent_sessions(conn, sessions, now)
        conn.commit()


def _sync_sent_sessions(conn, sessions: dict, now: float) -> None:
    existing = {
        str(row[0]) for row in conn.execute("SELECT umo FROM sent_session").fetchall()
    }
    target = {str(umo) for umo in sessions.keys()}
    for umo, items in sessions.items():
        if isinstance(items, list):
            _save_sent_session_row(conn, str(umo), items, now)
    stale = existing - target
    if stale:
        conn.executemany(
            "DELETE FROM sent_session WHERE umo = ?", [(umo,) for umo in stale]
        )


# ---------------------------------------------------------------------------
# 单值文档（自动同步设置 / 更新推送设置）
# ---------------------------------------------------------------------------


def load_doc(scope: str, key: str) -> Any:
    conn = _connect()
    with _lock:
        row = conn.execute(
            "SELECT data FROM doc WHERE scope = ? AND key = ?", (scope, key)
        ).fetchone()
    if not row:
        return None
    try:
        return json.loads(row["data"])
    except ValueError:
        return None


def save_doc(scope: str, key: str, value: Any) -> None:
    conn = _connect()
    with _lock:
        _save_doc_row(conn, scope, key, value, time.time())
        conn.commit()


# ---------------------------------------------------------------------------
# 状态信息（供调试 / 管理接口使用）
# ---------------------------------------------------------------------------


def load_collections(group_id: str) -> dict:
    """读取某群的全部专题合集：{collection_id: data}。"""
    gid = str(group_id or "").strip()
    if not gid:
        return {}
    conn = _connect()
    with _lock:
        rows = conn.execute(
            "SELECT collection_id, data FROM collection WHERE group_id = ?", (gid,)
        ).fetchall()
    result: dict = {}
    for row in rows:
        try:
            data = json.loads(row["data"])
        except ValueError:
            continue
        if isinstance(data, dict):
            result[str(row["collection_id"])] = data
    return result


def save_collection(group_id: str, collection_id: str, data: dict) -> None:
    conn = _connect()
    now = time.time()
    with _lock:
        conn.execute(
            "INSERT INTO collection (group_id, collection_id, data, updated_at) "
            "VALUES (?, ?, ?, ?) ON CONFLICT(group_id, collection_id) "
            "DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at",
            (str(group_id), str(collection_id), json.dumps(data, ensure_ascii=False), now),
        )
        conn.commit()


def delete_collection(group_id: str, collection_id: str) -> None:
    conn = _connect()
    with _lock:
        conn.execute(
            "DELETE FROM collection WHERE group_id = ? AND collection_id = ?",
            (str(group_id), str(collection_id)),
        )
        conn.commit()


def info() -> dict:
    conn = _connect()
    path = db_path()
    with _lock:
        tables = {
            "group_settings": "group_settings",
            "quote_meta": "quote_meta",
            "semantic_item": "semantic_item",
            "identity_user": "identity_user",
            "identity_person": "identity_person",
            "identity_alias": "identity_alias",
            "identity_blocked": "identity_blocked",
            "sent_session": "sent_session",
            "doc": "doc",
            "collection": "collection",
        }
        counts: dict[str, int] = {}
        for label, table in tables.items():
            row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
            counts[label] = int(row["n"]) if row else 0
        meta_rows = conn.execute("SELECT key, value FROM meta").fetchall()
    meta = {str(row["key"]): str(row["value"]) for row in meta_rows}
    size = path.stat().st_size if path.is_file() else 0
    wal = path.with_name(path.name + "-wal")
    return {
        "path": str(path),
        "size": size,
        "wal_size": wal.stat().st_size if wal.is_file() else 0,
        "schema_version": meta.get("schema_version"),
        "migrated_at": meta.get("migrated_at"),
        "migrated_sources": meta.get("migrated_sources"),
        "counts": counts,
    }


def checkpoint() -> dict:
    """把 WAL 合并进主库文件，便于备份。"""
    conn = _connect()
    with _lock:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
    return info()


# ---------------------------------------------------------------------------
# A1：全文检索（FTS5，大字符集按 CJK 单字 + 二元组切分）
# ---------------------------------------------------------------------------

_WORD_RE = re.compile(r"[a-z0-9]+|[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+")

_fts_dirty: set[str] = set()


def _fts_split(text: str) -> list[str]:
    tokens: list[str] = []
    for chunk in _WORD_RE.findall(str(text or "").lower()):
        if chunk[0].isascii():
            tokens.append(chunk)
            continue
        if len(chunk) == 1:
            tokens.append(chunk)
            continue
        tokens.extend(chunk[i : i + 2] for i in range(len(chunk) - 1))
        tokens.extend(list(chunk))
    return tokens


def _fts_doc_text(gid: str) -> dict[str, str]:
    conn = _connect()
    with _lock:
        meta_rows = conn.execute(
            "SELECT name, data FROM quote_meta WHERE group_id = ?", (str(gid),)
        ).fetchall()
        sem_rows = conn.execute(
            "SELECT name, data FROM semantic_item WHERE group_id = ?", (str(gid),)
        ).fetchall()

    def _decode(rows):
        result: dict = {}
        for row in rows:
            try:
                data = json.loads(row["data"])
            except ValueError:
                continue
            if isinstance(data, dict):
                result[str(row["name"])] = data
        return result

    meta = _decode(meta_rows)
    sem = _decode(sem_rows)
    docs: dict[str, str] = {}
    for name in set(meta) | set(sem):
        parts: list[str] = []
        info = meta.get(name) or {}
        entry = sem.get(name) or {}
        for source in (info, entry):
            for key in (
                "caption",
                "speaker",
                "nickname",
                "subject_name",
                "visible_text",
                "tone",
                "message_text",
            ):
                value = source.get(key)
                if isinstance(value, str) and value.strip():
                    parts.append(value.strip())
            tags = source.get("tags")
            if isinstance(tags, list):
                parts.extend(str(tag).strip() for tag in tags if str(tag).strip())
        parts.append(str(name))
        docs[name] = "\n".join(parts)
    return docs


def _fts_mark_dirty(group_id: str) -> None:
    gid = str(group_id or "").strip()
    if gid:
        _fts_dirty.add(gid)


def fts_rebuild(group_id: str) -> int:
    gid = str(group_id or "").strip()
    if not gid:
        return 0
    docs = _fts_doc_text(gid)
    conn = _connect()
    rows = []
    for name, text in docs.items():
        tokens = " ".join(_fts_split(text))
        rows.append((gid, name, text, tokens))
    with _lock:
        conn.execute("DELETE FROM quote_fts WHERE group_id = ?", (gid,))
        if rows:
            conn.executemany(
                "INSERT INTO quote_fts(group_id, name, text, tokens) VALUES(?, ?, ?, ?)",
                rows,
            )
        conn.commit()
    _fts_dirty.discard(gid)
    return len(rows)


def fts_rebuild_all() -> int:
    conn = _connect()
    with _lock:
        groups = [
            str(row[0])
            for row in conn.execute(
                "SELECT DISTINCT group_id FROM quote_meta UNION SELECT DISTINCT group_id FROM semantic_item"
            ).fetchall()
        ]
    total = 0
    for gid in groups:
        total += fts_rebuild(gid)
    return total


def fts_search(query: str, group_id: str = "", limit: int = 300) -> list[dict]:
    gid = str(group_id or "").strip()
    tokens = _fts_split(query)
    if not tokens:
        return []
    if gid in _fts_dirty:
        fts_rebuild(gid)
    expr = " ".join('"' + token.replace('"', "") + '"' for token in tokens)
    conn = _connect()
    sql = (
        "SELECT group_id, name, bm25(quote_fts) AS score FROM quote_fts "
        "WHERE quote_fts MATCH ?"
    )
    params: list = [expr]
    if gid:
        sql += " AND group_id = ?"
        params.append(gid)
    sql += " ORDER BY score LIMIT ?"
    params.append(max(1, min(1000, int(limit or 300))))
    try:
        with _lock:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        return []
    return [
        {
            "group_id": str(row["group_id"]),
            "name": str(row["name"]),
            "score": float(row["score"]),
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# A3：回收站（软删除，可恢复 / 彻底清除）
# ---------------------------------------------------------------------------


def trash_put(group_id: str, name: str, data: dict) -> None:
    conn = _connect()
    now = time.time()
    with _lock:
        conn.execute(
            "INSERT INTO trash(group_id, name, data, deleted_at) VALUES(?, ?, ?, ?) "
            "ON CONFLICT(group_id, name) DO UPDATE SET data = excluded.data, deleted_at = excluded.deleted_at",
            (
                str(group_id),
                str(name),
                json.dumps(data or {}, ensure_ascii=False),
                now,
            ),
        )
        conn.commit()


def trash_list(group_id: str = "") -> list[dict]:
    conn = _connect()
    gid = str(group_id or "").strip()
    sql = "SELECT group_id, name, data, deleted_at FROM trash"
    params: list = []
    if gid:
        sql += " WHERE group_id = ?"
        params.append(gid)
    sql += " ORDER BY deleted_at DESC"
    with _lock:
        rows = conn.execute(sql, params).fetchall()
    result = []
    for row in rows:
        try:
            data = json.loads(row["data"])
        except ValueError:
            data = {}
        result.append(
            {
                "group_id": str(row["group_id"]),
                "name": str(row["name"]),
                "deleted_at": float(row["deleted_at"]),
                "size": int((data or {}).get("size") or 0),
                "meta": (data or {}).get("meta") or {},
            }
        )
    return result


def trash_get(group_id: str, name: str) -> dict | None:
    conn = _connect()
    with _lock:
        row = conn.execute(
            "SELECT data FROM trash WHERE group_id = ? AND name = ?",
            (str(group_id), str(name)),
        ).fetchone()
    if not row:
        return None
    try:
        data = json.loads(row["data"])
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def trash_delete(group_id: str, names: list[str]) -> int:
    conn = _connect()
    gid = str(group_id)
    items = [(gid, str(name)) for name in names or []]
    if not items:
        return 0
    with _lock:
        conn.executemany("DELETE FROM trash WHERE group_id = ? AND name = ?", items)
        conn.commit()
    return len(items)


def trash_clear_group(group_id: str) -> int:
    conn = _connect()
    with _lock:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM trash WHERE group_id = ?", (str(group_id),)
        ).fetchone()
        conn.execute("DELETE FROM trash WHERE group_id = ?", (str(group_id),))
        conn.commit()
    return int(row["n"]) if row else 0


def trash_old(days: int) -> list[tuple[str, str]]:
    conn = _connect()
    cutoff = time.time() - max(1, int(days or 30)) * 86400
    with _lock:
        rows = conn.execute(
            "SELECT group_id, name FROM trash WHERE deleted_at < ?", (cutoff,)
        ).fetchall()
    return [(str(row["group_id"]), str(row["name"])) for row in rows]


# ---------------------------------------------------------------------------
# B1：自动打标签队列
# ---------------------------------------------------------------------------


def tag_queue_add(group_id: str, names: list[str]) -> int:
    conn = _connect()
    gid = str(group_id)
    now = time.time()
    rows = [
        (gid, str(name), "queued", 0, "", now)
        for name in names or []
        if str(name).strip()
    ]
    if not rows:
        return 0
    with _lock:
        before = conn.total_changes
        conn.executemany(
            "INSERT OR IGNORE INTO tag_queue(group_id, name, status, attempts, error, updated_at) "
            "VALUES(?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
        return int(conn.total_changes - before)


def tag_queue_names(group_id: str) -> set[str]:
    conn = _connect()
    with _lock:
        rows = conn.execute(
            "SELECT name FROM tag_queue WHERE group_id = ? AND status IN ('queued', 'done', 'skipped', 'missing')",
            (str(group_id),),
        ).fetchall()
    return {str(row["name"]) for row in rows}


def tag_queue_next() -> dict | None:
    conn = _connect()
    with _lock:
        row = conn.execute(
            "SELECT group_id, name, attempts FROM tag_queue WHERE status = 'queued' "
            "ORDER BY updated_at ASC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        conn.execute(
            "UPDATE tag_queue SET status = 'running', updated_at = ? WHERE group_id = ? AND name = ?",
            (time.time(), row["group_id"], row["name"]),
        )
        conn.commit()
    return {
        "group_id": str(row["group_id"]),
        "name": str(row["name"]),
        "attempts": int(row["attempts"] or 0),
    }


def tag_queue_set(
    group_id: str, name: str, status: str, attempts: int = 0, error: str = ""
) -> None:
    conn = _connect()
    with _lock:
        conn.execute(
            "UPDATE tag_queue SET status = ?, attempts = ?, error = ?, updated_at = ? "
            "WHERE group_id = ? AND name = ?",
            (
                str(status),
                int(attempts or 0),
                str(error or "")[:500],
                time.time(),
                str(group_id),
                str(name),
            ),
        )
        conn.commit()


def tag_queue_reset_running() -> int:
    conn = _connect()
    with _lock:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM tag_queue WHERE status = 'running'"
        ).fetchone()
        conn.execute(
            "UPDATE tag_queue SET status = 'queued', updated_at = ? WHERE status = 'running'",
            (time.time(),),
        )
        conn.commit()
    return int(row["n"]) if row else 0


def tag_queue_stats() -> dict:
    conn = _connect()
    with _lock:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM tag_queue GROUP BY status"
        ).fetchall()
    counts = {str(row["status"]): int(row["n"]) for row in rows}
    pending = counts.get("queued", 0) + counts.get("running", 0)
    return {
        "queued": counts.get("queued", 0),
        "running": counts.get("running", 0),
        "done": counts.get("done", 0),
        "failed": counts.get("failed", 0),
        "skipped": counts.get("skipped", 0),
        "missing": counts.get("missing", 0),
        "pending": pending,
        "total": sum(counts.values()),
    }


def tag_queue_clear(status: str = "") -> int:
    conn = _connect()
    with _lock:
        if status:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM tag_queue WHERE status = ?", (str(status),)
            ).fetchone()
            conn.execute("DELETE FROM tag_queue WHERE status = ?", (str(status),))
        else:
            row = conn.execute("SELECT COUNT(*) AS n FROM tag_queue").fetchone()
            conn.execute("DELETE FROM tag_queue")
        conn.commit()
    return int(row["n"]) if row else 0


# ---------------------------------------------------------------------------
# 俗名候选队列（v2.15.0）
# ---------------------------------------------------------------------------


def _alias_candidate_dict(row) -> dict:
    keys = row.keys()
    return {
        "id": int(row["id"]),
        "group_id": str(row["group_id"] or ""),
        "alias_key": str(row["alias_key"] or ""),
        "alias_name": str(row["alias_name"] or ""),
        "target_pid": str(row["target_pid"] or ""),
        "target_user_id": str(row["target_user_id"] or ""),
        "display_name": str(row["display_name"] or ""),
        "evidence": str(row["evidence"] or ""),
        "evidence_user": str(row["evidence_user"] or ""),
        "confidence": float(row["confidence"] or 0.0),
        "occurrences": int(row["occurrences"] or 0) if "occurrences" in keys else 0,
        "status": str(row["status"] or "pending"),
        "created_at": float(row["created_at"] or 0.0),
        "updated_at": float(row["updated_at"] or 0.0),
    }


def load_alias_candidates(group_id: str = "", status: str = "pending", limit: int = 200) -> list:
    """读取俗名候选：按群与状态过滤，按置信度、时间排序。"""
    conn = _connect()
    gid = str(group_id or "").strip()
    state = str(status or "pending").strip() or "pending"
    size = max(1, min(500, int(limit or 200)))
    sql = "SELECT * FROM alias_candidate WHERE status = ?"
    args = [state]
    if gid:
        sql += " AND group_id = ?"
        args.append(gid)
    sql += " ORDER BY confidence DESC, updated_at DESC LIMIT ?"
    args.append(size)
    with _lock:
        rows = conn.execute(sql, tuple(args)).fetchall()
    return [_alias_candidate_dict(row) for row in rows]


def count_alias_candidates(group_id: str = "", status: str = "pending") -> int:
    conn = _connect()
    gid = str(group_id or "").strip()
    state = str(status or "pending").strip() or "pending"
    sql = "SELECT COUNT(*) AS total FROM alias_candidate WHERE status = ?"
    args = [state]
    if gid:
        sql += " AND group_id = ?"
        args.append(gid)
    with _lock:
        row = conn.execute(sql, tuple(args)).fetchone()
    return int(row["total"] if row else 0)


def get_alias_candidate(candidate_id: int):
    conn = _connect()
    try:
        cid = int(candidate_id)
    except (TypeError, ValueError):
        return None
    with _lock:
        row = conn.execute(
            "SELECT * FROM alias_candidate WHERE id = ?", (cid,)
        ).fetchone()
    return _alias_candidate_dict(row) if row else None


def add_alias_candidate(
    group_id: str,
    alias_key: str,
    alias_name: str,
    target_pid: str,
    target_user_id: str,
    display_name: str,
    evidence: str,
    evidence_user: str,
    confidence: float,
    occurrences: int = 0,
) -> int:
    """写入一条待确认俗名；同一群+别名+目标只保留一条，重复出现时取最高置信度与最大出现次数。"""
    conn = _connect()
    now = time.time()
    gid = str(group_id or "").strip()
    key = str(alias_key or "").strip()
    name = str(alias_name or "").strip()[:32]
    uid = str(target_user_id or "").strip()
    if not gid or not key or not name or not uid:
        return 0
    value = max(0.0, min(1.0, float(confidence or 0.0)))
    occ = max(0, int(occurrences or 0))
    with _lock:
        row = conn.execute(
            "SELECT id, confidence, occurrences FROM alias_candidate "
            "WHERE group_id = ? AND alias_key = ? AND target_user_id = ? AND status = 'pending'",
            (gid, key, uid),
        ).fetchone()
        if row:
            merged = max(float(row["confidence"] or 0.0), value)
            merged_occ = max(int(row["occurrences"] or 0), occ)
            conn.execute(
                "UPDATE alias_candidate SET alias_name = ?, display_name = ?, target_pid = ?, "
                "evidence = ?, confidence = ?, occurrences = ?, updated_at = ? WHERE id = ?",
                (
                    name,
                    str(display_name or "").strip()[:64],
                    str(target_pid or "").strip(),
                    str(evidence or "").strip()[:200],
                    merged,
                    merged_occ,
                    now,
                    int(row["id"]),
                ),
            )
            conn.commit()
            return int(row["id"])
        cur = conn.execute(
            "INSERT INTO alias_candidate (group_id, alias_key, alias_name, target_pid, "
            "target_user_id, display_name, evidence, evidence_user, confidence, occurrences, "
            "status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)",
            (
                gid,
                key,
                name,
                str(target_pid or "").strip(),
                uid,
                str(display_name or "").strip()[:64],
                str(evidence or "").strip()[:200],
                str(evidence_user or "").strip()[:64],
                value,
                occ,
                now,
                now,
            ),
        )
        conn.commit()
        return int(cur.lastrowid or 0)


def set_alias_candidate_status(candidate_id: int, status: str) -> bool:
    conn = _connect()
    try:
        cid = int(candidate_id)
    except (TypeError, ValueError):
        return False
    state = str(status or "").strip()
    if not state:
        return False
    with _lock:
        cur = conn.execute(
            "UPDATE alias_candidate SET status = ?, updated_at = ? WHERE id = ?",
            (state, time.time(), cid),
        )
        conn.commit()
    return bool(cur.rowcount)
