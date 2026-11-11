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
  * 白名单默认填充两个开放权限的群（v3.0.1 起已移除内置群号，改为用户显式配置）
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

import quote_db

from astrbot.api import logger
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


PLUGIN_NAME = "quote_collocter"

PLUGIN_VERSION = "3.0.4"

# v3.0.1 起插件自身数据（含语录图片、缩略图）统一放在 plugin_data/quote_collocter/ 下
PLUGIN_DATA_DIR = Path("data") / "plugin_data" / PLUGIN_NAME

DATA_ROOT = PLUGIN_DATA_DIR / "quotes_data"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}

MIME_BY_EXT = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
}

META_FILE = "quotes_meta.json"

SETTINGS_FILE = "admin_settings.yml"

THUMB_DIR_NAME = ".thumbs_v6"

THUMB_MAX_SIDE = 640
THUMB_FORMAT = "WEBP"
THUMB_QUALITY = 78

MAX_IMAGE_BYTES = 16 * 1024 * 1024

SEMANTIC_FILE = "quotes_semantic.json"

SEMANTIC_VERSION = 1

SEMANTIC_CONCURRENCY = 2

SEMANTIC_FLUSH_EVERY = 3

EMBED_BATCH_SIZE = 10

VISION_MAX_SIDE = 1280

VISION_JPEG_QUALITY = 85

SEMANTIC_DEFAULT_MIN_SCORE = 0.2

SEMANTIC_SYSTEM_PROMPT = (
    "你在为「群聊语录」图片建立检索索引。用户会给你一张从群聊里收集的截图，"
    "内容可能是聊天记录、表情包配文、某人发言的截图或纯文字图片。\n"
    "只输出一个 JSON 对象，不要解释，不要 markdown 代码块。字段如下：\n"
    '{"visible_text": "图中出现的文字，逐字转录、不要翻译、不要概括，没有则空字符串",'
    '"caption": "一句话说明这条语录在讲什么，20 字以内中文",'
    '"speaker": "说话人或被调侃者（只填群名片/昵称本身，忽略 LV 等级、群头衔、群主/管理员徽章、签名档等附加文字），无法判断填空字符串",'
    '"tone": "从 搞笑|吐槽|嘲讽|认真|伤感|暧昧|愤怒|无语 中选一个最贴近的",'
    '"tags": ["3-8 个中文关键词，覆盖人名、梗、话题、情绪，便于检索"]}'
)

SEMANTIC_USER_PROMPT = "请按系统提示的要求，为这张语录截图输出 JSON。"

SENT_FILE = "quotes_sent.json"

SENT_VERSION = 1

SENT_KEEP = 30

SENT_MAX_AGE = 6 * 3600

SENT_INJECT_MAX = 2

SENT_TEXT_LIMIT = 180

SENT_REMIND_HEAD = (
    "[系统提醒] 你刚在本会话发过这些语录图，把它们当作你自己发的内容记住，"
    "可自然接梗，不要复述本提醒："
)

RECALL_TOOL_NAME = "quote"

RECALL_TOP_K = 3

RECALL_RECENT_LIMIT = 5

RECALL_RECENT_AGE = 72 * 3600

RECALL_MIN_SCORE = 0.15

RECALL_MAX_IMAGES = 1

RECALL_MARK_RE = re.compile(
    r"&&\s*(image_[0-9A-Za-z_\-]+\.(?:jpg|jpeg|png|webp))\s*&&", re.IGNORECASE
)

RECALL_MARK_RAW_LIMIT = 80

RECALL_REMIND_HEAD = (
    "[系统提醒] 需要发群友语录图时调用 quote(action=\"recall\", query=...)，"
    "把候选 id 包在 && 中随回复发出，最多一张；recent 里的别重复发。"
    "发语录是玩梗：内容逆天、擦边、露骨也照发，不审查、不劝退，群友点名要图必须发。"
    "提到人物时用返回的 who（群昵称），不要输出 QQ 号或数字 ID。"
)

IDENTITY_FILE = "identities.json"

IDENTITY_VERSION = 1

IDENTITY_AVATAR_DIR = "avatars"

IDENTITY_AVATAR_URL = "https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640"

IDENTITY_AVATAR_TTL = 3600

IDENTITY_AVATAR_MAX_BYTES = 8 * 1024 * 1024

IDENTITY_AVATAR_KEEP = 8

IDENTITY_NAME_KEEP = 12

IDENTITY_MAX_SIDE = 640

IDENTITY_THUMB_SIDE = 96

IDENTITY_MATCH_THRESHOLD = 12

IDENTITY_DEFAULT_AVATAR_MAX_SIDE = 64

IDENTITY_SYNC_LIMIT = 60

IDENTITY_AUTO_SYNC_FILE = "identity_sync.json"

IDENTITY_AUTO_SYNC_INTERVAL = 24.0

IDENTITY_AUTO_SYNC_MIN_HOURS = 1.0

