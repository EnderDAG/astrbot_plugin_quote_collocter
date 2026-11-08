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
from quote_identity import IDENTITY
from quote_core import META, SEMANTIC_CONCURRENCY, SEMANTIC_DEFAULT_MIN_SCORE, SEMANTIC_FILE, SEMANTIC_FLUSH_EVERY, SEMANTIC_SYSTEM_PROMPT, SEMANTIC_USER_PROMPT, SEMANTIC_VERSION, VISION_JPEG_QUALITY, VISION_MAX_SIDE, group_dir, group_ids, list_image_files


def _normalize_vector(vector) -> list[float]:
    if not isinstance(vector, (list, tuple)):
        raise ValueError("向量模型返回的不是数组")
    values = [float(item) for item in vector]
    if not values:
        raise ValueError("向量为空")
    if any(not math.isfinite(item) for item in values):
        raise ValueError("向量包含非法数值")
    norm = math.sqrt(sum(item * item for item in values))
    if norm <= 0:
        raise ValueError("向量为全零")
    return [item / norm for item in values]

def _cosine(left, right) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return float(sum(a * b for a, b in zip(left, right)))

def _provider_id(provider) -> str:
    meta = getattr(provider, "meta", None)
    if callable(meta):
        try:
            value = getattr(meta(), "id", "")
            if value:
                return str(value)
        except Exception:
            pass
    config = getattr(provider, "provider_config", None)
    if isinstance(config, dict) and config.get("id"):
        return str(config["id"])
    return ""

def _provider_model(provider) -> str:
    method = getattr(provider, "get_model", None)
    if callable(method):
        try:
            value = str(method() or "")
            if value:
                return value
        except Exception:
            pass
    for attr in ("model_name", "model", "embed_model"):
        value = getattr(provider, attr, None)
        if value:
            return str(value)
    return ""

def _provider_dimension(provider) -> int:
    method = getattr(provider, "get_dim", None)
    if not callable(method):
        return 0
    try:
        return int(method() or 0)
    except Exception:
        return 0

def resolve_embedding_provider(context, preferred: str = ""):
    """优先使用指定 id，否则自动挑一个可用的核心向量模型。"""
    wanted = str(preferred or "").strip()
    if wanted:
        provider = context.get_provider_by_id(wanted)
        if provider is not None and callable(getattr(provider, "get_embedding", None)):
            return provider
    try:
        providers = context.get_all_embedding_providers() or []
    except Exception:
        providers = []
    for provider in providers:
        if _provider_dimension(provider) > 0 and callable(
            getattr(provider, "get_embedding", None)
        ):
            return provider
    for provider in providers:
        if callable(getattr(provider, "get_embedding", None)):
            return provider
    return None

def resolve_caption_provider_id(context, preferred: str = "") -> str:
    """视觉模型：优先插件配置，其次 AstrBot 的图片描述 Provider，最后第一个对话模型。"""
    wanted = str(preferred or "").strip()
    if wanted:
        return wanted
    try:
        config = context.get_config() or {}
    except Exception:
        config = {}
    settings = {}
    if isinstance(config, dict):
        raw = config.get("provider_settings")
        if isinstance(raw, dict):
            settings = raw
    candidate = str(settings.get("default_image_caption_provider_id") or "").strip()
    if candidate:
        return candidate
    try:
        providers = context.get_all_providers() or []
    except Exception:
        providers = []
    for provider in providers:
        pid = _provider_id(provider)
        if pid:
            return pid
    return ""

def _response_text(response) -> str:
    value = getattr(response, "completion_text", None) or getattr(response, "text", None)
    if value:
        return str(value)
    if isinstance(response, dict):
        return str(response.get("completion_text") or response.get("text") or "")
    return str(response or "")

def _parse_json_object(text: str) -> dict:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\s*", "", raw)
        raw = re.sub(r"```\s*$", "", raw).strip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except ValueError:
        pass
    match = re.search(r"\{.*\}", raw, re.S)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, dict):
                return data
        except ValueError:
            pass
    raise ValueError(f"视觉模型未返回可解析的 JSON：{raw[:180]}")

