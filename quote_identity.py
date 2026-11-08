"""quote_collocter — 群友语录收集器 / WebUI 管理页面

v2.0:
  * 新增 WebUI「插件页面」语录管理器（pages/manage），可浏览、检索、批量删除、跨群移动、改设置
  * 新增插件 Web API（注册在 /quote_collocter/*）
  * 新增语录元数据 quotes_meta.json（投稿人 / 时间 / 消息 ID），为后续语义化留字段
  * 新增缩略图缓存 data/quotes_data/.thumbs/<群号>/
  * 原有指令与戳一戳行为保持兼容

v2.1:
  * 一键语义化：视觉模型产出 caption / tags / tone / speaker / visible_text，向量模型建索引
  * 语义检索：quotes 接口 mode=semantic + min_score，按余弦相似度排序
  * 索引存于 data/quotes_data/<群号>/quotes_semantic.json

v2.2:
  * 发送记忆：机器人发出的每条语录（/语录 与戳一戳）都会记进 data/plugin_data/quote_collocter/quotes_sent.json
  * on_llm_request 钩子把这些语录作为系统提醒注入上下文，让 AI 记住自己刚发过什么
  * 新增 sent 接口（状态 / 清空）与群设置项 remember

v2.3:
  * 修复插件页面被 sandbox iframe 包裹时 window.confirm 被拦截、按钮点击无响应的问题
  * 管理页面所有破坏性操作改用页面内自绘确认框

v2.4:
  * 新增 AI 语义召回：LLM 工具 recall_quotes 按语义检索本群语录图片
  * 回复中用 &&候选id&& 标记即可随消息发送图片，并记入发送记忆
  * 群设置新增 recall 开关（默认开启），管理页面可切换

v2.5:
  * 新增人物档案：QQ 号 ↔ 昵称历史 / 头像历史（dHash 指纹）双向关联
  * 群友换昵称、换头像后仍能认出是同一个人；同一人的多个 QQ 号可合并为一个 person
  * 管理页新增「人物档案」：同步头像、以图找人、合并 / 拆分身份、查看曾用名与头像墙
  * 语录卡片展示投稿人最新昵称与头像；投稿时自动刷新头像存档

v2.6:
  * 语录归属改为「语录里被拍的那个人」，而不是投稿人：每条语录通过视觉模型识别截图里的
    说话人昵称，自动匹配到群成员档案，按人物归纳语录
  * 管理页语录卡片显示归属人物头像与昵称；支持单条 / 批量手动指定人物、清除归属
  * 「人物档案」页面改为「语录人物」：按人物查看其名下全部语录缩略图
  * 新增接口：quotes/subject（指定归属）、quotes/auto_subject（按已有语义 speaker 回填）、
    identity/match_names（昵称 → 群成员候选）

v2.7:
  * 新增昵称别名表（identities.json 的 aliases）：截图里的各种昵称映射到 QQ 号，不再写进群名片历史
  * 归属识别时先查别名表，再按形近程度匹配；同一人被读错的名字可一键归并
  * 新增接口：identity/clusters（形近变体聚类）、identity/cluster_merge（一键归并）、
    identity/cleanup（整理旧别名）、identity/aliases、identity/alias_delete
  * 管理页「待确认归属」展示形近变体分组，可直接归并；新增「整理旧别名」按钮

v2.8:
  * AI 复述语录人物时改用群昵称（群名片优先），不再出现 QQ 号 / 数字 ID
  * recall_quotes 候选新增 who 字段（群昵称），并提示模型不要输出 QQ 号
  * 发送记忆里的说话人行改用群昵称，缺失时用「群友」代称

v2.8.1:
  * 召回标记只认图片 id（&&image_xxx.jpg&&），其它 &&文字&& 原样保留，避免误删正文
  * 标记校验放宽：只要本群目录中存在该图片即可发送，模型引用上下文旧 id 不再失效
  * 无效标记会记录原始文本（截断），便于排查模型写错的内容
  * 新增群设置「AI 没写标记时自动补发 top1」（auto_recall，默认关闭）

v2.8.2:
  * 放宽 AI 召回提示词：候选语录再逆天/擦边/露骨也照发，不再审查、劝退或要求换图
  * 群友点名要某张图 / 某人的语录时必须发送；回复只用一句吐槽，不复述原图敏感细节

v2.9.0:
  * 新增语录统计：总量、人物 / 投稿人排名、最近 30 天新增趋势、语义化覆盖率
  * 管理页新增「语录统计」弹窗，可按群筛选并查看语录数量排名
  * 群内新增「/语录排行」命令，输出本群语录数量与投稿数量排名

v2.9.1:
  * 修复群头衔 / LV 等级 / 身份徽章被 OCR 读成昵称、顶替 QQ 号成为语录归属的问题
  * 识别提示词要求 speaker 只取群名片或昵称本身，忽略 LV、头衔、徽章、签名档
  * 新增群头衔屏蔽词：成员列表的 title 与群主/管理员身份不再参与昵称匹配
  * 别名表增加可信度标记：只有人工/合并/字形高度相似的别名才用于自动归属
  * 「整理旧别名」扩展为「整理归属」：删除头衔别名、去重别名、解除错误归属

v2.9.2:
  * 修复群友改昵称 / 换号后，已确认归属的语录在 AI 召回里搜不到的问题
  * 召回时先核对 query 里的 QQ 号，再用该 QQ 的昵称 / 别名列表识别当事人，直接取出其名下语录

v2.9.3:
  * 新增身份自动同步：默认每 24 小时自动同步一次群成员昵称 / 群名片 / 头衔 / 头像
  * 周期可调（1–168 小时）或暂停；管理页「语录人物」顶部显示上次 / 下次同步时间
  * 新增接口 identity/schedule（GET 读取、POST 保存），设置存于 plugin_data/identity_sync.json

v2.9.4:
  * 插件更新后通过 DSH 桥接（astrbot_plugin_dsh_bridge）向白名单群聊自动推送更新日志
  * 白名单默认填充两个开放权限的群（1031430106 / 478864863），可在 plugin_data/update_announce.json 调整
  * 同一版本只推送一次；新增接口 announce（GET 预览 / POST 保存或测试推送）
"""

from __future__ import annotations

import asyncio
import base64
import difflib
import hashlib
import io
import json
import math
import os
import random
import re
import shutil
import tempfile
import threading
import time
from pathlib import Path

import aiohttp
import yaml

from astrbot import logger
from astrbot.api.all import *
from astrbot.api.web import error_response, json_response, request
from astrbot.api.event import filter
from astrbot.core.agent.message import TextPart
from astrbot.core.message.components import At, Image, Plain, Reply
from astrbot.core.message.message_event_result import ResultContentType
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)

try:
    from PIL import Image as PILImage
except Exception:  # pragma: no cover - Pillow 缺失时退化为原图
    PILImage = None

from quote_core import *  # noqa: F401,F403

import quote_db
from quote_core import IDENTITY_ALIAS_CONFIRM_RATIO, IDENTITY_ALIAS_SOURCE, IDENTITY_AUTO_SYNC_FILE, IDENTITY_AUTO_SYNC_INTERVAL, IDENTITY_AUTO_SYNC_MAX_HOURS, IDENTITY_AUTO_SYNC_MIN_HOURS, IDENTITY_AVATAR_DIR, IDENTITY_AVATAR_KEEP, IDENTITY_AVATAR_MAX_BYTES, IDENTITY_AVATAR_TTL, IDENTITY_AVATAR_URL, IDENTITY_DEFAULT_AVATAR_MAX_SIDE, IDENTITY_FILE, IDENTITY_MATCH_THRESHOLD, IDENTITY_MAX_SIDE, IDENTITY_NAME_KEEP, IDENTITY_THUMB_SIDE, IDENTITY_VERSION, PLUGIN_DATA_DIR, SPEAKER_SPLIT_RE, SUBJECT_ROLE_RE, SUBJECT_ROLE_WORDS, SUBJECT_TITLE_PREFIX_RE


def identity_store_path() -> Path:
    return PLUGIN_DATA_DIR / IDENTITY_FILE

def identity_avatar_dir() -> Path:
    return PLUGIN_DATA_DIR / IDENTITY_AVATAR_DIR

def avatar_cdn_url(user_id: str) -> str:
    return IDENTITY_AVATAR_URL.format(user_id=str(user_id))