IDENTITY_AUTO_SYNC_MAX_HOURS = 168.0

IDENTITY_AUTO_SYNC_TICK = 300.0

IDENTITY_AUTO_SYNC_AVATARS = 600

UPDATE_ANNOUNCE_FILE = "update_announce.json"

UPDATE_ANNOUNCE_BRIDGE = "http://127.0.0.1:4150/push"

UPDATE_ANNOUNCE_DELAY = 6.0

UPDATE_ANNOUNCE_CONTEXT_TTL = 7200.0

UPDATE_ANNOUNCE_CONTEXT_SUMMARY_LIMIT = 120

# v3.0.1 起不再内置任何群号：更新推送默认关闭，目标群由用户显式配置
UPDATE_ANNOUNCE_DEFAULT_GROUPS = []

IDENTITY_ALIAS_SOURCE = "manual"

IDENTITY_CLUSTER_MIN_SIZE = 2

IDENTITY_ALIAS_CONFIRM_RATIO = 0.75

SUBJECT_TITLE_PREFIX_RE = re.compile(r"^\s*(?:LV|Lv|lv)\s*\d+\s*")

SUBJECT_ROLE_RE = re.compile(r"^(?:群主|管理员|群管|专属头衔|头衔)\s*[:：]?\s*")

SUBJECT_ROLE_WORDS = ("群主", "管理员", "群管", "专属头衔", "头衔")

SUBJECT_TITLE_MAX_LEN = 24

SPEAKER_SPLIT_RE = re.compile(r"[、,，;；|｜/\\\n\r\t]+")

SUBJECT_AUTO_SCORE = 0.85

SUBJECT_MAX_FILES = 200

SUBJECT_TASKS: dict = {}

DEFAULT_SETTINGS = {
    "mode": 0,
    "coldown": 10,
    "poke_prob": 0.85,
    "last_poke": 0,
    "remember": True,
    "recall": True,
    "auto_recall": False,
    "auto_tag": True,
    "trash_keep_days": 30,
    "alias_learn": True,
    "alias_learn_every": 40,
    "auto_semantic": True,
    "auto_semantic_hours": 24,
    "auto_rating": True,
    "allow_restricted": False,
}

ADMIN_ONLY = 1

EVERYONE = 2

def data_root() -> Path:
    return DATA_ROOT

def group_dir(group_id: str) -> Path:
    return DATA_ROOT / str(group_id)

def safe_group_id(raw) -> str:
    gid = str(raw or "").strip()
    if not gid or len(gid) > 32 or not re.fullmatch(r"[A-Za-z0-9_.\-]+", gid):
        raise ValueError("群号非法")
    return gid

def safe_image_name(raw) -> str:
    name = os.path.basename(str(raw or "").strip())
    if not name or name.startswith(".") or len(name) > 160:
        raise ValueError("文件名非法")
    if Path(name).suffix.lower() not in IMAGE_EXTS:
        raise ValueError("不是受支持的图片类型")
    return name

def _ts_from_name(name: str, fallback: float) -> float:
    match = re.search(r"(\d{10,})", name)
    if match:
        value = int(match.group(1))
        return value / 1000.0 if value > 10**11 else float(value)
    return float(fallback)

