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
from quote_core import MAX_IMAGE_BYTES, META, MIME_BY_EXT, PLUGIN_VERSION, THUMB_DIR_NAME, THUMB_FORMAT, THUMB_MAX_SIDE, THUMB_QUALITY, _ts_from_name, data_root, group_dir, group_ids, list_image_files, load_settings


def thumb_path(group_id: str, name: str) -> Path:
    return group_dir(group_id) / THUMB_DIR_NAME / (name + ".webp")

def _read_bytes(path: Path, want_thumb: bool, cache: Path) -> tuple[bytes, str]:
    if want_thumb and PILImage is not None:
        if cache.is_file():
            return cache.read_bytes(), "image/jpeg"
        try:
            with PILImage.open(path) as img:
                img = img.convert("RGB")
                img.thumbnail((THUMB_MAX_SIDE, THUMB_MAX_SIDE))
                buffer = io.BytesIO()
                try:
                    img.save(
                        buffer,
                        format=THUMB_FORMAT,
                        quality=THUMB_QUALITY,
                        method=4,
                    )
                    mime = "image/webp"
                except Exception:
                    buffer = io.BytesIO()
                    img.save(buffer, format="JPEG", quality=76, optimize=True)
                    mime = "image/jpeg"
            payload = buffer.getvalue()
            try:
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_bytes(payload)
            except OSError:
                pass
            return payload, mime
        except Exception as exc:
            logger.warning(f"[quote] 生成缩略图失败，回退原图：{exc}")
    size = path.stat().st_size
    if size > MAX_IMAGE_BYTES:
        raise ValueError(f"图片过大（{size} 字节），请用缩略图模式查看")
    return path.read_bytes(), MIME_BY_EXT.get(path.suffix.lower(), "application/octet-stream")

def warm_thumbs_sync(limit: int = 24, group_id: str = "") -> dict:
    """后台预生成缺失的缩略图缓存。

    返回 {"generated": 本次生成数, "remaining": 仍缺失数, "groups": 扫描群数}。
    """
    if PILImage is None:
        return {"generated": 0, "remaining": 0, "groups": 0}
    targets = [group_id] if group_id else group_ids()
    missing: list[tuple[str, str]] = []
    for gid in targets:
        try:
            names = [item["name"] for item in list_image_files(gid)]
        except Exception:
            continue
        for name in names:
            if not thumb_path(gid, name).is_file():
                missing.append((gid, name))
    generated = 0
    for gid, name in missing[: max(0, int(limit))]:
        try:
            _read_bytes(group_dir(gid) / name, True, thumb_path(gid, name))
            generated += 1
        except Exception:
            continue
    return {
        "generated": generated,
        "remaining": max(0, len(missing) - generated),
        "groups": len(targets),
    }

def _payload_for(group_id: str, name: str, want_thumb: bool) -> dict:
    path = group_dir(group_id) / name
    if not path.is_file():
        raise FileNotFoundError(name)
    raw, mime = _read_bytes(path, want_thumb, thumb_path(group_id, name))
    stat = path.stat()
    meta = META.get(group_id, name)
    info = {
        "name": name,
        "group_id": group_id,
        "size": stat.st_size,
        "mtime": stat.st_mtime,
        "ts": meta.get("ts") or _ts_from_name(name, stat.st_mtime),
        "user_id": meta.get("user_id"),
        "nickname": meta.get("nickname"),
        "message_id": meta.get("message_id"),
        "thumb": want_thumb,
        "mime": mime,
        "data_url": f"data:{mime};base64,{base64.b64encode(raw).decode()}",
    }
    if not want_thumb and PILImage is not None:
        try:
            with PILImage.open(path) as img:
                info["width"], info["height"] = img.size
        except Exception:
            pass
    return info

def _overview_sync() -> dict:
    groups = []
    total_quotes = 0
    total_bytes = 0
    for gid in group_ids():
        files = list_image_files(gid)
        size = sum(item["size"] for item in files)
        settings = load_settings(gid)
        latest = max((item["ts"] for item in files), default=0)
        contributors = {
            (META.get(gid, item["name"]).get("user_id"))
            for item in files
            if META.get(gid, item["name"]).get("user_id")
        }
        groups.append(
            {
                "group_id": gid,
                "count": len(files),
                "bytes": size,
                "latest_ts": latest,
                "contributors": len(contributors),
                "settings": {
                    "mode": int(settings.get("mode", 0)),
                    "coldown": int(settings.get("coldown", 10)),
                    "poke_prob": float(settings.get("poke_prob", 0.85)),
                },
                "cover": files[0]["name"] if files else None,
            }
        )
        total_quotes += len(files)
        total_bytes += size
    groups.sort(key=lambda item: (-item["count"], item["group_id"]))
    return {
        "version": PLUGIN_VERSION,
        "data_root": str(data_root().resolve()),
        "groups": groups,
        "total_quotes": total_quotes,
        "total_bytes": total_bytes,
        "thumbnail": PILImage is not None,
    }
