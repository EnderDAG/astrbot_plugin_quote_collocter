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

v2.9.5:
  * 更新推送成功后把版本要点注入一次 LLM 上下文，让 AI 知道自己刚更新了什么

v2.9.6:
  * 新增 quote_stats 工具：AI 统计语录时按人物（pid）合并多个昵称，不再把同一人算成多个人

v2.10:
  * 语录人物改用稳定 pid（pid_XXXX）管理，昵称 / 头像 / 合并关系都挂到 pid 上

v2.11:
  * 数据层迁移到 SQLite（plugin_data/quote_collocter/quote.db），JSON 只作一次性迁移来源
  * 作者：enderdag（基于上游 litsum 二次开发）；新增 database 接口查看库状态

v2.12.0:
  * 补全群内语录命令：/抽语录 /今日语录 /语录查 /语录人物 /合集 /周报 /语录帮助
  * 新增专题合集：把语录按主题整理成合集，管理页可建 / 改 / 删，群里 /合集 名称 随机看图
  * 新增每周语录周报：统计本周新增、人物与投稿人 Top3，可通过 DSH 桥接自动推送到群

v2.12.3:
  * AI 工具合并为单个 quote(action=recall|stats|weekly)，工具说明从约 1.2K 字压到约 0.8K
  * 召回候选压到 3 条、每条只留 id/who/caption/tags（必要时 via/sent_ago）；最近发送记忆压到 5 条、注入最多 2 条
  * 新增召回缓存（同群同关键词 5 分钟复用）与召回提示节流（每群 30 分钟一次）
  * 召回工具显式导入 ago_text / slim_candidate，去掉对星号导入的隐式依赖

v2.12.2:
  * AI 召回候选从 5 条压到 3 条，字段精简为 id / who / pid / caption / tags / tone
  * 召回结果附带「最近已发过的图」，候选会标注 sent_ago，避免同一张图反复发送
  * /语录排行 支持按月：/语录排行 本月、/语录排行 上月，可再带条数（3–30）

v2.13.0:
  * A1 全文检索：SQLite FTS5（CJK 单字 + 二元组）建索引，支持关键词 + 人物 / 标签 /
    时间范围 / 是否已归属的组合筛选，管理页新增搜索框
  * A3 回收站：删除改为软删除（图片移入 .trash，元数据进 quote.db），可恢复 / 彻底删除，
    超过「回收站保留天数」自动清理
  * B1 自动打标签：新投稿自动进入后台语义化队列，逐条补视觉描述与向量，可暂停 / 恢复，
    失败自动重试（最多 3 次）

v2.14.0:
  * C3 年度报告：/年度报告 [@某人|昵称] [年份] 生成 Wrapped 风格竖版长图
    （年度语录数、全群排名、逐月分布、高光时刻、代表语录、最常投稿的人）
  * E1 数据可视化：新增 24×7 时段热力图、一年发帖日历、人物时间线 API，管理页「数据可视化」弹窗
  * 新接口：insights/heatmap、insights/timeline、insights/annual、insights/annual_image
 * v2.14.1：更新推送改为摘要推送——按条列出精简后的更新点，条目过多时保留前 6 条并提示查看完整日志，不再只发一句「细节见更新日志」
* v2.15.0：俗名学习——自动从群消息里学习群友俗名/外号，先进入「待确认俗名」队列，管理页确认后写入别名表（QQ > @提及 > 确认别名 > 群名片/昵称历史 > 形近）
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
from astrbot.api.event import MessageChain, filter
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

import os as _os
import sys as _sys

_PLUGIN_DIR = _os.path.dirname(_os.path.abspath(__file__))
if _PLUGIN_DIR not in _sys.path:
    _sys.path.insert(0, _PLUGIN_DIR)

from quote_core import *  # noqa: F401,F403

import quote_db
import quote_insights
import quote_rating
import quote_collab
from quote_annual_image import render_report as render_annual_report
from quote_identity import *  # noqa: F401,F403
from quote_identity import warm_avatar_thumbs_sync
from quote_announce import *  # noqa: F401,F403
from quote_semantic import *  # noqa: F401,F403
from quote_sent import *  # noqa: F401,F403
from quote_views import *  # noqa: F401,F403
from quote_stats import *  # noqa: F401,F403
from quote_recall import *  # noqa: F401, F403
import quote_alias_learn
from quote_collections import (
    create as collection_create,
    delete as collection_delete,
    get as collection_get,
    list_payload as collection_list,
    text_list as collection_text_list,
    update as collection_update,
)
from quote_commands import (
    collection_names,
    help_text,
    person_quotes,
    random_names,
    semantic_names,
    today_names,
    weekly as weekly_text,
)
from quote_weekly import (
    due_groups as weekly_due_groups,
    load_weekly_settings,
    report_text as weekly_report_text,
    save_weekly_settings,
    week_key,
    week_window,
    weekly_report_sync,
)
from quote_weekly_image import (
    render_card as weekly_card_render,
    render_for_group as weekly_card_for_group,
)
from quote_autotag import AUTOTAG
from quote_core import ADMIN_ONLY, DATA_ROOT, DEFAULT_SETTINGS, IDENTITY_AUTO_SYNC_AVATARS, IDENTITY_AUTO_SYNC_MAX_HOURS, IDENTITY_AUTO_SYNC_MIN_HOURS, IDENTITY_AUTO_SYNC_TICK, IDENTITY_CLUSTER_MIN_SIZE, IDENTITY_MATCH_THRESHOLD, IDENTITY_SYNC_LIMIT, IMAGE_EXTS, META, PLUGIN_DATA_DIR, PLUGIN_NAME, PLUGIN_VERSION, RECALL_MARK_RAW_LIMIT, RECALL_MARK_RE, RECALL_MAX_IMAGES, RECALL_RECENT_AGE, RECALL_RECENT_LIMIT, RECALL_REMIND_HEAD, RECALL_TOOL_NAME, RECALL_TOP_K, SEMANTIC_DEFAULT_MIN_SCORE, SENT_INJECT_MAX, SENT_KEEP, SENT_MAX_AGE, SUBJECT_AUTO_SCORE, SUBJECT_MAX_FILES, SUBJECT_TASKS, UPDATE_ANNOUNCE_DELAY, _ts_from_name, data_root, group_dir, group_ids, list_image_files, load_settings, normalize_settings, safe_group_id, safe_image_name, save_settings
from quote_identity import IDENTITY, IDENTITY_AVATAR_TASKS, _clean_ai_name, _clean_speaker_name, clean_speaker_title, fetch_avatar_bytes, load_identity_sync_settings, normalize_avatar, save_identity_sync_settings
from quote_semantic import SEMANTIC, SEMANTIC_RUNNER, _cosine, caption_quote, embed_text, embedding_signature, resolve_caption_provider_id, resolve_embedding_provider, semantic_status_sync
from quote_sent import SENT, inject_sent_memory, remember_sent_quote
from quote_views import _overview_sync, _payload_for, thumb_path, warm_thumbs_sync
from quote_stats import _ranking_text_sync, _statistics_sync
from quote_recall import _resolve_recall_name, _tool_json, ago_text, recall_cache_get, recall_cache_put, recall_candidates_sync, recall_person_quotes_sync, slim_candidate
from quote_announce import announce_context_block, announce_notes_summary, build_announce_text, load_update_announce, release_notes_sync, save_update_announce

# 召回提示节流（v2.12.3）：同群 30 分钟最多注入一次
_REMIND_TS: dict = {}
REMIND_INTERVAL = 1800.0


def _filter_restricted(records: list, mode: str) -> list:
    """按限制级筛选语录记录：0/默认=仅非限制级，1=仅限制级，all=全部。"""
    mode = str(mode or "0").strip().lower()
    if mode in ("1", "restricted", "限制级"):
        return [row for row in records if row.get("restricted")]
    if mode in ("all", "全部"):
        return records
    return [row for row in records if not row.get("restricted")]


def _allow_restricted(group_id: str) -> bool:
    """本群是否允许发送限制级语录（默认关闭）。"""
    try:
        return bool(load_settings(group_id).get("allow_restricted", False))
    except Exception:
        return False


def _filter_rating_names(group_id: str, names: list) -> list:
    """过滤掉限制级语录文件名（本群开启限制级时不过滤）。"""
    if _allow_restricted(group_id):
        return list(names)
    try:
        allowed = set(quote_rating.public_names_sync(group_id))
    except Exception:
        return list(names)
    return [name for name in names if name in allowed]


def _chat_pool(group_id: str) -> list:
    """群命令取图池：默认只含非限制级，本群开启后为全部。"""
    if _allow_restricted(group_id):
        try:
            return [str(item.get("name")) for item in list_image_files(group_id)]
        except Exception:
            return []
    return quote_rating.public_names_sync(group_id)


