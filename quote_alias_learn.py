"""quote_alias_learn.py — 群友俗名/外号学习（v2.15.0）。

被动收集群消息 → 低频让 LLM 抽取「谁被这样叫」→ 写入待确认候选表；
只有管理页人工确认后才写入别名表（confirmed），不会自动污染身份数据。
"""

from __future__ import annotations

import ast
import json
import re
import threading
import time
from collections import deque

import quote_db
from astrbot.api import logger
from quote_identity import IDENTITY

BUFFER_MAX = 160

BUFFER_TTL = 4 * 3600.0

MIN_MESSAGES = 24

DEFAULT_EVERY = 40

MIN_INTERVAL = 900.0

MAX_PER_RUN = 6

MAX_LINES = 60

ALIAS_MIN_LEN = 2

ALIAS_MAX_LEN = 16

# v3.0.5：俗名必须在最近消息里至少字面出现过这么多次才写入候选（1 = 过滤模型臆造，可调大更严格）
MIN_OCCURRENCES = 1

SKIP_PREFIXES = (
    "/",
    "！",
    "!",
    "语录投稿",
    "投稿权限",
    "戳戳冷却",
    "语录排行",
    "语录统计",
    "语录帮助",
    "年度报告",
)

_lock = threading.RLock()

_buffers: dict = {}

_last_run: dict = {}

SYSTEM_PROMPT = (
    "你是群聊里的“称呼观察员”。从最近的群消息里找出群友的俗名、外号、简称、谐音或习惯称呼，"
    "用来建立“外号 → 真人”的对照表。\n"
    "规则：\n"
    "1. 只输出有明确证据的称呼：原句里能看出某个人被这样叫（例如“阿零今天又…”、“叫老张的那个”）。\n"
    "2. 不要输出 @ 提及出来的名字：以 @ 开头的提及只是提醒，不算称呼；"
    "只记录正文里实际用来称呼某人的叫法。\n"
    "3. 不要输出普通词语、语气词、群名、头衔、等级、表情、口头禅。\n"
    "4. 称呼本身尽量短（2-16 个字），不要带标点。\n"
    "5. target 填该称呼指的人：优先原样抄群里出现的昵称；如果能看出 QQ 号也可以直接写号码。\n"
    "6. 不确定就不要输出。宁缺毋滥。\n"
    "只输出 JSON，不要解释："
    '{"aliases":[{"alias":"俗名","target":"它指的人","confidence":0.8,"evidence":"原句片段"}]}'
    "\n没有符合条件的就输出 {\"aliases\":[]}。最多 6 条。"
)


def _norm_text(text: str) -> str:
    return " ".join(str(text or "").split())


def _count_message_occurrences(lines: list, alias: str) -> int:
    """v3.0.5：统计别名在最近消息里出现的条数（字面包含，用于过滤模型臆造）。"""
    needle = _norm_text(alias)
    if not needle:
        return 0
    total = 0
    for item in lines or []:
        text = _norm_text(item.get("text") if isinstance(item, dict) else item)
        if needle in text:
            total += 1
    return total


def _same_as_display_name(alias: str, display_name: str) -> bool:
    """v3.0.5：别名与目标人物当前群名片/昵称相同时跳过（避免把 @ 名字当外号）。"""
    left = _norm_text(alias).strip("“”\"' ")
    right = _norm_text(display_name).strip("“”\"' ")
    return bool(left and right and left == right)


def record_message(group_id: str, user_id: str, display_name: str, text: str) -> None:
    """记录一条群消息到内存缓冲区（命令、超长文本会被跳过）。"""
    gid = str(group_id or "").strip()
    uid = str(user_id or "").strip()
    if not gid or not uid:
        return
    body = _norm_text(text)
    if not body or len(body) < 2 or len(body) > 200:
        return
    if body.startswith(SKIP_PREFIXES):
        return
    name = str(display_name or "").strip()[:32] or f"群友{uid[-4:]}"
    now = time.time()
    with _lock:
        buf = _buffers.get(gid)
        if buf is None:
            buf = deque(maxlen=BUFFER_MAX)
            _buffers[gid] = buf
        buf.append({"uid": uid, "name": name, "text": body, "ts": now})
        while buf and now - float(buf[0]["ts"]) > BUFFER_TTL:
            buf.popleft()


