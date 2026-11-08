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
import copy
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
from quote_identity import IDENTITY, IdentityStore, _clean_ai_name, _clean_speaker_name
from quote_core import META, group_dir, safe_image_name
from quote_semantic import SEMANTIC, _cosine


def _tool_json(payload: dict) -> str:
    try:
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        return json.dumps({"ok": False, "reason": "序列化检索结果失败"})

def _restricted_allowed(group_id: str) -> bool:
    """本群是否允许限制级语录进入 AI 召回（默认不允许）。"""
    try:
        return bool(load_settings(group_id).get("allow_restricted", False))
    except Exception:
        return False


def recall_candidates_sync(
    group_id: str,
    query_vector: list,
    *,
    top_k: int = RECALL_TOP_K,
    min_score: float = RECALL_MIN_SCORE,
) -> list:
    """同步扫描某群语义索引，返回按余弦相似度降序的候选列表。"""
    gid = str(group_id or "")
    if not gid or not query_vector:
        return []
    directory = group_dir(gid)
    items = SEMANTIC.items(gid)
    if not items:
        return []
    scored = []
    summaries: dict = {}
    alias_map: dict = {}
    meta_items: dict = {}
    try:
        summaries = IDENTITY.summaries()
        for row in IDENTITY.aliases_for():
            key = IdentityStore.name_key(row.get("name") or "")
            if key:
                alias_map.setdefault(key, row)
    except Exception:
        summaries, alias_map = {}, {}
    try:
        meta_items = META.load(gid)["items"]
    except Exception:
        meta_items = {}

    allow_restricted = _restricted_allowed(gid)

    def _who_for(entry: dict, fallback_uid: str = ""):
        uid = str(entry.get("user_id") or fallback_uid or "")
        owner = uid
        name = ""
        if uid:
            name = _clean_ai_name((summaries.get(uid) or {}).get("display_name"))
        speaker = str(entry.get("speaker") or "").strip()
        if not name and speaker:
            hit = alias_map.get(IdentityStore.name_key(speaker)) or {}
            alias_uid = str(hit.get("user_id") or "")
            if alias_uid:
                owner = alias_uid
                name = _clean_ai_name(
                    (summaries.get(alias_uid) or {}).get("display_name")
                )
        pid = str((summaries.get(owner) or {}).get("pid") or "") or (
            person_key((summaries.get(owner) or {}).get("person_id")) if owner else ""
        )
        return name or _clean_speaker_name(speaker) or "群友", pid

    for raw_name, entry in items.items():
        if not isinstance(entry, dict) or str(entry.get("status") or "") != "done":
            continue
        vector = entry.get("vector") or []
        if not vector:
            continue
        try:
            name = safe_image_name(str(raw_name))
        except ValueError:
            continue
        if name != str(raw_name) or not (directory / name).is_file():
            continue
        if not allow_restricted and (meta_items.get(name) or {}).get("restricted"):
            continue
        try:
            score = _cosine(query_vector, vector)
        except Exception:
            continue
        if score < min_score:
            continue
        speaker = str(entry.get("speaker") or "").strip()
        subject_uid = ""
        try:
            subject_uid = str((meta_items.get(name) or {}).get("subject_user_id") or "")
        except Exception:
            subject_uid = ""
        who, pid = _who_for(entry, subject_uid)
        scored.append(
            {
                "id": name,
                "score": round(score, 4),
                "who": who,
                "pid": pid,
                "caption": str(entry.get("caption") or "")[:160],
                "tags": [str(tag) for tag in (entry.get("tags") or [])][:5],
                "tone": str(entry.get("tone") or ""),
                "speaker": _clean_speaker_name(speaker),
                "visible_text": str(entry.get("visible_text") or "")[:160],
            }
        )
    scored.sort(key=lambda item: -item["score"])
    return scored[: max(1, int(top_k))]

