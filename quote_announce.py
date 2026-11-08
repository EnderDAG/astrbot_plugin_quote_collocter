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

import quote_db
from quote_core import PLUGIN_DATA_DIR, UPDATE_ANNOUNCE_BRIDGE, UPDATE_ANNOUNCE_CONTEXT_SUMMARY_LIMIT, UPDATE_ANNOUNCE_CONTEXT_TTL, UPDATE_ANNOUNCE_FILE


def update_announce_path() -> Path:
    return PLUGIN_DATA_DIR / UPDATE_ANNOUNCE_FILE

def _normalize_update_announce(data) -> dict:
    data = data if isinstance(data, dict) else {}
    groups = []
    raw_groups = data.get("groups")
    if isinstance(raw_groups, list):
        for item in raw_groups:
            if not isinstance(item, dict):
                continue
            gid = str(item.get("group_id") or "").strip()
            umo = str(item.get("umo") or "").strip()
            if not gid and not umo:
                continue
            if not umo and gid:
                umo = f"default:GroupMessage:{gid}"
            groups.append(
                {
                    "group_id": gid,
                    "umo": umo,
                    "name": str(item.get("name") or "").strip()[:32],
                }
            )
    try:
        last_ts = float(data.get("last_announced_at") or 0.0)
    except (TypeError, ValueError):
        last_ts = 0.0
    result = data.get("last_result")
    last_version = str(data.get("last_version") or "")
    context = data.get("last_context")
    if not isinstance(context, dict) or not context:
        context = {}
        if last_ts > 0 and last_version:
            gids = []
            if isinstance(result, dict):
                for item in result.get("results") or []:
                    if isinstance(item, dict) and item.get("ok") and item.get("group_id"):
                        gids.append(str(item.get("group_id")))
            context = {
                "at": last_ts,
                "version": last_version,
                "groups": gids,
                "summary": "",
            }
    return {
        "enabled": bool(data.get("enabled", False)),
        "bridge_url": str(data.get("bridge_url") or UPDATE_ANNOUNCE_BRIDGE),
        "bridge_token": str(data.get("bridge_token") or ""),
        "groups": groups,
        "last_version": last_version,
        "last_announced_at": last_ts,
        "last_result": result if isinstance(result, dict) else {},
        "last_context": context,
    }

def load_update_announce() -> dict:
    try:
        raw = quote_db.load_doc("announce", "settings")
    except Exception as exc:
        logger.warning(f"[quote] 读取更新推送设置失败：{exc}")
        raw = None
    return _normalize_update_announce(raw or {})


def save_update_announce(data) -> dict:
    settings = _normalize_update_announce(data)
    try:
        quote_db.save_doc("announce", "settings", settings)
    except Exception as exc:
        logger.warning(f"[quote] 保存更新推送设置失败：{exc}")
    return settings

def release_notes_sync(version: str) -> list:
    """读取本插件 CHANGELOG.md 中某个版本的条目，返回可推送的短文本行。"""
    path = Path(__file__).resolve().parent / "CHANGELOG.md"
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return []
    pattern = re.compile(r"^##\s+v?" + re.escape(version) + r"\s*(?:[（(][^)）]*[)）])?\s*$")
    lines = raw.splitlines()
    start = None
    for index, line in enumerate(lines):
        if pattern.match(line.strip()):
            start = index + 1
            break
    if start is None:
        return []
    notes = []
    for line in lines[start:]:
        text = line.strip()
        if text.startswith("## "):
            break
        if text.startswith("### "):
            notes.append("【" + text[4:].strip() + "】")
            continue
        if text.startswith("- "):
            notes.append("· " + text[2:].strip())
        elif text and not text.startswith("#") and notes:
            notes.append(text)
    return notes[:10]

def is_ui_only_release(version: str) -> bool:
    """判断某版本是否为「仅界面调整」。

    CHANGELOG 的版本段里如果出现 `ui-only` 标记（HTML 注释或方括号写法均可），
    就认为这次更新不需要向群里推送公告。
    """
    path = Path(__file__).resolve().parent / "CHANGELOG.md"
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return False
    pattern = re.compile(r"^##\s+v?" + re.escape(version) + r"\s*(?:[（(][^)）]*[)）])?\s*$")
    lines = raw.splitlines()
    start = None
    for index, line in enumerate(lines):
        if pattern.match(line.strip()):
            start = index + 1
            break
    if start is None:
        return False
    for line in lines[start:]:
        text = line.strip()
        if text.startswith("## "):
            break
        if "ui-only" in text.lower():
            return True
    return False