def pending_messages(group_id: str) -> int:
    with _lock:
        buf = _buffers.get(str(group_id or "").strip())
        return len(buf) if buf else 0


def take_lines(group_id: str, limit: int = MAX_LINES) -> list:
    with _lock:
        buf = _buffers.get(str(group_id or "").strip())
        if not buf:
            return []
        return [dict(item) for item in list(buf)[-max(4, int(limit)):]]


def should_run(group_id: str, every: int = DEFAULT_EVERY) -> bool:
    gid = str(group_id or "").strip()
    if not gid:
        return False
    threshold = max(MIN_MESSAGES, int(every or DEFAULT_EVERY))
    with _lock:
        buf = _buffers.get(gid)
        count = len(buf) if buf else 0
        last = float(_last_run.get(gid) or 0.0)
    if count < threshold:
        return False
    return (time.time() - last) >= MIN_INTERVAL


def _mark_ran(group_id: str) -> None:
    with _lock:
        _last_run[str(group_id or "").strip()] = time.time()


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


async def _chat_provider_id(context, umo: str = "") -> str:
    provider = None
    getter = getattr(context, "get_using_provider_async", None)
    try:
        if callable(getter):
            provider = await getter(umo or None)
        else:
            getter = getattr(context, "get_using_provider", None)
            if callable(getter):
                provider = getter(umo or None)
                if hasattr(provider, "__await__"):
                    provider = await provider
    except Exception:
        provider = None
    if provider is None:
        return ""
    return _provider_id(provider)


def _known_names(group_id: str, limit: int = 25) -> list:
    try:
        payload = IDENTITY.list_people("", group_id, 1, limit) or {}
    except Exception:
        return []
    items = payload.get("items") if isinstance(payload, dict) else []
    names = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("display_name") or "").strip()
        if name:
            names.append(name[:24])
    return names[:limit]


def _build_user_prompt(lines: list, known_names: list) -> str:
    rows = []
    for index, item in enumerate(lines, start=1):
        text = str(item.get("text") or "")[:120]
        rows.append(f"{index}. {item.get('name') or '群友'}: {text}")
    parts = ["最近的群消息：", "\n".join(rows)]
    if known_names:
        parts.append("")
        parts.append("已知群成员昵称（target 可参考，也可直接写消息里出现的昵称）：")
        parts.append("、".join(known_names))
    parts.append("")
    parts.append(
        "请找出这些消息里出现的群友俗名/外号，按上面的 JSON 格式输出。"
    )
    return "\n".join(parts)


def _response_text(response) -> str:
    value = getattr(response, "completion_text", None) or getattr(response, "text", None)
    if value:
        return str(value)
    if isinstance(response, dict):
        return str(response.get("completion_text") or response.get("text") or "")
    return str(response or "")


def _parse_payload(text: str) -> list:
    raw = str(text or "").strip()
    if not raw:
        return []
    candidates = [raw]
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        candidates.append(raw[start : end + 1])
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except ValueError:
            try:
                payload = ast.literal_eval(candidate)
            except (ValueError, SyntaxError):
                continue
        if not isinstance(payload, dict):
            continue
        items = payload.get("aliases")
        if not isinstance(items, list):
            continue
        cleaned = []
        for item in items:
            if not isinstance(item, dict):
                continue
            alias = _norm_text(item.get("alias"))
            target = _norm_text(item.get("target"))
            evidence = _norm_text(item.get("evidence"))[:120]
            alias = re.sub(r"[，。,.!！?？:：;；\"'“”‘’]", "", alias)
            if not alias or len(alias) < ALIAS_MIN_LEN or len(alias) > ALIAS_MAX_LEN:
                continue
            if not target:
                continue
            try:
                confidence = float(item.get("confidence") or 0.5)
            except (TypeError, ValueError):
                confidence = 0.5
            confidence = max(0.1, min(1.0, confidence))
            cleaned.append(
                {
                    "alias": alias,
                    "target": target[:32],
                    "evidence": evidence,
                    "confidence": confidence,
                }
            )
        return cleaned[:MAX_PER_RUN]
    return []