def build_semantic_text(fields: dict) -> str:
    parts = []
    visible = str(fields.get("visible_text") or "").strip()
    caption = str(fields.get("caption") or "").strip()
    tags = [str(tag) for tag in (fields.get("tags") or []) if str(tag).strip()]
    if visible:
        parts.append(visible)
    if caption:
        parts.append(caption)
    if tags:
        parts.append("关键字：" + "、".join(tags))
    return "\n".join(parts).strip()

def _prepare_visual_input(path: Path) -> tuple[list[str], list[str]]:
    """动图取首帧、过大图片降采样后交给视觉模型，返回 (可发送路径, 需清理的临时文件)。"""
    source = Path(path)
    if PILImage is None:
        return [str(source)], []
    temp_paths: list[str] = []
    try:
        with PILImage.open(source) as image:
            frames = int(getattr(image, "n_frames", 1) or 1)
            frame = image.convert("RGB")
            width, height = frame.size
            longest = max(width, height)
            needs_temp = frames > 1 or longest > VISION_MAX_SIDE
            if not needs_temp:
                return [str(source)], []
            if longest > VISION_MAX_SIDE:
                scale = VISION_MAX_SIDE / float(longest)
                frame = frame.resize(
                    (max(1, int(width * scale)), max(1, int(height * scale)))
                )
            handle = tempfile.NamedTemporaryFile(
                prefix="quote_vision_", suffix=".jpg", delete=False
            )
            try:
                frame.save(handle, format="JPEG", quality=VISION_JPEG_QUALITY)
            finally:
                handle.close()
            temp_paths.append(handle.name)
            return list(temp_paths), temp_paths
    except Exception as exc:
        for temp in temp_paths:
            try:
                Path(temp).unlink(missing_ok=True)
            except OSError:
                pass
        logger.warning(f"[quote] 视觉输入预处理失败，改用原图 {source}：{exc}")
        return [str(source)], []

async def caption_quote(context, provider_id: str, path: Path, hint: str = "") -> dict:
    if not provider_id:
        raise RuntimeError("未配置视觉模型（请先在 AstrBot 里设置图片描述模型）")
    visual_paths, temp_paths = await asyncio.to_thread(_prepare_visual_input, path)
    hint = str(hint or "").strip()[:300]
    prompt = SEMANTIC_USER_PROMPT
    if hint:
        prompt = (
            f"{SEMANTIC_USER_PROMPT}\n\n"
            f"【维护员参考意见（最高优先级，请据此修正识别）】\n{hint}\n"
            "注意：参考意见用于校正人物与情节判断，但仍须以图片实际内容为准；不要编造图中没有的内容。"
        )
    try:
        response = await context.llm_generate(
            chat_provider_id=provider_id,
            prompt=prompt,
            image_urls=visual_paths,
            system_prompt=SEMANTIC_SYSTEM_PROMPT,
            temperature=0,
            max_tokens=900,
        )
        payload = _parse_json_object(_response_text(response))
        tags = [
            str(tag).strip()[:40]
            for tag in (payload.get("tags") or [])
            if str(tag).strip()
        ]
        return {
            "caption": str(payload.get("caption") or "").strip()[:160],
            "visible_text": str(payload.get("visible_text") or "").strip()[:4000],
            "speaker": str(payload.get("speaker") or "").strip()[:80],
            "tone": str(payload.get("tone") or "").strip()[:24],
            "tags": tags[:10],
        }
    finally:
        for temp in temp_paths:
            try:
                Path(temp).unlink(missing_ok=True)
            except OSError:
                pass

async def embed_text(provider, text: str) -> list[float]:
    method = getattr(provider, "get_embedding", None)
    if not callable(method):
        raise RuntimeError("向量模型不可用")
    result = method(text)
    if hasattr(result, "__await__"):
        result = await result
    vector = _normalize_vector(result)
    dimension = _provider_dimension(provider)
    if dimension and len(vector) != dimension:
        raise RuntimeError(f"向量维度与模型声明不一致：{len(vector)} != {dimension}")
    return vector

def embedding_signature(provider) -> str:
    if provider is None:
        return ""
    return f"{_provider_id(provider)}:{_provider_model(provider)}:{_provider_dimension(provider)}"