def dhash_hex(data: bytes) -> str:
    """64 位差值哈希（16 进制）。Pillow 缺失或图片损坏时返回空串。"""
    if PILImage is None or not data:
        return ""
    try:
        image = PILImage.open(io.BytesIO(data))
        image = image.convert("L").resize(
            (9, 8), getattr(PILImage, "Resampling", PILImage).LANCZOS
        )
        pixels = list(image.getdata())
    except Exception:
        return ""
    bits = 0
    for row in range(8):
        for col in range(8):
            left = pixels[row * 9 + col]
            right = pixels[row * 9 + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return f"{bits:016x}"

def hamming_distance(left: str, right: str) -> int:
    """两个 16 进制 dHash 的汉明距离；非法输入返回 64。"""
    try:
        return bin(int(str(left), 16) ^ int(str(right), 16)).count("1")
    except (TypeError, ValueError):
        return 64

def _looks_like_default_avatar(data: bytes) -> bool:
    """QQ 默认头像尺寸很小（约 40×40），不能当作身份特征。"""
    if PILImage is None:
        return len(data) < 2048
    try:
        width, height = PILImage.open(io.BytesIO(data)).size
    except Exception:
        return True
    return max(width, height) <= IDENTITY_DEFAULT_AVATAR_MAX_SIDE

def normalize_avatar(data: bytes):
    """压缩成 JPEG 并计算指纹；返回 (jpeg_bytes, dhash, 是否为默认头像)。"""
    if not data:
        return None
    default = _looks_like_default_avatar(data)
    if PILImage is None:
        return data, "", default
    try:
        image = PILImage.open(io.BytesIO(data))
        image.load()
    except Exception:
        return None
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    if max(image.size) > IDENTITY_MAX_SIDE:
        image.thumbnail((IDENTITY_MAX_SIDE, IDENTITY_MAX_SIDE))
    buffer = io.BytesIO()
    try:
        image.save(buffer, format="JPEG", quality=88)
    except OSError:
        return None
    jpeg = buffer.getvalue()
    return jpeg, dhash_hex(jpeg), default

async def fetch_avatar_bytes(user_id: str):
    """从 QQ 头像 CDN 拉取指定 QQ 号的头像。"""
    url = avatar_cdn_url(user_id)
    try:
        timeout = aiohttp.ClientTimeout(total=12)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                url, headers={"User-Agent": "Mozilla/5.0"}
            ) as response:
                if response.status != 200:
                    return None
                data = await response.read()
    except Exception as exc:
        logger.debug(f"[quote] 拉取 QQ {user_id} 头像失败：{exc}")
        return None
    if not data or len(data) > IDENTITY_AVATAR_MAX_BYTES:
        return None
    return data

def identity_latest_name(user: dict) -> str:
    """取该用户最合适的称呼：优先群名片（card），其次最近使用的昵称。"""
    names = [item for item in (user.get("names") or []) if item.get("name")]
    if not names:
        return ""
    cards = [item for item in names if item.get("card")]
    pool = cards or names
    pool = sorted(pool, key=lambda item: item.get("last_seen") or 0)
    return str(pool[-1]["name"])

def _clean_ai_name(value: str) -> str:
    """过滤掉不适合给大模型看的名字（纯数字 / QQ 号样式）。"""
    text = str(value or "").strip()
    if not text:
        return ""
    if re.fullmatch(r"[\d\s\-_]{4,}", text):
        return ""
    return text[:40]

def _clean_speaker_name(value: str) -> str:
    """OCR 得到的 speaker 只保留像昵称的短文本，长句 / 带标点的多半是识别错位。"""
    text = _clean_ai_name(value)
    if not text:
        return ""
    if len(text) > 16 or re.search(r"[，。！？；：,!?;:、\n]", text):
        return ""
    return text

def _strip_speaker_titles(value: str) -> str:
    """去掉 LV 等级、群头衔、身份前缀；取并列名里最像昵称的一段。"""
    text = str(value or "").strip()
    if not text:
        return ""
    text = SUBJECT_TITLE_PREFIX_RE.sub("", text)
    text = SUBJECT_ROLE_RE.sub("", text)
    text = re.sub(r"^\s*[【\[（(]\s*[^】\]）)]{1,12}[】\]）)]\s*", "", text)
    parts = [item.strip() for item in SPEAKER_SPLIT_RE.split(text) if item.strip()]
    if len(parts) > 1:
        parts.sort(key=lambda item: (item in SUBJECT_ROLE_WORDS, -len(item)))
        text = parts[0]
    return text.strip()

def clean_speaker_title(value: str) -> str:
    """把 OCR/群头衔混在一起的说话人文本洗成干净的昵称。"""
    text = _strip_speaker_titles(value)
    text = _clean_speaker_name(text)
    if not text:
        return ""
    text = SUBJECT_TITLE_PREFIX_RE.sub("", text).strip()
    text = SUBJECT_ROLE_RE.sub("", text).strip()
    return text[:20]

def _identity_ai_name(person_id: str = "", user_id: str = "") -> str:
    """从人物档案里取群昵称；取不到返回空串。"""
    uid = str(user_id or "").strip()
    pid = str(person_id or "").strip()
    try:
        if uid:
            row = IDENTITY.summaries().get(uid) or {}
            name = _clean_ai_name(row.get("display_name"))
            if name:
                return name
        if pid:
            detail = IDENTITY.detail(person_id=pid)
            best = ""
            best_ts = -1.0
            for row in detail.get("users") or []:
                for item in row.get("names") or []:
                    name = _clean_ai_name(item.get("name"))
                    if not name:
                        continue
                    ts = float(item.get("last_seen") or 0)
                    if name and (ts > best_ts or not best):
                        best, best_ts = name, ts
            if best:
                return best
    except Exception:
        return ""
    return ""

def ai_sender_name(
    group_id: str = "",
    speaker: str = "",
    person_id: str = "",
    user_id: str = "",
) -> str:
    """给大模型看的「语录人物」：优先人物档案群昵称，其次别名/OCR 昵称。"""
    candidates = []
    name = _identity_ai_name(person_id=person_id, user_id=user_id)
    if name:
        candidates.append(name)
    text = str(speaker or "").strip()
    if text:
        try:
            alias = IDENTITY.alias_lookup(text, str(group_id or "")) or {}
            alias_uid = str(alias.get("user_id") or "").strip()
            if alias_uid:
                candidates.append(_identity_ai_name(user_id=alias_uid))
        except Exception:
            pass
        candidates.append(_clean_speaker_name(text))
    for candidate in candidates:
        if candidate:
            return candidate
    return "群友"

def identity_avatar_index(state: dict) -> dict:
    """sha → {sha, hash, user_ids}，用于「以图找人」。"""
    index: dict = {}
    for user_id, user in (state.get("users") or {}).items():
        for avatar in user.get("avatars") or []:
            sha = avatar.get("sha")
            if not sha or avatar.get("default"):
                continue
            entry = index.setdefault(
                sha,
                {"sha": sha, "hash": avatar.get("hash") or "", "user_ids": []},
            )
            if user_id not in entry["user_ids"]:
                entry["user_ids"].append(user_id)
    return index

def identity_sync_settings_path() -> Path:
    return PLUGIN_DATA_DIR / IDENTITY_AUTO_SYNC_FILE

def _normalize_identity_sync_settings(data) -> dict:
    data = data if isinstance(data, dict) else {}
    try:
        interval = float(data.get("interval_hours") or IDENTITY_AUTO_SYNC_INTERVAL)
    except (TypeError, ValueError):
        interval = IDENTITY_AUTO_SYNC_INTERVAL
    interval = min(IDENTITY_AUTO_SYNC_MAX_HOURS, max(IDENTITY_AUTO_SYNC_MIN_HOURS, interval))
    timestamps = {}
    for key in ("last_sync_at", "updated_at"):
        try:
            timestamps[key] = float(data.get(key) or 0.0)
        except (TypeError, ValueError):
            timestamps[key] = 0.0
    result = data.get("last_result")
    return {
        "enabled": bool(data.get("enabled", True)),
        "interval_hours": round(interval, 2),
        "last_sync_at": timestamps["last_sync_at"],
        "last_result": result if isinstance(result, dict) else {},
        "updated_at": timestamps["updated_at"],
    }

def load_identity_sync_settings() -> dict:
    try:
        raw = quote_db.load_doc("sync", "settings")
    except Exception as exc:
        logger.warning(f"[quote] 读取自动身份同步设置失败：{exc}")
        raw = None
    return _normalize_identity_sync_settings(raw or {})


def save_identity_sync_settings(data) -> dict:
    settings = _normalize_identity_sync_settings(data)
    try:
        quote_db.save_doc("sync", "settings", settings)
    except Exception as exc:
        logger.warning(f"[quote] 保存自动身份同步设置失败：{exc}")
    return settings