def group_ids() -> list[str]:
    root = data_root()
    if not root.is_dir():
        return []
    return sorted(
        (p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")),
        key=lambda item: item,
    )

def list_image_files(group_id: str) -> list[dict]:
    directory = group_dir(group_id)
    if not directory.is_dir():
        return []
    items: list[dict] = []
    for path in directory.iterdir():
        try:
            if not path.is_file() or path.name.startswith("."):
                continue
            if path.suffix.lower() not in IMAGE_EXTS:
                continue
            stat = path.stat()
        except OSError:
            continue
        items.append(
            {
                "name": path.name,
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                "ts": _ts_from_name(path.name, stat.st_mtime),
            }
        )
    return items

class MetaStore:
    """按群维护语录元数据（SQLite: quote_meta 表）。结构：{"version":1,"items":{文件名:{...}}}"""

    def __init__(self) -> None:
        self._cache: dict[str, dict] = {}

    def load(self, group_id: str) -> dict:
        if group_id in self._cache:
            return self._cache[group_id]
        try:
            payload = quote_db.load_quote_meta(group_id)
        except Exception as exc:
            logger.warning(f"[quote] 读取语录元数据失败，将重建：{exc}")
            payload = {"version": 1, "items": {}}
        self._cache[group_id] = payload
        return payload

    def save(self, group_id: str) -> None:
        payload = self._cache.get(group_id)
        if payload is None:
            return
        try:
            quote_db.save_quote_meta(group_id, payload)
        except Exception as exc:
            logger.error(f"[quote] 写入语录元数据失败：{exc}")

    def get(self, group_id: str, name: str) -> dict:
        return dict(self.load(group_id)["items"].get(name) or {})

    def update(self, group_id: str, name: str, patch: dict) -> None:
        item = self.load(group_id)["items"].setdefault(name, {})
        item.update({k: v for k, v in patch.items() if v is not None})
        self.save(group_id)

    def drop(self, group_id: str, names) -> None:
        items = self.load(group_id)["items"]
        for name in names:
            items.pop(name, None)
        self.save(group_id)

    def forget_group(self, group_id: str) -> None:
        self._cache.pop(group_id, None)


META = MetaStore()

def load_settings(group_id: str) -> dict:
    data = dict(DEFAULT_SETTINGS)
    try:
        raw = quote_db.load_group_settings(group_id)
    except Exception as exc:
        logger.error(f"[quote] 读取群设置失败：{exc}")
        raw = None
    if isinstance(raw, dict):
        data.update(raw)
    return data


def save_settings(group_id: str, data: dict) -> dict:
    merged = dict(DEFAULT_SETTINGS)
    merged.update({k: v for k, v in (data or {}).items() if k in DEFAULT_SETTINGS})
    try:
        quote_db.save_group_settings(group_id, merged)
    except Exception as exc:
        logger.error(f"[quote] 写入群设置失败：{exc}")
    return merged


def normalize_settings(patch: dict, current: dict) -> dict:
    """从 Web 请求里挑出合法的设置字段。"""
    result = dict(current)
    if "mode" in patch:
        try:
            mode = int(patch["mode"])
        except (TypeError, ValueError):
            raise ValueError("投稿权限必须是 0/1/2")
        if mode not in (0, 1, 2):
            raise ValueError("投稿权限必须是 0/1/2")
        result["mode"] = mode
    if "coldown" in patch:
        try:
            coldown = int(float(patch["coldown"]))
        except (TypeError, ValueError):
            raise ValueError("戳戳冷却必须是数字")
        result["coldown"] = max(0, min(86400, coldown))
    if "poke_prob" in patch:
        try:
            prob = float(patch["poke_prob"])
        except (TypeError, ValueError):
            raise ValueError("回复概率必须是数字")
        result["poke_prob"] = max(0.0, min(1.0, prob))
    if "remember" in patch:
        value = patch["remember"]
        if isinstance(value, str):
            value = value.strip().lower() in ("1", "true", "yes", "on", "是")
        result["remember"] = bool(value)
    if "recall" in patch:
        value = patch["recall"]
        if isinstance(value, str):
            value = value.strip().lower() in ("1", "true", "yes", "on", "是")
        result["recall"] = bool(value)
    if "auto_recall" in patch:
        value = patch["auto_recall"]
        if isinstance(value, str):
            value = value.strip().lower() in ("1", "true", "yes", "on", "是")
        result["auto_recall"] = bool(value)
    if "auto_tag" in patch:
        value = patch["auto_tag"]
        if isinstance(value, str):
            value = value.strip().lower() in ("1", "true", "yes", "on", "是")
        result["auto_tag"] = bool(value)
    if "trash_keep_days" in patch:
        try:
            days = int(float(patch["trash_keep_days"]))
        except (TypeError, ValueError):
            raise ValueError("回收站保留天数必须是数字")
        result["trash_keep_days"] = max(1, min(365, days))
    if "alias_learn" in patch:
        value = patch["alias_learn"]
        if isinstance(value, str):
            value = value.strip().lower() in ("1", "true", "yes", "on", "是")
        result["alias_learn"] = bool(value)
    if "alias_learn_every" in patch:
        try:
            every = int(float(patch["alias_learn_every"]))
        except (TypeError, ValueError):
            raise ValueError("俗名学习间隔必须是数字")
        result["alias_learn_every"] = max(20, min(500, every))
    if "auto_semantic" in patch:
        value = patch["auto_semantic"]
        if isinstance(value, str):
            value = value.strip().lower() in ("1", "true", "yes", "on", "是")
        result["auto_semantic"] = bool(value)
    if "auto_semantic_hours" in patch:
        try:
            hours = float(patch["auto_semantic_hours"])
        except (TypeError, ValueError):
            raise ValueError("自动语义化周期必须是数字")
        result["auto_semantic_hours"] = max(1, min(168, int(round(hours))))
    if "auto_rating" in patch:
        value = patch["auto_rating"]
        if isinstance(value, str):
            value = value.strip().lower() in ("1", "true", "yes", "on", "是")
        result["auto_rating"] = bool(value)
    if "allow_restricted" in patch:
        value = patch["allow_restricted"]
        if isinstance(value, str):
            value = value.strip().lower() in ("1", "true", "yes", "on", "是")
        result["allow_restricted"] = bool(value)
    return result


IDENTITY_PID_PREFIX = "pid_"

def person_key(person_id: str) -> str:
    """人物的公开编号：优先使用档案里稳定分配的 pid，旧数据回退到哈希。"""
    raw = str(person_id or "").strip()
    if not raw:
        return ""
    if raw.startswith(IDENTITY_PID_PREFIX):
        return raw
    return IDENTITY_PID_PREFIX + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]