class SemanticStore:
    """data/quotes_data/<群号>/quotes_semantic.json

    {"version":1,"signature":"id:model:dim","provider":{...},"updated_at":ts,
     "items":{"<文件名>":{"status":"done|failed|pending","caption":...,"tags":[...],
                          "visible_text":...,"speaker":...,"tone":...,
                          "vector":[...],"dimension":1024,"error":...,"checked_at":ts}}}
    """

    def __init__(self, filename: str = SEMANTIC_FILE):
        self._filename = filename
        self._cache: dict[str, dict] = {}
        self._dirty: dict[str, int] = {}
        self._lock = threading.RLock()

    def _path(self, group_id: str) -> Path:
        return group_dir(group_id) / self._filename

    @staticmethod
    def _blank() -> dict:
        return {
            "version": SEMANTIC_VERSION,
            "signature": "",
            "provider": {},
            "updated_at": 0,
            "items": {},
        }

    def load(self, group_id: str) -> dict:
        gid = str(group_id)
        with self._lock:
            cached = self._cache.get(gid)
            if cached is not None:
                return cached
            data = self._blank()
            try:
                raw = quote_db.load_semantic(gid)
            except Exception as exc:
                logger.warning(f"[quote] 语义索引读取失败，按空索引处理：{exc}")
                raw = None
            if isinstance(raw, dict):
                data["version"] = int(raw.get("version") or SEMANTIC_VERSION)
                data["signature"] = str(raw.get("signature") or "")
                provider = raw.get("provider")
                data["provider"] = provider if isinstance(provider, dict) else {}
                try:
                    data["updated_at"] = float(raw.get("updated_at") or 0)
                except (TypeError, ValueError):
                    data["updated_at"] = 0
                items = raw.get("items")
                data["items"] = items if isinstance(items, dict) else {}
            self._cache[gid] = data
            return data

    def flush(self, group_id: str, *, force: bool = False) -> None:
        gid = str(group_id)
        with self._lock:
            data = self._cache.get(gid)
            if data is None:
                return
            counter = self._dirty.get(gid, 0) + 1
            if not force and counter < SEMANTIC_FLUSH_EVERY:
                self._dirty[gid] = counter
                return
            self._dirty[gid] = 0
            data["updated_at"] = time.time()
            try:
                quote_db.save_semantic(gid, data)
            except Exception as exc:
                logger.error(f"[quote] 语义索引写入数据库失败：{exc}")

    def set_signature(self, group_id: str, provider, signature: str) -> None:
        gid = str(group_id)
        with self._lock:
            data = self.load(gid)
            data["signature"] = signature
            data["provider"] = {
                "id": _provider_id(provider),
                "model": _provider_model(provider),
                "dimension": _provider_dimension(provider),
            }

    def get(self, group_id: str, name: str) -> dict:
        with self._lock:
            item = self.load(group_id)["items"].get(name)
            return dict(item) if isinstance(item, dict) else {}

    def items(self, group_id: str) -> dict:
        with self._lock:
            return dict(self.load(group_id)["items"])

    def mark_pending(self, group_id: str, names) -> None:
        gid = str(group_id)
        with self._lock:
            data = self.load(gid)
            changed = False
            for name in names:
                entry = data["items"].get(name)
                if isinstance(entry, dict) and entry.get("status") == "done":
                    continue
                data["items"][name] = {"status": "pending"}
                changed = True
            if changed:
                self.flush(gid, force=True)

    def record_success(
        self,
        group_id: str,
        name: str,
        *,
        fields: dict,
        vector: list[float],
        dimension: int,
        signature: str,
        speaker: str = "",
        person_id: str = "",
        user_id: str = "",
        speaker_source: str = "",
    ) -> None:
        gid = str(group_id)
        with self._lock:
            data = self.load(gid)
            previous = data["items"].get(name)
            previous = previous if isinstance(previous, dict) else {}
            if signature:
                data["signature"] = signature
            entry = {
                "status": "done",
                "caption": fields.get("caption") or "",
                "visible_text": fields.get("visible_text") or "",
                "speaker": speaker or fields.get("speaker") or "",
                "tone": fields.get("tone") or "",
                "tags": list(fields.get("tags") or []),
                "vector": list(vector),
                "dimension": int(dimension or len(vector)),
                "checked_at": time.time(),
            }
            # 已由人物档案确定的归属优先保留，重跑语义化不能把它冲掉
            if person_id:
                entry["person_id"] = person_id
                entry["user_id"] = user_id
                entry["speaker_source"] = speaker_source or "identity"
                entry["speaker_at"] = time.time()
            else:
                for key in ("person_id", "user_id", "speaker_source", "speaker_at"):
                    if previous.get(key):
                        entry[key] = previous[key]
            data["items"][name] = entry
            self.flush(gid)

    def record_failure(self, group_id: str, name: str, error: str) -> None:
        gid = str(group_id)
        with self._lock:
            data = self.load(gid)
            previous = data["items"].get(name)
            entry = dict(previous) if isinstance(previous, dict) else {}
            entry.update(
                {
                    "status": "failed",
                    "error": str(error)[:400],
                    "checked_at": time.time(),
                }
            )
            entry.pop("vector", None)
            data["items"][name] = entry
            self.flush(gid, force=True)

    def drop(self, group_id: str, names) -> None:
        gid = str(group_id)
        with self._lock:
            data = self.load(gid)
            changed = False
            for name in names:
                if data["items"].pop(name, None) is not None:
                    changed = True
            if changed:
                self.flush(gid, force=True)

    def rename(self, source: str, target: str, name: str, new_name: str) -> None:
        with self._lock:
            entry = self.load(source)["items"].get(name)
            if not isinstance(entry, dict):
                return
            self.load(target)["items"][new_name] = dict(entry)
            self.drop(source, [name])
            self.flush(target, force=True)

    def set_speaker(
        self,
        group_id: str,
        name: str,
        speaker: str,
        *,
        person_id: str = "",
        user_id: str = "",
        flush: bool = True,
    ) -> bool:
        """把已识别的人物档案反向写回语义索引的 speaker（向量文本不含 speaker，无需重算）。"""
        gid = str(group_id)
        text = str(speaker or "").strip()
        if not text:
            return False
        with self._lock:
            data = self.load(gid)
            entry = data["items"].get(name)
            if not isinstance(entry, dict) or entry.get("status") != "done":
                return False
            if (
                entry.get("speaker") == text
                and str(entry.get("person_id") or "") == str(person_id or "")
                and str(entry.get("user_id") or "") == str(user_id or "")
            ):
                return False
            entry["speaker"] = text
            if person_id:
                entry["person_id"] = str(person_id)
            if user_id:
                entry["user_id"] = str(user_id)
            entry["speaker_source"] = "identity"
            entry["speaker_at"] = time.time()
            if flush:
                self.flush(gid, force=True)
            return True

    def forget_group(self, group_id: str) -> None:
        gid = str(group_id)
        with self._lock:
            self._cache.pop(gid, None)
            self._dirty.pop(gid, None)
            path = self._path(gid)
            if path.is_file():
                try:
                    path.unlink()
                except OSError:
                    pass