class IdentityStore:
    """人物档案：QQ 号 → 昵称历史 / 头像历史；同一人的多个号可合并成一个 person。"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._state: dict | None = None
        self._avatar_cache: dict = {}

    # ---- 读写 ----
    def _new_state(self) -> dict:
        return {
            "version": IDENTITY_VERSION,
            "updated_at": 0.0,
            "users": {},
            "persons": {},
            "aliases": {},
            "blocked": {},
            "next_pid": 1,
        }

    def _next_pid_locked(self, state: dict, used: set) -> str:
        while True:
            number = int(state.get("next_pid") or 1)
            state["next_pid"] = number + 1
            pid = f"{IDENTITY_PID_PREFIX}{number:04d}"
            if pid not in used:
                used.add(pid)
                return pid

    def _find_person_locked(self, state: dict, ref: str):
        text = str(ref or "").strip()
        if not text:
            return None, ""
        persons = state.get("persons") or {}
        if text in persons:
            return persons[text], text
        for person_id, person in persons.items():
            if isinstance(person, dict) and str(person.get("pid") or "") == text:
                return person, person_id
        user = (state.get("users") or {}).get(text)
        if isinstance(user, dict):
            person_id = str(user.get("person_id") or "")
            if person_id in persons:
                return persons[person_id], person_id
        return None, ""

    def _load_locked(self) -> dict:
        if self._state is not None:
            return self._state
        state = self._new_state()
        try:
            raw = quote_db.load_identity_state()
        except Exception as exc:
            logger.warning(f"[quote] 读取人物档案失败，将重建：{exc}")
            raw = None
        if isinstance(raw, dict):
            if isinstance(raw.get("users"), dict):
                state["users"] = raw["users"]
            if isinstance(raw.get("persons"), dict):
                state["persons"] = raw["persons"]
            state["version"] = raw.get("version", IDENTITY_VERSION)
            state["updated_at"] = raw.get("updated_at", 0.0)
            if isinstance(raw.get("aliases"), dict):
                state["aliases"] = raw["aliases"]
            if isinstance(raw.get("blocked"), dict):
                state["blocked"] = raw["blocked"]
            try:
                state["next_pid"] = max(1, int(raw.get("next_pid") or 1))
            except (TypeError, ValueError):
                state["next_pid"] = 1
        pid_dirty = any(
            isinstance(person, dict) and not person.get("pid")
            for person in state["persons"].values()
        )
        now = time.time()
        for user_id, user in state["users"].items():
            if not isinstance(user, dict):
                continue
            user.setdefault("names", [])
            user.setdefault("avatars", [])
            user.setdefault("groups", {})
            user.setdefault("current_avatar", "")
            user.setdefault("avatar_checked_at", 0.0)
            user.setdefault("created_at", now)
            user.setdefault("last_seen", now)
            person_id = user.get("person_id") or f"p_{user_id}"
            user["person_id"] = person_id
            self._ensure_person(state, person_id, user_id, now)
        self._normalize_locked(state)
        self._state = state
        if pid_dirty:
            # 给旧档案补齐稳定 pid 后立刻落盘，避免 pid 在每次重启后变化。
            self._save_locked()
        return state

    def _normalize_locked(self, state: dict) -> None:
        """保证 users 与 persons 双向一致（合并/拆分/旧档案自动修复）。"""
        users = state.get("users") or {}
        persons = state.setdefault("persons", {})
        now = time.time()
        for user_id, user in users.items():
            if not isinstance(user, dict):
                continue
            pid = str(user.get("person_id") or f"p_{user_id}")
            user["person_id"] = pid
            person = persons.get(pid)
            if not isinstance(person, dict):
                persons[pid] = {
                    "person_id": pid,
                    "user_ids": [user_id],
                    "created_at": now,
                    "updated_at": now,
                }
            elif user_id not in (person.get("user_ids") or []):
                person.setdefault("user_ids", []).append(user_id)
        for pid, person in list(persons.items()):
            if not isinstance(person, dict):
                persons.pop(pid, None)
                continue
            members = [
                item
                for item in (person.get("user_ids") or [])
                if item in users and users[item].get("person_id") == pid
            ]
            if members:
                person["user_ids"] = members
            else:
                persons.pop(pid, None)
        used_pids = set()
        pending_persons = []
        for person in persons.values():
            if not isinstance(person, dict):
                continue
            current = str(person.get("pid") or "").strip()
            if current and current not in used_pids:
                person["pid"] = current
                used_pids.add(current)
            else:
                pending_persons.append(person)
        max_number = 0
        for current in used_pids:
            if current.startswith(IDENTITY_PID_PREFIX):
                tail = current[len(IDENTITY_PID_PREFIX):]
                if tail.isdigit():
                    max_number = max(max_number, int(tail))
        state["next_pid"] = max(int(state.get("next_pid") or 1), max_number + 1)
        for person in pending_persons:
            person["pid"] = self._next_pid_locked(state, used_pids)
        aliases = state.get("aliases")
        if not isinstance(aliases, dict):
            aliases = state["aliases"] = {}
        for key, entry in list(aliases.items()):
            if not isinstance(entry, dict):
                aliases.pop(key, None)
                continue
            uid = str(entry.get("user_id") or "").strip()
            if not uid or uid not in users:
                aliases.pop(key, None)
                continue
            entry["user_id"] = uid
            entry["name"] = str(entry.get("name") or key)[:64]
            entry.setdefault("source", IDENTITY_ALIAS_SOURCE)
            entry.setdefault("count", 1)
            entry.setdefault("created_at", now)
            entry.setdefault("last_seen", now)
            if "confirmed" not in entry:
                entry["confirmed"] = self._alias_confidence(
                    entry, users.get(uid) or {}
                )
        blocked = state.get("blocked")
        if not isinstance(blocked, dict):
            blocked = state["blocked"] = {}
        for key, entry in list(blocked.items()):
            if not isinstance(entry, dict):
                blocked.pop(key, None)
                continue
            entry["name"] = str(entry.get("name") or key)[:64]
            entry.setdefault("source", "title")
            entry.setdefault("count", 1)
            entry.setdefault("created_at", now)
            entry.setdefault("last_seen", now)

    def _save_locked(self) -> None:
        state = self._state
        if state is None:
            return
        self._normalize_locked(state)
        state["updated_at"] = time.time()
        try:
            quote_db.save_identity_state(state)
        except Exception as exc:
            logger.error(f"[quote] 写入人物档案数据库失败：{exc}")

    def _ensure_person(self, state: dict, person_id: str, user_id: str, now: float) -> dict:
        person = state["persons"].get(person_id)
        if not isinstance(person, dict):
            person = {
                "person_id": person_id,
                "user_ids": [],
                "created_at": now,
                "updated_at": now,
            }
            state["persons"][person_id] = person
            used = {
                str(item.get("pid") or "")
                for item in state["persons"].values()
                if isinstance(item, dict)
            }
            person["pid"] = self._next_pid_locked(state, used)
        person.setdefault("user_ids", [])
        if user_id not in person["user_ids"]:
            person["user_ids"].append(user_id)
            person["updated_at"] = now
        return person

    def _ensure_user(self, state: dict, user_id: str, now: float) -> dict:
        user = state["users"].get(user_id)
        if not isinstance(user, dict):
            user = {
                "user_id": user_id,
                "names": [],
                "avatars": [],
                "groups": {},
                "person_id": f"p_{user_id}",
                "current_avatar": "",
                "avatar_checked_at": 0.0,
                "created_at": now,
                "last_seen": now,
            }
            state["users"][user_id] = user
        else:
            user.setdefault("names", [])
            user.setdefault("avatars", [])
            user.setdefault("groups", {})
            user.setdefault("current_avatar", "")
            user.setdefault("avatar_checked_at", 0.0)
            user.setdefault("created_at", now)
            user.setdefault("last_seen", now)
            user["person_id"] = user.get("person_id") or f"p_{user_id}"
        self._ensure_person(state, user["person_id"], user_id, now)
        return user

    # ---- 记录 ----
    def touch(
        self, user_id: str, nickname: str = "", group_id: str = "", card: str = ""
    ) -> bool:
        """记录一次出现（昵称历史 / 群归属）。返回是否有变化。"""
        user_id = str(user_id or "").strip()
        if not user_id:
            return False
        now = time.time()
        changed = False
        with self._lock:
            state = self._load_locked()
            existed = user_id in state["users"]
            user = self._ensure_user(state, user_id, now)
            user["last_seen"] = now
            changed = not existed
            name_values = (
                nickname if isinstance(nickname, (list, tuple)) else [nickname]
            )
            card_value = str(card or "").strip()[:64]
            if card_value and card_value not in name_values:
                name_values = [card_value] + list(name_values)
            if self._touch_names(user, name_values, now, card_value):
                changed = True
            if self._touch_group(user, str(group_id or "").strip(), now):
                changed = True
            if changed:
                self._save_locked()
        return changed

    def touch_many(self, rows) -> int:
        """批量记录出现：rows = [(user_id, [names], group_id)]；返回新增用户数。"""
        now = time.time()
        added = 0
        with self._lock:
            state = self._load_locked()
            for row in rows or []:
                try:
                    user_id, name_values, group_id = row
                except (TypeError, ValueError):
                    continue
                user_id = str(user_id or "").strip()
                if not user_id:
                    continue
                if user_id not in state["users"]:
                    added += 1
                user = self._ensure_user(state, user_id, now)
                user["last_seen"] = now
                if not isinstance(name_values, (list, tuple)):
                    name_values = [name_values]
                card_value = ""
                if len(name_values) > 1:
                    card_value = str(name_values[0] or "").strip()[:64]
                self._touch_names(user, name_values, now, card_value)
                if group_id:
                    self._touch_group(user, str(group_id).strip(), now)
            self._save_locked()
        return added

    @staticmethod
    def _touch_names(user: dict, name_values, now: float, card_value: str = "") -> bool:
        """把若干昵称记入历史（去重、计数、按最近使用保留至多 N 个）。"""
        changed = False
        seen = set()
        card_value = str(card_value or "").strip()[:64]
        for value in name_values or []:
            nickname = str(value or "").strip()[:64]
            if not nickname or nickname in seen:
                continue
            seen.add(nickname)
            is_card = bool(card_value) and nickname == card_value
            names = user["names"]
            record = next(
                (item for item in names if item.get("name") == nickname), None
            )
            if record is None:
                names.append(
                    {
                        "name": nickname,
                        "count": 1,
                        "first_seen": now,
                        "last_seen": now,
                        "card": is_card,
                    }
                )
                names.sort(key=lambda item: item.get("last_seen") or 0)
                if len(names) > IDENTITY_NAME_KEEP:
                    del names[: -IDENTITY_NAME_KEEP]
                changed = True
            else:
                record["count"] = int(record.get("count") or 0) + 1
                record["last_seen"] = now
                if is_card and not record.get("card"):
                    record["card"] = True
                    changed = True
        return changed

    @staticmethod
    def _touch_group(user: dict, group_id: str, now: float) -> bool:
        if not group_id:
            return False
        groups = user["groups"]
        entry = groups.get(group_id)
        if entry is None:
            groups[group_id] = {"first_seen": now, "last_seen": now, "count": 1}
            return True
        entry["last_seen"] = now
        entry["count"] = int(entry.get("count") or 0) + 1
        return False

    def record_avatar(self, user_id: str, data: bytes) -> dict | None:
        """归一化后落盘，登记进该用户的头像历史；默认头像只更新检查时间。"""
        user_id = str(user_id or "").strip()
        if not user_id:
            return None
        normalized = normalize_avatar(data)
        if normalized is None:
            return None
        jpeg, digest, is_default = normalized
        now = time.time()
        if is_default:
            with self._lock:
                state = self._load_locked()
                user = self._ensure_user(state, user_id, now)
                user["avatar_checked_at"] = now
                self._save_locked()
            return None
        sha = hashlib.sha1(jpeg).hexdigest()[:16]
        target = identity_avatar_dir() / f"{sha}.jpg"
        try:
            identity_avatar_dir().mkdir(parents=True, exist_ok=True)
            if not target.is_file():
                tmp = target.with_suffix(".jpg.tmp")
                tmp.write_bytes(jpeg)
                os.replace(tmp, target)
        except Exception as exc:
            logger.error(f"[quote] 保存头像 {target} 失败：{exc}")
            return None
        digest = digest or dhash_hex(jpeg)
        entry = {"sha": sha, "hash": digest, "default": False, "new": False}
        with self._lock:
            state = self._load_locked()
            user = self._ensure_user(state, user_id, now)
            avatars = user["avatars"]
            record = next((item for item in avatars if item.get("sha") == sha), None)
            if record is None:
                avatars.append(
                    {
                        "sha": sha,
                        "hash": digest,
                        "default": False,
                        "first_seen": now,
                        "last_seen": now,
                    }
                )
                avatars.sort(key=lambda item: item.get("first_seen") or 0)
                if len(avatars) > IDENTITY_AVATAR_KEEP:
                    del avatars[: -IDENTITY_AVATAR_KEEP]
                entry["new"] = True
            else:
                record["hash"] = digest or record.get("hash") or ""
                record["last_seen"] = now
            user["current_avatar"] = sha
            user["avatar_checked_at"] = now
            user["last_seen"] = now
            self._save_locked()
        return entry

    def mark_avatar_checked(self, user_id: str) -> None:
        user_id = str(user_id or "").strip()
        if not user_id:
            return
        now = time.time()
        with self._lock:
            state = self._load_locked()
            user = self._ensure_user(state, user_id, now)
            user["avatar_checked_at"] = now
            self._save_locked()

    def needs_avatar(self, user_id: str, ttl: int = IDENTITY_AVATAR_TTL) -> bool:
        """没有头像或距上次检查超过 ttl 时才需要拉取。"""
        user_id = str(user_id or "").strip()
        if not user_id:
            return False
        with self._lock:
            user = (self._load_locked().get("users") or {}).get(user_id) or {}
            avatars = user.get("avatars") or []
            checked = float(user.get("avatar_checked_at") or 0)
        return not avatars or (time.time() - checked) > ttl

    def mark_avatar_stale(self, user_id: str) -> None:
        user_id = str(user_id or "").strip()
        if not user_id:
            return
        with self._lock:
            state = self._load_locked()
            user = state["users"].get(user_id)
            if isinstance(user, dict):
                user["avatar_checked_at"] = 0.0
                self._save_locked()

    # ---- 查询 ----
    def get_user(self, user_id: str) -> dict:
        user_id = str(user_id or "").strip()
        if not user_id:
            return {}
        with self._lock:
            user = (self._load_locked().get("users") or {}).get(user_id) or {}
            return json.loads(json.dumps(user))

    def _preferred_name_locked(
        self, state: dict, user_id: str, group_id: str = ""
    ) -> str:
        """当前最合适的称呼：已确认俗名（同群优先、最新优先）→ 群名片/QQ 昵称。"""
        uid = str(user_id or "").strip()
        if not uid:
            return ""
        gid = str(group_id or "").strip()
        best = None
        aliases = state.get("aliases") or {}
        for entry in aliases.values():
            if not isinstance(entry, dict):
                continue
            if str(entry.get("user_id") or "").strip() != uid:
                continue
            if not entry.get("confirmed", True):
                continue
            if str(entry.get("source") or "") not in ("learned", "manual", "merge"):
                continue
            name = str(entry.get("name") or "").strip()
            if not name:
                continue
            score = (
                0 if gid and str(entry.get("group_id") or "") == gid else 1,
                0 if str(entry.get("source") or "") == "learned" else 1,
                len(name),
                -float(entry.get("last_seen") or entry.get("created_at") or 0),
                name,
            )
            if best is None or score < best[0]:
                best = (score, name)
        if best:
            return best[1]
        user = (state.get("users") or {}).get(uid) or {}
        return identity_latest_name(user)

    def _display_name_locked(self, state: dict, user: dict) -> str:
        """对外的展示名：俗名优先。"""
        uid = str((user or {}).get("user_id") or "")
        return self._preferred_name_locked(state, uid)

    def preferred_name(
        self, user_id: str = "", person_id: str = "", group_id: str = ""
    ) -> str:
        """对外展示 / 归属使用的称呼：俗名优先，其次群名片或 QQ 当前昵称。"""
        uid = str(user_id or "").strip()
        if not uid and person_id:
            try:
                detail = self.detail(person_id=str(person_id))
            except Exception:
                detail = {}
            users = detail.get("users") or []
            uid = str((users[0] or {}).get("user_id") or "") if users else ""
        if not uid:
            return ""
        with self._lock:
            return self._preferred_name_locked(self._load_locked(), uid, group_id)

    def summaries(self) -> dict:
        """user_id → {person_id, pid, display_name, avatar_sha}，供语录列表补全。"""
        with self._lock:
            state = self._load_locked()
            users = state.get("users") or {}
            persons = state.get("persons") or {}
            rows = {}
            for user_id, user in users.items():
                person_id = str(user.get("person_id") or "")
                person = persons.get(person_id) or {}
                rows[user_id] = {
                    "person_id": person_id,
                    "pid": str(person.get("pid") or person_key(person_id)),
                    "display_name": self._preferred_name_locked(state, user_id),
                    "avatar_sha": user.get("current_avatar") or "",
                }
            return rows

    def overview(self) -> dict:
        with self._lock:
            state = self._load_locked()
            users = state.get("users") or {}
            avatars = sum(len(user.get("avatars") or []) for user in users.values())
            with_avatar = sum(1 for user in users.values() if user.get("current_avatar"))
            named = sum(1 for user in users.values() if user.get("names"))
            payload = {
                "version": state.get("version", IDENTITY_VERSION),
                "users": len(users),
                "persons": len(state.get("persons") or {}),
                "avatars": avatars,
                "with_avatar": with_avatar,
                "named": named,
                "threshold": IDENTITY_MATCH_THRESHOLD,
                "updated_at": state.get("updated_at") or 0.0,
            }
        return payload

    def list_people(self, keyword: str = "", group_id: str = "", page: int = 1, page_size: int = 48) -> dict:
        needle = str(keyword or "").strip().lower()
        gid = str(group_id or "").strip()
        with self._lock:
            state = self._load_locked()
            users = state.get("users") or {}
            persons = state.get("persons") or {}
            rows = []
            for person_id, person in persons.items():
                user_ids = [uid for uid in (person.get("user_ids") or []) if uid in users]
                if not user_ids:
                    continue
                if gid and not any(
                    gid in (users[uid].get("groups") or {}) for uid in user_ids
                ):
                    continue
                display = ""
                avatar_sha = ""
                last_seen = 0.0
                groups = set()
                names = []
                for uid in user_ids:
                    user = users[uid]
                    last_seen = max(last_seen, float(user.get("last_seen") or 0))
                    groups.update((user.get("groups") or {}).keys())
                    if not avatar_sha and user.get("current_avatar"):
                        avatar_sha = str(user["current_avatar"])
                    if not display:
                        display = identity_latest_name(user)
                    names.extend(user.get("names") or [])
                if needle:
                    haystack = (
                        [display, person_id]
                        + [str(uid) for uid in user_ids]
                        + [str(item.get("name") or "") for item in names]
                    )
                    if not any(needle in item.lower() for item in haystack):
                        continue
                rows.append(
                    {
                        "person_id": person_id,
                        "pid": str(person.get("pid") or person_key(person_id)),
                        "user_ids": user_ids,
                        "display_name": display or user_ids[0],
                        "avatar_sha": avatar_sha,
                        "groups": sorted(groups),
                        "last_seen": last_seen,
                        "is_merged": len(user_ids) > 1,
                    }
                )
            rows.sort(key=lambda row: -row["last_seen"])
            total = len(rows)
            try:
                page = max(1, int(page or 1))
                page_size = max(1, min(200, int(page_size or 48)))
            except (TypeError, ValueError):
                page, page_size = 1, 48
            pages = max(1, math.ceil(total / page_size)) if total else 1
            start = (page - 1) * page_size
            items = rows[start: start + page_size]
        return {
            "total": total,
            "page": page,
            "pages": pages,
            "page_size": page_size,
            "items": items,
        }

    def detail(self, user_id: str = "", person_id: str = "") -> dict:
        with self._lock:
            state = self._load_locked()
            users = state.get("users") or {}
            persons = state.get("persons") or {}
            uid = str(user_id or "").strip()
            pid = str(person_id or "").strip()
            if uid:
                user = users.get(uid)
                if not isinstance(user, dict):
                    raise KeyError(f"没有找到 QQ {uid} 的档案")
                pid = user.get("person_id") or ""
            if not pid:
                raise KeyError("缺少 user_id 或 person_id")
            person = persons.get(pid)
            if not isinstance(person, dict):
                found, key = self._find_person_locked(state, pid)
                if not isinstance(found, dict):
                    raise KeyError(f"没有找到人物 {pid}")
                person, pid = found, key
            rows = []
            for member_id in person.get("user_ids") or []:
                user = users.get(member_id)
                if not isinstance(user, dict):
                    continue
                rows.append(
                    {
                        "user_id": member_id,
                        "person_id": person.get("person_id") or pid,
                        "names": json.loads(json.dumps(user.get("names") or [])),
                        "avatars": json.loads(json.dumps(user.get("avatars") or [])),
                        "current_avatar": user.get("current_avatar") or "",
                        "groups": sorted((user.get("groups") or {}).keys()),
                        "last_seen": user.get("last_seen") or 0.0,
                        "created_at": user.get("created_at") or 0.0,
                    }
                )
            rows.sort(key=lambda row: -float(row.get("last_seen") or 0))
            first_uid = str(rows[0]["user_id"]) if rows else ""
            return {
                "display_name": (
                    self._preferred_name_locked(state, first_uid) if first_uid else ""
                ),
                "avatar_sha": (rows[0].get("current_avatar") or "") if rows else "",
                "person_id": pid,
                "pid": str(person.get("pid") or person_key(pid)),
                "user_ids": [row["user_id"] for row in rows],
                "is_merged": len(rows) > 1,
                "users": rows,
            }

    def match_hash(self, digest: str, threshold: int = IDENTITY_MATCH_THRESHOLD) -> list:
        try:
            limit = max(0, min(64, int(threshold)))
        except (TypeError, ValueError):
            limit = IDENTITY_MATCH_THRESHOLD
        with self._lock:
            state = self._load_locked()
            users = state.get("users") or {}
            results = []
            for sha, entry in identity_avatar_index(state).items():
                distance = hamming_distance(digest, entry.get("hash") or "")
                if distance > limit:
                    continue
                for uid in entry["user_ids"]:
                    user = users.get(uid) or {}
                    results.append(
                        {
                            "user_id": uid,
                            "person_id": user.get("person_id") or "",
                            "display_name": self._display_name_locked(state, user),
                            "sha": sha,
                            "distance": distance,
                        }
                    )
            results.sort(key=lambda row: (row["distance"], row["user_id"]))
        return results

    def match_exact(self, sha: str) -> list:
        sha = str(sha or "").strip().lower()
        if not sha:
            return []
        with self._lock:
            state = self._load_locked()
            users = state.get("users") or {}
            results = []
            for uid in identity_avatar_index(state).get(sha, {}).get("user_ids", []):
                user = users.get(uid) or {}
                results.append(
                    {
                        "user_id": uid,
                        "person_id": user.get("person_id") or "",
                        "display_name": self._display_name_locked(state, user),
                        "sha": sha,
                        "distance": 0,
                    }
                )
            return results

    @staticmethod
    def name_key(value: str) -> str:
        """昵称归一化：去空白、转小写，便于跨大小写/空格匹配。"""
        text = str(value or "").strip().lower()
        text = re.sub(r"\s+", "", text)
        return text[:64]

    def _match_names_locked(self, needle: str, group_id: str) -> list:
        """在已加载的档案里按昵称找候选（需持有 self._lock）。"""
        state = self._load_locked()
        users = state.get("users") or {}
        blocked_keys = set((state.get("blocked") or {}).keys())
        rows = []
        for uid, user in users.items():
            if group_id and group_id not in (user.get("groups") or {}):
                continue
            best = None
            for item in user.get("names") or []:
                name = str(item.get("name") or "").strip()
                key = self.name_key(name)
                if not key or key in blocked_keys:
                    continue
                score = 0.0
                if key == needle:
                    score = 1.0
                elif len(key) >= 2 and (key in needle or needle in key):
                    score = 0.8
                elif len(key) >= 3:
                    ratio = difflib.SequenceMatcher(None, key, needle).ratio()
                    if ratio >= 0.82:
                        score = round(ratio, 3)
                if not score:
                    continue
                if best is None or score > best[0]:
                    best = (score, name, float(item.get("last_seen") or 0))
            if best is None:
                continue
            rows.append(
                {
                    "user_id": uid,
                    "person_id": user.get("person_id") or "",
                    "display_name": self._display_name_locked(state, user),
                    "matched_name": best[1],
                    "matched_by": (
                        "exact"
                        if best[0] >= 0.999
                        else "contains"
                        if best[0] >= 0.8
                        else "fuzzy"
                    ),
                    "score": best[0],
                    "avatar_sha": user.get("current_avatar") or "",
                    "last_seen": float(user.get("last_seen") or 0),
                }
            )
        return rows

    def match_names(self, query: str, group_id: str = "", limit: int = 8) -> list:
        """把截图里的说话人昵称匹配到群成员档案（精确 > 包含 > 相似，本群优先）。"""
        needle = self.name_key(query)
        if not needle or self.is_blocked(query):
            return []
        try:
            wanted = max(1, min(32, int(limit or 8)))
        except (TypeError, ValueError):
            wanted = 8
        with self._lock:
            rows = self._match_names_locked(needle, group_id)
            if not rows and group_id:
                rows = self._match_names_locked(needle, "")
                for row in rows:
                    row["matched_by"] = "global"
                    row["score"] = round(float(row.get("score") or 0) * 0.92, 3)
        rows.sort(key=lambda row: (-row["score"], -row["last_seen"], row["user_id"]))
        return rows[:wanted]

    @staticmethod
    def name_distance(left: str, right: str) -> int:
        a, b = str(left or ""), str(right or "")
        if len(a) != len(b):
            return 10 ** 6
        return sum(1 for x, y in zip(a, b) if x != y)

    @classmethod
    def names_alike(cls, left: str, right: str) -> bool:
        """两个截图昵称是否像同一个人（长度相同且只差 1~2 个字，允许 OCR 误读）。"""
        na, nb = cls.name_key(left), cls.name_key(right)
        if not na or not nb:
            return False
        if na == nb:
            return True
        if len(na) != len(nb):
            return False
        distance = cls.name_distance(na, nb)
        allowed = 1 if len(na) <= 6 else 2
        return 1 <= distance <= allowed

    @classmethod
    def cluster_names(cls, records) -> list:
        """把同一人的昵称变体聚成簇；removable 是明显属于 OCR 噪声、可清理的条目。"""
        rows = []
        for record in records or []:
            if not isinstance(record, dict):
                continue
            name = str(record.get("name") or "").strip()
            if not name:
                continue
            rows.append(
                {
                    "name": name,
                    "count": int(record.get("count") or 0),
                    "first_seen": float(record.get("first_seen") or 0.0),
                }
            )
        rows.sort(key=lambda row: (-row["count"], row["first_seen"], -len(row["name"])))
        clusters: list = []
        for row in rows:
            placed = False
            for cluster in clusters:
                if any(cls.names_alike(row["name"], member["name"]) for member in cluster):
                    cluster.append(row)
                    placed = True
                    break
            if not placed:
                clusters.append([row])
        payload = []
        for cluster in clusters:
            cluster.sort(key=lambda row: (row["first_seen"] or 0.0, -row["count"]))
            keep = cluster[0]["name"]
            removable = [
                row["name"]
                for row in cluster[1:]
                if row["count"] <= 2 and row["name"] != keep
            ]
            payload.append(
                {
                    "names": [row["name"] for row in cluster],
                    "keep": keep,
                    "removable": removable,
                    "counts": [row["count"] for row in cluster],
                }
            )
        payload.sort(key=lambda item: (-len(item["names"]), item["names"][0]))
        return payload

    # ---- 别名表：截图昵称 → QQ 号（方案 A：昵称不会写进群名片历史） ----
    # ---- 别名可信度（V7：只保留人工/合并/字形高度相似的别名） ----
    @staticmethod
    def _alias_confidence(entry: dict, user: dict) -> bool:
        source = str(entry.get("source") or "").strip()
        if source in ("manual", "merge"):
            return True
        name = str(entry.get("name") or "").strip()
        names = [
            str(item.get("name") or "")
            for item in (user.get("names") or [])
            if isinstance(item, dict)
        ]
        if not name or not names:
            return False
        if name in names:
            return True
        best = max(difflib.SequenceMatcher(None, name, item).ratio() for item in names)
        return best >= IDENTITY_ALIAS_CONFIRM_RATIO

    # ---- 群头衔/等级屏蔽词（V7：这些文本不参与昵称匹配） ----
    def blocked_add_many(self, names, source: str = "title") -> int:
        cleaned: list = []
        for raw in names or []:
            text = str(raw or "").strip()[:64]
            key = self.name_key(text)
            if key and text and (key, text) not in cleaned:
                cleaned.append((key, text))
        if not cleaned:
            return 0
        now = time.time()
        added = 0
        with self._lock:
            state = self._load_locked()
            blocked = state.setdefault("blocked", {})
            for key, text in cleaned:
                entry = blocked.get(key)
                if isinstance(entry, dict):
                    entry["last_seen"] = now
                    continue
                blocked[key] = {
                    "name": text,
                    "source": source,
                    "count": 1,
                    "created_at": now,
                    "last_seen": now,
                }
                added += 1
            self._save_locked()
        return added

    def blocked_list(self) -> list:
        with self._lock:
            blocked = self._load_locked().get("blocked") or {}
            rows = [dict(entry) for entry in blocked.values() if isinstance(entry, dict)]
        rows.sort(key=lambda item: str(item.get("name") or ""))
        return rows

    def is_blocked(self, name) -> bool:
        key = self.name_key(name)
        if not key:
            return False
        with self._lock:
            blocked = self._load_locked().get("blocked") or {}
            return key in blocked

    def blocked_delete(self, name) -> bool:
        key = self.name_key(name)
        if not key:
            return False
        with self._lock:
            state = self._load_locked()
            if key not in (state.get("blocked") or {}):
                return False
            state["blocked"].pop(key, None)
            self._save_locked()
            return True

    # ---- 群头衔清理（V7：删除头衔别名、去重、弱化可疑形近） ----
    @staticmethod
    def _looks_like_title(name: str) -> bool:
        text = str(name or "").strip()
        if not text:
            return False
        if SUBJECT_TITLE_PREFIX_RE.match(text):
            return True
        if SUBJECT_ROLE_RE.match(text):
            return True
        if len(text) <= 8 and any(word in text for word in SUBJECT_ROLE_WORDS):
            return True
        return False

    def cleanup_titles(self, dry_run: bool = True) -> dict:
        delete: list = []
        redundant: list = []
        unconfirm: list = []
        titles: list = []
        with self._lock:
            state = self._load_locked()
            users = state.get("users") or {}
            aliases = state.get("aliases") or {}
            for key, entry in aliases.items():
                if not isinstance(entry, dict):
                    continue
                name = str(entry.get("name") or key).strip()
                uid = str(entry.get("user_id") or "").strip()
                if not name:
                    continue
                if self._looks_like_title(name) or self.is_blocked(name):
                    delete.append(name)
                    titles.append(name)
                    continue
                user = users.get(uid) or {}
                names = [
                    str(item.get("name") or "").strip()
                    for item in (user.get("names") or [])
                    if isinstance(item, dict)
                ]
                source = str(entry.get("source") or "").strip()
                if name in names:
                    if source in ("manual", "merge"):
                        continue
                    redundant.append(name)
                    continue
                best = max(
                    [difflib.SequenceMatcher(None, name, item).ratio() for item in names]
                    or [0.0]
                )
                if source == "migrated":
                    if best >= IDENTITY_ALIAS_CONFIRM_RATIO:
                        continue
                    if best < 0.6:
                        delete.append(name)
                    else:
                        unconfirm.append(name)
            plan = {
                "delete": sorted(set(delete)),
                "redundant": sorted(set(redundant) - set(delete)),
                "unconfirm": sorted(set(unconfirm) - set(delete)),
                "titles": sorted(set(titles)),
            }
            if not dry_run:
                applied = 0
                for name in plan["delete"] + plan["redundant"]:
                    key = self.name_key(name)
                    if key in aliases:
                        aliases.pop(key, None)
                        applied += 1
                for name in plan["unconfirm"]:
                    key = self.name_key(name)
                    entry = aliases.get(key)
                    if isinstance(entry, dict):
                        entry["confirmed"] = False
                        applied += 1
                self._save_locked()
                plan["applied"] = applied
        plan["counts"] = {
            "delete": len(plan["delete"]),
            "redundant": len(plan["redundant"]),
            "unconfirm": len(plan["unconfirm"]),
            "titles": len(plan["titles"]),
        }
        return plan

    def alias_add(self, name, user_id, group_id: str = "", source: str = IDENTITY_ALIAS_SOURCE) -> dict:
        key = self.name_key(name)
        uid = str(user_id or "").strip()
        if not key or not uid:
            return {}
        with self._lock:
            state = self._load_locked()
            if uid not in state["users"]:
                self._ensure_user(state, uid, time.time())
            entry = state["aliases"].get(key)
            if not isinstance(entry, dict):
                entry = {
                    "name": str(name or "").strip()[:64],
                    "user_id": uid,
                    "group_id": str(group_id or "").strip(),
                    "source": source or IDENTITY_ALIAS_SOURCE,
                    "count": 0,
                    "created_at": time.time(),
                }
                state["aliases"][key] = entry
            entry["user_id"] = uid
            entry["count"] = int(entry.get("count") or 0) + 1
            entry["last_seen"] = time.time()
            if group_id:
                entry["group_id"] = str(group_id).strip()
            if source:
                entry["source"] = source
            self._save_locked()
            return dict(entry)

    def alias_add_many(self, rows, source: str = IDENTITY_ALIAS_SOURCE) -> int:
        added = 0
        with self._lock:
            state = self._load_locked()
            for row in rows or []:
                try:
                    name, user_id = row[0], row[1]
                    group_id = row[2] if len(row) > 2 else ""
                except (TypeError, IndexError):
                    continue
                key = self.name_key(name)
                uid = str(user_id or "").strip()
                if not key or not uid:
                    continue
                if uid not in state["users"]:
                    self._ensure_user(state, uid, time.time())
                entry = state["aliases"].get(key)
                if not isinstance(entry, dict):
                    entry = {
                        "name": str(name or "").strip()[:64],
                        "user_id": uid,
                        "group_id": str(group_id or "").strip(),
                        "source": source,
                        "count": 0,
                        "created_at": time.time(),
                    }
                    state["aliases"][key] = entry
                entry["user_id"] = uid
                entry["count"] = int(entry.get("count") or 0) + 1
                entry["last_seen"] = time.time()
                if group_id:
                    entry["group_id"] = str(group_id).strip()
                added += 1
            if added:
                self._save_locked()
        return added

    def alias_lookup(self, name, group_id: str = "") -> dict:
        """按别名表把截图昵称换成 QQ 号：先精确，再形近（同一人的 OCR 变体）。"""
        needle = self.name_key(name)
        if not needle:
            return {}
        if self.is_blocked(name):
            return {}
        with self._lock:
            aliases = self._load_locked().get("aliases") or {}
            exact = aliases.get(needle)
            if isinstance(exact, dict) and exact.get("confirmed", True):
                return dict(exact)
            best = None
            gid = str(group_id or "").strip()
            for key, entry in aliases.items():
                if not isinstance(entry, dict):
                    continue
                if not entry.get("confirmed", True):
                    continue
                if not self.names_alike(name, entry.get("name") or key):
                    continue
                distance = self.name_distance(needle, key)
                score = (distance, 0 if gid and entry.get("group_id") == gid else 1)
                if best is None or score < best[0]:
                    best = (score, dict(entry))
            return best[1] if best else {}

    def aliases_for(self, user_id: str = "") -> list:
        uid = str(user_id or "").strip()
        with self._lock:
            aliases = self._load_locked().get("aliases") or {}
            rows = [
                dict(entry)
                for entry in aliases.values()
                if isinstance(entry, dict)
                and (not uid or str(entry.get("user_id") or "") == uid)
            ]
        rows.sort(
            key=lambda item: (-float(item.get("last_seen") or 0.0), str(item.get("name") or ""))
        )
        return rows

    def resolve_text_people(self, text: str, group_id: str = "", limit: int = 6) -> list:
        """从一句话里认出被点名的群友：先核对 QQ 号，再用该 QQ 的昵称 / 别名列表核对。"""
        raw = str(text or "")
        needle = raw.strip().lower()
        if not needle:
            return []
        gid = str(group_id or "").strip()
        with self._lock:
            state = self._load_locked()
            users = state.get("users") or {}
            aliases = state.get("aliases") or {}
            blocked = state.get("blocked") or {}
            picked: dict = {}

            def _touch(uid: str, matched: str, weight: float) -> None:
                uid = str(uid or "").strip()
                user = users.get(uid)
                if not user:
                    return
                person_id = str(user.get("person_id") or f"p_{uid}")
                score = weight
                if gid and gid in (user.get("groups") or {}):
                    score += 0.5
                row = picked.get(person_id)
                if row is None or score > row["_score"]:
                    picked[person_id] = {
                        "_score": score,
                        "user_id": uid,
                        "person_id": person_id,
                        "display_name": self._display_name_locked(state, user),
                        "matched_name": matched,
                    }

            for match in re.finditer(r"(?<!\d)(\d{5,12})(?!\d)", raw):
                _touch(match.group(1), match.group(1), 100.0)
            for uid, user in users.items():
                for item in user.get("names") or []:
                    if not isinstance(item, dict):
                        continue
                    name = str(item.get("name") or "").strip()
                    key = IdentityStore.name_key(name)
                    if key in blocked:
                        continue
                    if len(key) >= 2 and (key in needle or name.lower() in needle):
                        _touch(uid, name, 10.0 + len(key))
            for key, entry in aliases.items():
                if not isinstance(entry, dict):
                    continue
                if not entry.get("confirmed", True):
                    continue
                if key in blocked:
                    continue
                name = str(entry.get("name") or key).strip()
                name_key = IdentityStore.name_key(name)
                if len(name_key) >= 2 and (name_key in needle or name.lower() in needle):
                    _touch(entry.get("user_id") or "", name, 10.0 + len(name_key))
            rows = list(picked.values())
        rows.sort(key=lambda item: (-item["_score"], str(item.get("matched_name") or "")))
        for row in rows:
            row.pop("_score", None)
        return rows[: max(1, int(limit))]

    def alias_delete(self, name) -> bool:
        key = self.name_key(name)
        if not key:
            return False
        with self._lock:
            state = self._load_locked()
            if key not in state["aliases"]:
                return False
            state["aliases"].pop(key, None)
            self._save_locked()
            return True

    def drop_names(self, user_id: str, names) -> int:
        """从昵称历史里删除指定名字（清理 OCR 变体）。"""
        uid = str(user_id or "").strip()
        wanted = {self.name_key(item) for item in (names or []) if self.name_key(item)}
        if not uid or not wanted:
            return 0
        removed = 0
        with self._lock:
            state = self._load_locked()
            user = state["users"].get(uid)
            if not isinstance(user, dict):
                return 0
            kept = []
            for item in user.get("names") or []:
                if isinstance(item, dict) and self.name_key(item.get("name") or "") in wanted:
                    removed += 1
                    continue
                kept.append(item)
            if removed:
                user["names"] = kept
                self._save_locked()
        return removed

    def avatar_thumb_path(self, sha: str, side: int = IDENTITY_THUMB_SIDE):
        return PLUGIN_DATA_DIR / "avatars_thumb" / f"{sha}_{side}.jpg"

    def avatar_data_url(self, sha: str, side: int = IDENTITY_THUMB_SIDE) -> str:
        sha = str(sha or "").strip().lower()
        if not re.fullmatch(r"[0-9a-f]{16}", sha):
            return ""
        cache_key = f"{sha}:{side}"
        if cache_key in self._avatar_cache:
            return self._avatar_cache[cache_key]
        path = identity_avatar_dir() / f"{sha}.jpg"
        if not path.is_file():
            return ""
        thumb = self.avatar_thumb_path(sha, side) if (PILImage is not None and side) else None
        data = None
        if thumb is not None and thumb.is_file():
            try:
                data = thumb.read_bytes()
            except OSError:
                data = None
        if data is None:
            try:
                data = path.read_bytes()
            except OSError:
                return ""
            if PILImage is not None and side:
                try:
                    image = PILImage.open(io.BytesIO(data))
                    if image.mode not in ("RGB", "L"):
                        image = image.convert("RGB")
                    image.thumbnail((side, side))
                    buffer = io.BytesIO()
                    image.save(buffer, format="JPEG", quality=82)
                    data = buffer.getvalue()
                    if thumb is not None:
                        try:
                            thumb.parent.mkdir(parents=True, exist_ok=True)
                            thumb.write_bytes(data)
                        except OSError:
                            pass
                except Exception:
                    pass
        url = "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")
        if len(self._avatar_cache) > 400:
            self._avatar_cache.clear()
        self._avatar_cache[cache_key] = url
        return url

    # ---- 修改 ----
    def merge(self, user_ids) -> dict | None:
        tokens = [str(uid).strip() for uid in (user_ids or []) if str(uid).strip()]
        tokens = list(dict.fromkeys(tokens))
        now = time.time()
        with self._lock:
            state = self._load_locked()
            users = state["users"]
            expanded = []
            for token in tokens:
                if token in users:
                    expanded.append(token)
                    continue
                person, _ = self._find_person_locked(state, token)
                if isinstance(person, dict):
                    expanded.extend(person.get("user_ids") or [])
            ids = list(dict.fromkeys(uid for uid in expanded if uid in users))
            if len(ids) < 2:
                return None
            survivor_pid = ""
            best_size = -1
            for uid in ids:
                old_person = state["persons"].get(
                    str(users[uid].get("person_id") or "")
                )
                if not isinstance(old_person, dict):
                    continue
                current = str(old_person.get("pid") or "")
                size = len(old_person.get("user_ids") or [])
                if current and size > best_size:
                    survivor_pid, best_size = current, size
            pid = f"p_{min(ids)}"
            existing = state["persons"].get(pid)
            if isinstance(existing, dict):
                remaining = [
                    item for item in (existing.get("user_ids") or []) if item not in ids
                ]
                if remaining:
                    other_pid = f"p_{remaining[0]}"
                    if other_pid == pid or other_pid in state["persons"]:
                        other_pid = f"{pid}_r{int(now)}"
                    for member in remaining:
                        if isinstance(users.get(member), dict):
                            users[member]["person_id"] = other_pid
                    state["persons"][other_pid] = {
                        "person_id": other_pid,
                        "user_ids": remaining,
                        "created_at": existing.get("created_at", now),
                        "updated_at": now,
                    }
            person = {
                "person_id": pid,
                "pid": survivor_pid,
                "user_ids": [],
                "created_at": now,
                "updated_at": now,
            }
            for uid in ids:
                user = users[uid]
                old_pid = user.get("person_id")
                user["person_id"] = pid
                user["last_seen"] = max(float(user.get("last_seen") or 0), now)
                if old_pid and old_pid != pid:
                    old_person = state["persons"].get(old_pid)
                    if isinstance(old_person, dict):
                        old_person["user_ids"] = [
                            item
                            for item in (old_person.get("user_ids") or [])
                            if item not in ids
                        ]
                        if old_person["user_ids"]:
                            old_person["updated_at"] = now
                        else:
                            state["persons"].pop(old_pid, None)
                person["user_ids"].append(uid)
            state["persons"][pid] = person
            if not person.get("pid"):
                used = {
                    str(item.get("pid") or "")
                    for item in state["persons"].values()
                    if isinstance(item, dict)
                }
                person["pid"] = self._next_pid_locked(state, used)
            self._save_locked()
            return json.loads(json.dumps(state["persons"].get(pid) or person))

    def split_person(self, person_id: str) -> dict | None:
        pid = str(person_id or "").strip()
        now = time.time()
        with self._lock:
            state = self._load_locked()
            person = state["persons"].get(pid)
            if not isinstance(person, dict):
                return None
            moved = []
            for uid in list(person.get("user_ids") or []):
                user = state["users"].get(uid)
                if not isinstance(user, dict):
                    continue
                new_pid = f"p_{uid}"
                user["person_id"] = new_pid
                state["persons"][new_pid] = {
                    "person_id": new_pid,
                    "user_ids": [uid],
                    "created_at": now,
                    "updated_at": now,
                }
                moved.append(uid)
            state["persons"].pop(pid, None)
            self._save_locked()
            return {"person_id": pid, "user_ids": moved}

    def split_user(self, user_id: str) -> dict | None:
        uid = str(user_id or "").strip()
        now = time.time()
        with self._lock:
            state = self._load_locked()
            user = state["users"].get(uid)
            if not isinstance(user, dict):
                return None
            old_pid = user.get("person_id") or f"p_{uid}"
            person = state["persons"].get(old_pid)
            if not isinstance(person, dict):
                return None
            members = [item for item in (person.get("user_ids") or []) if item != uid]
            new_pid = f"p_{uid}"
            if not members:
                return {"person_id": old_pid, "user_ids": [uid]}
            if new_pid == old_pid:
                # 原 person_id 恰好与该 QQ 号同名，剩余成员改挂到另一个 person_id
                rest_pid = f"p_{members[0]}"
                if rest_pid == old_pid or rest_pid in state["persons"]:
                    rest_pid = f"{old_pid}_r{int(now)}"
                for member in members:
                    if isinstance(state["users"].get(member), dict):
                        state["users"][member]["person_id"] = rest_pid
                state["persons"][rest_pid] = {
                    "person_id": rest_pid,
                    "user_ids": members,
                    "created_at": now,
                    "updated_at": now,
                }
                state["persons"].pop(old_pid, None)
            else:
                person["user_ids"] = members
                person["updated_at"] = now
            user["person_id"] = new_pid
            state["persons"][new_pid] = {
                "person_id": new_pid,
                "user_ids": [uid],
                "created_at": now,
                "updated_at": now,
            }
            self._save_locked()
            return {"person_id": new_pid, "user_ids": [uid]}

    def reset(self) -> int:
        with self._lock:
            removed = len((self._state or {}).get("users") or {})
            self._state = self._new_state()
            self._avatar_cache.clear()
            self._save_locked()
        try:
            directory = identity_avatar_dir()
            if directory.is_dir():
                shutil.rmtree(directory, ignore_errors=True)
        except Exception as exc:
            logger.warning(f"[quote] 清理头像目录失败：{exc}")
        return removed

    def alias_candidates(self, group_id: str = "", status: str = "pending", limit: int = 200) -> list:
        """读取俗名候选（按群/状态过滤）。"""
        try:
            return quote_db.load_alias_candidates(group_id, status, limit)
        except Exception as exc:
            logger.warning(f"[quote] 读取俗名候选失败：{exc}")
            return []

    def alias_candidate_count(self, group_id: str = "", status: str = "pending") -> int:
        try:
            return quote_db.count_alias_candidates(group_id, status)
        except Exception:
            return 0

    def alias_candidate_add(
        self,
        alias,
        user_id,
        group_id: str = "",
        evidence: str = "",
        confidence: float = 0.5,
        evidence_user: str = "",
    ) -> int:
        """把一条「俗名 → QQ」写入待确认队列；已确认指向同一人则跳过。"""
        text = str(alias or "").strip().strip("“”\"' ")
        uid = str(user_id or "").strip()
        if not text or not uid:
            return 0
        key = self.name_key(text)
        if not key:
            return 0
        try:
            existing = self.alias_lookup(text, group_id) or {}
        except Exception:
            existing = {}
        if str(existing.get("user_id") or "") == uid:
            return 0
        with self._lock:
            state = self._load_locked()
            user = state["users"].get(uid)
            person_id = ""
            person = {}
            if isinstance(user, dict):
                person_id = str(user.get("person_id") or "")
                person = state["persons"].get(person_id) or {}
        display_name = ""
        if isinstance(person, dict):
            display_name = str(person.get("display_name") or "").strip()
        if not display_name:
            display_name = self._display_name_locked(state, user) if isinstance(user, dict) else ""
        try:
            return quote_db.add_alias_candidate(
                str(group_id or "").strip(),
                key,
                text,
                person_key(person_id) if person_id else "",
                uid,
                display_name,
                evidence,
                evidence_user,
                confidence,
            )
        except Exception as exc:
            logger.warning(f"[quote] 写入俗名候选失败：{exc}")
            return 0

    def alias_candidate_confirm(self, candidate_id) -> dict:
        """确认候选：写入别名表并强制标记 confirmed。"""
        try:
            row = quote_db.get_alias_candidate(candidate_id)
        except Exception as exc:
            logger.warning(f"[quote] 读取俗名候选失败：{exc}")
            return {}
        if not row or str(row.get("status")) != "pending":
            return {}
        uid = str(row.get("target_user_id") or "").strip()
        name = str(row.get("alias_name") or "").strip()
        gid = str(row.get("group_id") or "").strip()
        if not uid or not name:
            return {}
        entry = self.alias_add(name, uid, gid, source="learned")
        if not entry:
            return {}
        key = self.name_key(name)
        with self._lock:
            state = self._load_locked()
            current = state["aliases"].get(key)
            if isinstance(current, dict):
                current["confirmed"] = True
                current["source"] = "learned"
                self._save_locked()
                entry = dict(current)
        try:
            quote_db.set_alias_candidate_status(row.get("id"), "confirmed")
        except Exception:
            pass
        return entry

    def alias_candidate_reject(self, candidate_id) -> bool:
        try:
            row = quote_db.get_alias_candidate(candidate_id)
        except Exception:
            return False
        if not row or str(row.get("status")) != "pending":
            return False
        try:
            return bool(quote_db.set_alias_candidate_status(row.get("id"), "rejected"))
        except Exception:
            return False

def warm_avatar_thumbs_sync(limit: int = 120) -> dict:
    """把尚未生成的头像缩略图批量落到 avatars_thumb，避免打开弹层时现场缩放。"""
    if PILImage is None:
        return {"generated": 0, "remaining": 0}
    generated = 0
    directory = identity_avatar_dir()
    if not directory.is_dir():
        return {"generated": 0, "remaining": 0}
    files = sorted(directory.glob("*.jpg"))
    remaining = 0
    for path in files:
        sha = path.stem.lower()
        if not re.fullmatch(r"[0-9a-f]{16}", sha):
            continue
        if IDENTITY.avatar_thumb_path(sha).is_file():
            continue
        if generated >= limit:
            remaining += 1
            continue
        try:
            IDENTITY.avatar_data_url(sha)
            generated += 1
        except Exception:
            pass
    return {"generated": generated, "remaining": remaining}


IDENTITY = IdentityStore()

IDENTITY_AVATAR_TASKS: dict = {}
