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
from quote_core import META, SENT_INJECT_MAX, SENT_KEEP, SENT_MAX_AGE, SENT_REMIND_HEAD, SENT_TEXT_LIMIT, SENT_VERSION, load_settings
from quote_semantic import SEMANTIC
from quote_identity import _clean_ai_name, ai_sender_name


class SentMemory:
    """按会话（umo）记录刚发出的语录。

    结构：{"version":1,"sessions":{"<umo>":[{key,ts,group_id,name,caption,tone,tags,text,sender,remembered}]}}
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.RLock()
        self._data: dict = {"version": SENT_VERSION, "sessions": {}}
        self._loaded = False

    def _ensure(self) -> dict:
        if self._loaded:
            return self._data
        self._loaded = True
        try:
            raw = quote_db.load_sent()
        except Exception as exc:
            logger.warning(f"[quote] 读取发送记忆失败，将重建：{exc}")
            raw = None
        if isinstance(raw, dict) and isinstance(raw.get("sessions"), dict):
            self._data = {
                "version": raw.get("version", SENT_VERSION),
                "sessions": raw["sessions"],
            }
        return self._data

    def save(self) -> None:
        with self._lock:
            payload = self._ensure()
            try:
                quote_db.save_sent(payload)
            except Exception as exc:
                logger.error(f"[quote] 写入发送记忆失败：{exc}")

    def _session(self, unmo: str, create: bool = False) -> list:
        sessions = self._ensure()["sessions"]
        items = sessions.get(unmo)
        if items is None:
            if not create:
                return []
            items = []
            sessions[unmo] = items
        return items

    def append(self, unmo: str, entry: dict) -> dict:
        if not unmo:
            return {}
        with self._lock:
            items = self._session(unmo, create=True)
            record = dict(entry)
            record.setdefault("ts", time.time())
            record["key"] = f"{float(record['ts']):.3f}:{record.get('name', '')}"
            record["remembered"] = False
            items.append(record)
            del items[: max(0, len(items) - SENT_KEEP)]
            self.save()
        return record

    def pending(self, unmo: str) -> list[dict]:
        now = time.time()
        with self._lock:
            items = list(self._session(unmo))
        return [
            item
            for item in items
            if not item.get("remembered")
            and now - float(item.get("ts") or 0) <= SENT_MAX_AGE
        ]

    def mark_remembered(self, unmo: str, keys) -> None:
        target = {k for k in keys if k}
        if not target:
            return
        with self._lock:
            changed = False
            for item in self._session(unmo):
                if item.get("key") in target and not item.get("remembered"):
                    item["remembered"] = True
                    changed = True
            if changed:
                self.save()

    def counts(self, group_id: str = "") -> dict:
        now = time.time()
        with self._lock:
            sessions = self._ensure()["sessions"]
            snapshot = {k: list(v) for k, v in sessions.items()}
        total = 0
        pending = 0
        sessions_seen = 0
        for items in snapshot.values():
            hit = False
            for item in items:
                if group_id and str(item.get("group_id") or "") != str(group_id):
                    continue
                if now - float(item.get("ts") or 0) > SENT_MAX_AGE:
                    continue
                hit = True
                total += 1
                if not item.get("remembered"):
                    pending += 1
            if hit:
                sessions_seen += 1
        return {"total": total, "pending": pending, "sessions": sessions_seen}

    def recent(self, group_ids, limit: int = 8, max_age: float = 0.0) -> list[dict]:
        """按群取最近发过的语录（同名去重，按时间倒序）。"""
        wanted = {str(gid) for gid in (group_ids or []) if str(gid)}
        now = time.time()
        age = float(max_age or 0)
        with self._lock:
            sessions = self._ensure()["sessions"]
            snapshot = [item for items in sessions.values() for item in items]
        best: dict = {}
        for item in snapshot:
            if wanted and str(item.get("group_id") or "") not in wanted:
                continue
            ts = float(item.get("ts") or 0)
            if age and now - ts > age:
                continue
            name = str(item.get("name") or "")
            if not name:
                continue
            if name not in best or ts > float(best[name].get("ts") or 0):
                best[name] = item
        rows = sorted(best.values(), key=lambda item: -float(item.get("ts") or 0))
        return [dict(item) for item in rows[: max(1, int(limit))]]

    def clear(self, group_id: str = "") -> int:
        with self._lock:
            sessions = self._ensure()["sessions"]
            removed = 0
            if not group_id:
                for items in sessions.values():
                    removed += len(items)
                sessions.clear()
            else:
                for unmo in list(sessions.keys()):
                    kept = [
                        i
                        for i in sessions[unmo]
                        if str(i.get("group_id") or "") != str(group_id)
                    ]
                    removed += len(sessions[unmo]) - len(kept)
                    if kept:
                        sessions[unmo] = kept
                    else:
                        sessions.pop(unmo, None)
            if removed:
                self.save()
        return removed

SENT = SentMemory(PLUGIN_DATA_DIR / SENT_FILE)

def sent_entry_line(entry: dict, index: int) -> str:
    who = _clean_ai_name(entry.get("who")) or "群友"
    try:
        import time as _time

        ts = float(entry.get("ts") or 0)
        if ts:
            from quote_recall import ago_text

            ago = "｜" + ago_text(max(0.0, _time.time() - ts))
        else:
            ago = ""
    except Exception:
        ago = ""
    return f"{index}. {str(entry.get('name') or '语录')}｜{who[:16]}{ago}"

def sent_memory_block(entries: list) -> str:
    lines = [SENT_REMIND_HEAD]
    for index, entry in enumerate(entries, start=1):
        lines.append(sent_entry_line(entry, index))
    lines.append("（这些图是你刚在群里发的，可自然接梗，别复述本提醒。）")
    return "\n".join(lines)

async def inject_sent_memory(req, unmo: str, remember: bool = True) -> int:
    """把尚未注入过的「已发送语录」写进本次 LLM 请求，返回注入条数。"""
    if not remember or req is None or not unmo:
        return 0
    items = await asyncio.to_thread(SENT.pending, unmo)
    if not items:
        return 0
    chosen = items[-SENT_INJECT_MAX:]
    try:
        req.extra_user_content_parts.append(TextPart(text=sent_memory_block(chosen)))
    except Exception as exc:
        logger.debug(f"[quote] 注入发送记忆失败：{exc}")
        return 0
    await asyncio.to_thread(SENT.mark_remembered, unmo, [i.get("key") for i in chosen])
    return len(chosen)

def remember_sent_quote(event, group_id: str, name: str) -> dict:
    """记录一条「刚发出」的语录（带语义描述，若已建索引）。"""
    if not name:
        return {}
    gid = str(group_id or "")
    try:
        settings = load_settings(gid)
        if not settings.get("remember", True):
            return {}
    except Exception:
        pass
    entry: dict = {"ts": time.time(), "group_id": gid, "name": str(name)}
    try:
        meta = META.get(gid, name)
        entry["sender"] = meta.get("nickname") or ""
    except Exception:
        pass
    try:
        sem = SEMANTIC.get(gid, name)
        if isinstance(sem, dict) and sem:
            entry["caption"] = sem.get("caption") or ""
            entry["tone"] = sem.get("tone") or ""
            entry["tags"] = sem.get("tags") or []
            entry["text"] = sem.get("visible_text") or ""
            entry["who"] = ai_sender_name(
                gid,
                speaker=str(sem.get("speaker") or ""),
                person_id=str(sem.get("person_id") or ""),
                user_id=str(sem.get("user_id") or ""),
            )
        else:
            entry["who"] = ai_sender_name(gid, speaker=str(entry.get("sender") or ""))
    except Exception:
        entry["who"] = "群友"
    try:
        unmo = str(getattr(event, "unified_msg_origin", "") or "")
    except Exception:
        unmo = ""
    record = SENT.append(unmo, entry)
    if record:
        logger.info(f"[quote] 已记录发送记忆：群 {gid} / {name}")
    return record