SEMANTIC = SemanticStore()

class SemanticRunner:
    """单实例后台语义化任务：并发跑视觉描述 + 向量，并暴露进度。"""

    def __init__(self):
        self._task: asyncio.Task | None = None
        self._cancel = False
        self._state = self._blank_state()

    @staticmethod
    def _blank_state() -> dict:
        return {
            "running": False,
            "scope": "",
            "groups": [],
            "total": 0,
            "processed": 0,
            "ok": 0,
            "failed": 0,
            "current": "",
            "started_at": 0.0,
            "finished_at": 0.0,
            "error": "",
            "cancel_requested": False,
            "provider": {},
        }

    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def state(self) -> dict:
        state = dict(self._state)
        state["running"] = self.is_running()
        return state

    def cancel(self) -> None:
        self._cancel = True
        self._state["cancel_requested"] = True

    @staticmethod
    def _needs(entry: dict, scope: str) -> bool:
        status = str((entry or {}).get("status") or "")
        if scope == "all":
            return True
        if scope == "failed":
            return status == "failed"
        if not status or status in {"pending", "failed"}:
            return True
        return status == "done" and not (entry or {}).get("vector")

    def start(
        self,
        context,
        group_ids_to_run,
        *,
        scope: str = "pending",
        caption_provider_id: str = "",
        embedding_provider_id: str = "",
    ) -> dict:
        if self.is_running():
            raise RuntimeError("已有一个语义化任务在运行中，请等待完成或先取消")
        targets: list[tuple[str, str]] = []
        for gid in group_ids_to_run:
            existing = SEMANTIC.items(gid)
            for item in list_image_files(gid):
                entry = existing.get(item["name"]) or {}
                if self._needs(entry, scope):
                    targets.append((gid, item["name"]))
        self._cancel = False
        self._state = self._blank_state()
        self._state.update(
            {
                "scope": scope,
                "groups": sorted({gid for gid, _ in targets}),
                "total": len(targets),
                "started_at": time.time(),
            }
        )
        self._task = asyncio.create_task(
            self._run(context, targets, caption_provider_id, embedding_provider_id)
        )
        return self.state

    async def _run(self, context, targets, caption_provider_id, embedding_provider_id):
        embedding = resolve_embedding_provider(context, embedding_provider_id)
        signature = embedding_signature(embedding)
        self._state["provider"] = {
            "id": _provider_id(embedding) if embedding else "",
            "model": _provider_model(embedding) if embedding else "",
            "dimension": _provider_dimension(embedding) if embedding else 0,
            "caption_provider_id": caption_provider_id,
        }
        logger.info(
            f"[quote] 语义化任务开始：{len(targets)} 张，视觉模型={caption_provider_id or '未配置'}，"
            f"向量模型={signature or '未配置'}"
        )
        semaphore = asyncio.Semaphore(max(1, SEMANTIC_CONCURRENCY))
        try:
            await asyncio.gather(
                *[
                    self._worker(
                        context, semaphore, gid, name, caption_provider_id, embedding, signature
                    )
                    for gid, name in targets
                ]
            )
        except Exception as exc:  # pragma: no cover - gather 内部已逐条兜底
            self._state["error"] = str(exc)
            logger.error(f"[quote] 语义化任务异常：{exc}", exc_info=True)
        finally:
            for gid in {gid for gid, _ in targets}:
                SEMANTIC.flush(gid, force=True)
            self._state["finished_at"] = time.time()
            self._state["current"] = ""
            logger.info(
                f"[quote] 语义化任务结束：成功 {self._state['ok']} / 失败 {self._state['failed']} "
                f"/ 共 {self._state['total']}"
            )

    async def _worker(
        self, context, semaphore, gid, name, caption_provider_id, embedding, signature
    ):
        if self._cancel:
            return
        async with semaphore:
            if self._cancel:
                return
            self._state["current"] = f"{gid}/{name}"
            try:
                await self._process_one(
                    context, gid, name, caption_provider_id, embedding, signature
                )
                self._state["ok"] += 1
            except Exception as exc:
                self._state["failed"] += 1
                await asyncio.to_thread(SEMANTIC.record_failure, gid, name, str(exc))
                logger.warning(f"[quote] 语义化失败 {gid}/{name}：{exc}")
            finally:
                self._state["processed"] += 1
            await asyncio.sleep(0.05)

    async def _process_one(
        self, context, gid, name, caption_provider_id, embedding, signature
    ):
        path = group_dir(gid) / name
        if not path.is_file():
            raise FileNotFoundError("图片文件不存在")
        try:
            subject = META.get(gid, name) or {}
        except Exception:
            subject = {}
        hint = str((subject or {}).get("semantic_hint") or "").strip()[:300]
        if hint:
            logger.info(f"[quote] 语义化使用参考意见：{gid}/{name}（{len(hint)} 字）")
        fields = await caption_quote(context, caption_provider_id, path, hint=hint)
        text = build_semantic_text(fields)
        if not text:
            raise RuntimeError("未能从图中提取到任何可用文本")
        vector: list[float] = []
        dimension = 0
        if embedding is not None:
            vector = await embed_text(embedding, text)
            dimension = len(vector)
            await asyncio.to_thread(SEMANTIC.set_signature, gid, embedding, signature)
        speaker = ""
        person_id = ""
        uid = ""
        # 人物档案已指定归属时，语义 speaker 用档案里的规范名，重跑语义化不丢
        if isinstance(subject, dict) and subject.get("subject_user_id"):
            uid = str(subject["subject_user_id"])
            row = IDENTITY.summaries().get(uid) or {}
            speaker = str(row.get("display_name") or subject.get("subject_name") or "")
            person_id = str(row.get("person_id") or f"p_{uid}")
        await asyncio.to_thread(
            SEMANTIC.record_success,
            gid,
            name,
            fields=fields,
            vector=vector,
            dimension=dimension,
            signature=signature,
            speaker=speaker,
            person_id=person_id,
            user_id=uid,
            speaker_source="identity" if uid else "",
        )
        try:
            from quote_core import load_settings
            import quote_rating

            if bool(load_settings(gid).get("auto_rating", True)):
                verdict = quote_rating.classify(
                    caption=str((fields or {}).get("caption") or ""),
                    tags=(fields or {}).get("tags") or [],
                    visible_text=str((fields or {}).get("visible_text") or ""),
                    tone=str((fields or {}).get("tone") or ""),
                )
                META.update(
                    gid,
                    name,
                    {
                        "restricted": bool(verdict["restricted"]),
                        "rating_source": "auto",
                        "rating_reason": str(verdict["reason"])[:80],
                    },
                )
        except Exception as exc:  # pragma: no cover - 识别失败不影响语义化
            logger.debug(f"[quote] 自动限制级识别失败：{exc}")
        if hint:
            try:
                META.update(gid, name, {"semantic_hint": "", "semantic_hint_by": ""})
            except Exception as exc:  # pragma: no cover - 清理失败不影响结果
                logger.debug(f"[quote] 清理参考意见失败：{exc}")