def recall_person_quotes_sync(
    group_id: str, user_ids, *, limit: int = RECALL_TOP_K
) -> list:
    """按已确认的人物归属直接列出某人的语录（不依赖语义相似度）。"""
    gid = str(group_id or "")
    wanted = {str(uid) for uid in (user_ids or []) if str(uid)}
    if not gid or not wanted:
        return []
    directory = group_dir(gid)
    try:
        meta_items = META.load(gid)["items"]
    except Exception:
        meta_items = {}
    items = SEMANTIC.items(gid)
    summaries: dict = {}
    try:
        summaries = IDENTITY.summaries()
    except Exception:
        summaries = {}
    allow_restricted = _restricted_allowed(gid)
    rows = []
    for raw_name, info in (meta_items or {}).items():
        if not isinstance(info, dict):
            continue
        uid = str(info.get("subject_user_id") or "").strip()
        if uid not in wanted:
            continue
        try:
            name = safe_image_name(str(raw_name))
        except ValueError:
            continue
        if name != str(raw_name):
            continue
        if not (directory / name).is_file():
            continue
        if not allow_restricted and (meta_items.get(name) or {}).get("restricted"):
            continue
        entry = (items or {}).get(name) or {}
        if not isinstance(entry, dict):
            entry = {}
        speaker = str(entry.get("speaker") or "").strip()
        who = _clean_ai_name((summaries.get(uid) or {}).get("display_name"))
        if not who:
            who = _clean_speaker_name(speaker) or "群友"
        pid = str((summaries.get(uid) or {}).get("pid") or "") or person_key(
            (summaries.get(uid) or {}).get("person_id")
        )
        rows.append(
            {
                "id": name,
                "score": 1.0,
                "via": "person",
                "user_id": uid,
                "who": who,
                "pid": pid,
                "caption": str(entry.get("caption") or "")[:160],
                "tags": [str(tag) for tag in (entry.get("tags") or [])][:5],
                "tone": str(entry.get("tone") or ""),
                "speaker": _clean_speaker_name(speaker),
                "visible_text": str(entry.get("visible_text") or "")[:160],
            }
        )
    rows.sort(
        key=lambda item: -float((meta_items.get(item["id"]) or {}).get("ts") or 0.0)
    )
    return rows[: max(1, int(limit))]

def _resolve_recall_name(raw: str, allowed, group_id: str) -> str:
    """把标记里的图片名规范成可发送的语录文件名。

    优先接受本轮工具返回过的候选；也接受本群目录里真实存在的图片，
    这样模型直接引用上下文里发送记忆的旧语录 id 时不会被误判为无效标记。
    """
    name = str(raw or "").strip()
    if not name:
        return ""
    try:
        safe = safe_image_name(name)
    except ValueError:
        return ""
    if safe != name:
        return ""
    try:
        if not (group_dir(group_id) / safe).is_file():
            return ""
    except Exception:
        return ""
    if allowed and safe not in allowed:
        logger.debug(f"[quote] 语录标记不在本轮候选，按本群图片发送：{safe}")
    return safe

def slim_candidate(row: dict) -> dict:
    """把召回候选压成给模型看的最小字段集（去掉长文本、pid、语气与相似度分）。"""
    out: dict = {
        "id": str(row.get("id") or ""),
        "who": str(row.get("who") or "群友")[:16],
        "caption": str(row.get("caption") or "")[:60],
    }
    tags = [str(tag)[:8] for tag in (row.get("tags") or [])][:2]
    if tags:
        out["tags"] = tags
    if str(row.get("via") or "") == "person":
        out["via"] = "person"
    sent = str(row.get("sent_ago") or "")
    if sent:
        out["sent_ago"] = sent
    return out


def ago_text(seconds: float) -> str:
    """把秒数转成「刚刚 / N 分钟前 / N 小时前 / N 天前」。"""
    sec = max(0.0, float(seconds or 0))
    if sec < 60:
        return "刚刚"
    if sec < 3600:
        return f"{int(sec // 60)} 分钟前"
    if sec < 86400:
        return f"{int(sec // 3600)} 小时前"
    return f"{int(sec // 86400)} 天前"

# ---------------------------------------------------------------- #
# AI 召回缓存（v2.12.3）：同群同关键词 5 分钟内复用检索结果
# ---------------------------------------------------------------- #
_RECALL_CACHE: dict = {}
_RECALL_CACHE_LOCK = threading.Lock()
RECALL_CACHE_TTL = 300.0
RECALL_CACHE_MAX = 64


def recall_cache_key(group_id: str, keyword: str) -> str:
    text = re.sub(r"\s+", "", str(keyword or "")).lower()
    return f"{group_id}:{text}"


def recall_cache_get(group_id: str, keyword: str):
    key = recall_cache_key(group_id, keyword)
    now = time.time()
    with _RECALL_CACHE_LOCK:
        row = _RECALL_CACHE.get(key)
        if not row:
            return None
        ts, payload = row
        if now - ts > RECALL_CACHE_TTL:
            _RECALL_CACHE.pop(key, None)
            return None
        return copy.deepcopy(payload)


def recall_cache_put(
    group_id: str, keyword: str, candidates: list, person_candidates: list = None
) -> None:
    key = recall_cache_key(group_id, keyword)
    payload = {
        "candidates": list(candidates or []),
        "person": list(person_candidates or []),
    }
    with _RECALL_CACHE_LOCK:
        if len(_RECALL_CACHE) >= RECALL_CACHE_MAX:
            oldest = min(_RECALL_CACHE.items(), key=lambda item: item[1][0])[0]
            _RECALL_CACHE.pop(oldest, None)
        _RECALL_CACHE[key] = (time.time(), copy.deepcopy(payload))