def announce_notes_summary(notes) -> str:
    """把更新条目压成一句近况摘要，供大模型上下文使用。"""
    heading = ""
    parts = []
    for note in list(notes or []):
        text = re.sub(r"\s+", " ", str(note).replace("`", "").replace("**", "")).strip()
        if not text:
            continue
        if text.startswith("【") and text.endswith("】"):
            heading = heading or text.strip("【】").strip()
            continue
        text = text.lstrip("·-• ").strip().rstrip("。；;. ")
        if text:
            parts.append(text)
    summary = "；".join(parts[:3]) if parts else heading
    if len(summary) > UPDATE_ANNOUNCE_CONTEXT_SUMMARY_LIMIT:
        summary = summary[: UPDATE_ANNOUNCE_CONTEXT_SUMMARY_LIMIT - 1].rstrip("；，, ") + "…"
    return summary

def announce_context_block(settings, group_id, now=None) -> str:
    """推送更新后一段时间内，给该群的大模型上下文注入一条近况提示。"""
    context = {}
    if isinstance(settings, dict):
        raw = settings.get("last_context")
        if isinstance(raw, dict):
            context = raw
    try:
        at = float(context.get("at") or 0.0)
    except (TypeError, ValueError):
        at = 0.0
    if at <= 0 or not group_id:
        return ""
    if now is None:
        now = time.time()
    if now - at > UPDATE_ANNOUNCE_CONTEXT_TTL:
        return ""
    groups = [str(item) for item in (context.get("groups") or []) if str(item)]
    if groups and str(group_id) not in groups:
        return ""
    version = str(context.get("version") or "").strip()
    summary = str(context.get("summary") or "").strip()
    when = time.strftime("%H:%M", time.localtime(at))
    head = f"你刚才在本群推送了《语录插件更新》v{version} 的通告（{when}）"
    if summary:
        head += f"，要点：{summary}"
    return (
        "【近况提示】" + head + "。"
        "如果群友提到刚才的推送、追问更新内容，可以自然地接着聊、按需简要说明；"
        "不要否认发过这条消息，也不要整段复述推送原文。"
    )

ANNOUNCE_MAX_LINES = 6
ANNOUNCE_LINE_LIMIT = 72
ANNOUNCE_FALLBACK_LIMIT = 110


def _metadata_desc_tail() -> str:
    """从 metadata.yaml 的 desc 里取最后一句，作为推送摘要的兜底。"""
    try:
        raw = (Path(__file__).resolve().parent / "metadata.yaml").read_text(encoding="utf-8")
    except OSError:
        return ""
    for line in raw.splitlines():
        if not line.startswith("desc:"):
            continue
        parts = [part.strip() for part in line[5:].strip().split("。") if part.strip()]
        if not parts:
            return ""
        tail = parts[-1]
        if len(tail) > ANNOUNCE_FALLBACK_LIMIT:
            tail = tail[: ANNOUNCE_FALLBACK_LIMIT - 1].rstrip() + "…"
        return tail
    return ""


def _clean_announce_note(note) -> str:
    text = re.sub(r"\s+", " ", str(note).replace("`", "").replace("**", "")).strip()
    text = text.lstrip("·-• ").strip()
    if text.startswith("版本号"):
        return ""
    if len(text) > ANNOUNCE_LINE_LIMIT:
        text = text[: ANNOUNCE_LINE_LIMIT - 1].rstrip("；，, ") + "…"
    return text


def build_announce_text(version: str, notes) -> str:
    """推送更新公告：列出精简后的更新条目；条目过多时只推送前几条摘要。"""
    head = f"【语录插件更新】v{version}"
    cleaned = [text for text in (_clean_announce_note(note) for note in list(notes or [])) if text]
    total = len(cleaned)
    lines = []
    for index, text in enumerate(cleaned[:ANNOUNCE_MAX_LINES], 1):
        lines.append(f"{index}. {text}")
    if total > ANNOUNCE_MAX_LINES:
        lines.append(f"…另有 {total - ANNOUNCE_MAX_LINES} 条更新，完整说明见管理页「更新日志」。")
    if not lines:
        fallback = _metadata_desc_tail()
        lines = [f"· {fallback}" if fallback else "· 本次更新包含若干修复与优化，详见管理页「更新日志」。"]
    body = "\n".join(lines)
    tail = "已自动完成部署与重载，无需额外操作；本条由 DSH 桥接自动推送。"
    return f"{head}\n{body}\n{tail}"