def _resolve_target(target: str, group_id: str) -> dict:
    text = str(target or "").strip()
    if not text:
        return {}
    digits = re.search(r"\d{5,12}", text)
    if digits:
        uid = digits.group(0)
        try:
            info = (IDENTITY.summaries() or {}).get(uid)
        except Exception:
            info = None
        if isinstance(info, dict) and info.get("person_id"):
            return {
                "user_id": uid,
                "person_id": info.get("person_id"),
                "display_name": info.get("display_name") or "",
                "matched_name": text,
            }
    try:
        rows = IDENTITY.resolve_text_people(text, group_id, limit=3) or []
    except Exception:
        rows = []
    if rows:
        return rows[0]
    try:
        alias = IDENTITY.alias_lookup(text, group_id) or {}
    except Exception:
        alias = {}
    uid = str(alias.get("user_id") or "").strip()
    if uid:
        try:
            info = (IDENTITY.summaries() or {}).get(uid) or {}
        except Exception:
            info = {}
        return {
            "user_id": uid,
            "person_id": info.get("person_id") or f"p_{uid}",
            "display_name": info.get("display_name") or "",
            "matched_name": text,
        }
    return {}


async def learn(context, group_id: str, *, every: int = DEFAULT_EVERY, force: bool = False, lines=None) -> dict:
    """跑一次俗名学习：返回 {added, parsed, used, skipped, reason}。"""
    gid = str(group_id or "").strip()
    if not gid:
        return {"skipped": True, "reason": "no_group"}
    if not force and not should_run(gid, every):
        return {"skipped": True, "reason": "not_due"}
    picked = lines if isinstance(lines, list) else take_lines(gid)
    if len(picked) < 6:
        _mark_ran(gid)
        return {"skipped": True, "reason": "too_few_messages", "used": len(picked)}
    provider_id = await _chat_provider_id(context, f"default:GroupMessage:{gid}")
    if not provider_id:
        return {"skipped": True, "reason": "no_provider", "used": len(picked)}
    prompt = _build_user_prompt(picked, _known_names(gid))
    try:
        response = await context.llm_generate(
            chat_provider_id=provider_id,
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.2,
            max_tokens=800,
        )
    except Exception as exc:
        logger.warning(f"[quote] 俗名学习模型调用失败：{exc}")
        _mark_ran(gid)
        return {"skipped": True, "reason": f"llm_error:{exc}", "used": len(picked)}
    items = _parse_payload(_response_text(response))
    added = 0
    kept = []
    dropped_occurrence = 0
    dropped_name = 0
    for item in items:
        resolved = _resolve_target(item.get("target"), gid)
        if not resolved:
            continue
        user_id = str(resolved.get("user_id") or "").strip()
        if not user_id:
            continue
        alias_text = str(item.get("alias") or "").strip()
        occurrences = _count_message_occurrences(picked, alias_text)
        if occurrences < MIN_OCCURRENCES:
            dropped_occurrence += 1
            continue
        if _same_as_display_name(alias_text, resolved.get("display_name") or ""):
            dropped_name += 1
            continue
        try:
            cid = IDENTITY.alias_candidate_add(
                alias_text,
                user_id,
                gid,
                evidence=item.get("evidence") or "",
                confidence=item.get("confidence") or 0.5,
                occurrences=occurrences,
            )
        except Exception as exc:
            logger.debug(f"[quote] 写入俗名候选失败：{exc}")
            continue
        if cid:
            added += 1
            kept.append(
                {
                    "id": cid,
                    "alias": item.get("alias"),
                    "target": resolved.get("display_name") or item.get("target"),
                    "confidence": item.get("confidence"),
                    "occurrences": occurrences,
                }
            )
    _mark_ran(gid)
    return {
        "added": added,
        "parsed": len(items),
        "used": len(picked),
        "dropped_occurrence": dropped_occurrence,
        "dropped_name": dropped_name,
        "items": kept,
    }