class Quote_Plugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.quotes_data_path = str(DATA_ROOT)
        self._image_lock = asyncio.Lock()
        self._bot = None
        self._identity_sync_task = None
        self._update_announce_task = None
        self._weekly_task = None
        self._trash_task = None
        self._auto_semantic_task = None
        self._thumb_warm_task = None
        self._avatar_warm_task = None

        bot_config = context.get_config()
        admins = bot_config.get("admins_id", [])
        self.admins = [str(admin) for admin in admins] if admins else []
        if self.admins:
            logger.info(f"从 astrbot 配置中获取到管理员ID列表: {self.admins}")
        else:
            logger.warning("未找到任何管理员ID，某些需要管理员权限的命令可能无法使用")

        self._register_web_apis()

    async def initialize(self):
        data_root().mkdir(parents=True, exist_ok=True)
        PLUGIN_DATA_DIR.mkdir(parents=True, exist_ok=True)
        try:
            await asyncio.to_thread(quote_db.ensure_initialized)
            media_info = quote_db.media_migration_result()
            if media_info.startswith("moved") or media_info.startswith("no legacy"):
                logger.info(f"[quote] 数据目录已就绪：{data_root().resolve()}（{media_info}）")
            elif media_info.startswith("failed"):
                logger.warning(
                    f"[quote] 旧语录图片目录迁移失败（不影响运行，下次启动重试）：{media_info}"
                )
        except Exception as exc:
            logger.warning(f"[quote] 初始化数据库失败：{exc}")
        embedding = resolve_embedding_provider(self.context)
        caption_id = resolve_caption_provider_id(self.context)
        logger.info(
            f"[quote] v{PLUGIN_VERSION} 已就绪，数据目录 {data_root().resolve()}；"
            f"向量模型={embedding_signature(embedding) or '未配置'}，"
            f"视觉模型={caption_id or '未配置'}"
        )
        try:
            self._identity_sync_task = asyncio.create_task(self._identity_sync_loop())
        except Exception as exc:
            logger.warning(f"[quote] 启动身份自动同步失败：{exc}")
        auto_sync = load_identity_sync_settings()
        logger.info(
            f"[quote] 身份自动同步：{'启用' if auto_sync['enabled'] else '已暂停'}，"
            f"每 {auto_sync['interval_hours']:g} 小时一次"
        )
        try:
            self._update_announce_task = asyncio.create_task(self._announce_update_startup())
        except Exception as exc:
            logger.warning(f"[quote] 启动更新推送失败：{exc}")
        try:
            self._weekly_task = asyncio.create_task(self._weekly_loop())
        except Exception as exc:
            logger.warning(f"[quote] 启动每周语录周报任务失败：{exc}")
        try:
            AUTOTAG.start(self)
        except Exception as exc:
            logger.warning(f"[quote] 启动自动打标签队列失败：{exc}")
        try:
            count = await asyncio.to_thread(quote_db.fts_rebuild_all)
            logger.info(f"[quote] 全文检索索引已就绪（{count} 条）")
        except Exception as exc:
            logger.warning(f"[quote] 重建全文检索索引失败：{exc}")
        try:
            purged = await asyncio.to_thread(self._purge_trash_sync, "")
            if purged:
                logger.info(f"[quote] 回收站自动清理 {purged} 张过期语录")
        except Exception as exc:
            logger.warning(f"[quote] 回收站自动清理失败：{exc}")
        try:
            self._trash_task = asyncio.create_task(self._trash_loop())
        except Exception as exc:
            logger.warning(f"[quote] 启动回收站定时清理失败：{exc}")
        try:
            self._alias_learn_task = asyncio.create_task(self._alias_learn_loop())
        except Exception as exc:
            logger.warning(f"[quote] 启动俗名学习任务失败：{exc}")
        try:
            self._auto_semantic_task = asyncio.create_task(self._auto_semantic_loop())
            self._thumb_warm_task = asyncio.create_task(self._thumb_warm_loop())
            self._avatar_warm_task = asyncio.create_task(self._avatar_warm_loop())
        except Exception as exc:
            logger.warning(f"[quote] 启动自动语义化任务失败：{exc}")

        try:
            base = quote_collab.public_base()
            await quote_collab.start(self.context, port=6190)
            entry = base or "未设置（请在管理页「协作维护」中填写外网地址）"
            logger.info(f"[quote] 协作维护页已启动（127.0.0.1:6190，外网入口 {entry}）")
        except Exception as exc:
            logger.warning(f"[quote] 启动协作维护页失败：{exc}")

    async def terminate(self):
        try:
            AUTOTAG.stop()
        except Exception:
            pass
        if SEMANTIC_RUNNER.is_running():
            SEMANTIC_RUNNER.cancel()
            logger.info("[quote] 插件卸载，已请求取消进行中的语义化任务")
        for task in list(IDENTITY_AVATAR_TASKS.values()):
            if not task.done():
                task.cancel()
        IDENTITY_AVATAR_TASKS.clear()
        task = getattr(self, "_identity_sync_task", None)
        if task is not None and not task.done():
            task.cancel()
            logger.info("[quote] 插件卸载，已停止身份自动同步")
        announce_task = getattr(self, "_update_announce_task", None)
        if announce_task is not None and not announce_task.done():
            announce_task.cancel()
        weekly_task = getattr(self, "_weekly_task", None)
        if weekly_task is not None and not weekly_task.done():
            weekly_task.cancel()
            logger.info("[quote] 插件卸载，已停止每周语录周报任务")
        trash_task = getattr(self, "_trash_task", None)
        if trash_task is not None and not trash_task.done():
            trash_task.cancel()
            logger.info("[quote] 插件卸载，已停止回收站定时清理")
        alias_task = getattr(self, "_alias_learn_task", None)
        if alias_task is not None and not alias_task.done():
            alias_task.cancel()
            logger.info("[quote] 插件卸载，已停止俗名学习任务")
        semantic_task = getattr(self, "_auto_semantic_task", None)
        if semantic_task is not None and not semantic_task.done():
            semantic_task.cancel()
            logger.info("[quote] 插件卸载，已停止自动语义化任务")
        thumb_task = getattr(self, "_thumb_warm_task", None)
        if thumb_task is not None and not thumb_task.done():
            thumb_task.cancel()
        avatar_task = getattr(self, "_avatar_warm_task", None)
        if avatar_task is not None and not avatar_task.done():
            avatar_task.cancel()
        try:
            await quote_collab.stop()
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Web API 注册
    # ------------------------------------------------------------------ #
    def _register_web_apis(self):
        registered = []

        def route(path, handler, methods, desc):
            self.context.register_web_api(
                f"/{PLUGIN_NAME}/{path}", handler, methods, desc
            )
            registered.append(path)

        route("overview", self.api_overview, ["GET"], "语录总览：群列表与统计")
        route("statistics", self.api_statistics, ["GET"], "语录统计：总量、人物与投稿人排名、新增趋势")
        route("quotes", self.api_quotes, ["GET"], "分页读取某群语录列表")
        route("quotes/search", self.api_quotes_search, ["GET"], "全文检索语录：关键词 + 人物 / 标签 / 时间筛选")
        route("trash", self.api_trash, ["GET"], "回收站：已删除的语录列表")
        route("trash/restore", self.api_trash_restore, ["POST"], "从回收站恢复语录")
        route("trash/purge", self.api_trash_purge, ["POST"], "彻底删除回收站中的语录")
        route("tag/queue", self.api_tag_queue, ["GET", "POST"], "自动打标签队列：状态 / 入队 / 暂停 / 清空")
        route("image", self.api_image, ["GET"], "读取语录图片（缩略图/原图）")
        route("images/batch", self.api_images_batch, ["GET"], "批量读取语录缩略图（最多 15 张）")
        route("quotes/delete", self.api_delete_quotes, ["POST"], "批量删除语录")
        route("quotes/move", self.api_move_quotes, ["POST"], "批量移动语录到其它群")
        route("quotes/rebind", self.api_quotes_rebind, ["POST"], "重填全部语录归属：按俗名/QQ 当前昵称刷新")
        route("quotes/restricted", self.api_quotes_restricted, ["POST"], "批量标记 / 取消限制级")
        route("quotes/rating", self.api_quotes_rating, ["GET"], "限制级统计")
        route("quotes/auto_rating", self.api_quotes_auto_rating, ["POST"], "批量自动识别限制级")
        route("semantic/auto", self.api_semantic_auto, ["GET"], "自动语义化状态：周期、上次/下次运行、待处理数")
        route("group/delete", self.api_delete_group, ["POST"], "清空并删除某个群的语录目录")
        route("settings", self.api_settings, ["GET", "POST"], "读取/保存群设置")
        route("semantic/status", self.api_semantic_status, ["GET"], "语义索引状态与模型可用性")
        route("semantic/run", self.api_semantic_run, ["POST"], "启动或取消一键语义化任务")
        route("semantic/progress", self.api_semantic_progress, ["GET"], "语义化任务进度")
        route("semantic/reset", self.api_semantic_reset, ["POST"], "清空某群的语义索引")
        route("sent", self.api_sent, ["GET", "POST"], "已发送语录记忆：状态与清空")
        route("identity/overview", self.api_identity_overview, ["GET"], "人物档案统计")
        route("identity/list", self.api_identity_list, ["GET"], "人物档案列表（按人聚合）")
        route("identity/detail", self.api_identity_detail, ["GET"], "人物/QQ 号档案详情")
        route("identity/avatars", self.api_identity_avatars, ["POST"], "批量读取头像缩略图")
        route("identity/match", self.api_identity_match, ["POST"], "以图找人：头像指纹匹配")
        route("identity/sync", self.api_identity_sync, ["POST"], "同步身份：昵称历史 + 头像拉取")
        route("identity/merge", self.api_identity_merge, ["POST"], "把多个 QQ 号合并为同一人")
        route("identity/split", self.api_identity_split, ["POST"], "拆分已合并的身份")
        route("identity/reset", self.api_identity_reset, ["POST"], "清空人物档案")
        route("identity/schedule", self.api_identity_schedule, ["GET", "POST"], "身份自动同步：读取/设置周期与下次时间")
        route("database", self.api_database, ["GET"], "SQLite 数据库状态：路径、大小、各表行数与迁移信息")
        route("announce", self.api_announce, ["GET", "POST"], "更新推送：白名单群聊、最近结果与测试推送")
        route("collections", self.api_collections, ["GET", "POST"], "专题合集：列表 / 新建 / 更新 / 删除")
        route("collections/delete", self.api_collections, ["POST"], "删除专题合集")
        route("weekly", self.api_weekly, ["GET", "POST"], "每周语录周报：读取 / 保存推送设置")
        route("weekly/test", self.api_weekly_test, ["POST"], "立即生成并推送一次周报")
        route("insights/heatmap", self.api_insights_heatmap, ["GET"], "数据可视化：24×7 时段热力图与发帖日历")
        route("insights/timeline", self.api_person_timeline, ["GET"], "人物时间线：某人按月新增语录与高光标签")
        route("insights/annual", self.api_annual_report, ["GET"], "年度报告数据（人物 × 年份）")
        route("insights/annual_image", self.api_annual_image, ["GET"], "年度报告长图（base64 PNG）")
        route(
            "identity/match_names",
            self.api_identity_match_names,
            ["GET"],
            "把截图里的说话人昵称匹配到群成员",
        )
        route(
            "quotes/subject",
            self.api_quotes_subject,
            ["POST"],
            "手动指定/清除某条语录的归属人物",
        )
        route(
            "quotes/auto_subject",
            self.api_quotes_auto_subject,
            ["POST"],
            "按语义化 speaker 自动回填语录归属人物",
        )
        route(
            "quotes/review",
            self.api_quotes_review,
            ["GET"],
            "待人工确认的语录归属（按截图昵称聚合）",
        )
        route(
            "quotes/bind_name",
            self.api_quotes_bind_name,
            ["POST"],
            "把一个截图昵称下的所有未归属语录绑定到某个人物",
        )
        route(
            "semantic/backfill_speaker",
            self.api_semantic_backfill_speaker,
            ["POST"],
            "把已识别人物档案反向写回语义索引的 speaker",
        )
        route(
            "identity/clusters",
            self.api_identity_clusters,
            ["GET"],
            "已绑定昵称的形近变体聚类（同一人被读错的名字）",
        )
        route(
            "identity/cluster_merge",
            self.api_identity_cluster_merge,
            ["POST"],
            "把一组形近昵称变体合并到同一个人物",
        )
        route(
            "identity/cleanup",
            self.api_identity_cleanup,
            ["POST"],
            "整理旧别名：迁移已绑定昵称并清理 OCR 变体",
        )
        route(
            "identity/aliases",
            self.api_identity_aliases,
            ["GET"],
            "读取昵称别名表（截图昵称 → QQ 号）",
        )
        route(
            "identity/alias_delete",
            self.api_identity_alias_delete,
            ["POST"],
            "删除一条昵称别名",
        )
        route(
            "alias/candidates",
            self.api_alias_candidates,
            ["GET"],
            "俗名学习：待确认别名候选列表",
        )
        route(
            "alias/candidate_confirm",
            self.api_alias_candidate_confirm,
            ["POST"],
            "确认一条俗名候选，写入别名表",
        )
        route(
            "alias/candidate_reject",
            self.api_alias_candidate_reject,
            ["POST"],
            "忽略一条俗名候选",
        )
        route(
            "alias/learn",
            self.api_alias_learn,
            ["POST"],
            "立即对某群跑一次俗名学习",
        )
        route(
            "collab/members",
            self.api_collab_members,
            ["GET", "POST"],
            "协作维护：成员列表 / 添加 / 移除",
        )
        route(
            "collab/tokens",
            self.api_collab_tokens,
            ["GET", "POST"],
            "协作维护：登录令牌列表 / 生成 / 吊销",
        )
        route(
            "collab/audit",
            self.api_collab_audit,
            ["GET", "POST"],
            "协作维护：审计日志 / 撤销",
        )
        route(
            "collab/base",
            self.api_collab_base,
            ["GET", "POST"],
            "协作维护：协作页外网地址查看 / 保存",
        )
        logger.info(f"[quote] 已注册 {len(registered)} 个 Web API 路由（/{PLUGIN_NAME}/*）")

    # ------------------------------------------------------------------ #
    # 协作维护（管理页 API）
    # ------------------------------------------------------------------ #
    async def api_collab_members(self):
        body = (await request.json(default={}) or {}) if request.method.upper() == "POST" else {}
        try:
            gid = safe_group_id(str(body.get("group_id") or request.query.get("group_id", "") or ""))
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        if request.method.upper() == "GET":
            data = await asyncio.to_thread(quote_collab.admin_members, gid)
            return json_response({"group_id": gid, **data})
        action = str(body.get("action") or "add").lower()
        qq = str(body.get("qq") or "").strip()
        if not qq.isdigit() or len(qq) < 5:
            return error_response("QQ 号不正确", status_code=400)
        actor = (getattr(self, "admins", None) or ["dashboard"])[0]
        if action == "remove":
            removed = await asyncio.to_thread(quote_collab.admin_remove_member, gid, qq, str(actor))
            return json_response({"ok": True, "removed": bool(removed)})
        role = "curator" if str(body.get("role") or "") == "curator" else "editor"
        await asyncio.to_thread(quote_collab.admin_upsert_member, gid, qq, role, str(actor))
        return json_response({"ok": True, "qq": qq, "role": role})

    async def api_collab_tokens(self):
        body = (await request.json(default={}) or {}) if request.method.upper() == "POST" else {}
        try:
            gid = safe_group_id(str(body.get("group_id") or request.query.get("group_id", "") or ""))
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        if request.method.upper() == "GET":
            data = await asyncio.to_thread(quote_collab.admin_tokens, gid)
            return json_response({"group_id": gid, **data})
        actor = str((getattr(self, "admins", None) or ["dashboard"])[0])
        action = str(body.get("action") or "create").lower()
        if action == "revoke":
            token_id = str(body.get("token_id") or "").strip()
            ok = await asyncio.to_thread(quote_collab.admin_revoke_token, gid, token_id, actor)
            return json_response({"ok": bool(ok)})
        qq = str(body.get("qq") or "").strip()
        if not qq.isdigit() or len(qq) < 5:
            return error_response("QQ 号不正确", status_code=400)
        role = "curator" if str(body.get("role") or "") == "curator" else "editor"
        try:
            hours = int(body.get("hours", 168))
        except (TypeError, ValueError):
            hours = 168
        if hours < 0:
            hours = 0
        data = await asyncio.to_thread(
            quote_collab.admin_create_token, gid, qq, role, hours, actor
        )
        return json_response({"ok": True, **data})

    async def api_collab_base(self):
        if request.method.upper() == "GET":
            return json_response({"public_base": quote_collab.public_base()})
        body = (await request.json(default={}) or {}) or {}
        value = str(body.get("public_base") or "").strip()
        try:
            base = await asyncio.to_thread(quote_collab.set_public_base, value)
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        return json_response({"ok": True, "public_base": base})

    async def api_collab_audit(self):
        body = (await request.json(default={}) or {}) if request.method.upper() == "POST" else {}
        try:
            gid = safe_group_id(str(body.get("group_id") or request.query.get("group_id", "") or ""))
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        if request.method.upper() == "POST":
            try:
                audit_id = int(body.get("id") or 0)
            except (TypeError, ValueError):
                audit_id = 0
            if audit_id <= 0:
                return error_response("缺少审计记录 id", status_code=400)
            actor = str((getattr(self, "admins", None) or ["dashboard"])[0])
            data = await asyncio.to_thread(
                quote_collab.undo_audit,
                audit_id,
                actor_qq=actor,
                actor_name="管理页",
                ip="dashboard",
                group_id=gid,
            )
            return json_response(data, status_code=200 if data.get("ok") else 400)
        try:
            limit = max(1, min(200, int(request.query.get("limit", 60, type=int) or 60)))
        except (TypeError, ValueError):
            limit = 60
        items = await asyncio.to_thread(quote_collab.list_audit, gid, limit)
        return json_response({"group_id": gid, "items": items})

    # ------------------------------------------------------------------ #
    # Web API 处理函数
    # ------------------------------------------------------------------ #
    async def api_overview(self):
        try:
            payload = await asyncio.to_thread(_overview_sync)
        except Exception as exc:
            logger.error(f"[quote] overview 失败：{exc}", exc_info=True)
            return error_response(f"读取总览失败：{exc}", status_code=500)
        return json_response(payload)

    async def api_database(self):
        """SQLite 数据库状态：路径、大小、各表行数与迁移信息。"""
        try:
            info = await asyncio.to_thread(quote_db.info)
        except Exception as exc:
            logger.error(f"[quote] 读取数据库状态失败：{exc}")
            return error_response(f"读取数据库状态失败：{exc}", status_code=500)
        return json_response(info)

    async def api_statistics(self):
        query = request.query
        try:
            top = int(query.get("top", 20, type=int) or 20)
            days = int(query.get("days", 30, type=int) or 30)
        except (TypeError, ValueError):
            top, days = 20, 30
        try:
            gid = safe_group_id(query.get("group_id")) if query.get("group_id") else ""
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        try:
            payload = await asyncio.to_thread(_statistics_sync, gid, top, days)
        except Exception as exc:
            logger.error(f"[quote] 语录统计失败：{exc}", exc_info=True)
            return error_response(f"读取统计失败：{exc}", status_code=500)
        return json_response(payload)

    async def api_collections(self):
        """专题合集：GET 列表 / POST 新建、更新、删除。"""
        if request.method.upper() == "GET":
            try:
                gid = safe_group_id(request.query.get("group_id")) if request.query.get("group_id") else ""
            except ValueError as exc:
                return error_response(str(exc), status_code=400)
            collection_id = str(request.query.get("collection_id") or "").strip()
            if collection_id:
                row = await asyncio.to_thread(collection_get, gid, collection_id)
                if row is None:
                    return error_response("合集不存在", status_code=404)
                return json_response({"group_id": gid, "collection": row})
            rows = await asyncio.to_thread(collection_list, gid) if gid else []
            return json_response({"group_id": gid, "collections": rows})

        body = await request.json(default={}) or {}
        try:
            gid = safe_group_id(body.get("group_id"))
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        action = str(body.get("action") or "create").strip()
        try:
            if action == "create":
                row = await asyncio.to_thread(
                    collection_create,
                    gid,
                    body.get("name") or "",
                    body.get("desc") or "",
                    body.get("ids") or [],
                    body.get("creator") or "",
                )
            elif action in {"update", "set_ids", "add", "remove"}:
                collection_id = str(body.get("collection_id") or "").strip()
                if not collection_id:
                    return error_response("缺少 collection_id", status_code=400)
                add_ids = None
                remove_ids = None
                ids = None
                if action == "set_ids":
                    ids = body.get("ids") or []
                elif action == "add":
                    add_ids = body.get("add_ids") or body.get("ids") or []
                elif action == "remove":
                    remove_ids = body.get("remove_ids") or body.get("ids") or []
                row = await asyncio.to_thread(
                    collection_update,
                    gid,
                    collection_id,
                    name=body.get("name"),
                    desc=body.get("desc"),
                    ids=ids,
                    add_ids=add_ids,
                    remove_ids=remove_ids,
                )
            elif action == "delete":
                collection_id = str(body.get("collection_id") or "").strip()
                if not collection_id:
                    return error_response("缺少 collection_id", status_code=400)
                await asyncio.to_thread(collection_delete, gid, collection_id)
                return json_response(
                    {"ok": True, "collections": await asyncio.to_thread(collection_list, gid)}
                )
            else:
                return error_response(f"未知操作：{action}", status_code=400)
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        except KeyError as exc:
            return error_response(f"合集不存在：{exc}", status_code=404)
        except Exception as exc:
            logger.error(f"[quote] 合集操作失败：{exc}", exc_info=True)
            return error_response(f"合集操作失败：{exc}", status_code=500)
        return json_response(
            {
                "ok": True,
                "collection": row,
                "collections": await asyncio.to_thread(collection_list, gid),
            }
        )

    async def api_weekly(self):
        """每周语录周报：GET 读取设置与预览 / POST 保存设置。"""
        settings = await asyncio.to_thread(load_weekly_settings)
        if request.method.upper() != "GET":
            body = await request.json(default={}) or {}
            try:
                settings = await asyncio.to_thread(save_weekly_settings, body)
            except ValueError as exc:
                return error_response(str(exc), status_code=400)
        _start, _end, label_start, label_end = week_window()
        previews = {}
        for gid in (settings.get("groups") or [])[:3]:
            try:
                previews[gid] = await asyncio.to_thread(weekly_text, gid)
            except Exception:
                continue
        return json_response(
            {
                "settings": settings,
                "week_label": f"{label_start}–{label_end}",
                "groups": group_ids(),
                "previews": previews,
            }
        )

    async def api_insights_heatmap(self):
        query = request.query
        raw_group = (query.get("group_id") or "").strip()
        try:
            gid = safe_group_id(raw_group) if raw_group else ""
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        try:
            days = int(query.get("days", 365) or 365)
        except (TypeError, ValueError):
            days = 365
        try:
            data = await asyncio.to_thread(quote_insights.heatmap_sync, gid, days)
        except Exception as exc:
            logger.error(f"[quote] 热力图统计失败：{exc}", exc_info=True)
            return error_response(f"热力图统计失败：{exc}", status_code=500)
        return json_response(data)

    async def api_person_timeline(self):
        query = request.query
        pid = (query.get("pid") or "").strip()
        raw_group = (query.get("group_id") or "").strip()
        try:
            gid = safe_group_id(raw_group) if raw_group else ""
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        if not pid:
            return error_response("缺少 pid 参数", status_code=400)
        try:
            data = await asyncio.to_thread(quote_insights.person_timeline_sync, pid, gid)
        except KeyError as exc:
            return error_response(f"人物不存在：{exc}", status_code=404)
        except Exception as exc:
            logger.error(f"[quote] 人物时间线统计失败：{exc}", exc_info=True)
            return error_response(f"人物时间线统计失败：{exc}", status_code=500)
        return json_response(data)

    async def api_annual_report(self):
        query = request.query
        pid = (query.get("pid") or "").strip()
        raw_group = (query.get("group_id") or "").strip()
        try:
            gid = safe_group_id(raw_group) if raw_group else ""
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        if not pid:
            return error_response("缺少 pid 参数", status_code=400)
        try:
            year = int(query.get("year", 0) or 0)
        except (TypeError, ValueError):
            year = 0
        try:
            report = await asyncio.to_thread(quote_insights.annual_report_sync, pid, year, gid)
        except KeyError as exc:
            return error_response(f"人物不存在：{exc}", status_code=404)
        except Exception as exc:
            logger.error(f"[quote] 年度报告统计失败：{exc}", exc_info=True)
            return error_response(f"年度报告统计失败：{exc}", status_code=500)
        return json_response(report)

    async def api_annual_image(self):
        query = request.query
        pid = (query.get("pid") or "").strip()
        raw_group = (query.get("group_id") or "").strip()
        try:
            gid = safe_group_id(raw_group) if raw_group else ""
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        if not pid:
            return error_response("缺少 pid 参数", status_code=400)
        try:
            year = int(query.get("year", 0) or 0)
        except (TypeError, ValueError):
            year = 0
        try:
            report = await asyncio.to_thread(quote_insights.annual_report_sync, pid, year, gid)
            path = await asyncio.to_thread(render_annual_report, report)
            raw = await asyncio.to_thread(lambda: Path(path).read_bytes())
        except KeyError as exc:
            return error_response(f"人物不存在：{exc}", status_code=404)
        except Exception as exc:
            logger.error(f"[quote] 年度报告图片生成失败：{exc}", exc_info=True)
            return error_response(f"年度报告图片生成失败：{exc}", status_code=500)
        encoded = base64.b64encode(raw).decode("ascii")
        return json_response(
            {
                "filename": Path(path).name,
                "image": "data:image/png;base64," + encoded,
                "report": {
                    "year": report.get("year"),
                    "display_name": report.get("display_name"),
                    "pid": report.get("pid"),
                    "total": report.get("total"),
                    "share": report.get("share"),
                    "rank": report.get("rank"),
                    "ranked_total": report.get("ranked_total"),
                    "group_total": report.get("group_total"),
                },
            }
        )

    async def api_weekly_test(self):
        body = await request.json(default={}) or {}
        gid = str(body.get("group_id") or "").strip()
        if gid:
            groups = [gid]
        else:
            settings = await asyncio.to_thread(load_weekly_settings)
            groups = list(settings.get("groups") or [])
        if not groups:
            return error_response("请先选择要推送的群聊", status_code=400)
        result = await self._weekly_push_once(groups)
        return json_response(result)

    async def _weekly_loop(self):
        """每周语录周报：到点后按配置推送，同一周只推送一次。"""
        await asyncio.sleep(45)
        while True:
            try:
                groups = await asyncio.to_thread(weekly_due_groups)
                if groups:
                    result = await self._weekly_push_once(groups)
                    ok = sum(1 for item in result.get("results") or [] if item.get("ok"))
                    logger.info(f"[quote] 周报推送：{ok}/{len(result.get('results') or [])} 个群成功")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(f"[quote] 周报任务异常：{exc}")
            await asyncio.sleep(600)

    async def _weekly_push_once(self, groups=None) -> dict:
        settings = await asyncio.to_thread(load_weekly_settings)
        targets = [str(gid) for gid in (groups or settings.get("groups") or []) if str(gid)]
        announce = await asyncio.to_thread(load_update_announce)
        url = str(announce.get("bridge_url") or "").strip()
        token = str(announce.get("bridge_token") or "").strip()
        if not url:
            return {"ok": False, "error": "未配置 DSH 桥接地址", "results": []}
        headers = {"Content-Type": "application/json", "X-DSH-Token": token}
        results = []
        for gid in targets:
            umo = f"default:GroupMessage:{gid}"
            item = {"group_id": gid, "ok": False}
            # 发图片周报：优先 AstrBot 消息链（会自动转 base64），其次协议端直发
            card_path = ""
            try:
                card = await asyncio.to_thread(weekly_card_for_group, gid)
                card_path = str(card[0] if isinstance(card, tuple) else card)
                chain = MessageChain(
                    [Image.fromFileSystem(str(Path(card_path).resolve()))]
                )
                item["ok"] = bool(await self.context.send_message(umo, chain))
                if item["ok"]:
                    item["via"] = "astrbot"
            except Exception as exc:
                item["error"] = f"astrbot: {exc!r}"
                logger.warning(
                    f"[quote] 周报图片经 AstrBot 发送失败 {gid}：{exc!r}", exc_info=True
                )
            if not item["ok"] and card_path:
                try:
                    raw = Path(card_path).resolve().read_bytes()
                    bot = self._bot_client()
                    if bot is None:
                        raise RuntimeError("协议端客户端不可用")
                    await bot.call_action(
                        "send_group_msg",
                        group_id=int(gid),
                        message=[
                            {
                                "type": "image",
                                "data": {
                                    "file": "base64://"
                                    + base64.b64encode(raw).decode("ascii")
                                },
                            }
                        ],
                    )
                    item["ok"] = True
                    item["via"] = "onebot"
                except Exception as exc:
                    item["error"] = (
                        f"{item.get('error') or ''} onebot: {exc!r}".strip()
                    )
                    logger.warning(
                        f"[quote] 周报图片经协议端直发失败 {gid}：{exc!r}"
                    )
            if item["ok"]:
                item.pop("error", None)
                results.append(item)
                continue
            # 回退：DSH 桥接发纯文字
            try:
                text = await asyncio.to_thread(weekly_text, gid)
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=20)
                ) as session:
                    async with session.post(
                        url,
                        json={"session": umo, "text": text},
                        headers=headers,
                    ) as resp:
                        payload = await resp.json(content_type=None)
                        item["status"] = resp.status
                        item["ok"] = bool(isinstance(payload, dict) and payload.get("sent"))
                if item["ok"]:
                    item["via"] = "bridge"
            except Exception as exc:
                item["error"] = str(exc)
            results.append(item)
        now = time.time()
        settings["last_result"] = {"at": now, "results": results}
        if any(item["ok"] for item in results):
            settings["last_week"] = week_key(now)
        await asyncio.to_thread(save_weekly_settings, settings)
        return {"ok": any(item["ok"] for item in results), "results": results}

    @staticmethod
    def _quote_records(gid: str) -> list[dict]:
        """读取某群全部语录并补全人物信息（供检索使用）。"""
        files = list_image_files(gid)
        meta = META.load(gid)
        semantic = SEMANTIC.items(gid)
        records = []
        for item in files:
            info = dict(meta["items"].get(item["name"]) or {})
            sem = dict(semantic.get(item["name"]) or {})
            tags = info.get("tags") or sem.get("tags") or []
            records.append(
                {
                    "group_id": gid,
                    "name": item["name"],
                    "size": item["size"],
                    "mtime": item["mtime"],
                    "ts": info.get("ts") or item["ts"],
                    "user_id": info.get("user_id"),
                    "nickname": info.get("nickname"),
                    "message_id": info.get("message_id"),
                    "caption": info.get("caption") or sem.get("caption"),
                    "tags": list(tags),
                    "tone": sem.get("tone") or "",
                    "speaker": sem.get("speaker") or "",
                    "semantic_text": str(sem.get("visible_text") or "")[:600],
                    "semantic_status": str(sem.get("status") or "pending"),
                    "has_vector": bool(sem.get("vector")),
                    "subject_user_id": str(info.get("subject_user_id") or ""),
                    "subject_name": str(info.get("subject_name") or ""),
                    "subject_source": str(info.get("subject_source") or ""),
                    "restricted": bool(info.get("restricted")),
                    "rating_source": str(info.get("rating_source") or ""),
                }
            )
        try:
            people = IDENTITY.summaries()
        except Exception:
            people = {}
        for item in records:
            summary = people.get(str(item.get("user_id") or "")) or {}
            item["person_id"] = summary.get("person_id") or ""
            item["display_name"] = summary.get("display_name") or item.get("nickname") or ""
            item["avatar_sha"] = summary.get("avatar_sha") or ""
            subject = people.get(str(item.get("subject_user_id") or "")) or {}
            item["subject_person_id"] = subject.get("person_id") or ""
            item["subject_person_name"] = subject.get("display_name") or ""
            item["subject_avatar_sha"] = subject.get("avatar_sha") or ""
            item["subject_display_name"] = item.get("subject_person_name") or ""
            item["subject_review_name"] = clean_speaker_title(item.get("subject_name") or "")
            item["subject_assigned"] = bool(item.get("subject_user_id"))
        return records

    async def api_quotes_search(self):
        query = request.query
        raw_group = (query.get("group_id") or "").strip()
        try:
            gid = safe_group_id(raw_group) if raw_group else ""
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        keyword = (query.get("q") or "").strip()
        tag = (query.get("tag") or "").strip()
        person_id = (query.get("person_id") or "").strip()
        assigned = (query.get("assigned") or "").strip()
        sort = (query.get("sort") or "rank").strip()
        try:
            page = max(1, int(query.get("page", 1) or 1))
            page_size = max(6, min(200, int(query.get("page_size", 48) or 48)))
        except (TypeError, ValueError):
            page, page_size = 1, 48
        try:
            date_from = float(query.get("from_ts") or 0)
            date_to = float(query.get("to_ts") or 0)
        except (TypeError, ValueError):
            date_from, date_to = 0.0, 0.0

        groups = [gid] if gid else await asyncio.to_thread(group_ids)
        records: list[dict] = []
        for one in groups:
            try:
                records.extend(await asyncio.to_thread(self._quote_records, one))
            except Exception as exc:
                logger.error(f"[quote] 检索读取群 {one} 失败：{exc}")

        if keyword:
            try:
                hits = await asyncio.to_thread(quote_db.fts_search, keyword, gid, 800)
            except Exception as exc:
                logger.warning(f"[quote] 全文检索失败：{exc}")
                hits = []
            if not hits:
                # 退化为 LIKE 匹配（含短关键词）
                needle = keyword.lower()
                records = [
                    item
                    for item in records
                    if needle in str(item.get("name") or "").lower()
                    or needle in str(item.get("caption") or "").lower()
                    or needle in str(item.get("semantic_text") or "").lower()
                    or needle in str(item.get("nickname") or "").lower()
                    or needle in str(item.get("speaker") or "").lower()
                    or any(needle in str(t).lower() for t in item.get("tags") or [])
                ]
            else:
                ranked = {}
                for idx, hit in enumerate(hits):
                    ranked[(str(hit.get("group_id")), str(hit.get("name")))] = idx
                records = [
                    item
                    for item in records
                    if (item["group_id"], item["name"]) in ranked
                ]
                records.sort(
                    key=lambda item: ranked[(item["group_id"], item["name"])]
                )

        if tag:
            tag_lower = tag.lower()
            records = [
                item
                for item in records
                if any(tag_lower in str(t).lower() for t in item.get("tags") or [])
            ]
        if person_id:
            try:
                detail = await asyncio.to_thread(IDENTITY.detail, "", person_id)
            except KeyError:
                return error_response(f"人物不存在：{person_id}", status_code=404)
            uids = {str(user.get("user_id") or "") for user in detail.get("users") or []}
            records = [item for item in records if item["subject_user_id"] in uids]
        if assigned == "1":
            records = [item for item in records if item["subject_assigned"]]
        elif assigned == "0":
            records = [item for item in records if not item["subject_assigned"]]
        if date_from:
            records = [item for item in records if float(item["ts"] or 0) >= date_from]
        if date_to:
            records = [item for item in records if float(item["ts"] or 0) <= date_to]
        restricted_mode = (query.get("restricted") or "0").strip().lower()
        records = _filter_restricted(records, restricted_mode)

        if sort == "old":
            records.sort(key=lambda item: item["ts"])
        elif not keyword:
            records.sort(key=lambda item: -item["ts"])

        total = len(records)
        start = (page - 1) * page_size
        window = records[start : start + page_size]
        return json_response(
            {
                "group_id": gid,
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": max(1, (total + page_size - 1) // page_size),
                "keyword": keyword,
                "tag": tag,
                "person_id": person_id,
                "items": window,
            }
        )

    async def api_quotes(self):
        query = request.query
        try:
            gid = safe_group_id(query.get("group_id", ""))
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        try:
            page = max(1, int(query.get("page", 1, type=int) or 1))
            page_size = int(query.get("page_size", 48, type=int) or 48)
        except (TypeError, ValueError):
            page, page_size = 1, 48
        page_size = max(6, min(200, page_size))
        keyword = (query.get("q") or "").strip()
        keyword_lower = keyword.lower()
        sort = (query.get("sort") or "new").strip()
        mode = (query.get("mode") or "browse").strip().lower()
        if mode not in {"browse", "semantic"}:
            mode = "browse"
        try:
            min_score = float(query.get("min_score", SEMANTIC_DEFAULT_MIN_SCORE) or SEMANTIC_DEFAULT_MIN_SCORE)
        except (TypeError, ValueError):
            min_score = SEMANTIC_DEFAULT_MIN_SCORE

        try:
            files = await asyncio.to_thread(list_image_files, gid)
            meta = await asyncio.to_thread(META.load, gid)
            semantic = await asyncio.to_thread(SEMANTIC.items, gid)
        except Exception as exc:
            return error_response(f"读取语录失败：{exc}", status_code=500)

        records = []
        for item in files:
            info = dict(meta["items"].get(item["name"]) or {})
            sem = dict(semantic.get(item["name"]) or {})
            tags = info.get("tags") or sem.get("tags") or []
            records.append(
                {
                    "name": item["name"],
                    "size": item["size"],
                    "mtime": item["mtime"],
                    "ts": info.get("ts") or item["ts"],
                    "user_id": info.get("user_id"),
                    "nickname": info.get("nickname"),
                    "message_id": info.get("message_id"),
                    "caption": info.get("caption") or sem.get("caption"),
                    "tags": list(tags),
                    "tone": sem.get("tone") or "",
                    "speaker": sem.get("speaker") or "",
                    "semantic_text": str(sem.get("visible_text") or "")[:600],
                    "semantic_status": str(sem.get("status") or "pending"),
                    "has_vector": bool(sem.get("vector")),
                    "subject_user_id": str(info.get("subject_user_id") or ""),
                    "subject_name": str(info.get("subject_name") or ""),
                    "subject_source": str(info.get("subject_source") or ""),
                    "restricted": bool(info.get("restricted")),
                    "rating_source": str(info.get("rating_source") or ""),
                }
            )

        try:
            people = await asyncio.to_thread(IDENTITY.summaries)
        except Exception:
            people = {}
        for item in records:
            summary = people.get(str(item.get("user_id") or "")) or {}
            item["person_id"] = summary.get("person_id") or ""
            item["display_name"] = (
                summary.get("display_name") or item.get("nickname") or ""
            )
            item["avatar_sha"] = summary.get("avatar_sha") or ""
            subject = people.get(str(item.get("subject_user_id") or "")) or {}
            item["subject_person_id"] = subject.get("person_id") or ""
            item["subject_person_name"] = subject.get("display_name") or ""
            item["subject_avatar_sha"] = subject.get("avatar_sha") or ""
            item["subject_display_name"] = item.get("subject_person_name") or ""
            item["subject_review_name"] = clean_speaker_title(
                item.get("subject_name") or ""
            )
            item["subject_assigned"] = bool(item.get("subject_user_id"))

        person_id = (query.get("person_id") or "").strip()
        subject_uid = (query.get("subject_user_id") or "").strip()
        assigned = (query.get("assigned") or "").strip()
        if person_id:
            try:
                detail = await asyncio.to_thread(IDENTITY.detail, "", person_id)
            except KeyError:
                return error_response(f"人物不存在：{person_id}", status_code=404)
            uids = {
                str(user.get("user_id") or "") for user in detail.get("users") or []
            }
            records = [item for item in records if item["subject_user_id"] in uids]
        elif subject_uid:
            records = [
                item for item in records if item["subject_user_id"] == subject_uid
            ]
        if assigned == "1":
            records = [item for item in records if item["subject_assigned"]]
        elif assigned == "0":
            records = [item for item in records if not item["subject_assigned"]]

        restricted_mode = (query.get("restricted") or "0").strip().lower()
        records = _filter_restricted(records, restricted_mode)

        if mode == "semantic" and keyword:
            embedder = resolve_embedding_provider(
                self.context, (query.get("embedding_provider_id") or "").strip()
            )
            if embedder is None:
                return error_response("没有可用的向量模型，无法进行语义检索", status_code=400)
            try:
                query_vector = await embed_text(embedder, keyword)
            except Exception as exc:
                logger.error(f"[quote] 语义检索失败：{exc}", exc_info=True)
                return error_response(f"语义检索失败：{exc}", status_code=500)
            scored = []
            for item in records:
                entry = semantic.get(item["name"]) or {}
                vector = entry.get("vector") or []
                if not vector:
                    continue
                score = _cosine(query_vector, vector)
                if score < min_score:
                    continue
                item["score"] = round(score, 6)
                scored.append(item)
            scored.sort(key=lambda item: -float(item.get("score") or 0.0))
            records = scored
        elif keyword_lower:
            records = [
                item
                for item in records
                if keyword_lower in (item["name"] or "").lower()
                or keyword_lower in str(item["nickname"] or "").lower()
                or keyword_lower in str(item["user_id"] or "").lower()
                or keyword_lower in str(item["caption"] or "").lower()
                or keyword_lower in str(item["semantic_text"] or "").lower()
                or keyword_lower in str(item["tone"] or "").lower()
                or any(keyword_lower in str(tag).lower() for tag in item["tags"])
            ]

        if mode != "semantic" or not keyword:
            if sort == "old":
                records.sort(key=lambda item: item["ts"])
            elif sort == "big":
                records.sort(key=lambda item: -item["size"])
            elif sort == "small":
                records.sort(key=lambda item: item["size"])
            else:
                records.sort(key=lambda item: -item["ts"])

        total = len(records)
        start = (page - 1) * page_size
        window = records[start : start + page_size]
        return json_response(
            {
                "group_id": gid,
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": max(1, (total + page_size - 1) // page_size),
                "sort": sort,
                "mode": mode,
                "min_score": min_score,
                "keyword": keyword,
                "total_bytes": sum(item["size"] for item in records),
                "items": window,
            }
        )

    async def api_image(self):
        query = request.query
        try:
            gid = safe_group_id(query.get("group_id", ""))
            name = safe_image_name(query.get("name", ""))
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        want_thumb = (query.get("size") or "thumb") != "original"
        try:
            # 缓存命中时无写入，直接并发读；只有需要生成缩略图时才加锁
            cache_ready = want_thumb and thumb_path(gid, name).is_file()
            if cache_ready:
                payload = await asyncio.to_thread(_payload_for, gid, name, want_thumb)
            else:
                async with self._image_lock:
                    payload = await asyncio.to_thread(_payload_for, gid, name, want_thumb)
        except FileNotFoundError:
            return error_response("图片不存在", status_code=404)
        except ValueError as exc:
            return error_response(str(exc), status_code=413)
        except Exception as exc:
            logger.error(f"[quote] 读取图片 {gid}/{name} 失败：{exc}", exc_info=True)
            return error_response(f"读取图片失败：{exc}", status_code=500)
        return json_response(payload)

    async def api_images_batch(self):
        """一次请求读取多张图片（默认缩略图），减少桥接往返。"""
        query = request.query
        try:
            gid = safe_group_id(query.get("group_id", ""))
            raw_names = (query.get("names") or "").split(",")
            names = []
            for item in raw_names:
                item = item.strip()
                if not item:
                    continue
                if len(names) >= 15:
                    break
                names.append(safe_image_name(item))
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        if not names:
            return error_response("缺少 names", status_code=400)
        want_thumb = (query.get("size") or "thumb") != "original"
        items: dict = {}
        errors: list = []
        for name in names:
            try:
                cache_ready = want_thumb and thumb_path(gid, name).is_file()
                if cache_ready:
                    payload = await asyncio.to_thread(_payload_for, gid, name, want_thumb)
                else:
                    async with self._image_lock:
                        payload = await asyncio.to_thread(_payload_for, gid, name, want_thumb)
                items[name] = payload.get("data_url", "")
            except Exception as exc:
                errors.append({"name": name, "error": str(exc)})
        return json_response({"items": items, "errors": errors})

    async def api_delete_quotes(self):
        body = await request.json(default={}) or {}
        try:
            gid = safe_group_id(body.get("group_id"))
            names = [safe_image_name(item) for item in (body.get("names") or [])]
        except (ValueError, TypeError) as exc:
            return error_response(str(exc), status_code=400)
        if not names:
            return error_response("没有选择要删除的语录", status_code=400)

        def worker() -> dict:
            deleted, missing = [], []
            directory = group_dir(gid)
            trash_dir = directory / ".trash"
            for name in names:
                target = directory / name
                if target.is_file():
                    try:
                        trash_dir.mkdir(parents=True, exist_ok=True)
                        dest = trash_dir / name
                        shutil.move(str(target), str(dest))
                        info = META.get(gid, name) or {}
                        sem = (SEMANTIC.items(gid) or {}).get(name) or {}
                        size = dest.stat().st_size if dest.is_file() else 0
                        quote_db.trash_put(
                            gid,
                            name,
                            {"meta": info, "semantic": sem, "size": size},
                        )
                        deleted.append(name)
                    except OSError as exc:
                        logger.error(f"[quote] 删除 {target} 失败：{exc}")
                        missing.append(name)
                else:
                    missing.append(name)
                cache = thumb_path(gid, name)
                if cache.is_file():
                    try:
                        cache.unlink()
                    except OSError:
                        pass
            META.drop(gid, deleted)
            SEMANTIC.drop(gid, deleted)
            return {"deleted": deleted, "missing": missing}

        result = await asyncio.to_thread(worker)
        logger.info(f"[quote] 群 {gid} 删除语录 {len(result['deleted'])} 张")
        return json_response(result)

    async def api_trash(self):
        query = request.query
        raw_group = (query.get("group_id") or "").strip()
        try:
            gid = safe_group_id(raw_group) if raw_group else ""
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        try:
            items = await asyncio.to_thread(quote_db.trash_list, gid)
        except Exception as exc:
            logger.error(f"[quote] 读取回收站失败：{exc}", exc_info=True)
            return error_response(f"读取回收站失败：{exc}", status_code=500)
        return json_response({"group_id": gid, "total": len(items), "items": items})

    async def api_trash_restore(self):
        body = await request.json(default={}) or {}
        try:
            gid = safe_group_id(body.get("group_id"))
            names = [safe_image_name(item) for item in (body.get("names") or [])]
        except (ValueError, TypeError) as exc:
            return error_response(str(exc), status_code=400)
        if not names:
            return error_response("没有选择要恢复的语录", status_code=400)

        def worker() -> dict:
            restored, missing = [], []
            directory = group_dir(gid)
            trash_dir = directory / ".trash"
            for name in names:
                data = quote_db.trash_get(gid, name)
                if data is None:
                    missing.append(name)
                    continue
                src = trash_dir / name
                if not src.is_file():
                    quote_db.trash_delete(gid, [name])
                    missing.append(name)
                    continue
                try:
                    directory.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(src), str(directory / name))
                except OSError as exc:
                    logger.error(f"[quote] 恢复 {name} 失败：{exc}")
                    missing.append(name)
                    continue
                info = data.get("meta") or {}
                if info:
                    META.update(gid, name, info)
                quote_db.trash_delete(gid, [name])
                try:
                    SEMANTIC.drop(gid, [name])
                except Exception:
                    pass
                try:
                    quote_db.tag_queue_add(gid, [name])
                except Exception:
                    pass
                restored.append(name)
            return {"restored": restored, "missing": missing}

        result = await asyncio.to_thread(worker)
        logger.info(f"[quote] 群 {gid} 从回收站恢复语录 {len(result['restored'])} 张")
        return json_response(result)

    async def api_trash_purge(self):
        body = await request.json(default={}) or {}
        try:
            gid = safe_group_id(body.get("group_id"))
            names = [safe_image_name(item) for item in (body.get("names") or [])]
        except (ValueError, TypeError) as exc:
            return error_response(str(exc), status_code=400)
        purge_all = bool(body.get("all"))
        if not names and not purge_all:
            return error_response("没有选择要彻底删除的语录", status_code=400)

        def worker() -> dict:
            directory = group_dir(gid)
            trash_dir = directory / ".trash"
            targets = list(names)
            if purge_all:
                targets = [row["name"] for row in quote_db.trash_list(gid)]
            removed = []
            for name in targets:
                target = trash_dir / name
                if target.is_file():
                    try:
                        target.unlink()
                    except OSError as exc:
                        logger.debug(f"[quote] 彻底删除 {target} 失败：{exc}")
                        continue
                removed.append(name)
            if removed:
                quote_db.trash_delete(gid, removed)
            return {"purged": removed}

        result = await asyncio.to_thread(worker)
        logger.info(f"[quote] 群 {gid} 彻底删除回收站语录 {len(result['purged'])} 张")
        return json_response(result)

    async def api_move_quotes(self):
        body = await request.json(default={}) or {}
        try:
            source = safe_group_id(body.get("from_group") or body.get("group_id"))
            target_group = safe_group_id(body.get("to_group"))
            names = [safe_image_name(item) for item in (body.get("names") or [])]
        except (ValueError, TypeError) as exc:
            return error_response(str(exc), status_code=400)
        if not names:
            return error_response("没有选择要移动的语录", status_code=400)
        if source == target_group:
            return error_response("源群与目标群相同", status_code=400)

        def worker() -> dict:
            moved, missing = [], []
            src_dir = group_dir(source)
            dst_dir = group_dir(target_group)
            dst_dir.mkdir(parents=True, exist_ok=True)
            for name in names:
                src = src_dir / name
                if not src.is_file():
                    missing.append(name)
                    continue
                dst = dst_dir / name
                index = 1
                while dst.exists():
                    dst = dst_dir / f"{Path(name).stem}_{index}{Path(name).suffix}"
                    index += 1
                try:
                    shutil.move(str(src), str(dst))
                except OSError as exc:
                    logger.error(f"[quote] 移动 {src} 失败：{exc}")
                    missing.append(name)
                    continue
                moved.append({"from": name, "to": dst.name})
                cache = thumb_path(source, name)
                if cache.is_file():
                    try:
                        cache.unlink()
                    except OSError:
                        pass
                info = META.get(source, name)
                META.update(target_group, dst.name, info)
                SEMANTIC.rename(source, target_group, name, dst.name)
            META.drop(source, [item["from"] for item in moved])
            return {"moved": moved, "missing": missing}

        result = await asyncio.to_thread(worker)
        logger.info(f"[quote] {source} -> {target_group} 移动 {len(result['moved'])} 张")
        return json_response(result)

    async def api_delete_group(self):
        body = await request.json(default={}) or {}
        try:
            gid = safe_group_id(body.get("group_id"))
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        if not body.get("confirm"):
            return error_response("需要确认后才可删除整个群的语录", status_code=400)

        def worker() -> dict:
            directory = group_dir(gid)
            count = len(list_image_files(gid))
            if directory.is_dir():
                shutil.rmtree(directory, ignore_errors=True)
            META.forget_group(gid)
            SEMANTIC.forget_group(gid)
            return {"group_id": gid, "deleted": count}

        result = await asyncio.to_thread(worker)
        logger.warning(f"[quote] 已清空群 {gid} 的 {result['deleted']} 张语录")
        return json_response(result)

    async def _thumb_warm_loop(self) -> None:
        """启动后延迟预生成缺失缩略图，降低首次打开管理页的等待。"""
        await asyncio.sleep(45)
        while True:
            try:
                result = await asyncio.to_thread(warm_thumbs_sync, 24)
                if result.get("generated"):
                    logger.info(
                        f"[quote] 缩略图预生成：+{result['generated']}，"
                        f"剩余 {result['remaining']}"
                    )
                if not result.get("remaining"):
                    return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(f"[quote] 缩略图预生成失败：{exc}")
            await asyncio.sleep(90)

    async def _avatar_warm_loop(self) -> None:
        """启动后预生成 96px 头像缩略图，避免打开人物/统计弹层时现场缩放。"""
        await asyncio.sleep(20)
        while True:
            try:
                result = await asyncio.to_thread(warm_avatar_thumbs_sync, 160)
                if result.get("generated"):
                    logger.info(f"[quote] 头像缩略图预生成：+{result['generated']}")
                if not result.get("remaining"):
                    return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(f"[quote] 头像缩略图预生成失败：{exc}")
            await asyncio.sleep(30)

    async def _trash_loop(self) -> None:
        """每 6 小时清理一次过期回收站条目。"""
        await asyncio.sleep(600)
        while True:
            try:
                purged = await asyncio.to_thread(self._purge_trash_sync, "")
                if purged:
                    logger.info(f"[quote] 回收站定时清理 {purged} 张过期语录")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(f"[quote] 回收站定时清理失败：{exc}")
            await asyncio.sleep(6 * 3600)

    # ------------------------------------------------------------------ #
    # 自动语义化：默认每 24 小时为尚未语义化的新语录补齐描述与向量
    # ------------------------------------------------------------------ #

    @staticmethod
    def _semantic_schedule() -> dict:
        try:
            raw = quote_db.load_doc("semantic", "schedule")
        except Exception:
            raw = None
        return dict(raw) if isinstance(raw, dict) else {}

    @staticmethod
    def _save_semantic_schedule(schedule: dict) -> None:
        try:
            quote_db.save_doc("semantic", "schedule", schedule)
        except Exception as exc:
            logger.debug(f"[quote] 保存语义化计划失败：{exc}")

    async def _auto_semantic_tick(self) -> None:
        if SEMANTIC_RUNNER.is_running():
            return
        try:
            status = await asyncio.to_thread(semantic_status_sync, self.context)
        except Exception as exc:
            logger.debug(f"[quote] 自动语义化状态检查失败：{exc}")
            return
        if not status.get("ready"):
            logger.debug("[quote] 自动语义化跳过：语义模型未就绪（需要视觉 + 向量模型）")
            return
        pending_map = {
            str(row.get("group_id") or ""): sum(
                int(row.get(key) or 0)
                for key in ("pending", "failed", "vectorless", "stale")
            )
            for row in status.get("groups") or []
        }
        schedule = self._semantic_schedule()
        now = time.time()
        due: list = []
        changed = False
        for gid in group_ids():
            try:
                settings = load_settings(gid)
            except Exception:
                continue
            if not bool(settings.get("auto_semantic", True)):
                continue
            try:
                hours = float(settings.get("auto_semantic_hours", 24) or 24)
            except (TypeError, ValueError):
                hours = 24.0
            hours = max(1.0, min(168.0, hours))
            last = float(schedule.get(gid) or 0)
            if now - last < hours * 3600:
                continue
            if pending_map.get(gid, 0) <= 0:
                schedule[gid] = now
                changed = True
                continue
            due.append(gid)
        if changed:
            self._save_semantic_schedule(schedule)
        if not due:
            return
        try:
            state = SEMANTIC_RUNNER.start(
                self.context,
                due,
                scope="pending",
                caption_provider_id=str(status.get("caption_provider_id") or ""),
                embedding_provider_id=str((status.get("embedding") or {}).get("id") or ""),
            )
        except RuntimeError:
            return
        for gid in due:
            schedule[gid] = now
        self._save_semantic_schedule(schedule)
        logger.info(
            f"[quote] 自动语义化已启动：{len(due)} 个群，共 {state.get('total', 0)} 条"
        )

    async def _auto_semantic_loop(self) -> None:
        await asyncio.sleep(90)
        while True:
            try:
                await self._auto_semantic_tick()
            except Exception as exc:
                logger.debug(f"[quote] 自动语义化任务异常：{exc}")
            await asyncio.sleep(1800)

    # ------------------------------------------------------------------ #
    # 重填全部语录归属：按「俗名 → QQ 当前昵称」刷新 subject 与语义 speaker
    # ------------------------------------------------------------------ #

    @staticmethod
    def _rebind_attributions_sync(group_id: str = "") -> dict:
        targets = [group_id] if group_id else group_ids()
        summaries = IDENTITY.summaries()
        result = {
            "groups": [],
            "scanned": 0,
            "assigned": 0,
            "renamed": 0,
            "missing": 0,
            "skipped": 0,
            "semantic": 0,
        }
        for gid in targets:
            try:
                items = (META.load(gid) or {}).get("items") or {}
            except Exception:
                continue
            if not isinstance(items, dict) or not items:
                continue
            group_stat = {"group_id": gid, "scanned": 0, "assigned": 0, "renamed": 0}
            for name, info in list(items.items()):
                if not isinstance(info, dict):
                    continue
                result["scanned"] += 1
                group_stat["scanned"] += 1
                uid = str(info.get("subject_user_id") or "").strip()
                speaker = str(info.get("subject_name") or "").strip()
                if not uid and speaker:
                    try:
                        alias = IDENTITY.alias_lookup(speaker, gid) or {}
                    except Exception:
                        alias = {}
                    alias_uid = str(alias.get("user_id") or "").strip()
                    if alias_uid and alias_uid in summaries:
                        uid = alias_uid
                        pref = str(
                            (summaries.get(uid) or {}).get("display_name") or speaker
                        )
                        try:
                            META.update(
                                gid,
                                name,
                                {
                                    "subject_user_id": uid,
                                    "subject_name": pref[:80],
                                    "subject_source": "rebind",
                                },
                            )
                        except Exception as exc:
                            logger.debug(f"[quote] 重填归属失败 {gid}/{name}：{exc}")
                            continue
                        result["assigned"] += 1
                        group_stat["assigned"] += 1
                        speaker = pref
                    else:
                        result["skipped"] += 1
                        continue
                if uid:
                    row = summaries.get(uid) or {}
                    pref = str(row.get("display_name") or "").strip()
                    if not pref:
                        result["missing"] += 1
                    elif pref != speaker:
                        try:
                            META.update(gid, name, {"subject_name": pref[:80]})
                            result["renamed"] += 1
                            group_stat["renamed"] += 1
                            speaker = pref
                        except Exception as exc:
                            logger.debug(f"[quote] 重填归属失败 {gid}/{name}：{exc}")
                if not uid or not speaker:
                    continue
                try:
                    if SEMANTIC.set_speaker(
                        gid,
                        name,
                        speaker,
                        person_id=str((summaries.get(uid) or {}).get("person_id") or ""),
                        user_id=uid,
                        flush=False,
                    ):
                        result["semantic"] += 1
                except Exception as exc:
                    logger.debug(f"[quote] 重填语义 speaker 失败 {gid}/{name}：{exc}")
            try:
                SEMANTIC.flush(gid, force=True)
            except Exception:
                pass
            if group_stat["scanned"]:
                result["groups"].append(group_stat)
        return result

    async def api_semantic_auto(self):
        """自动语义化状态：各群开关/周期、上次与下次运行、待处理数量。"""
        schedule = self._semantic_schedule() or {}
        try:
            status = await asyncio.to_thread(semantic_status_sync, self.context)
        except Exception:
            status = {}
        totals = status.get("totals") or {}
        now = time.time()
        groups = []
        for gid in group_ids():
            try:
                settings = load_settings(gid)
            except Exception:
                continue
            hours = float(settings.get("auto_semantic_hours", 24) or 24)
            enabled = bool(settings.get("auto_semantic", True))
            last = float(schedule.get(gid) or 0)
            next_run = (last + hours * 3600) if last else (now + 600)
            groups.append(
                {
                    "group_id": gid,
                    "enabled": enabled,
                    "hours": hours,
                    "last_run": last,
                    "next_run": next_run,
                }
            )
        upcoming = [g["next_run"] for g in groups if g["enabled"]]
        return json_response(
            {
                "enabled": any(g["enabled"] for g in groups),
                "running": bool(SEMANTIC_RUNNER.is_running()),
                "next_run": min(upcoming) if upcoming else 0,
                "ready": bool(status.get("ready")),
                "embedding": status.get("embedding") or {},
                "caption_provider_id": str(status.get("caption_provider_id") or ""),
                "pending": int(totals.get("pending") or 0),
                "total": int(totals.get("total") or 0),
                "done": int(totals.get("done") or 0),
                "groups": groups,
            }
        )

    async def api_quotes_rebind(self):
        body = await request.json(default={}) or {}
        try:
            gid = safe_group_id(body.get("group_id")) if body.get("group_id") else ""
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        try:
            payload = await asyncio.to_thread(self._rebind_attributions_sync, gid)
        except Exception as exc:
            logger.error(f"[quote] 重填语录归属失败：{exc}", exc_info=True)
            return error_response(f"重填归属失败：{exc}", status_code=500)
        logger.info(
            f"[quote] 重填语录归属完成：扫描 {payload['scanned']}，"
            f"新归属 {payload['assigned']}，改名 {payload['renamed']}，"
            f"语义 {payload['semantic']}"
        )
        return json_response(payload)

    async def _alias_learn_loop(self) -> None:
        """每 60 秒检查一次各群是否到了学习俗名的时候（消息量 + 间隔双重节流）。"""
        await asyncio.sleep(150)
        while True:
            try:
                for gid in group_ids():
                    try:
                        settings = await asyncio.to_thread(load_settings, gid)
                    except Exception:
                        continue
                    if not bool(settings.get("alias_learn", True)):
                        continue
                    every = int(settings.get("alias_learn_every", 40) or 40)
                    result = await quote_alias_learn.learn(self.context, gid, every=every)
                    if result.get("added"):
                        logger.info(
                            f"[quote] 俗名学习：群 {gid} 新增 {result['added']} 条待确认候选"
                        )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.debug(f"[quote] 俗名学习任务异常：{exc}")
            await asyncio.sleep(60)

    @staticmethod
    def _purge_trash_sync(group_id: str = "") -> int:
        """按每群「回收站保留天数」清理过期回收站条目。"""
        removed = 0
        groups = [group_id] if group_id else group_ids()
        for gid in groups:
            try:
                days = int(load_settings(gid).get("trash_keep_days", 30) or 30)
            except Exception:
                days = 30
            try:
                rows = quote_db.trash_old(days)
            except Exception:
                continue
            names = [name for row_gid, name in rows if row_gid == gid]
            if not names:
                continue
            trash_dir = group_dir(gid) / ".trash"
            for name in names:
                target = trash_dir / name
                if target.is_file():
                    try:
                        target.unlink()
                    except OSError:
                        pass
            removed += quote_db.trash_delete(gid, names)
        return removed

    async def api_settings(self):
        if request.method.upper() == "GET":
            try:
                gid = safe_group_id(request.query.get("group_id", ""))
            except ValueError as exc:
                return error_response(str(exc), status_code=400)
            settings = await asyncio.to_thread(load_settings, gid)
            return json_response(
                {
                    "group_id": gid,
                    "mode": int(settings.get("mode", 0)),
                    "coldown": int(settings.get("coldown", 10)),
                    "poke_prob": float(settings.get("poke_prob", 0.85)),
                    "remember": bool(settings.get("remember", True)),
                    "recall": bool(settings.get("recall", True)),
                    "auto_recall": bool(settings.get("auto_recall", False)),
                    "auto_tag": bool(settings.get("auto_tag", True)),
                    "trash_keep_days": int(settings.get("trash_keep_days", 30)),
                    "alias_learn": bool(settings.get("alias_learn", True)),
                    "alias_learn_every": int(settings.get("alias_learn_every", 40)),
                    "auto_semantic": bool(settings.get("auto_semantic", True)),
                    "auto_semantic_hours": int(settings.get("auto_semantic_hours", 24)),
                    "auto_rating": bool(settings.get("auto_rating", True)),
                    "allow_restricted": bool(settings.get("allow_restricted", False)),
                    "admins": self.admins,
                }
            )

        body = await request.json(default={}) or {}
        try:
            gid = safe_group_id(body.get("group_id"))
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        current = await asyncio.to_thread(load_settings, gid)
        try:
            merged = normalize_settings(body, current)
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        saved = await asyncio.to_thread(save_settings, gid, merged)
        logger.info(
            f"[quote] 群 {gid} 设置已更新：mode={saved['mode']} "
            f"coldown={saved['coldown']} poke_prob={saved['poke_prob']} "
            f"remember={saved.get('remember', True)} recall={saved.get('recall', True)} "
            f"auto_recall={saved.get('auto_recall', False)} "
            f"auto_tag={saved.get('auto_tag', True)} "
            f"trash_keep_days={saved.get('trash_keep_days', 30)} "
            f"alias_learn={saved.get('alias_learn', True)} "
            f"alias_learn_every={saved.get('alias_learn_every', 40)} "
            f"auto_semantic={saved.get('auto_semantic', True)} "
            f"auto_semantic_hours={saved.get('auto_semantic_hours', 24)} "
            f"auto_rating={saved.get('auto_rating', True)}"
        )
        return json_response(
            {
                "group_id": gid,
                "mode": int(saved["mode"]),
                "coldown": int(saved["coldown"]),
                "poke_prob": float(saved["poke_prob"]),
                "remember": bool(saved.get("remember", True)),
                "recall": bool(saved.get("recall", True)),
                "auto_recall": bool(saved.get("auto_recall", False)),
                "auto_tag": bool(saved.get("auto_tag", True)),
                "trash_keep_days": int(saved.get("trash_keep_days", 30)),
                "alias_learn": bool(saved.get("alias_learn", True)),
                "alias_learn_every": int(saved.get("alias_learn_every", 40)),
                "auto_rating": bool(saved.get("auto_rating", True)),
                "allow_restricted": bool(saved.get("allow_restricted", False)),
            }
        )

    # ------------------------------------------------------------------ #
    # 语义化（V2）
    # ------------------------------------------------------------------ #
    @staticmethod
    def _semantic_params(query) -> dict:
        return {
            "embedding_provider_id": (query.get("embedding_provider_id") or "").strip(),
            "caption_provider_id": (query.get("caption_provider_id") or "").strip(),
        }

    async def api_semantic_status(self):
        query = request.query
        try:
            gid = (query.get("group_id") or "").strip()
            if gid:
                gid = safe_group_id(gid)
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        try:
            status = await asyncio.to_thread(
                semantic_status_sync, self.context, group_id=gid, **self._semantic_params(query)
            )
        except Exception as exc:
            logger.error(f"[quote] 读取语义状态失败：{exc}", exc_info=True)
            return error_response(f"读取语义状态失败：{exc}", status_code=500)
        status["task"] = SEMANTIC_RUNNER.state
        return json_response(status)

    async def api_semantic_run(self):
        body = await request.json(default={}) or {}
        action = str(body.get("action") or "start").strip().lower()
        if action == "cancel":
            SEMANTIC_RUNNER.cancel()
            return json_response({"cancelled": True, "task": SEMANTIC_RUNNER.state})
        try:
            raw_group = str(body.get("group_id") or "").strip()
            targets = [safe_group_id(raw_group)] if raw_group else group_ids()
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        if not targets:
            return error_response("没有可以处理的群", status_code=400)
        scope = str(body.get("scope") or "pending").strip().lower()
        if scope not in {"pending", "failed", "all"}:
            scope = "pending"
        caption_provider_id = resolve_caption_provider_id(
            self.context, str(body.get("caption_provider_id") or "").strip()
        )
        try:
            state = SEMANTIC_RUNNER.start(
                self.context,
                targets,
                scope=scope,
                caption_provider_id=caption_provider_id,
                embedding_provider_id=str(body.get("embedding_provider_id") or "").strip(),
            )
        except RuntimeError as exc:
            return error_response(str(exc), status_code=409)
        return json_response({"started": True, "task": state})

    async def api_semantic_progress(self):
        return json_response({"task": SEMANTIC_RUNNER.state})

    async def api_tag_queue(self):
        if request.method.upper() == "GET":
            state = dict(AUTOTAG.state)
            state["group_id"] = (request.query.get("group_id") or "").strip()
            return json_response(state)
        body = await request.json(default={}) or {}
        action = str(body.get("action") or "status").strip().lower()
        raw_group = str(body.get("group_id") or "").strip()
        gid = ""
        if raw_group:
            try:
                gid = safe_group_id(raw_group)
            except ValueError as exc:
                return error_response(str(exc), status_code=400)
        result: dict = {"action": action}
        if action == "pause":
            AUTOTAG.pause()
        elif action == "resume":
            AUTOTAG.resume()
        elif action == "enqueue":
            result.update(await asyncio.to_thread(AUTOTAG.enqueue_pending, gid))
        elif action == "clear":
            status = str(body.get("status") or "").strip().lower()
            result["cleared"] = await asyncio.to_thread(quote_db.tag_queue_clear, status)
        elif action != "status":
            return error_response(f"未知操作：{action}", status_code=400)
        result["state"] = AUTOTAG.state
        return json_response(result)

    async def api_semantic_reset(self):
        body = await request.json(default={}) or {}
        try:
            gid = safe_group_id(body.get("group_id"))
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        if not body.get("confirm"):
            return error_response("需要确认后才可清空语义索引", status_code=400)

        def worker() -> dict:
            count = len(SEMANTIC.items(gid))
            SEMANTIC.forget_group(gid)
            return {"group_id": gid, "cleared": count}

        result = await asyncio.to_thread(worker)
        logger.warning(f"[quote] 已清空群 {gid} 的 {result['cleared']} 条语义索引")
        return json_response(result)

    async def api_sent(self):
        """已发送语录记忆：GET 状态 / POST 清空。"""
        if request.method.upper() == "GET":
            query = request.query
            try:
                gid = safe_group_id(query.get("group_id")) if query.get("group_id") else ""
            except ValueError as exc:
                return error_response(str(exc), status_code=400)
            counts = await asyncio.to_thread(SENT.counts, gid)
            return json_response(
                {
                    "group_id": gid,
                    "keep": SENT_KEEP,
                    "max_age": SENT_MAX_AGE,
                    "inject_max": SENT_INJECT_MAX,
                    **counts,
                }
            )
        body = await request.json(default={}) or {}
        try:
            gid = safe_group_id(body.get("group_id")) if body.get("group_id") else ""
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        cleared = await asyncio.to_thread(SENT.clear, gid)
        logger.warning(f"[quote] 已清空发送记忆 {cleared} 条（group_id={gid or '全部'}）")
        return json_response({"cleared": cleared, "group_id": gid})

    # ------------------------------------------------------------------ #
    # 人物档案 Web API（V5）
    # ------------------------------------------------------------------ #
    @staticmethod
    def _subject_counts_sync() -> dict:
        """按语录归属（被拍的群友）统计：{user_id: 语录数}。"""
        counts: dict = {}
        for gid in group_ids():
            try:
                items = META.load(gid)["items"]
            except Exception:
                continue
            for info in items.values():
                if not isinstance(info, dict):
                    continue
                uid = str(info.get("subject_user_id") or "").strip()
                if uid:
                    counts[uid] = counts.get(uid, 0) + 1
        return counts

    @staticmethod
    def _person_quote_counts(counts: dict) -> dict:
        """把 QQ 号维度的语录数汇总到 person 维度。"""
        if not counts:
            return {}
        try:
            people = IDENTITY.summaries()
        except Exception:
            return {}
        by_person: dict = {}
        for uid, count in counts.items():
            pid = str((people.get(uid) or {}).get("person_id") or "")
            if pid:
                by_person[pid] = by_person.get(pid, 0) + int(count)
        return by_person

    @staticmethod
    def _person_quotes_sync(user_ids: list) -> list:
        """收集某人物名下所有语录（跨群）。"""
        wanted = {str(uid) for uid in user_ids if str(uid)}
        rows: list = []
        for gid in group_ids():
            try:
                items = META.load(gid)["items"]
            except Exception:
                continue
            for name, info in items.items():
                if not isinstance(info, dict):
                    continue
                uid = str(info.get("subject_user_id") or "")
                if uid not in wanted:
                    continue
                rows.append(
                    {
                        "group_id": gid,
                        "name": name,
                        "ts": info.get("ts") or _ts_from_name(name, 0),
                        "caption": info.get("caption") or "",
                        "subject_name": info.get("subject_name") or "",
                    }
                )
        rows.sort(key=lambda row: -float(row.get("ts") or 0))
        return rows

    @staticmethod
    def _seed_identities_sync() -> dict:
        groups = group_ids()
        user_ids: list = []
        for gid in groups:
            try:
                items = META.load(gid)["items"]
            except Exception:
                continue
            for info in items.values():
                if not isinstance(info, dict):
                    continue
                uid = str(info.get("user_id") or "").strip()
                if not uid:
                    continue
                try:
                    IDENTITY.touch(uid, str(info.get("nickname") or ""), gid)
                except Exception as exc:
                    logger.debug(f"[quote] 身份种子失败 {uid}：{exc}")
                    continue
                if uid not in user_ids:
                    user_ids.append(uid)
        return {"groups": groups, "user_ids": user_ids}

    def _bot_client(self):
        """取 aiocqhttp 客户端（优先用最近一次消息事件里的 bot）。"""
        bot = getattr(self, "_bot", None)
        if bot is not None and hasattr(bot, "call_action"):
            return bot
        try:
            for inst in self.context.platform_manager.get_insts():
                candidate = getattr(inst, "bot", None)
                if candidate is not None and hasattr(candidate, "call_action"):
                    self._bot = candidate
                    return candidate
        except Exception as exc:
            logger.debug(f"[quote] 获取平台实例失败：{exc}")
        return None

    async def _fetch_group_members(self) -> dict:
        """拉取已收录群的成员列表，用于首次补全 / 换名换头像后的兜底识别。"""
        rows: list = []
        titles: list = []
        scanned: dict = {}
        errors: list = []
        bot = self._bot_client()
        if bot is None:
            return {"rows": rows, "titles": titles, "scanned": scanned, "errors": errors}
        for gid in group_ids():
            try:
                members = await bot.call_action(
                    "get_group_member_list", group_id=int(gid)
                )
            except Exception as exc:
                errors.append(f"{gid}: {exc}")
                continue
            if not isinstance(members, list):
                errors.append(f"{gid}: 返回格式异常")
                continue
            count = 0
            for member in members:
                if not isinstance(member, dict):
                    continue
                uid = str(member.get("user_id") or "").strip()
                if not uid:
                    continue
                names = []
                for key in ("card", "nickname"):
                    value = str(member.get(key) or "").strip()
                    if value and value not in names:
                        names.append(value)
                title = str(member.get("title") or "").strip()
                if title and title not in titles:
                    titles.append(title)
                role = str(member.get("role") or "").strip().lower()
                if role in ("owner", "admin"):
                    role_name = "群主" if role == "owner" else "管理员"
                    if role_name not in titles:
                        titles.append(role_name)
                rows.append((uid, names, gid))
                count += 1
            scanned[gid] = count
        blocked = 0
        if titles:
            try:
                blocked = await asyncio.to_thread(
                    IDENTITY.blocked_add_many, titles, "member-title"
                )
            except Exception as exc:
                logger.debug(f"[quote] 记录群头衔失败：{exc}")
        return {
            "rows": rows,
            "titles": titles,
            "blocked": blocked,
            "scanned": scanned,
            "errors": errors,
        }

    async def _sync_identity_avatar(self, user_id: str) -> bool:
        try:
            data = await fetch_avatar_bytes(user_id)
            if not data:
                await asyncio.to_thread(IDENTITY.mark_avatar_checked, user_id)
                return False
            entry = await asyncio.to_thread(IDENTITY.record_avatar, user_id, data)
            return entry is not None
        except Exception as exc:
            logger.debug(f"[quote] 同步头像失败 {user_id}：{exc}")
            return False

    def schedule_avatar_sync(self, user_id: str) -> None:
        """没有头像或档案过期时，在后台拉一次头像（不阻塞消息处理）。"""
        user_id = str(user_id or "").strip()
        if not user_id:
            return
        try:
            if not IDENTITY.needs_avatar(user_id):
                return
            existing = IDENTITY_AVATAR_TASKS.get(user_id)
            if existing is not None and not existing.done():
                return
            task = asyncio.create_task(self._sync_identity_avatar(user_id))
            IDENTITY_AVATAR_TASKS[user_id] = task
            task.add_done_callback(lambda _t: IDENTITY_AVATAR_TASKS.pop(user_id, None))
        except RuntimeError:
            pass
        except Exception as exc:
            logger.debug(f"[quote] 调度头像同步失败 {user_id}：{exc}")

    # ------------------------------------------------------------------ #
    # 语录归属人物（V6）：识别"被拍的人"，而不是投稿人
    # ------------------------------------------------------------------ #
    @staticmethod
    def _pick_subject_match(candidates: list) -> tuple:
        """从昵称候选里挑出足够确定的一个：唯一精确匹配，或唯一高置信候选。"""
        if not candidates:
            return "", "no_match"
        exact = [row for row in candidates if float(row.get("score") or 0) >= 0.999]
        if len(exact) == 1:
            return str(exact[0].get("user_id") or ""), "exact"
        best = float(candidates[0].get("score") or 0)
        if len(candidates) == 1 and best >= SUBJECT_AUTO_SCORE:
            return str(candidates[0].get("user_id") or ""), "only"
        return "", "ambiguous"

    async def _vision_speaker(self, path: Path) -> str:
        """用视觉模型读出截图里的说话人昵称（复用语义化的 caption 流程）。"""
        provider_id = resolve_caption_provider_id(self.context)
        if not provider_id:
            return ""
        try:
            fields = await caption_quote(self.context, provider_id, path)
        except Exception as exc:
            logger.debug(f"[quote] 识别语录说话人失败 {path.name}：{exc}")
            return ""
        speaker = str((fields or {}).get("speaker") or "").strip()
        return speaker[:80]

    async def _auto_subject_for(
        self, gid: str, name: str, allow_vision: bool = True
    ) -> str:
        """给一条语录自动匹配归属人物；返回状态串。"""
        try:
            info = dict(META.get(gid, name) or {})
        except Exception:
            info = {}
        if str(info.get("subject_user_id") or "").strip():
            return "assigned"
        speaker = str(info.get("subject_name") or "").strip()
        source = str(info.get("subject_source") or "").strip()
        if not speaker:
            try:
                semantic = await asyncio.to_thread(SEMANTIC.items, gid)
            except Exception:
                semantic = {}
            entry = (semantic or {}).get(name) or {}
            speaker = str(entry.get("speaker") or "").strip()
            if speaker:
                source = "semantic"
        if not speaker and allow_vision:
            path = group_dir(gid) / name
            if path.is_file():
                speaker = await self._vision_speaker(path)
                if speaker:
                    source = "vision"
        if not speaker:
            return "no_name"
        raw_speaker = speaker
        speaker = clean_speaker_title(speaker) or _clean_speaker_name(speaker)
        if not speaker:
            speaker = raw_speaker
        try:
            raw_blocked = await asyncio.to_thread(IDENTITY.is_blocked, raw_speaker)
            clean_blocked = await asyncio.to_thread(IDENTITY.is_blocked, speaker)
        except Exception:
            raw_blocked = clean_blocked = False
        if raw_blocked or clean_blocked:
            await asyncio.to_thread(
                META.update,
                gid,
                name,
                {
                    "subject_name": "",
                    "subject_raw_name": raw_speaker[:80],
                    "subject_source": "blocked",
                },
            )
            return "blocked"
        alias = await asyncio.to_thread(IDENTITY.alias_lookup, speaker, gid)
        alias_uid = str((alias or {}).get("user_id") or "").strip()
        if alias_uid:
            await asyncio.to_thread(
                META.update,
                gid,
                name,
                {
                    "subject_user_id": alias_uid,
                    "subject_name": speaker[:80],
                    "subject_raw_name": raw_speaker[:80],
                    "subject_source": "alias",
                },
            )
            try:
                summary = await asyncio.to_thread(IDENTITY.summaries)
                row = summary.get(alias_uid) or {}
                await asyncio.to_thread(
                    SEMANTIC.set_speaker,
                    gid,
                    name,
                    str(row.get("display_name") or speaker),
                    person_id=str(row.get("person_id") or ""),
                    user_id=alias_uid,
                )
            except Exception as exc:
                logger.debug(f"[quote] 别名回填语义 speaker 失败 {gid}/{name}：{exc}")
            return "assigned"
        candidates = await asyncio.to_thread(IDENTITY.match_names, speaker, gid, 8)
        uid, reason = self._pick_subject_match(candidates)
        patch = {
            "subject_name": speaker[:80],
            "subject_raw_name": raw_speaker[:80],
            "subject_source": source or "auto",
        }
        if uid:
            patch["subject_user_id"] = uid
        await asyncio.to_thread(META.update, gid, name, patch)
        if uid:
            try:
                matched = next(
                    (row for row in candidates if str(row.get("user_id")) == uid), {}
                )
                canonical = str(matched.get("display_name") or speaker)
                await asyncio.to_thread(
                    SEMANTIC.set_speaker,
                    gid,
                    name,
                    canonical,
                    person_id=str(matched.get("person_id") or ""),
                    user_id=uid,
                )
            except Exception as exc:
                logger.debug(f"[quote] 回填语义 speaker 失败 {gid}/{name}：{exc}")
        return "assigned" if uid else reason

    def schedule_subject_sync(self, gid: str, name: str) -> None:
        """投稿后异步识别归属人物，不阻塞回复。"""
        if not gid or not name or gid in SUBJECT_TASKS:
            return
        try:
            task = asyncio.create_task(self._subject_task(gid, name))
            SUBJECT_TASKS[gid] = task
            task.add_done_callback(lambda _t: SUBJECT_TASKS.pop(gid, None))
        except RuntimeError:
            pass

    async def _subject_task(self, gid: str, name: str) -> None:
        try:
            status = await self._auto_subject_for(gid, name, allow_vision=True)
            if status in ("ambiguous", "no_name"):
                logger.info(f"[quote] 语录 {gid}/{name} 归属未确定：{status}")
        except Exception as exc:
            logger.debug(f"[quote] 语录归属识别失败 {gid}/{name}：{exc}")

    def _latest_name_of(self, user: dict) -> str:
        """取档案里 last_seen 最新的昵称（用于展示）。"""
        best = (0.0, "")
        for item in user.get("names") or []:
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            seen = float(item.get("last_seen") or 0)
            if seen >= best[0]:
                best = (seen, name)
        return best[1]

    def _subject_target_sync(self, user_id: str = "", person_id: str = "") -> dict:
        """校验并返回归属目标：{'user_id','display_name','person_id'}。"""
        if person_id:
            detail = IDENTITY.detail("", str(person_id))
            users = detail.get("users") or []
            if not users:
                raise KeyError(f"人物不存在：{person_id}")
            user = users[0]
            latest = self._latest_name_of(user)
            return {
                "user_id": str(user.get("user_id") or ""),
                "display_name": str(
                    detail.get("display_name") or user.get("display_name") or latest
                ),
                "person_id": str(person_id),
            }
        uid = str(user_id or "").strip()
        if not uid:
            raise ValueError("缺少 user_id 或 person_id")
        detail = IDENTITY.detail(uid, "")
        user = (detail.get("users") or [{}])[0]
        latest = self._latest_name_of(user)
        return {
            "user_id": uid,
            "display_name": str(
                detail.get("display_name") or user.get("display_name") or latest
            ),
            "person_id": str(detail.get("person_id") or ""),
        }

    async def api_quotes_subject(self):
        body = await request.json(default={}) or {}
        try:
            gid = safe_group_id(body.get("group_id"))
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        raw_names = body.get("names") or []
        if isinstance(raw_names, str):
            raw_names = [raw_names]
        try:
            names = [safe_image_name(item) for item in raw_names]
        except (ValueError, TypeError) as exc:
            return error_response(str(exc), status_code=400)
        clear = bool(body.get("clear"))
        if not names:
            return error_response("没有选择要指定归属的语录", status_code=400)
        names = names[:SUBJECT_MAX_FILES]
        if clear:
            target = {"user_id": "", "display_name": "", "person_id": ""}
        else:
            try:
                target = await asyncio.to_thread(
                    self._subject_target_sync,
                    str(body.get("user_id") or "").strip(),
                    str(body.get("person_id") or "").strip(),
                )
            except KeyError as exc:
                return error_response(str(exc), status_code=404)
            except ValueError as exc:
                return error_response(str(exc), status_code=400)
        updated = 0
        for name in names:
            if clear:
                patch = {"subject_user_id": "", "subject_source": ""}
            else:
                patch = {
                    "subject_user_id": target["user_id"],
                    "subject_name": target["display_name"],
                    "subject_source": "manual",
                }
            await asyncio.to_thread(META.update, gid, name, patch)
            if not clear:
                await asyncio.to_thread(
                    SEMANTIC.set_speaker,
                    gid,
                    name,
                    target["display_name"],
                    person_id=target["person_id"],
                    user_id=target["user_id"],
                )
            updated += 1
        logger.info(
            f"[quote] 手动指定归属 {gid}：{updated} 条 → "
            f"{target['display_name'] or '清除'}"
        )
        return json_response(
            {
                "group_id": gid,
                "updated": updated,
                "user_id": target["user_id"],
                "person_id": target["person_id"],
                "display_name": target["display_name"],
            }
        )

    async def api_quotes_restricted(self):
        body = await request.json(default={}) or {}
        try:
            gid = safe_group_id(body.get("group_id"))
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        raw_names = body.get("names") or []
        if isinstance(raw_names, str):
            raw_names = [raw_names]
        try:
            names = [safe_image_name(item) for item in raw_names]
        except (ValueError, TypeError) as exc:
            return error_response(str(exc), status_code=400)
        if not names:
            return error_response("没有选择要标记的语录", status_code=400)
        value = bool(body.get("restricted"))
        reason = "手动标记" if value else "手动取消"
        updated = 0
        for name in names[:200]:
            await asyncio.to_thread(
                META.update,
                gid,
                name,
                {"restricted": value, "rating_source": "manual", "rating_reason": reason},
            )
            updated += 1
        logger.info(f"[quote] 手动标记限制级 {gid}：{updated} 条 → {value}")
        return json_response(
            {"group_id": gid, "updated": updated, "restricted": value}
        )

    async def api_quotes_rating(self):
        raw_group = (request.query.get("group_id") or "").strip()
        gid = ""
        if raw_group:
            try:
                gid = safe_group_id(raw_group)
            except ValueError as exc:
                return error_response(str(exc), status_code=400)
        data = await asyncio.to_thread(quote_rating.stats_sync, gid)
        return json_response(data)

    async def api_quotes_auto_rating(self):
        body = await request.json(default={}) or {}
        raw_group = str(body.get("group_id") or "").strip()
        gid = ""
        if raw_group:
            try:
                gid = safe_group_id(raw_group)
            except ValueError as exc:
                return error_response(str(exc), status_code=400)
        overwrite = bool(body.get("overwrite"))
        data = await asyncio.to_thread(
            quote_rating.apply_auto_rating_sync, gid, overwrite
        )
        return json_response(data)

    async def api_quotes_auto_subject(self):
        body = await request.json(default={}) or {}
        try:
            gid = safe_group_id(body.get("group_id")) if body.get("group_id") else ""
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        try:
            limit = max(1, min(500, int(body.get("limit") or 200)))
        except (TypeError, ValueError):
            limit = 200
        allow_vision = bool(body.get("vision"))
        only_unassigned = body.get("only_unassigned", True) is not False
        targets = [gid] if gid else group_ids()
        counts = {"scanned": 0, "assigned": 0, "ambiguous": 0, "no_name": 0, "skipped": 0}
        for target_gid in targets:
            if counts["scanned"] >= limit:
                break
            try:
                files = await asyncio.to_thread(list_image_files, target_gid)
            except Exception:
                continue
            for item in files:
                if counts["scanned"] >= limit:
                    break
                name = item["name"]
                if only_unassigned:
                    try:
                        info = dict(META.get(target_gid, name) or {})
                    except Exception:
                        info = {}
                    if str(info.get("subject_user_id") or "").strip():
                        counts["skipped"] += 1
                        continue
                counts["scanned"] += 1
                try:
                    status = await self._auto_subject_for(
                        target_gid, name, allow_vision=allow_vision
                    )
                except Exception as exc:
                    logger.debug(f"[quote] 回填归属失败 {target_gid}/{name}：{exc}")
                    status = "error"
                if status == "assigned":
                    counts["assigned"] += 1
                elif status == "ambiguous":
                    counts["ambiguous"] += 1
                elif status == "no_name":
                    counts["no_name"] += 1
        logger.info(f"[quote] 语录归属回填完成：{counts}")
        return json_response({"group_id": gid, **counts})

    @staticmethod
    def _subject_review_sync(group_id: str = "", limit: int = 60) -> dict:
        """待人工确认的归属：按截图中读到的昵称聚合（尚无 QQ 归属的语录）。"""
        targets = [group_id] if group_id else group_ids()
        rows: dict = {}
        for gid in targets:
            try:
                items = META.load(gid)["items"]
            except Exception:
                continue
            for name, info in items.items():
                if not isinstance(info, dict):
                    continue
                if str(info.get("subject_user_id") or "").strip():
                    continue
                speaker = str(info.get("subject_name") or "").strip()
                if not speaker:
                    continue
                row = rows.setdefault(
                    speaker,
                    {"subject_name": speaker, "count": 0, "groups": [], "samples": []},
                )
                row["count"] += 1
                if gid not in row["groups"]:
                    row["groups"].append(gid)
                if len(row["samples"]) < 3:
                    row["samples"].append({"group_id": gid, "name": name})
        ordered = sorted(rows.values(), key=lambda row: -int(row["count"]))
        return {
            "total_names": len(rows),
            "total_quotes": sum(int(row["count"]) for row in rows.values()),
            "items": ordered[: max(1, min(200, int(limit or 60)))],
        }

    @staticmethod
    def _bind_subject_name_sync(subject_name: str, target: dict, group_id: str = "") -> dict:
        """把一个昵称下的所有未归属语录一次性归到目标人物（并记为别名）。"""
        needle = IDENTITY.name_key(subject_name)
        if not needle:
            return {"updated": 0, "groups": []}
        targets = [group_id] if group_id else group_ids()
        updated = 0
        groups: list = []
        for gid in targets:
            try:
                items = dict(META.load(gid)["items"])
            except Exception:
                continue
            touched = 0
            speakers = 0
            for name, info in items.items():
                if not isinstance(info, dict):
                    continue
                if str(info.get("subject_user_id") or "").strip():
                    continue
                if IDENTITY.name_key(str(info.get("subject_name") or "")) != needle:
                    continue
                META.update(
                    gid,
                    name,
                    {
                        "subject_user_id": target["user_id"],
                        "subject_name": subject_name,
                        "subject_source": "manual",
                    },
                )
                if SEMANTIC.set_speaker(
                    gid,
                    name,
                    target["display_name"] or subject_name,
                    person_id=target.get("person_id") or "",
                    user_id=target["user_id"],
                    flush=False,
                ):
                    speakers += 1
                touched += 1
            if touched:
                if speakers:
                    SEMANTIC.flush(gid, force=True)
                updated += touched
                groups.append(
                    {"group_id": gid, "updated": touched, "speakers": speakers}
                )
        return {
            "subject_name": subject_name,
            "updated": updated,
            "groups": groups,
        }

    @staticmethod
    def _identity_clusters_sync(group_id: str = "", limit: int = 40) -> dict:
        """已绑定昵称的形近变体聚类（同一人不同截图被误读），用于一键归并。"""
        targets = [group_id] if group_id else group_ids()
        summaries = IDENTITY.summaries()
        items_out: list = []
        for gid in targets:
            try:
                items = META.load(gid)["items"]
            except Exception:
                continue
            bound: dict = {}
            for name, info in items.items():
                if not isinstance(info, dict):
                    continue
                uid = str(info.get("subject_user_id") or "").strip()
                speaker = str(info.get("subject_name") or "").strip()
                if not uid or not speaker:
                    continue
                by_name = bound.setdefault(uid, {})
                by_name[speaker] = by_name.get(speaker, 0) + 1
            for uid, by_name in bound.items():
                if len(by_name) < 2:
                    continue
                try:
                    detail = IDENTITY.detail(uid, "")
                except KeyError:
                    continue
                user = (detail.get("users") or [{}])[0]
                seen = {
                    str(item.get("name") or ""): float(item.get("first_seen") or 0.0)
                    for item in (user.get("names") or [])
                    if isinstance(item, dict)
                }
                records = [
                    {"name": speaker, "count": count, "first_seen": seen.get(speaker, 0.0)}
                    for speaker, count in by_name.items()
                ]
                aliased = {
                    str(row.get("name") or "") for row in IDENTITY.aliases_for(uid)
                }
                for cluster in IDENTITY.cluster_names(records):
                    if len(cluster["names"]) < 2:
                        continue
                    if not cluster["removable"] and len(cluster["names"]) < 3:
                        continue
                    remaining = [
                        name for name in cluster["names"] if name not in aliased
                    ]
                    if len(remaining) < 2:
                        # 这些写法都已经归并到同一个 QQ 号了，不用再提示
                        continue
                    cluster = dict(cluster)
                    cluster["names"] = remaining
                    cluster["keep"] = remaining[0]
                    items_out.append(
                        {
                            "group_id": gid,
                            "user_id": uid,
                            "person_id": str(user.get("person_id") or ""),
                            "display_name": str(
                                (summaries.get(uid) or {}).get("display_name") or uid
                            ),
                            "quote_count": sum(
                                count
                                for speaker, count in by_name.items()
                                if speaker in cluster["names"]
                            ),
                            **cluster,
                        }
                    )
        items_out.sort(key=lambda item: (-len(item["names"]), -int(item["quote_count"])))
        return {"total": len(items_out), "items": items_out[: max(1, min(120, limit))]}

    @staticmethod
    def _cluster_merge_sync(target: dict, names, group_id: str = "") -> dict:
        """把一组形近昵称变体统一归到目标人物（写别名 + 绑定未归属语录）。"""
        uid = str(target.get("user_id") or "").strip()
        if not uid:
            raise ValueError("目标人物缺少 user_id")
        wanted: list = []
        for name in names or []:
            clean = str(name or "").strip()[:64]
            if clean and clean not in wanted:
                wanted.append(clean)
        if not wanted:
            raise ValueError("没有要合并的昵称")
        IDENTITY.alias_add_many([(name, uid, group_id) for name in wanted], source="merge")
        updated = 0
        for name in wanted:
            result = Quote_Plugin._bind_subject_name_sync(name, target, group_id)
            updated += int(result.get("updated") or 0)
        return {"user_id": uid, "names": wanted, "updated": updated}

    @staticmethod
    def _identity_cleanup_sync(group_id: str = "", dry_run: bool = True) -> dict:
        """旧数据整理：把已绑定的截图昵称迁到别名表，并清理形近的 OCR 变体昵称。"""
        targets = [group_id] if group_id else group_ids()
        bind_rows: list = []
        for gid in targets:
            try:
                items = META.load(gid)["items"]
            except Exception:
                continue
            for name, info in items.items():
                if not isinstance(info, dict):
                    continue
                uid = str(info.get("subject_user_id") or "").strip()
                speaker = str(info.get("subject_name") or "").strip()
                if uid and speaker:
                    bind_rows.append((speaker, uid, gid))
        summaries = IDENTITY.summaries()
        bound_by_uid: dict = {}
        for speaker, uid, _gid in bind_rows:
            bound_by_uid.setdefault(uid, set()).add(speaker)
        plans: list = []
        total_drop = 0
        for uid, speakers in bound_by_uid.items():
            try:
                detail = IDENTITY.detail(uid, "")
            except KeyError:
                continue
            user = (detail.get("users") or [{}])[0]
            history = [
                {
                    "name": str(item.get("name") or ""),
                    "count": int(item.get("count") or 0),
                    "first_seen": float(item.get("first_seen") or 0.0),
                }
                for item in (user.get("names") or [])
                if isinstance(item, dict)
            ]
            drop: list = []
            for cluster in IDENTITY.cluster_names(history):
                if len(cluster["names"]) < IDENTITY_CLUSTER_MIN_SIZE:
                    continue
                for name in cluster["removable"]:
                    if name in speakers and name != cluster["keep"] and name not in drop:
                        drop.append(name)
            if drop:
                total_drop += len(drop)
                plans.append(
                    {
                        "user_id": uid,
                        "display_name": str(
                            (summaries.get(uid) or {}).get("display_name") or ""
                        ),
                        "drop_names": drop,
                    }
                )
        title_plan = IDENTITY.cleanup_titles(dry_run=True)
        title_names = set(title_plan.get("delete") or []) | set(
            title_plan.get("titles") or []
        )
        title_quotes: list = []
        if title_names:
            for gid in targets:
                try:
                    items = META.load(gid)["items"]
                except Exception:
                    continue
                for quote_name, info in items.items():
                    if not isinstance(info, dict):
                        continue
                    uid = str(info.get("subject_user_id") or "").strip()
                    speaker = str(info.get("subject_name") or "").strip()
                    if not uid or not speaker:
                        continue
                    if (
                        speaker in title_names
                        or IDENTITY._looks_like_title(speaker)
                    ):
                        title_quotes.append((gid, quote_name, speaker, uid))
        payload = {
            "group_id": group_id,
            "dry_run": dry_run,
            "title_aliases": int(title_plan.get("counts", {}).get("titles", 0)),
            "title_quotes": len(title_quotes),
            "titles": list(title_plan.get("titles") or [])[:12],
            "unbind_samples": [
                {"group_id": row[0], "name": row[1], "subject_name": row[2]}
                for row in title_quotes[:10]
            ],
            "bound_quotes": len(bind_rows),
            "alias_names": len({row[0] for row in bind_rows}),
            "alias_users": len(bound_by_uid),
            "drop_users": len(plans),
            "drop_names": total_drop,
            "samples": plans[:15],
        }
        if dry_run:
            return payload
        title_applied = IDENTITY.cleanup_titles(dry_run=False)
        drop_set = set(title_plan.get("delete") or []) | set(
            title_plan.get("redundant") or []
        ) | set(title_plan.get("unconfirm") or [])
        unbound = 0
        for gid, quote_name, speaker, _uid in title_quotes:
            try:
                META.update(
                    gid,
                    quote_name,
                    {
                        "subject_user_id": "",
                        "subject_name": "",
                        "subject_raw_name": speaker[:80],
                        "subject_source": "review",
                    },
                )
                unbound += 1
            except Exception:
                continue
        fresh_rows: list = []
        for gid in targets:
            try:
                items = META.load(gid)["items"]
            except Exception:
                continue
            for quote_name, info in items.items():
                if not isinstance(info, dict):
                    continue
                uid = str(info.get("subject_user_id") or "").strip()
                speaker = str(info.get("subject_name") or "").strip()
                if not uid or not speaker:
                    continue
                if speaker in drop_set or IDENTITY._looks_like_title(speaker):
                    continue
                if IDENTITY.is_blocked(speaker):
                    continue
                fresh_rows.append((speaker, uid, gid))
        added = IDENTITY.alias_add_many(fresh_rows, source="migrated") if fresh_rows else 0
        dropped = 0
        for plan in plans:
            dropped += IDENTITY.drop_names(plan["user_id"], plan["drop_names"])
        payload.update(
            {
                "applied": True,
                "aliases_added": added,
                "unbound_kept_raw": unbound,
                "names_dropped": dropped,
                "titles_cleaned": int(title_applied.get("applied") or 0),
                "quotes_unbound": unbound,
            }
        )
        return payload

    async def api_quotes_review(self):
        query = request.query
        try:
            gid = safe_group_id(query.get("group_id")) if query.get("group_id") else ""
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        try:
            limit = max(1, min(200, int(query.get("limit") or 60)))
        except (TypeError, ValueError):
            limit = 60
        try:
            payload = await asyncio.to_thread(self._subject_review_sync, gid, limit)
        except Exception as exc:
            logger.error(f"[quote] 待确认归属读取失败：{exc}", exc_info=True)
            return error_response(f"读取待确认归属失败：{exc}", status_code=500)
        return json_response({"group_id": gid, **payload})

    @staticmethod
    def _backfill_speakers_sync(group_id: str = "") -> dict:
        """把已识别的归属人物反向写回语义索引的 speaker（向量文本不含 speaker，无需重算）。"""
        targets = [group_id] if group_id else group_ids()
        summaries = IDENTITY.summaries()
        updated = 0
        scanned = 0
        skipped = 0
        groups: list = []
        for gid in targets:
            try:
                items = META.load(gid)["items"]
            except Exception:
                continue
            semantic = SEMANTIC.items(gid)
            touched = 0
            for name, info in items.items():
                if not isinstance(info, dict):
                    continue
                uid = str(info.get("subject_user_id") or "").strip()
                if not uid:
                    continue
                entry = semantic.get(name)
                if not isinstance(entry, dict) or entry.get("status") != "done":
                    skipped += 1
                    continue
                scanned += 1
                row = summaries.get(uid) or {}
                speaker = str(row.get("display_name") or "").strip()
                if not speaker:
                    skipped += 1
                    continue
                if SEMANTIC.set_speaker(
                    gid,
                    name,
                    speaker,
                    person_id=str(row.get("person_id") or ""),
                    user_id=uid,
                    flush=False,
                ):
                    touched += 1
            if touched:
                SEMANTIC.flush(gid, force=True)
                updated += touched
                groups.append({"group_id": gid, "updated": touched})
        return {
            "updated": updated,
            "scanned": scanned,
            "skipped": skipped,
            "groups": groups,
        }

    async def api_semantic_backfill_speaker(self):
        body = await request.json(default={}) or {}
        try:
            gid = safe_group_id(body.get("group_id")) if body.get("group_id") else ""
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        try:
            payload = await asyncio.to_thread(self._backfill_speakers_sync, gid)
        except Exception as exc:
            logger.error(f"[quote] 人物档案回填语义 speaker 失败：{exc}", exc_info=True)
            return error_response(f"回填语义 speaker 失败：{exc}", status_code=500)
        if payload.get("updated"):
            logger.info(
                f"[quote] 人物档案回填语义 speaker：{payload['updated']} 条"
            )
        return json_response(payload)

    async def api_quotes_bind_name(self):
        body = await request.json(default={}) or {}
        subject_name = str(body.get("subject_name") or "").strip()
        if not subject_name:
            return error_response("缺少 subject_name", status_code=400)
        try:
            gid = safe_group_id(body.get("group_id")) if body.get("group_id") else ""
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        try:
            target = await asyncio.to_thread(
                self._subject_target_sync,
                str(body.get("user_id") or "").strip(),
                str(body.get("person_id") or "").strip(),
            )
        except KeyError as exc:
            return error_response(str(exc), status_code=404)
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        try:
            result = await asyncio.to_thread(
                self._bind_subject_name_sync, subject_name, target, gid
            )
        except Exception as exc:
            logger.error(f"[quote] 绑定昵称归属失败：{exc}", exc_info=True)
            return error_response(f"绑定归属失败：{exc}", status_code=500)
        try:
            await asyncio.to_thread(
                IDENTITY.alias_add,
                subject_name,
                target["user_id"],
                gid or "",
                "manual",
            )
        except Exception as exc:
            logger.debug(f"[quote] 记录昵称别名失败：{exc}")
        logger.info(
            f"[quote] 昵称「{subject_name}」→ {target['display_name']}"
            f"（QQ {target['user_id']}）：更新 {result.get('updated', 0)} 条"
        )
        return json_response(
            {
                "subject_name": subject_name,
                "user_id": target["user_id"],
                "person_id": target["person_id"],
                "display_name": target["display_name"],
                **result,
            }
        )

    async def api_identity_match_names(self):
        query = request.query
        name = (query.get("name") or "").strip()
        if not name:
            return error_response("缺少 name", status_code=400)
        try:
            gid = safe_group_id(query.get("group_id")) if query.get("group_id") else ""
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        try:
            limit = max(1, min(32, int(query.get("limit") or 8)))
        except (TypeError, ValueError):
            limit = 8
        try:
            rows = await asyncio.to_thread(IDENTITY.match_names, name, gid, limit)
        except Exception as exc:
            logger.error(f"[quote] 昵称匹配失败：{exc}", exc_info=True)
            return error_response(f"昵称匹配失败：{exc}", status_code=500)
        return json_response({"name": name, "group_id": gid, "items": rows})

    async def api_identity_clusters(self):
        query = request.query
        try:
            gid = safe_group_id(query.get("group_id")) if query.get("group_id") else ""
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        try:
            limit = max(1, min(120, int(query.get("limit") or 40)))
        except (TypeError, ValueError):
            limit = 40
        try:
            payload = await asyncio.to_thread(self._identity_clusters_sync, gid, limit)
        except Exception as exc:
            logger.error(f"[quote] 昵称变体聚类失败：{exc}", exc_info=True)
            return error_response(f"昵称变体聚类失败：{exc}", status_code=500)
        return json_response({"group_id": gid, **payload})

    async def api_identity_cluster_merge(self):
        body = await request.json(default={}) or {}
        raw_names = body.get("names") or []
        if isinstance(raw_names, str):
            raw_names = [raw_names]
        names = []
        for item in raw_names:
            clean = str(item or "").strip()[:64]
            if clean and clean not in names:
                names.append(clean)
        if not names:
            return error_response("缺少 names", status_code=400)
        try:
            gid = safe_group_id(body.get("group_id")) if body.get("group_id") else ""
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        try:
            target = await asyncio.to_thread(
                self._subject_target_sync,
                str(body.get("user_id") or "").strip(),
                str(body.get("person_id") or "").strip(),
            )
        except KeyError as exc:
            return error_response(str(exc), status_code=404)
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        try:
            result = await asyncio.to_thread(
                self._cluster_merge_sync, target, names, gid
            )
        except Exception as exc:
            logger.error(f"[quote] 合并昵称变体失败：{exc}", exc_info=True)
            return error_response(f"合并昵称变体失败：{exc}", status_code=500)
        logger.info(
            f"[quote] 昵称变体归并：{names} → {target['display_name']}"
            f"（更新 {result.get('updated', 0)} 条）"
        )
        return json_response(
            {
                "subject_names": names,
                "display_name": target["display_name"],
                "user_id": target["user_id"],
                "person_id": target["person_id"],
                **result,
            }
        )

    async def api_identity_cleanup(self):
        body = await request.json(default={}) or {}
        dry_run = body.get("dry_run", True) is not False
        try:
            gid = safe_group_id(body.get("group_id")) if body.get("group_id") else ""
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        try:
            payload = await asyncio.to_thread(self._identity_cleanup_sync, gid, dry_run)
        except Exception as exc:
            logger.error(f"[quote] 整理旧别名失败：{exc}", exc_info=True)
            return error_response(f"整理旧别名失败：{exc}", status_code=500)
        if not dry_run:
            logger.info(
                f"[quote] 旧别名整理完成：别名 {payload.get('aliases_added', 0)} 条，"
                f"清理昵称 {payload.get('names_dropped', 0)} 个"
            )
        return json_response(payload)

    async def api_identity_aliases(self):
        query = request.query
        user_id = (query.get("user_id") or "").strip()
        try:
            rows = await asyncio.to_thread(IDENTITY.aliases_for, user_id)
        except Exception as exc:
            logger.error(f"[quote] 读取昵称别名失败：{exc}", exc_info=True)
            return error_response(f"读取昵称别名失败：{exc}", status_code=500)
        return json_response({"user_id": user_id, "items": rows})

    async def api_identity_alias_delete(self):
        body = await request.json(default={}) or {}
        name = str(body.get("name") or "").strip()
        if not name:
            return error_response("缺少 name", status_code=400)
        try:
            removed = await asyncio.to_thread(IDENTITY.alias_delete, name)
        except Exception as exc:
            logger.error(f"[quote] 删除昵称别名失败：{exc}", exc_info=True)
            return error_response(f"删除昵称别名失败：{exc}", status_code=500)
        return json_response({"name": name, "removed": bool(removed)})

    async def api_alias_candidates(self):
        query = request.query
        try:
            gid = safe_group_id(query.get("group_id")) if query.get("group_id") else ""
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        status = str(query.get("status") or "pending").strip() or "pending"
        try:
            limit = int(query.get("limit", 200, type=int) or 200)
        except (TypeError, ValueError):
            limit = 200
        try:
            rows = await asyncio.to_thread(
                IDENTITY.alias_candidates, gid, status, max(1, min(500, limit))
            )
            total = await asyncio.to_thread(IDENTITY.alias_candidate_count, gid, status)
        except Exception as exc:
            logger.error(f"[quote] 读取俗名候选失败：{exc}", exc_info=True)
            return error_response(f"读取俗名候选失败：{exc}", status_code=500)
        return json_response({"group_id": gid, "status": status, "total": total, "items": rows})

    async def api_alias_candidate_confirm(self):
        body = await request.json(default={}) or {}
        try:
            cid = int(body.get("id") or 0)
        except (TypeError, ValueError):
            cid = 0
        if not cid:
            return error_response("缺少 id", status_code=400)
        try:
            entry = await asyncio.to_thread(IDENTITY.alias_candidate_confirm, cid)
        except Exception as exc:
            logger.error(f"[quote] 确认俗名候选失败：{exc}", exc_info=True)
            return error_response(f"确认俗名候选失败：{exc}", status_code=500)
        if not entry:
            return error_response("候选不存在或已处理", status_code=404)
        logger.info(f"[quote] 已确认俗名：{entry.get('name')} → {entry.get('user_id')}")
        return json_response({"id": cid, "status": "confirmed", "alias": entry})

    async def api_alias_candidate_reject(self):
        body = await request.json(default={}) or {}
        try:
            cid = int(body.get("id") or 0)
        except (TypeError, ValueError):
            cid = 0
        if not cid:
            return error_response("缺少 id", status_code=400)
        try:
            ok = await asyncio.to_thread(IDENTITY.alias_candidate_reject, cid)
        except Exception as exc:
            logger.error(f"[quote] 忽略俗名候选失败：{exc}", exc_info=True)
            return error_response(f"忽略俗名候选失败：{exc}", status_code=500)
        if not ok:
            return error_response("候选不存在或已处理", status_code=404)
        return json_response({"id": cid, "status": "rejected"})

    async def api_alias_learn(self):
        body = await request.json(default={}) or {}
        try:
            gid = safe_group_id(body.get("group_id"))
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        try:
            result = await quote_alias_learn.learn(self.context, gid, force=True)
        except Exception as exc:
            logger.error(f"[quote] 俗名学习失败：{exc}", exc_info=True)
            return error_response(f"俗名学习失败：{exc}", status_code=500)
        return json_response(result)

    async def api_identity_overview(self):
        try:
            payload = await asyncio.to_thread(IDENTITY.overview)
            counts = await asyncio.to_thread(self._subject_counts_sync)
            payload["quote_users"] = len(counts)
            payload["assigned_quotes"] = sum(counts.values())
        except Exception as exc:
            logger.error(f"[quote] identity overview 失败：{exc}", exc_info=True)
            return error_response(f"读取人物档案失败：{exc}", status_code=500)
        return json_response(payload)

    async def api_identity_list(self):
        query = request.query
        keyword = (query.get("q") or "").strip()
        try:
            gid = safe_group_id(query.get("group_id")) if query.get("group_id") else ""
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        try:
            page = int(query.get("page", 1, type=int) or 1)
            page_size = int(query.get("page_size", 48, type=int) or 48)
        except (TypeError, ValueError):
            page, page_size = 1, 48
        try:
            payload = await asyncio.to_thread(
                IDENTITY.list_people, keyword, gid, page, page_size
            )
            counts = await asyncio.to_thread(self._subject_counts_sync)
            by_person = await asyncio.to_thread(self._person_quote_counts, counts)
        except Exception as exc:
            logger.error(f"[quote] identity list 失败：{exc}", exc_info=True)
            return error_response(f"读取人物列表失败：{exc}", status_code=500)
        for item in payload["items"]:
            pid = str(item.get("person_id") or "")
            item["quote_count"] = int(by_person.get(pid, 0))
        return json_response(payload)

    async def api_identity_detail(self):
        query = request.query
        user_id = (query.get("user_id") or "").strip()
        person_id = (query.get("person_id") or "").strip()
        if not user_id and not person_id:
            return error_response("缺少 user_id 或 person_id", status_code=400)
        try:
            payload = await asyncio.to_thread(IDENTITY.detail, user_id, person_id)
            counts = await asyncio.to_thread(self._subject_counts_sync)
        except KeyError as exc:
            return error_response(str(exc), status_code=404)
        except Exception as exc:
            logger.error(f"[quote] identity detail 失败：{exc}", exc_info=True)
            return error_response(f"读取人物详情失败：{exc}", status_code=500)
        user_ids = [str(user.get("user_id") or "") for user in payload.get("users", [])]
        total = 0
        for user in payload.get("users", []):
            user["quote_count"] = counts.get(str(user.get("user_id")), 0)
            total += user["quote_count"]
        payload["quote_count"] = total
        try:
            payload["quotes"] = await asyncio.to_thread(
                self._person_quotes_sync, user_ids
            )
        except Exception as exc:
            logger.debug(f"[quote] 读取人物语录失败：{exc}")
        return json_response(payload)

    async def api_identity_avatars(self):
        body = await request.json(default={}) or {}
        raw = body.get("shas") or []
        if not isinstance(raw, list):
            return error_response("shas 必须是数组", status_code=400)
        shas = []
        for item in raw[:80]:
            sha = str(item or "").strip().lower()
            if re.fullmatch(r"[0-9a-f]{16}", sha) and sha not in shas:
                shas.append(sha)
        items = {}
        for sha in shas:
            data_url = await asyncio.to_thread(IDENTITY.avatar_data_url, sha)
            if data_url:
                items[sha] = data_url
        return json_response(
            {"items": items, "missing": [sha for sha in shas if sha not in items]}
        )

    async def api_identity_match(self):
        body = await request.json(default={}) or {}
        sha = str(body.get("sha") or "").strip().lower()
        image = str(body.get("image") or "")
        threshold = body.get("threshold")
        try:
            limit = int(threshold) if threshold is not None else IDENTITY_MATCH_THRESHOLD
        except (TypeError, ValueError):
            limit = IDENTITY_MATCH_THRESHOLD
        digest = ""
        if image.startswith("data:"):
            try:
                _, _, encoded = image.partition(",")
                raw = base64.b64decode(encoded or "")
            except Exception:
                return error_response("图片数据无法解析", status_code=400)
            normalized = await asyncio.to_thread(normalize_avatar, raw)
            if normalized is None:
                return error_response("无法识别的图片", status_code=400)
            digest = normalized[1]
        if sha:
            candidates = await asyncio.to_thread(IDENTITY.match_exact, sha)
        elif digest:
            candidates = await asyncio.to_thread(IDENTITY.match_hash, digest, limit)
        else:
            return error_response("请提供 sha 或图片 data URL", status_code=400)
        return json_response(
            {
                "threshold": limit,
                "hash": digest,
                "candidates": candidates[:30],
            }
        )

    async def api_identity_sync(self):
        body = await request.json(default={}) or {}
        force = bool(body.get("force"))
        try:
            limit = max(1, min(200, int(body.get("limit") or IDENTITY_SYNC_LIMIT)))
        except (TypeError, ValueError):
            limit = IDENTITY_SYNC_LIMIT
        try:
            seeded = await asyncio.to_thread(self._seed_identities_sync)
        except Exception as exc:
            logger.error(f"[quote] identity sync 种子失败：{exc}", exc_info=True)
            return error_response(f"同步身份失败：{exc}", status_code=500)
        member_rows: list = []
        member_scanned: dict = {}
        member_errors: list = []
        member_titles: list = []
        member_blocked = 0
        new_members = 0
        if bool(body.get("members", True)):
            try:
                members = await self._fetch_group_members()
                member_rows = members["rows"]
                member_scanned = members["scanned"]
                member_errors = members["errors"]
                member_titles = members.get("titles") or []
                member_blocked = int(members.get("blocked") or 0)
                if member_rows:
                    new_members = await asyncio.to_thread(
                        IDENTITY.touch_many, member_rows
                    )
            except Exception as exc:
                logger.warning(f"[quote] 拉取群成员列表失败：{exc}")
        user_ids = list(seeded["user_ids"])
        seen_ids = set(user_ids)
        for uid, _names, _gid in member_rows:
            if uid not in seen_ids:
                seen_ids.add(uid)
                user_ids.append(uid)
        targets = []
        for uid in user_ids:
            if force or IDENTITY.needs_avatar(uid):
                targets.append(uid)
        pending = targets[limit:]
        targets = targets[:limit]
        synced = 0
        for start in range(0, len(targets), 4):
            chunk = targets[start: start + 4]
            results = await asyncio.gather(
                *[self._sync_identity_avatar(uid) for uid in chunk],
                return_exceptions=True,
            )
            synced += sum(1 for item in results if item is True)
        overview = await asyncio.to_thread(IDENTITY.overview)
        member_total = sum(member_scanned.values())
        logger.info(
            f"[quote] 身份同步完成：种子 {len(seeded['user_ids'])} 个 QQ，"
            f"群成员 {member_total} 人（新增 {new_members}），"
            f"拉取头像 {synced}/{len(targets)}，待同步 {len(pending)}"
        )
        return json_response(
            {
                "seed_users": len(seeded["user_ids"]),
                "seed_groups": len(seeded["groups"]),
                "member_users": member_total,
                "member_groups": len(member_scanned),
                "member_errors": len(member_errors),
                "member_titles": len(member_titles),
                "titles_blocked": member_blocked,
                "new_users": new_members,
                "tried": len(targets),
                "synced": synced,
                "remaining": len(pending),
                **overview,
            }
        )

    async def _auto_identity_sync_once(self) -> dict:
        """执行一次自动身份同步：群成员 / 昵称 / 头像。"""
        try:
            seeded = await asyncio.to_thread(self._seed_identities_sync)
        except Exception as exc:
            logger.warning(f"[quote] 定时身份同步：种子失败 {exc}")
            return {"ok": False, "error": str(exc)}
        member_rows: list = []
        member_scanned: dict = {}
        member_titles: list = []
        titles_blocked = 0
        new_members = 0
        try:
            members = await self._fetch_group_members()
            member_rows = members["rows"]
            member_scanned = members["scanned"]
            member_titles = members.get("titles") or []
            titles_blocked = int(members.get("blocked") or 0)
            if member_rows:
                new_members = await asyncio.to_thread(IDENTITY.touch_many, member_rows)
        except Exception as exc:
            logger.warning(f"[quote] 定时身份同步：拉取群成员失败 {exc}")
        user_ids = list(seeded["user_ids"])
        seen_ids = set(user_ids)
        for uid, _names, _gid in member_rows:
            if uid not in seen_ids:
                seen_ids.add(uid)
                user_ids.append(uid)
        targets = [uid for uid in user_ids if IDENTITY.needs_avatar(uid)]
        pending = targets[IDENTITY_AUTO_SYNC_AVATARS:]
        targets = targets[:IDENTITY_AUTO_SYNC_AVATARS]
        synced = 0
        for start in range(0, len(targets), 4):
            chunk = targets[start: start + 4]
            results = await asyncio.gather(
                *[self._sync_identity_avatar(uid) for uid in chunk],
                return_exceptions=True,
            )
            synced += sum(1 for item in results if item is True)
        member_total = sum(member_scanned.values())
        logger.info(
            f"[quote] 定时身份同步完成：群成员 {member_total} 人（新增 {new_members}），"
            f"拉取头像 {synced}/{len(targets)}，待同步 {len(pending)}"
        )
        return {
            "ok": True,
            "member_users": member_total,
            "new_users": new_members,
            "member_titles": len(member_titles),
            "titles_blocked": titles_blocked,
            "tried": len(targets),
            "synced": synced,
            "remaining": len(pending),
        }

    async def _identity_sync_loop(self):
        try:
            while True:
                try:
                    settings = await asyncio.to_thread(load_identity_sync_settings)
                    interval = float(settings["interval_hours"]) * 3600.0
                    now = time.time()
                    if settings["enabled"] and now - float(settings["last_sync_at"] or 0.0) >= interval:
                        logger.info(
                            f"[quote] 开始定时身份同步（每 {settings['interval_hours']:g} 小时）"
                        )
                        result = await self._auto_identity_sync_once()
                        settings["last_sync_at"] = time.time()
                        settings["last_result"] = {"at": settings["last_sync_at"], **result}
                        settings["updated_at"] = settings["last_sync_at"]
                        await asyncio.to_thread(save_identity_sync_settings, settings)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.warning(f"[quote] 定时身份同步失败：{exc}")
                await asyncio.sleep(IDENTITY_AUTO_SYNC_TICK)
        except asyncio.CancelledError:
            logger.info("[quote] 身份自动同步任务已停止")

    async def api_identity_schedule(self):
        """身份自动同步：GET 读取 / POST 修改周期。"""
        settings = await asyncio.to_thread(load_identity_sync_settings)
        if request.method.upper() != "GET":
            body = await request.json(default={}) or {}
            if "enabled" in body:
                settings["enabled"] = bool(body.get("enabled"))
            if "interval_hours" in body:
                try:
                    value = float(body.get("interval_hours"))
                except (TypeError, ValueError):
                    return error_response("interval_hours 必须是数字", status_code=400)
                settings["interval_hours"] = min(
                    IDENTITY_AUTO_SYNC_MAX_HOURS, max(IDENTITY_AUTO_SYNC_MIN_HOURS, value)
                )
            settings["updated_at"] = time.time()
            settings = await asyncio.to_thread(save_identity_sync_settings, settings)
            logger.info(
                f"[quote] 自动身份同步设置已更新：enabled={settings['enabled']} "
                f"interval={settings['interval_hours']:g}h"
            )
        interval = float(settings["interval_hours"]) * 3600.0
        next_sync_at = 0.0
        if settings["enabled"]:
            next_sync_at = float(settings["last_sync_at"] or 0.0) + interval
            if next_sync_at < time.time():
                next_sync_at = time.time()
        return json_response({**settings, "next_sync_at": next_sync_at})

    async def api_announce(self):
        """更新推送：GET 读取配置与文案预览 / POST 保存或测试推送。"""
        settings = await asyncio.to_thread(load_update_announce)
        if request.method.upper() != "GET":
            body = await request.json(default={}) or {}
            if "enabled" in body:
                settings["enabled"] = bool(body.get("enabled"))
            if "groups" in body:
                settings["groups"] = body.get("groups") or []
            if "bridge_url" in body:
                settings["bridge_url"] = str(body.get("bridge_url") or "")
            if "bridge_token" in body:
                settings["bridge_token"] = str(body.get("bridge_token") or "")
            settings = await asyncio.to_thread(save_update_announce, settings)
            if body.get("test"):
                result = await self._announce_update_once(force=True)
                return json_response({"settings": settings, "result": result})
            return json_response({"settings": settings})
        notes = await asyncio.to_thread(release_notes_sync, PLUGIN_VERSION)
        return json_response(
            {
                "settings": settings,
                "version": PLUGIN_VERSION,
                "preview": build_announce_text(PLUGIN_VERSION, notes),
            }
        )

    async def _announce_update_startup(self):
        """启动后推送更新日志：等 QQ 适配器连上再试，失败按退避重试。"""
        try:
            settings = await asyncio.to_thread(load_update_announce)
            if not settings["enabled"] or settings["last_version"] == PLUGIN_VERSION:
                return
            if await asyncio.to_thread(is_ui_only_release, PLUGIN_VERSION):
                settings["last_version"] = PLUGIN_VERSION
                settings["last_announced_at"] = time.time()
                settings["last_result"] = {
                    "at": time.time(),
                    "version": PLUGIN_VERSION,
                    "skipped": "ui-only",
                    "results": [],
                }
                await asyncio.to_thread(save_update_announce, settings)
                logger.info(
                    f"[quote] v{PLUGIN_VERSION} 为界面调整，跳过群推送"
                )
                return
            delays = [UPDATE_ANNOUNCE_DELAY, 20.0, 30.0, 45.0]
            for attempt, delay in enumerate(delays, start=1):
                await asyncio.sleep(delay)
                result = await self._announce_update_once()
                if result.get("ok") or result.get("skipped"):
                    return
                logger.info(f"[quote] 更新推送第 {attempt} 次未成功，稍后重试")
            logger.warning("[quote] 更新推送多次未成功，本次跳过；下次启动仍会重试")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(f"[quote] 更新推送失败：{exc}")

    async def _announce_update_once(self, force: bool = False) -> dict:
        settings = await asyncio.to_thread(load_update_announce)
        if not settings["enabled"]:
            return {"ok": False, "skipped": "disabled"}
        if not force and settings["last_version"] == PLUGIN_VERSION:
            return {"ok": True, "skipped": "already", "version": PLUGIN_VERSION}
        notes = await asyncio.to_thread(release_notes_sync, PLUGIN_VERSION)
        text = build_announce_text(PLUGIN_VERSION, notes)
        token = str(settings["bridge_token"] or "").strip()
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-DSH-Token"] = token
        results = []
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=20)
            ) as session:
                for group in settings["groups"]:
                    umo = group.get("umo") or f"default:GroupMessage:{group.get('group_id')}"
                    item = {"umo": umo, "group_id": group.get("group_id") or "", "ok": False}
                    try:
                        async with session.post(
                            settings["bridge_url"],
                            json={"session": umo, "text": text},
                            headers=headers,
                        ) as resp:
                            payload = await resp.json(content_type=None)
                            item["status"] = resp.status
                            item["ok"] = bool(
                                isinstance(payload, dict) and payload.get("sent")
                            )
                    except Exception as exc:
                        item["error"] = str(exc)
                    results.append(item)
        except Exception as exc:
            logger.warning(f"[quote] 更新推送失败：{exc}")
            return {"ok": False, "error": str(exc), "version": PLUGIN_VERSION}
        now = time.time()
        if any(item["ok"] for item in results):
            settings["last_version"] = PLUGIN_VERSION
            settings["last_announced_at"] = now
            settings["last_context"] = {
                "at": now,
                "version": PLUGIN_VERSION,
                "groups": [
                    str(item.get("group_id"))
                    for item in results
                    if item.get("ok") and item.get("group_id")
                ],
                "summary": announce_notes_summary(notes),
            }
        settings["last_result"] = {"at": now, "version": PLUGIN_VERSION, "results": results}
        await asyncio.to_thread(save_update_announce, settings)
        logger.info(
            f"[quote] 更新推送 v{PLUGIN_VERSION}："
            f"{sum(1 for item in results if item['ok'])}/{len(results)} 个群成功"
        )
        return {
            "ok": any(item["ok"] for item in results),
            "version": PLUGIN_VERSION,
            "results": results,
            "text": text,
        }

    async def api_identity_merge(self):
        body = await request.json(default={}) or {}
        user_ids = body.get("user_ids") or body.get("pids") or []
        if not isinstance(user_ids, list):
            return error_response("user_ids/pids 必须是数组", status_code=400)
        try:
            person = await asyncio.to_thread(IDENTITY.merge, user_ids)
        except Exception as exc:
            logger.error(f"[quote] identity merge 失败：{exc}", exc_info=True)
            return error_response(f"合并失败：{exc}", status_code=500)
        if not person:
            return error_response("至少需要两个已档案的 QQ 号", status_code=400)
        logger.info(f"[quote] 合并人物 {person['person_id']} ← {person['user_ids']}")
        return json_response({"person": person})

    async def api_identity_split(self):
        body = await request.json(default={}) or {}
        user_id = str(body.get("user_id") or "").strip()
        person_id = str(body.get("person_id") or "").strip()
        try:
            if user_id:
                result = await asyncio.to_thread(IDENTITY.split_user, user_id)
            elif person_id:
                result = await asyncio.to_thread(IDENTITY.split_person, person_id)
            else:
                return error_response("缺少 user_id 或 person_id", status_code=400)
        except Exception as exc:
            logger.error(f"[quote] identity split 失败：{exc}", exc_info=True)
            return error_response(f"拆分失败：{exc}", status_code=500)
        if not result:
            return error_response("没有可拆分的档案", status_code=404)
        return json_response(result)

    async def api_identity_reset(self):
        body = await request.json(default={}) or {}
        if not body.get("confirm"):
            return error_response("需要 confirm=true 才能清空人物档案", status_code=400)
        try:
            removed = await asyncio.to_thread(IDENTITY.reset)
        except Exception as exc:
            logger.error(f"[quote] identity reset 失败：{exc}", exc_info=True)
            return error_response(f"清空失败：{exc}", status_code=500)
        logger.warning(f"[quote] 已清空人物档案（{removed} 个 QQ）")
        return json_response({"removed": removed})

    # ------------------------------------------------------------------ #
    # 指令兼容层
    # ------------------------------------------------------------------ #
    def create_main_folder(self):
        data_root().mkdir(parents=True, exist_ok=True)

    def create_group_folder(self, group_id):
        (group_dir(str(group_id))).mkdir(parents=True, exist_ok=True)

    def random_image_from_folder(self, folder_path):
        if not os.path.exists(folder_path):
            return None
        files = os.listdir(folder_path)
        images = [
            file
            for file in files
            if os.path.splitext(file)[1].lower() in IMAGE_EXTS
            and os.path.isfile(os.path.join(folder_path, file))
        ]
        if not images:
            return None
        return os.path.join(folder_path, random.choice(images))

    def is_admin(self, user_id):
        return str(user_id) in self.admins

    def gain_mode(self, event):
        value = None
        msg = event.message_str.strip()
        if msg:
            match = re.search(r"[-+]?\d*\.?\d+", msg)
            if match:
                value = match.group()
        return value

    # ------------------------------------------------------------------ #
    # 投稿
    # ------------------------------------------------------------------ #
    async def download_image(self, event: AstrMessageEvent, file_id: str, group_id) -> str:
        try:
            assert isinstance(event, AiocqhttpMessageEvent)
            client = event.bot

            payloads = {"file_id": file_id}
            download_by_api_failed = 0
            download_by_file_failed = 0

            message_obj = event.message_obj
            image_obj = None
            for component in message_obj.message:
                if isinstance(component, Image):
                    image_obj = component
                    break

            if image_obj:
                file_path = await image_obj.convert_to_file_path()
                if file_path:
                    logger.info(f"尝试从本地缓存{file_path}读取图片")
                    try:
                        with open(file_path, "rb") as handle:
                            data = handle.read()
                        return self._persist(data, group_id)
                    except Exception as exc:
                        download_by_file_failed = 1
                        logger.error(f"在读取本地缓存时遇到问题: {exc}")
                else:
                    download_by_file_failed = 1
            else:
                download_by_file_failed = 1

            result = {}
            if download_by_file_failed == 1:
                result = await client.api.call_action("get_image", **payloads)
                file_path = result.get("file")
                if file_path and os.path.exists(file_path):
                    logger.info(f"尝试从协议端api返回的路径{file_path}读取图片")
                    try:
                        with open(file_path, "rb") as handle:
                            data = handle.read()
                        return self._persist(data, group_id)
                    except Exception as exc:
                        download_by_api_failed = 1
                        logger.error(f"在通过api下载图片时遇到问题: {exc}")
                else:
                    download_by_api_failed = 1

            if download_by_api_failed == 1 and download_by_file_failed == 1:
                url = result.get("url")
                if url:
                    logger.info(f"尝试从URL下载图片: {url}")
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(url) as response:
                                if response.status == 200:
                                    return self._persist(await response.read(), group_id)
                                logger.error(f"从URL下载图片失败: HTTP {response.status}")
                    except Exception as exc:
                        logger.error(f"从URL下载出错: {exc}")
                else:
                    logger.error("API返回结果中没有URL，无法下载")
        except Exception as exc:
            raise Exception(f"{exc}")

    def _persist(self, data: bytes, group_id) -> str:
        gid = str(group_id)
        directory = group_dir(gid)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"image_{int(time.time() * 1000)}.jpg"
        target.write_bytes(data)
        logger.info(f"图片已保存到 {target}")
        try:
            SEMANTIC.mark_pending(gid, [target.name])
        except Exception as exc:
            logger.warning(f"[quote] 标记语义待处理失败：{exc}")
        return str(target)

    # ------------------------------------------------------------------ #
    # LLM 请求钩子：把刚发过的语录写进上下文（V3）
    # ------------------------------------------------------------------ #
    @filter.on_llm_request()
    async def on_llm_request(self, event: AstrMessageEvent, req) -> None:
        try:
            try:
                group_id = str(event.get_group_id() or "")
            except Exception:
                group_id = ""
            remember = True
            if group_id:
                settings = await asyncio.to_thread(load_settings, group_id)
                remember = bool(settings.get("remember", True))
            injected = await inject_sent_memory(
                req, str(getattr(event, "unified_msg_origin", "") or ""), remember
            )
            if injected:
                logger.info(
                    f"[quote] 已向 LLM 上下文注入 {injected} 条发送记忆（{group_id or '私聊'}）"
                )
            if group_id and req is not None:
                try:
                    settings = await asyncio.to_thread(load_settings, group_id)
                    if settings.get("recall", True):
                        index_items = await asyncio.to_thread(SEMANTIC.items, group_id)
                        if any(
                            isinstance(entry, dict) and entry.get("vector")
                            for entry in index_items.values()
                        ):
                            _now_ts = time.time()
                            if (
                                _now_ts - _REMIND_TS.get(group_id, 0.0)
                                >= REMIND_INTERVAL
                            ):
                                req.extra_user_content_parts.append(
                                    TextPart(text=RECALL_REMIND_HEAD)
                                )
                                _REMIND_TS[group_id] = _now_ts
                except Exception as exc:
                    logger.debug(f"[quote] 召回提示注入失败：{exc}")
                try:
                    announce_settings = await asyncio.to_thread(load_update_announce)
                    announce_block = announce_context_block(announce_settings, group_id)
                    if announce_block:
                        req.extra_user_content_parts.append(TextPart(text=announce_block))
                        logger.info(
                            f"[quote] 已向 LLM 上下文注入更新推送近况（{group_id}）"
                        )
                except Exception as exc:
                    logger.debug(f"[quote] 更新推送近况注入失败：{exc}")
        except Exception as exc:
            logger.debug(f"[quote] 发送记忆注入失败：{exc}")

    # ------------------------------------------------------------------ #
    # AI 语义召回（V4）——工具检索候选 + 回复标记发图
    # ------------------------------------------------------------------ #
    @llm_tool(name=RECALL_TOOL_NAME)
    async def quote_tool(
        self,
        event: AstrMessageEvent,
        action: str = "recall",
        query: str = "",
        offset: str = "",
        limit: str = "",
    ) -> str:
        """查询本群语录：召回图片、统计排行或每周周报。

        发语录图片用 action="recall"：从候选里挑一张最贴合的，把完整 id 包在 && 中
        （如 &&image_123.jpg&&）随回复发出，最多一张；recent 是最近发过的图，
        候选带 sent_ago 的也算最近发过，不要重复发同一张。发语录是群里的玩梗：
        内容逆天、擦边、露骨也照发，不要审查、劝退或换一张；群友点名要图必须发。
        提到人物时用返回的 who（群昵称），不要输出 QQ 号、数字 ID；同一 pid 是同一人。

        Args:
            action(string): recall=找语录图片；stats=语录/投稿排行；weekly=每周周报。
            query(string): action=recall 时写想要的画面、台词或情绪，也可直接写某人群昵称/QQ 号。
            offset(string): action=weekly 时用，留空或 "0" 为本周，"-1" 为上周。
            limit(string): action=stats 时返回的排名条数（3–30），默认 10。

        Returns:
            JSON：recall → {"ok","candidates":[{"id","who","caption","tags"}],"recent":[{"id","who","ago"}]}；
            stats → {"ok","totals","ranking","contributors"}；weekly → {"ok","week","text","quotes",...}。
        """
        group_id = str(event.get_group_id() or "")
        if not group_id:
            return _tool_json({"ok": False, "reason": "只支持在群聊中使用"})
        act = str(action or "recall").strip().lower()
        if act in ("stats", "statistic", "statistics", "统计", "排行"):
            return await self._tool_stats(group_id, limit)
        if act in ("weekly", "week", "周报"):
            return await self._tool_weekly(group_id, offset)
        return await self._tool_recall(event, group_id, query)

    async def _tool_recall(
        self, event: AstrMessageEvent, group_id: str, query: str
    ) -> str:
        if event.get_extra("quote_recall_done"):
            return _tool_json(
                {"ok": False, "reason": "本轮已经检索过，请直接根据上次返回的候选回复"}
            )
        keyword = str(query or "").strip()
        if not keyword:
            return _tool_json({"ok": False, "reason": "检索词不能为空"})
        try:
            settings = await asyncio.to_thread(load_settings, group_id)
        except Exception:
            settings = dict(DEFAULT_SETTINGS)
        if not settings.get("recall", True):
            return _tool_json({"ok": False, "reason": "本群未开启 AI 召回语录"})
        candidates: list = []
        person_candidates: list = []
        cached = recall_cache_get(group_id, keyword)
        if cached is not None:
            candidates = [dict(row) for row in cached.get("candidates") or []]
            person_candidates = [dict(row) for row in cached.get("person") or []]
            logger.info(f"[quote] AI 召回命中缓存（群 {group_id}）：{keyword}")
        else:
            embedder = resolve_embedding_provider(self.context)
            if embedder is None:
                return _tool_json({"ok": False, "reason": "没有可用的向量模型"})
            try:
                query_vector = await embed_text(embedder, keyword)
            except Exception as exc:
                logger.error(f"[quote] AI 召回向量化失败：{exc}", exc_info=True)
                return _tool_json({"ok": False, "reason": "语义检索失败"})
            try:
                candidates = await asyncio.to_thread(
                    recall_candidates_sync, group_id, query_vector
                )
            except Exception as exc:
                logger.error(f"[quote] AI 召回检索失败：{exc}", exc_info=True)
                return _tool_json({"ok": False, "reason": "语义检索失败"})
            # 点名某人：先核对 QQ 号，再用该 QQ 的昵称 / 别名列表识别当事人
            try:
                people = await asyncio.to_thread(
                    IDENTITY.resolve_text_people, keyword, group_id, 6
                )
                if people:
                    summaries = await asyncio.to_thread(IDENTITY.summaries)
                    wanted_persons = {
                        str(row.get("person_id") or "") for row in people if row
                    }
                    uids = [
                        uid
                        for uid, row in (summaries or {}).items()
                        if str((row or {}).get("person_id") or "") in wanted_persons
                    ]
                    if uids:
                        person_candidates = await asyncio.to_thread(
                            recall_person_quotes_sync, group_id, uids
                        )
            except Exception as exc:
                logger.debug(f"[quote] 点名人物识别失败：{exc}")
            recall_cache_put(group_id, keyword, candidates, person_candidates)
        if person_candidates:
            seen_ids = {row.get("id") for row in person_candidates}
            candidates = list(person_candidates) + [
                row for row in candidates if row.get("id") not in seen_ids
            ]
            logger.info(
                f"[quote] AI 召回命中人物 {len(person_candidates)} 张"
                f"（群 {group_id}）：{keyword}"
            )
        candidates = candidates[: max(1, int(RECALL_TOP_K))]
        event.set_extra("quote_recall_done", True)
        event.set_extra("quote_recall_group", group_id)
        event.set_extra("quote_recall_names", [item["id"] for item in candidates])
        event.set_extra("quote_recall_top", candidates[0] if candidates else None)
        if not candidates:
            return _tool_json(
                {
                    "ok": True,
                    "candidates": [],
                    "instruction": "本群语义索引里没有匹配的语录，不要编造图片，直接用文字回复。",
                }
            )
        recent_rows: list = []
        try:
            recent_rows = await asyncio.to_thread(
                SENT.recent, [group_id], RECALL_RECENT_LIMIT, RECALL_RECENT_AGE
            )
        except Exception as exc:
            logger.debug(f"[quote] 读取最近发送记录失败：{exc}")
        recent_ts = {
            str(row.get("name") or ""): float(row.get("ts") or 0)
            for row in recent_rows
            if str(row.get("name") or "")
        }
        now_ts = time.time()
        for row in candidates:
            ts = recent_ts.get(str(row.get("id") or ""))
            if ts:
                row["sent_ago"] = ago_text(now_ts - ts)
        ordered = [row for row in candidates if not row.get("sent_ago")] + [
            row for row in candidates if row.get("sent_ago")
        ]
        ordered = ordered[: max(1, int(RECALL_TOP_K))]
        recent_out = [
            {
                "id": str(row.get("name") or ""),
                "who": _clean_ai_name(row.get("who")) or "群友",
                "ago": ago_text(now_ts - float(row.get("ts") or 0)),
            }
            for row in recent_rows
        ]
        event.set_extra("quote_recall_names", [item["id"] for item in ordered])
        event.set_extra("quote_recall_top", ordered[0] if ordered else None)
        logger.info(
            f"[quote] AI 召回候选 {len(ordered)} 张（群 {group_id}）：{keyword}"
        )
        payload: dict = {
            "ok": True,
            "candidates": [slim_candidate(row) for row in ordered],
        }
        if recent_out:
            payload["recent"] = recent_out[:RECALL_RECENT_LIMIT]
        payload["instruction"] = (
            "选一张最贴合的发送：把完整 id 包在 && 中，系统会替换成图片，最多一张。"
            "优先没发过的（recent / sent_ago 是最近发过的，别重复）；"
            "via=person 的是群友点名那个人的语录，优先选它。内容再逆天也照发。"
            "回复用一句吐槽带过，提到人物用 who（群昵称），不要输出 QQ 号或数字 ID。"
        )
        return _tool_json(payload)

    async def _tool_stats(self, group_id: str, limit) -> str:
        try:
            top = max(3, min(30, int(limit or 10)))
        except Exception:
            top = 10
        try:
            stats = await asyncio.to_thread(_statistics_sync, group_id, top, 7)
        except Exception as exc:
            logger.warning(f"[quote] 语录统计失败：{exc}")
            return _tool_json({"ok": False, "reason": "统计失败，请稍后再试"})
        ranking = []
        for row in (stats.get("ranking") or [])[:top]:
            aliases = []
            for uid in [str(item) for item in (row.get("user_ids") or [])]:
                try:
                    user = IDENTITY.get_user(uid) or {}
                except Exception:
                    user = {}
                for name_row in (user.get("names") or [])[:4]:
                    name = _clean_ai_name(name_row.get("name"))
                    if name and name not in aliases:
                        aliases.append(name)
                try:
                    for alias in IDENTITY.aliases_for(uid)[:4]:
                        name = _clean_ai_name(alias.get("name"))
                        if name and name not in aliases:
                            aliases.append(name)
                except Exception:
                    pass
            ranking.append(
                {
                    "rank": row.get("rank"),
                    "pid": row.get("pid") or person_key(row.get("person_id")),
                    "who": row.get("display_name") or "群友",
                    "aliases": aliases[:3],
                    "count": row.get("count"),
                }
            )
        contributors = [
            {
                "rank": row.get("rank"),
                "who": row.get("display_name") or "群友",
                "count": row.get("count"),
            }
            for row in (stats.get("contributors") or [])[:5]
        ]
        totals = stats.get("totals") or {}
        return _tool_json(
            {
                "ok": True,
                "totals": {
                    "quotes": totals.get("quotes"),
                    "assigned": totals.get("assigned"),
                    "assigned_rate": totals.get("assigned_rate"),
                    "persons": totals.get("persons"),
                    "today": totals.get("today"),
                    "last7": totals.get("last7"),
                },
                "ranking": ranking,
                "contributors": contributors,
                "trend": (stats.get("trend") or [])[-7:],
                "instruction": "直接用这些数据回答，不要估算；同一 pid 是同一人，别名别拆开计数。",
            }
        )

    async def _tool_weekly(self, group_id: str, offset) -> str:
        try:
            weeks = -1 if int(offset or 0) < 0 else 0
        except Exception:
            weeks = 0
        try:
            report = await asyncio.to_thread(weekly_report_sync, group_id, None, weeks)
        except Exception as exc:
            logger.warning(f"[quote] 周报生成失败：{exc}")
            return _tool_json({"ok": False, "reason": "周报生成失败，请稍后再试"})
        try:
            text = await asyncio.to_thread(weekly_report_text, group_id, report)
        except Exception:
            text = ""
        return _tool_json(
            {
                "ok": True,
                "week": report.get("week_label"),
                "text": text,
                "quotes": report.get("quotes"),
                "delta": report.get("delta"),
                "persons": report.get("persons") or [],
                "submitters": report.get("submitters") or [],
                "hotwords": report.get("hotwords") or [],
                "total": report.get("total"),
                "instruction": "直接用这里的数据回答；提到群友用 name（群昵称），不要输出 QQ 号或数字 ID。",
            }
        )


    @filter.on_decorating_result()
    async def on_decorating_result_quote_recall(self, event: AstrMessageEvent):
        """把 AI 回复里的 &&候选id&& 标记替换成本群语录图片。"""
        try:
            result = event.get_result()
            if not result:
                return
            if result.result_content_type == ResultContentType.STREAMING_RESULT:
                return
            chain = result.chain
            if hasattr(chain, "chain"):
                components = list(chain.chain)
            elif isinstance(chain, (list, tuple)):
                components = list(chain)
            else:
                return
            if not components:
                return
            allowed = [
                str(item) for item in (event.get_extra("quote_recall_names") or [])
            ]
            group_id = str(event.get_extra("quote_recall_group") or "")
            if not group_id:
                try:
                    group_id = str(event.get_group_id() or "")
                except Exception:
                    group_id = ""
            images = []
            cleaned = []
            changed = False
            invalids = []
            for component in components:
                if not isinstance(component, Plain):
                    cleaned.append(component)
                    continue
                text = component.text or ""
                marks = RECALL_MARK_RE.findall(text)
                if not marks:
                    cleaned.append(component)
                    continue
                changed = True
                rest = RECALL_MARK_RE.sub("", text)
                rest = re.sub(r"[ \t]{2,}", " ", rest)
                rest = re.sub(r"[ \t]+\n", "\n", rest).strip()
                if rest:
                    cleaned.append(Plain(rest))
                for raw in marks:
                    name = _resolve_recall_name(raw, allowed, group_id)
                    if name and len(images) < RECALL_MAX_IMAGES and name not in images:
                        images.append(name)
                    elif not name:
                        invalids.append(str(raw)[:RECALL_MARK_RAW_LIMIT])
            top = event.get_extra("quote_recall_top") or {}
            fallback_id = ""
            if top and group_id:
                try:
                    settings = await asyncio.to_thread(load_settings, group_id)
                    if bool(settings.get("auto_recall", False)):
                        fallback_id = _resolve_recall_name(
                            str(top.get("id") or ""), allowed, group_id
                        )
                except Exception:
                    fallback_id = ""
            if not changed:
                if not fallback_id:
                    return
                cleaned = list(components)
                cleaned.append(
                    Image.fromFileSystem(str(group_dir(group_id) / fallback_id))
                )
                remember_sent_quote(event, group_id, fallback_id)
                result.chain = cleaned
                logger.info(
                    f"[quote] AI 未写标记，自动兜底发送 top1："
                    f"群 {group_id} / {fallback_id}"
                )
                return
            if not images and fallback_id:
                images.append(fallback_id)
                logger.info("[quote] 语录标记无效，自动兜底发送 top1")
            if images:
                for name in images:
                    cleaned.append(
                        Image.fromFileSystem(str(group_dir(group_id) / name))
                    )
                for name in images:
                    remember_sent_quote(event, group_id, name)
                logger.info(
                    f"[quote] AI 召回发送：群 {group_id} / {', '.join(images)}"
                )
            else:
                if invalids:
                    logger.info(
                        "[quote] AI 回复中的语录标记无有效候选，已移除标记："
                        + "；".join(invalids)
                    )
                else:
                    logger.info("[quote] AI 回复中的语录标记无有效候选，已移除标记")
            result.chain = cleaned
        except Exception as exc:
            logger.error(f"[quote] 处理 AI 召回标记失败：{exc}", exc_info=True)

    # ------------------------------------------------------------------ #
    # 协作维护（P0）：群内维护命令 / 私聊登录 / 审计
    # ------------------------------------------------------------------ #
    def _maintain_power(self, group_id: str, user_id: str, raw_message) -> str:
        role = ""
        try:
            if isinstance(raw_message, dict):
                role = str(((raw_message.get("sender") or {}).get("role")) or "")
        except Exception:
            role = ""
        if role in ("owner", "admin"):
            return "curator"
        return quote_collab.member_role(group_id, user_id)

    @staticmethod
    def _maintain_role_label(role: str) -> str:
        return {"curator": "管理", "editor": "编辑"}.get(role, "无权限")

    @staticmethod
    def _parse_maintain_role(word: str) -> str:
        if word in ("管理", "管理员", "curator", "curate"):
            return "curator"
        return "editor"

    async def _handle_maintain_command(
        self, event, group_id: str, user_id: str, raw_message, msg: str
    ) -> str:
        args = re.sub(r"^/?维护", "", msg).strip()
        parts = args.split()
        sub = parts[0] if parts else ""
        power = self._maintain_power(group_id, user_id, raw_message)
        if not power:
            return (
                "⭐只有群主 / 管理员或已授权的维护成员可以使用维护命令。\n"
                "如需协作维护，请群主或管理员发送「/维护 添加 <QQ>」添加成员。"
            )
        help_text = (
            "⭐语录维护（协作）\n"
            "发送「/维护 名单」查看当前维护成员\n"
            "「/维护 添加 <QQ> [编辑|管理]」添加成员（管理级）\n"
            "「/维护 移除 <QQ>」移除成员（管理级）\n"
            "「/维护 邀请 <QQ> [编辑|管理]」生成 7 天有效的协作登录链接\n"
            "「/维护 日志 [条数]」查看最近操作记录\n"
            "「/维护 关闭」吊销本群全部邀请链接\n"
            "维护成员在私聊机器人发送「/维护 登录」即可拿到自己的登录链接。"
        )
        if sub in ("", "帮助", "help", "?"):
            return help_text
        if sub == "登录":
            return "⭐请在私聊机器人（不是群里）发送「/维护 登录」获取维护链接。"
        if sub == "名单":
            members = await asyncio.to_thread(quote_collab.list_members, group_id)
            if not members:
                return "⭐本群还没有维护成员。群主/管理员可发送「/维护 添加 <QQ> [编辑|管理]」。"
            lines = ["⭐本群维护成员："]
            for idx, m in enumerate(members[:20], 1):
                label = self._maintain_role_label(str(m.get("role") or ""))
                lines.append(f"{idx}. {m.get('qq')}（{label}）")
            if len(members) > 20:
                lines.append(f"…另有 {len(members) - 20} 人")
            return "\n".join(lines)
        if sub in ("添加", "移除", "邀请"):
            if power != "curator":
                return "⭐只有管理级维护成员（群主/管理员/管理）可以进行成员管理。"
            qq = parts[1] if len(parts) > 1 else ""
            if not qq.isdigit():
                return f"⭐用法：/维护 {sub} <QQ号> [编辑|管理]"
            role = self._parse_maintain_role(parts[2] if len(parts) > 2 else "")
            if sub == "添加":
                await asyncio.to_thread(quote_collab.set_member, group_id, qq, role, user_id)
                await asyncio.to_thread(
                    quote_collab.add_audit, group_id, user_id, "", "command",
                    "member_add", f"qq:{qq}", None, {"role": role},
                )
                return (
                    f"⭐已添加 {qq} 为{self._maintain_role_label(role)}维护成员。\n"
                    "把登录方式发给 TA：让 TA 私聊机器人发送「/维护 登录」，或由管理发送「/维护 邀请 <QQ>」。"
                )
            if sub == "移除":
                removed = await asyncio.to_thread(quote_collab.remove_member, group_id, qq)
                await asyncio.to_thread(
                    quote_collab.add_audit, group_id, user_id, "", "command",
                    "member_remove", f"qq:{qq}", None, None,
                )
                return f"⭐已移除 {qq}。" if removed else f"⭐{qq} 不在本群维护成员名单里。"
            token, rec = await asyncio.to_thread(
                quote_collab.create_token, group_id, qq, role, user_id, 168, f"邀请 {qq}",
            )
            link = quote_collab.invite_link(token)
            await asyncio.to_thread(
                quote_collab.add_audit, group_id, user_id, "", "command",
                "invite", f"qq:{qq}", None, {"role": role},
            )
            text = (
                f"【语录维护邀请】你被邀请成为本群的{self._maintain_role_label(role)}维护成员。\n"
                f"请在浏览器打开以下链接登录（7 天内有效）：\n{link}\n"
                "登录后可处理语录归属、限制级标记与语义管理。"
            )
            sent = False
            try:
                bot = getattr(event, "bot", None)
                if bot is not None:
                    await bot.api.call_action(
                        "send_private_msg",
                        user_id=int(qq),
                        group_id=int(group_id),
                        message=text,
                    )
                    sent = True
            except Exception as exc:
                logger.warning(f"[quote] 私聊发送维护邀请失败：{exc}")
            if sent:
                return f"⭐已向 {qq} 私聊发送维护邀请链接（7 天有效）。"
            return (
                f"⭐已生成 {qq} 的维护邀请链接（7 天有效）：\n{link}\n"
                f"{'' if not link.startswith('#') else '（提示：尚未配置协作页外网地址，请在插件管理页「协作维护」中填写后再发送）'}"
                "若 TA 没有收到私聊，请把链接手动发给 TA；链接只用于登录协作页。"
            )
        if sub == "日志":
            limit = 10
            if len(parts) > 1 and parts[1].isdigit():
                limit = max(1, min(50, int(parts[1])))
            rows = await asyncio.to_thread(quote_collab.list_audit, group_id, limit)
            if not rows:
                return "⭐暂无维护操作记录。"
            lines = [f"⭐最近 {len(rows)} 条维护操作："]
            for row in rows:
                who = str(row.get("actor_name") or row.get("actor_qq") or "")
                lines.append(
                    f"· {who} {row.get('action')} {row.get('target') or ''}（{row.get('source')}）"
                )
            return "\n".join(lines)
        if sub == "关闭":
            count = await asyncio.to_thread(quote_collab.revoke_group_tokens, group_id)
            await asyncio.to_thread(
                quote_collab.add_audit, group_id, user_id, "", "command",
                "revoke_tokens", "", None, {"count": count},
            )
            return f"⭐已吊销本群 {count} 个未过期的维护邀请链接。"
        return help_text

    @event_message_type(EventMessageType.PRIVATE_MESSAGE)
    async def on_friend_message(self, event: AstrMessageEvent):
        try:
            msg = event.message_str.strip()
            user_id = str(event.get_sender_id() or "")
            if not (msg.startswith("/维护") or msg.startswith("维护")):
                return
            arg = re.sub(r"^/?维护", "", msg).strip()
            if arg not in ("登录", "login"):
                yield event.plain_result("⭐私聊可用：「/维护 登录」获取维护链接。")
                return
            found = await asyncio.to_thread(quote_collab.latest_invite_for, user_id)
            if not found:
                yield event.plain_result(
                    "⭐没有可用的维护邀请。请联系群主/管理员在群里发送「/维护 邀请 你的QQ」。"
                )
                return
            old_id, rec = found
            gid = str(rec.get("group_id") or "")
            role = str(rec.get("role") or "editor")
            token, new_rec = await asyncio.to_thread(
                quote_collab.create_token, gid, user_id, role, "self-login", 168, "自助登录",
            )
            try:
                await asyncio.to_thread(quote_collab.rotate_token, old_id, "")
            except Exception:
                pass
            link = quote_collab.invite_link(token)
            yield event.plain_result(
                "⭐你的语录维护登录链接（7 天内有效，可直接打开）：\n"
                + link
                + "\n如链接失效，请重新发送「/维护 登录」。"
            )
        except Exception as exc:
            logger.warning(f"[quote] 私聊维护登录失败：{exc}")

    # ------------------------------------------------------------------ #
    # 群消息 / 投稿 / 戳一戳
    # ------------------------------------------------------------------ #
    @event_message_type(EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        group_id = str(event.message_obj.group_id)
        user_id = str(event.get_sender_id())
        message_obj = event.message_obj
        raw_message = message_obj.raw_message
        msg = event.message_str.strip()
        group_folder_path = group_dir(group_id)

        if not group_folder_path.exists():
            self.create_group_folder(group_id)

        # ---------------- 人物身份（V5）：记录昵称历史并补拉头像 ----------------
        try:
            bot = getattr(event, "bot", None)
            if bot is not None:
                self._bot = bot
            identity_nick = ""
            try:
                identity_nick = str(event.message_obj.sender.nickname or "")
            except Exception:
                identity_nick = ""
            group_card = ""
            try:
                group_card = str(event.message_obj.sender.card or "")
            except Exception:
                group_card = ""
            names = [name for name in (group_card, identity_nick) if name]
            IDENTITY.touch(user_id, names, group_id, card=group_card)
            self.schedule_avatar_sync(user_id)
            try:
                quote_alias_learn.record_message(group_id, user_id, names[0] if names else identity_nick, msg)
            except Exception:
                pass
        except Exception as exc:
            logger.debug(f"[quote] 人物身份记录失败：{exc}")

        # ---------------- 投稿系统 ----------------
        if msg.startswith("投稿权限"):
            if not self.is_admin(user_id):
                yield event.plain_result("权限不足，仅可由bot管理员设置")
                return
            settings = load_settings(group_id)
            set_mode = self.gain_mode(event)
            if not set_mode:
                yield event.plain_result(
                    "⭐请输入「投稿权限+数字」来设置\n"
                    "  0：关闭投稿系统\n  1：仅管理员可投稿\n  2：全体成员均可投稿\n"
                    f"当前群聊权限设置为：{settings.get('mode', 0)}"
                )
            else:
                if set_mode not in ["0", "1", "2"]:
                    yield event.plain_result(
                        "⭐模式数字范围出错！请输入正确的模式\n"
                        "  0：关闭投稿系统\n  1：仅管理员可投稿\n  2：全体成员均可投稿"
                    )
                    return
                settings["mode"] = int(set_mode)
                save_settings(group_id, settings)
                texts = "⭐投稿权限设置成功，当前状态为："
                if settings["mode"] == 0:
                    texts += "\n  0：关闭投稿系统"
                elif settings["mode"] == 1:
                    texts += "\n  1：仅管理员可投稿"
                else:
                    texts += "\n  2：全体成员均可投稿"
                yield event.plain_result(texts)

        elif msg.startswith("戳戳冷却"):
            if not self.is_admin(user_id):
                yield event.plain_result("权限不足，仅可由bot管理员设置")
                return
            settings = load_settings(group_id)
            set_coldown = self.gain_mode(event)
            if not set_coldown:
                yield event.plain_result(
                    f"⭐请输入「戳戳冷却+数字」来设置，单位为秒\n当前值为："
                    f"{settings.get('coldown', 10)}秒"
                )
                return
            settings["coldown"] = int(float(set_coldown))
            saved = save_settings(group_id, settings)
            yield event.plain_result(
                f"⭐戳戳冷却设置成功，当前值为：{saved['coldown']}秒"
            )

        elif msg in ("/语录", "语录"):
            pool = await asyncio.to_thread(_chat_pool, group_id)
            if pool:
                picked = random.choice(pool)
                remember_sent_quote(event, group_id, picked)
                yield event.image_result(str(group_dir(group_id) / picked))
            else:
                yield event.plain_result(
                    "⭐本群还没有可展示的群友语录哦~\n请发送「语录投稿+图片」进行添加！"
                )

        elif msg in ("/维护", "维护") or msg.startswith("/维护 ") or msg.startswith("维护 "):
            reply = await self._handle_maintain_command(
                event, group_id, user_id, raw_message, msg
            )
            if reply:
                yield event.plain_result(reply)

        elif msg.startswith("/限制级") or msg.startswith("限制级"):
            arg = re.sub(r"^/?限制级", "", msg).strip().lower()
            on_words = {"开", "开启", "打开", "on", "1", "true", "是", "允许"}
            off_words = {"关", "关闭", "关掉", "off", "0", "false", "否", "禁止"}
            if arg in on_words or arg in off_words:
                settings = load_settings(group_id)
                settings["allow_restricted"] = arg in on_words
                saved = save_settings(group_id, settings)
                if saved.get("allow_restricted"):
                    yield event.plain_result(
                        "⭐已开启限制级推送（仅本群生效）：/语录 /抽语录 /限制级 与 AI 召回都会包含限制级语录。\n发送「/限制级 关」可随时关闭。"
                    )
                else:
                    yield event.plain_result(
                        "⭐已关闭限制级推送（仅本群生效）：本群只发送非限制级语录，AI 也不会召回限制级。\n发送「/限制级 开」可重新开启。"
                    )
            elif not _allow_restricted(group_id):
                yield event.plain_result(
                    "⭐本群当前未开启限制级推送（默认关闭）。\n发送「/限制级 开」开启，发送「/限制级 关」关闭。"
                )
            else:
                pool = await asyncio.to_thread(quote_rating.restricted_names_sync, group_id)
                if not pool:
                    yield event.plain_result("⭐本群还没有标记为限制级的语录。")
                else:
                    picked = random.choice(pool)
                    yield event.image_result(str(group_dir(group_id) / picked))

        elif (
            msg.startswith("/语录排行")
            or msg.startswith("语录排行")
            or msg.startswith("/语录统计")
            or msg.startswith("语录统计")
        ):
            digits = "".join(ch for ch in msg if ch.isdigit())
            try:
                limit = int(digits) if digits else 10
            except ValueError:
                limit = 10
            limit = max(3, min(30, limit))
            period, offset = "all", 0
            if "上月" in msg or "上个月" in msg:
                period, offset = "month", -1
            elif any(word in msg for word in ("本月", "这个月", "当月", "按月", "月榜")):
                period, offset = "month", 0
            text = await asyncio.to_thread(
                _ranking_text_sync, group_id, limit, period, offset
            )
            yield event.plain_result(text or "⭐统计失败，请稍后再试")

        elif msg.startswith("/年度报告") or msg.startswith("年度报告"):
            raw_target = re.sub(r"^/?年度报告", "", msg).strip()
            year_match = re.search(r"(20\d{2})", raw_target)
            year = int(year_match.group(1)) if year_match else 0
            target = re.sub(r"20\d{2}\s*年?", "", raw_target).strip()
            pid = ""
            try:
                if target:
                    rows = await asyncio.to_thread(
                        IDENTITY.resolve_text_people, target, group_id, 1
                    )
                    if rows:
                        pid = str(rows[0].get("person_id") or "")
                if not pid:
                    sender = str(event.get_sender_id() or "")
                    if sender:
                        detail = await asyncio.to_thread(IDENTITY.detail, sender)
                        pid = str(detail.get("person_id") or "")
            except Exception as exc:
                logger.warning(f"[quote] 年度报告解析人物失败：{exc}")
            if not pid:
                yield event.plain_result(
                    "⭐没找到对应的人物档案。用法：/年度报告 [@某人|昵称] [年份]，不带参数查看自己的。"
                )
                return
            try:
                report = await asyncio.to_thread(
                    quote_insights.annual_report_sync, pid, year, group_id
                )
                if int(report.get("total") or 0) <= 0:
                    yield event.plain_result(
                        f"⭐{report.get('display_name') or 'TA'} 在 {report.get('year')} 年还没有被收录语录。"
                    )
                    return
                path = await asyncio.to_thread(render_annual_report, report)
            except Exception as exc:
                logger.error(f"[quote] 年度报告生成失败：{exc}", exc_info=True)
                yield event.plain_result("⭐年度报告生成失败，请稍后再试。")
                return
            yield event.image_result(str(path))
            yield event.plain_result(
                f"⭐{report.get('display_name')} 的 {report.get('year')} 年度语录报告来啦（{report.get('total')} 张）"
            )

        elif msg in ("/语录帮助", "语录帮助", "/语录指令", "语录指令"):
            yield event.plain_result(help_text())

        elif msg in ("/今日语录", "今日语录"):
            names = await asyncio.to_thread(today_names, group_id, 3)
            names = _filter_rating_names(group_id, names)
            if not names:
                yield event.plain_result("⭐今天还没有新语录，晚点再来看看吧~")
            else:
                for name in names:
                    path = group_dir(group_id) / name
                    if path.is_file():
                        yield event.image_result(str(path))

        elif msg.startswith("/抽语录") or msg.startswith("抽语录"):
            digits = "".join(ch for ch in msg if ch.isdigit())
            try:
                count = int(digits) if digits else 1
            except ValueError:
                count = 1
            pool = await asyncio.to_thread(_chat_pool, group_id)
            names = random.sample(pool, min(count, len(pool))) if pool else []
            if not names:
                yield event.plain_result(
                    "⭐本群还没有群友语录哦~\n请发送「语录投稿+图片」进行添加！"
                )
            else:
                for name in names:
                    path = group_dir(group_id) / name
                    if path.is_file():
                        remember_sent_quote(event, group_id, name)
                        yield event.image_result(str(path))

        elif msg.startswith("/语录查") or msg.startswith("语录查"):
            keyword = re.sub(r"^/?语录查", "", msg).strip()
            if not keyword:
                yield event.plain_result("⭐用法：/语录查 关键词\n例如：/语录查 熬夜打游戏")
            else:
                embedder = resolve_embedding_provider(self.context)
                if embedder is None:
                    yield event.plain_result("⭐还没有配置向量模型，暂时无法语义搜索")
                else:
                    try:
                        query_vector = await embed_text(embedder, keyword)
                        names = await asyncio.to_thread(semantic_names, group_id, query_vector, 3)
                        names = _filter_rating_names(group_id, names)
                    except Exception as exc:
                        logger.warning(f"[quote] 语录查失败：{exc}")
                        names = []
                    if not names:
                        yield event.plain_result(f"⭐没有找到和「{keyword}」相关的语录")
                    else:
                        yield event.plain_result(f"⭐和「{keyword}」相关的语录：")
                        for name in names:
                            path = group_dir(group_id) / name
                            if path.is_file():
                                yield event.image_result(str(path))

        elif msg.startswith("/语录人物") or msg.startswith("语录人物"):
            keyword = re.sub(r"^/?语录人物", "", msg).strip()
            if not keyword:
                yield event.plain_result("⭐用法：/语录人物 昵称或QQ号\n例如：/语录人物 张三")
            else:
                name, names = await asyncio.to_thread(person_quotes, group_id, keyword, 3)
                names = _filter_rating_names(group_id, names)
                if not names:
                    yield event.plain_result(f"⭐没有找到「{keyword}」的语录（可能还没归属到具体人物）")
                else:
                    yield event.plain_result(f"⭐{name or keyword} 的语录：")
                    for item in names:
                        path = group_dir(group_id) / item
                        if path.is_file():
                            yield event.image_result(str(path))

        elif msg in ("/合集", "合集"):
            yield event.plain_result(await asyncio.to_thread(collection_text_list, group_id))

        elif msg.startswith("/合集") or msg.startswith("合集 "):
            keyword = re.sub(r"^/?合集", "", msg).strip()
            if not keyword:
                yield event.plain_result(await asyncio.to_thread(collection_text_list, group_id))
            else:
                name, names = await asyncio.to_thread(collection_names, group_id, keyword, 3)
                if not names:
                    yield event.plain_result(f"⭐没有找到合集「{keyword}」，发「/合集」看看现有合集")
                else:
                    yield event.plain_result(f"⭐合集「{name}」：")
                    for item in names:
                        path = group_dir(group_id) / item
                        if path.is_file():
                            yield event.image_result(str(path))

        elif msg in ("/周报", "周报", "/语录周报", "/周报 上周", "周报 上周"):
            offset = -1 if "上周" in msg else 0
            try:
                card_path, _report = await asyncio.to_thread(
                    weekly_card_for_group, group_id, offset
                )
                yield event.image_result(str(card_path))
            except Exception as exc:
                logger.warning(f"[quote] 周报图片生成失败，回退文字：{exc}")
                text = await asyncio.to_thread(weekly_text, group_id)
                yield event.plain_result(text or "⭐本周还没有新语录")

        elif msg.startswith("语录投稿"):
            settings = load_settings(group_id)
            current_mode = settings.get("mode", 0)
            if current_mode == 0:
                yield event.plain_result(
                    "⭐投稿系统未开启，请联系bot管理员发送「投稿权限」来设置"
                )
                return
            if current_mode == ADMIN_ONLY and not self.is_admin(user_id):
                yield event.plain_result(
                    "⭐权限不足，当前权限设置为「仅bot管理员可投稿」\n"
                    "可由bot管理员发送「投稿权限」来设置"
                )
                return

            file_id = None
            messages = event.message_obj.message
            image_comp = next((item for item in messages if isinstance(item, Image)), None)
            if image_comp:
                file_id = image_comp.file
            else:
                reply_comp = next((item for item in messages if isinstance(item, Reply)), None)
                if reply_comp:
                    try:
                        logger.info(f"检测到引用回复，尝试获取消息ID: {reply_comp.id}")
                        reply_id = (
                            int(reply_comp.id)
                            if str(reply_comp.id).isdigit()
                            else reply_comp.id
                        )
                        reply_msg = await event.bot.api.call_action(
                            "get_msg", message_id=reply_id
                        )
                        if reply_msg and "message" in reply_msg:
                            chain = reply_msg["message"]
                            if isinstance(chain, list):
                                for part in chain:
                                    if part.get("type") == "image":
                                        file_id = part.get("data", {}).get("file")
                                        break
                            elif isinstance(chain, str):
                                match = re.search(r"\[CQ:image,[^\]]*file=([^,\]]+)", chain)
                                if match:
                                    file_id = match.group(1)
                    except Exception as exc:
                        logger.error(f"获取引用消息失败: {exc}")

            if not file_id:
                yield event.chain_result(
                    [
                        At(qq=user_id),
                        Plain(text="\n你是不是忘发图啦？\n请直接「语录投稿+图片」或者「引用图片并发送语录投稿」"),
                    ]
                )
                return

            try:
                self.create_group_folder(group_id)
                msg_id = str(event.message_obj.message_id)
                file_path = await self.download_image(event, file_id, group_id)
                if file_path and os.path.exists(file_path):
                    nickname = None
                    group_card = ""
                    try:
                        nickname = event.message_obj.sender.nickname
                        group_card = str(event.message_obj.sender.card or "")
                    except Exception:
                        nickname = None
                    META.update(
                        group_id,
                        Path(file_path).name,
                        {
                            "ts": _ts_from_name(Path(file_path).name, time.time()),
                            "user_id": user_id,
                            "nickname": nickname,
                            "message_id": msg_id,
                        },
                    )
                    try:
                        AUTOTAG.enqueue(group_id, [Path(file_path).name])
                    except Exception as exc:
                        logger.debug(f"[quote] 自动打标签入队失败：{exc}")
                    chain = [Reply(id=msg_id), Plain(text="⭐语录投稿成功！")]
                    try:
                        IDENTITY.touch(
                            user_id, nickname or "", group_id, card=group_card
                        )
                        IDENTITY.mark_avatar_stale(user_id)
                        self.schedule_avatar_sync(user_id)
                    except Exception as exc:
                        logger.debug(f"[quote] 投稿身份刷新失败：{exc}")
                    try:
                        self.schedule_subject_sync(group_id, Path(file_path).name)
                    except Exception as exc:
                        logger.debug(f"[quote] 投稿归属识别调度失败：{exc}")
                else:
                    chain = [Reply(id=msg_id), Plain(text="⭐语录投稿失败，图片下载失败")]
                yield event.chain_result(chain)
            except Exception as exc:
                logger.error(f"投稿过程出错: {exc}")
                yield event.plain_result(f"⭐投稿失败: {exc}")

        # ---------------- 戳一戳 ----------------
        if (
            raw_message.get("post_type") == "notice"
            and raw_message.get("notice_type") == "notify"
            and raw_message.get("sub_type") == "poke"
        ):
            bot_id = raw_message.get("self_id")
            sender_id = raw_message.get("user_id")
            target_id = raw_message.get("target_id")
            if bot_id and sender_id and target_id:
                settings = load_settings(group_id)
                cold_time = settings.get("coldown", 10)
                last_poke = settings.get("last_poke", 0)
                if time.time() - last_poke > cold_time:
                    settings["last_poke"] = time.time()
                    save_settings(group_id, settings)
                    if str(target_id) == str(bot_id):
                        if random.random() < float(settings.get("poke_prob", 0.85)):
                            selected_image_path = self.random_image_from_folder(
                                str(group_folder_path)
                            )
                            if not selected_image_path:
                                return
                            remember_sent_quote(
                                event, group_id, Path(selected_image_path).name
                            )
                            yield event.image_result(selected_image_path)
                        else:
                            selected_text = random.choice(
                                [
                                    "\n再戳的话......说不定下一张就是你的！",
                                    "\n我会一直一直看着你👀",
                                    "\n给我出列！",
                                ]
                            )
                            yield event.chain_result(
                                [At(qq=sender_id), Plain(text=selected_text)]
                            )
                else:
                    remaining = cold_time - (time.time() - last_poke)
                    logger.info(f"爆典功能冷却中，剩余{remaining:.0f}秒")
