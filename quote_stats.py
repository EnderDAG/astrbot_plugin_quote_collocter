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
from quote_identity import IDENTITY
from quote_core import META, PLUGIN_VERSION, group_ids, list_image_files
from quote_semantic import SEMANTIC


def _statistics_sync(group_id: str = "", top: int = 20, trend_days: int = 30) -> dict:
    """统计语录总量、人物排名、投稿人排名与最近新增趋势（可按群过滤）。"""
    gid_filter = str(group_id or "").strip()
    try:
        top = max(1, min(100, int(top or 20)))
    except (TypeError, ValueError):
        top = 20
    try:
        trend_days = max(1, min(180, int(trend_days or 30)))
    except (TypeError, ValueError):
        trend_days = 30
    groups = [gid for gid in group_ids() if not gid_filter or gid == gid_filter]
    try:
        people = IDENTITY.summaries()
    except Exception:
        people = {}
    day_seconds = 86400
    now = time.time()
    today_day = int(now // day_seconds)
    start_day = today_day - (trend_days - 1)
    trend = {start_day + i: 0 for i in range(trend_days)}
    total_quotes = 0
    total_bytes = 0
    assigned_total = 0
    unassigned_total = 0
    semantic_total = 0
    submissions_total = 0
    by_user = {}
    by_submitter = {}
    group_rows = []
    for gid in groups:
        files = list_image_files(gid)
        try:
            meta_items = META.load(gid)["items"]
        except Exception:
            meta_items = {}
        try:
            semantic_items = SEMANTIC.items(gid)
        except Exception:
            semantic_items = {}
        group_bytes = 0
        group_assigned = 0
        group_semantic = 0
        group_submitters = set()
        for item in files:
            name = item["name"]
            info = meta_items.get(name) or {}
            total_quotes += 1
            group_bytes += int(item.get("size") or 0)
            ts = float(item.get("ts") or 0)
            day = int(ts // day_seconds)
            if day in trend:
                trend[day] += 1
            uid = str(info.get("subject_user_id") or "").strip()
            if uid:
                assigned_total += 1
                group_assigned += 1
                entry = by_user.setdefault(
                    uid, {"count": 0, "groups": {}, "last_ts": 0.0}
                )
                entry["count"] += 1
                entry["groups"][gid] = entry["groups"].get(gid, 0) + 1
                entry["last_ts"] = max(entry["last_ts"], ts)
            else:
                unassigned_total += 1
            submitter = str(info.get("user_id") or "").strip()
            if submitter:
                submissions_total += 1
                group_submitters.add(submitter)
                sub = by_submitter.setdefault(
                    submitter,
                    {"count": 0, "names": set(), "groups": {}, "last_ts": 0.0},
                )
                sub["count"] += 1
                sub["groups"][gid] = sub["groups"].get(gid, 0) + 1
                sub["last_ts"] = max(sub["last_ts"], ts)
                nickname = str(info.get("nickname") or "").strip()
                if nickname:
                    sub["names"].add(nickname)
            entry = semantic_items.get(name)
            if isinstance(entry, dict) and entry.get("vector"):
                semantic_total += 1
                group_semantic += 1
        total_bytes += group_bytes
        group_rows.append(
            {
                "group_id": gid,
                "quotes": len(files),
                "bytes": group_bytes,
                "assigned": group_assigned,
                "unassigned": len(files) - group_assigned,
                "semantic": group_semantic,
                "submitters": len(group_submitters),
            }
        )

    by_person = {}
    for uid, entry in by_user.items():
        who = people.get(uid) or {}
        pid = str(who.get("person_id") or "") or uid
        row = by_person.setdefault(
            pid,
            {
                "person_id": pid,
                "pid": str(who.get("pid") or person_key(pid)),
                "user_ids": [],
                "display_name": "",
                "avatar_sha": "",
                "count": 0,
                "groups": {},
                "last_ts": 0.0,
            },
        )
        row["user_ids"].append(uid)
        row["count"] += entry["count"]
        row["last_ts"] = max(row["last_ts"], entry["last_ts"])
        for gid, count in entry["groups"].items():
            row["groups"][gid] = row["groups"].get(gid, 0) + count
        if not row["display_name"] and who.get("display_name"):
            row["display_name"] = str(who["display_name"])
        if not row["avatar_sha"] and who.get("avatar_sha"):
            row["avatar_sha"] = str(who["avatar_sha"])
    ranking = []
    for row in by_person.values():
        if not row["display_name"]:
            row["display_name"] = row["user_ids"][0] if row["user_ids"] else row["person_id"]
        row["groups"] = [
            {"group_id": gid, "count": count}
            for gid, count in sorted(row["groups"].items(), key=lambda kv: -kv[1])
        ]
        ranking.append(row)
    ranking.sort(key=lambda item: (-item["count"], -item["last_ts"]))
    for index, row in enumerate(ranking, start=1):
        row["rank"] = index

    contributors = []
    for uid, entry in by_submitter.items():
        who = people.get(uid) or {}
        name = str(who.get("display_name") or "").strip()
        if not name:
            names = sorted(entry["names"], key=len, reverse=True)
            name = names[0] if names else uid
        contributors.append(
            {
                "user_id": uid,
                "display_name": name,
                "avatar_sha": str(who.get("avatar_sha") or ""),
                "count": entry["count"],
                "last_ts": entry["last_ts"],
                "groups": [
                    {"group_id": gid, "count": count}
                    for gid, count in sorted(entry["groups"].items(), key=lambda kv: -kv[1])
                ],
            }
        )
    contributors.sort(key=lambda item: (-item["count"], -item["last_ts"]))
    for index, row in enumerate(contributors, start=1):
        row["rank"] = index

    last7 = sum(trend.get(today_day - i, 0) for i in range(7))
    return {
        "version": PLUGIN_VERSION,
        "generated_at": now,
        "group_id": gid_filter,
        "trend_days": trend_days,
        "totals": {
            "quotes": total_quotes,
            "bytes": total_bytes,
            "groups": len(groups),
            "persons": len(ranking),
            "assigned": assigned_total,
            "unassigned": unassigned_total,
            "assigned_rate": round(assigned_total / total_quotes, 4) if total_quotes else 0.0,
            "submissions": submissions_total,
            "contributors": len(contributors),
            "semantic": semantic_total,
            "semantic_rate": round(semantic_total / total_quotes, 4) if total_quotes else 0.0,
            "today": int(trend.get(today_day, 0)),
            "last7": last7,
        },
        "groups": sorted(group_rows, key=lambda item: -item["quotes"]),
        "ranking": ranking[:top],
        "contributors": contributors[:top],
        "trend": [
            {
                "date": time.strftime("%Y-%m-%d", time.localtime(day * day_seconds)),
                "count": count,
            }
            for day, count in sorted(trend.items())
        ],
    }

def _month_window(offset: int = 0):
    """返回 (YYYY-MM 标签, 起始时间戳, 结束时间戳)。offset=0 本月，-1 上月。"""
    now = time.localtime()
    year, month = int(now.tm_year), int(now.tm_mon) + int(offset)
    while month <= 0:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    start = float(time.mktime((year, month, 1, 0, 0, 0, 0, 0, -1)))
    ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
    end = float(time.mktime((ny, nm, 1, 0, 0, 0, 0, 0, -1)))
    return f"{year}-{month:02d}", start, end


def _monthly_ranking_sync(group_id: str, offset: int = 0, limit: int = 10) -> dict:
    """按月统计本群语录排行与投稿排行（offset=0 本月，-1 上月）。"""
    gid = str(group_id or "")
    label, start, end = _month_window(offset)
    result = {"label": label, "quotes": 0, "ranking": [], "contributors": []}
    if not gid:
        return result
    try:
        people = IDENTITY.summaries()
    except Exception:
        people = {}
    try:
        files = list_image_files(gid)
        meta_items = META.load(gid)["items"]
    except Exception:
        files, meta_items = [], {}
    by_user: dict = {}
    by_submitter: dict = {}
    total = 0
    for item in files:
        name = str(item.get("name") or "")
        ts = float(item.get("ts") or 0)
        if ts < start or ts >= end:
            continue
        total += 1
        info = meta_items.get(name) or {}
        uid = str(info.get("subject_user_id") or "").strip()
        if uid:
            row = by_user.setdefault(uid, {"count": 0, "last_ts": 0.0})
            row["count"] += 1
            row["last_ts"] = max(row["last_ts"], ts)
        submitter = str(info.get("user_id") or "").strip()
        if submitter:
            row = by_submitter.setdefault(submitter, {"count": 0, "last_ts": 0.0})
            row["count"] += 1
            row["last_ts"] = max(row["last_ts"], ts)
    by_person: dict = {}
    for uid, row in by_user.items():
        who = people.get(uid) or {}
        pid = str(who.get("person_id") or "") or uid
        person = by_person.setdefault(
            pid,
            {
                "person_id": pid,
                "pid": str(who.get("pid") or person_key(pid)),
                "display_name": "",
                "count": 0,
                "last_ts": 0.0,
            },
        )
        person["count"] += row["count"]
        person["last_ts"] = max(person["last_ts"], row["last_ts"])
        if not person["display_name"] and who.get("display_name"):
            person["display_name"] = str(who["display_name"])
    ranking = list(by_person.values())
    for row in ranking:
        if not row["display_name"]:
            row["display_name"] = str(row["person_id"])
    ranking.sort(key=lambda item: (-item["count"], -item["last_ts"]))
    for index, row in enumerate(ranking, start=1):
        row["rank"] = index
    contributors = []
    for uid, row in by_submitter.items():
        who = people.get(uid) or {}
        contributors.append(
            {
                "rank": 0,
                "display_name": str(who.get("display_name") or uid),
                "count": row["count"],
                "last_ts": row["last_ts"],
            }
        )
    contributors.sort(key=lambda item: (-item["count"], -item["last_ts"]))
    for index, row in enumerate(contributors, start=1):
        row["rank"] = index
    result.update(
        {
            "quotes": total,
            "ranking": ranking[: max(1, int(limit))],
            "contributors": contributors[: max(1, int(limit))],
        }
    )
    return result


def _ranking_text_sync(
    group_id: str, limit: int = 10, period: str = "all", offset: int = 0
) -> str:
    """群内「/语录排行」命令的文本输出（period="month" 时按月统计）。"""
    if str(period or "") == "month":
        try:
            data = _monthly_ranking_sync(group_id, offset, limit)
        except Exception as exc:
            logger.error(f"[quote] 月度语录统计失败：{exc}", exc_info=True)
            return ""
        label = data["label"]
        suffix = "本月" if offset >= 0 else "上月"
        lines = [f"⭐本群 {label} 语录排行（{suffix}，共新增 {data['quotes']} 张）"]
        if not data["quotes"]:
            lines.append("这个月还没有新语录~")
            return chr(10).join(lines)
        if data["ranking"]:
            lines.append("—— 本月语录数量排名 ——")
            for row in data["ranking"]:
                lines.append(f"  {row['rank']}. {row['display_name']} —— {row['count']} 条")
        if data["contributors"]:
            lines.append("—— 本月投稿数量排名 ——")
            for row in data["contributors"]:
                lines.append(f"  {row['rank']}. {row['display_name']} —— {row['count']} 条")
        return chr(10).join(lines)
    try:
        stats = _statistics_sync(group_id, limit, 30)
    except Exception as exc:
        logger.error(f"[quote] 语录统计失败：{exc}", exc_info=True)
        return ""
    totals = stats["totals"]
    lines = [f"⭐本群语录统计：共 {totals['quotes']} 张"]
    if not totals["quotes"]:
        lines.append("还没有语录，发送「语录投稿+图片」即可添加！")
        return chr(10).join(lines)
    rate = round(float(totals["assigned_rate"]) * 100)
    lines.append(f"   已归属 {totals['assigned']} 张（{rate}%），未归属 {totals['unassigned']} 张")
    lines.append(f"   投稿人 {totals['contributors']} 位，人物 {totals['persons']} 位")
    if stats["ranking"]:
        lines.append("—— 语录数量排名 ——")
        for row in stats["ranking"]:
            lines.append(f"  {row['rank']}. {row['display_name']} —— {row['count']} 条")
    if stats["contributors"]:
        lines.append("—— 投稿数量排名 ——")
        for row in stats["contributors"]:
            lines.append(f"  {row['rank']}. {row['display_name']} —— {row['count']} 条")
    return chr(10).join(lines)