SEMANTIC_RUNNER = SemanticRunner()

def semantic_status_sync(
    context, *, embedding_provider_id: str = "", caption_provider_id: str = "", group_id: str = ""
) -> dict:
    embedding = resolve_embedding_provider(context, embedding_provider_id)
    caption_id = resolve_caption_provider_id(context, caption_provider_id)
    signature = embedding_signature(embedding)
    provider_info = {
        "id": _provider_id(embedding) if embedding else "",
        "model": _provider_model(embedding) if embedding else "",
        "dimension": _provider_dimension(embedding) if embedding else 0,
        "ready": bool(embedding is not None and _provider_dimension(embedding) > 0),
    }
    groups = [group_id] if group_id else group_ids()
    details = []
    totals = {"total": 0, "done": 0, "failed": 0, "pending": 0, "vectorless": 0, "stale": 0}
    for gid in groups:
        names = [item["name"] for item in list_image_files(gid)]
        items = SEMANTIC.items(gid)
        counter = {"total": len(names), "done": 0, "failed": 0, "pending": 0, "vectorless": 0, "stale": 0}
        for name in names:
            entry = items.get(name) or {}
            status = str(entry.get("status") or "pending")
            if status == "done":
                counter["done"] += 1
                if not entry.get("vector"):
                    counter["vectorless"] += 1
                elif (
                    provider_info["dimension"]
                    and int(entry.get("dimension") or 0)
                    and int(entry["dimension"]) != provider_info["dimension"]
                ):
                    counter["stale"] += 1
            elif status == "failed":
                counter["failed"] += 1
            else:
                counter["pending"] += 1
        for key, value in counter.items():
            totals[key] += value
        details.append(
            {
                "group_id": gid,
                "signature": str(SEMANTIC.load(gid).get("signature") or ""),
                **counter,
            }
        )
    return {
        "embedding": provider_info,
        "signature": signature,
        "caption_provider_id": caption_id,
        "ready": bool(provider_info["ready"] and caption_id),
        "concurrency": SEMANTIC_CONCURRENCY,
        "min_score": SEMANTIC_DEFAULT_MIN_SCORE,
        "totals": totals,
        "groups": details,
    }
