"""quote_autotag.py — 自动打标签 / 批量语义化队列（v2.13.0）。

新投稿的语录会自动进入队列，由后台任务逐条跑「视觉描述 + 向量」，
不再需要手动点「一键语义化」。队列状态持久化在 quote.db 的 tag_queue 表，
插件重启后继续处理未完成的条目。
"""

from __future__ import annotations

import asyncio
import time

from astrbot.api import logger

from quote_core import META, group_dir, group_ids, list_image_files, load_settings
from quote_semantic import (
    SEMANTIC,
    SEMANTIC_RUNNER,
    embedding_signature,
    resolve_caption_provider_id,
    resolve_embedding_provider,
)

import quote_db

TICK = 6.0  # 每轮间隔秒数
MAX_ATTEMPTS = 3


class AutoTagger:
    """后台自动打标签任务（单实例）。"""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._plugin = None
        self._paused = False
        self._busy = False
        self._last: dict = {}
        self._error = ""

    # ------------------------------------------------------------------ #
    # 生命周期
    # ------------------------------------------------------------------ #
    def start(self, plugin) -> None:
        self._plugin = plugin
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
        self._task = None

    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def state(self) -> dict:
        stats = self._stats()
        stats.update(
            {
                "running": self.is_running(),
                "busy": self._busy,
                "paused": self._paused,
                "last": dict(self._last),
                "error": self._error,
                "tick": TICK,
            }
        )
        return stats

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    # ------------------------------------------------------------------ #
    # 入队
    # ------------------------------------------------------------------ #
    def enqueue(self, group_id: str, names) -> dict:
        gid = str(group_id or "").strip()
        items = [str(name) for name in (names or []) if str(name).strip()]
        if not gid or not items:
            return {"queued": 0, "skipped": 0}
        try:
            settings = load_settings(gid)
        except Exception:
            settings = {}
        if not bool(settings.get("auto_tag", True)):
            return {"queued": 0, "skipped": len(items)}
        queued = quote_db.tag_queue_add(gid, items)
        return {"queued": queued, "skipped": len(items) - queued}

    def enqueue_pending(self, group_id: str = "") -> dict:
        """扫描所有群，把还没跑完语义化的语录加入队列。"""
        groups = [str(group_id)] if group_id else group_ids()
        total = 0
        found = 0
        for gid in groups:
            try:
                settings = load_settings(gid)
            except Exception:
                settings = {}
            if not bool(settings.get("auto_tag", True)):
                continue
            done = quote_db.tag_queue_names(gid)
            items = SEMANTIC.items(gid)
            names: list[str] = []
            for item in list_image_files(gid):
                name = str(item["name"])
                if name in done:
                    continue
                entry = items.get(name) or {}
                status = str(entry.get("status") or "pending")
                if status == "done" and entry.get("vector"):
                    continue
                names.append(name)
                found += 1
            if names:
                total += quote_db.tag_queue_add(gid, names)
        return {"groups": len(groups), "pending": found, "queued": total}

    # ------------------------------------------------------------------ #
    # 后台处理
    # ------------------------------------------------------------------ #
    def _stats(self) -> dict:
        try:
            return quote_db.tag_queue_stats()
        except Exception:
            return {}

    def _pick(self) -> dict | None:
        try:
            return quote_db.tag_queue_next()
        except Exception as exc:
            self._error = f"读取队列失败：{exc}"
            return None

    async def _loop(self) -> None:
        await asyncio.sleep(5.0)
        try:
            reset = await asyncio.to_thread(quote_db.tag_queue_reset_running)
            if reset:
                logger.info(f"[quote] 自动打标签队列恢复 {reset} 个中断任务")
        except Exception:
            pass
        logger.info("[quote] 自动打标签队列已启动")
        while True:
            try:
                if not self._paused:
                    await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover - 保底
                self._error = str(exc)
                logger.warning(f"[quote] 自动打标签任务异常：{exc}")
            await asyncio.sleep(TICK)

    async def _tick(self) -> None:
        row = await asyncio.to_thread(self._pick)
        if not row:
            return
        gid = str(row.get("group_id") or "")
        name = str(row.get("name") or "")
        if not gid or not name:
            return
        settings = await asyncio.to_thread(load_settings, gid)
        if not bool(settings.get("auto_tag", True)):
            await asyncio.to_thread(
                quote_db.tag_queue_set, gid, name, "skipped", 0, ""
            )
            return
        path = group_dir(gid) / name
        if not path.is_file():
            await asyncio.to_thread(
                quote_db.tag_queue_set, gid, name, "missing", 0, "图片不存在"
            )
            return
        self._busy = True
        started = time.time()
        try:
            context = self._plugin.context if self._plugin is not None else None
            embedding = await asyncio.to_thread(
                resolve_embedding_provider, context
            )
            signature = embedding_signature(embedding)
            caption_id = await asyncio.to_thread(resolve_caption_provider_id, context)
            await SEMANTIC_RUNNER._process_one(
                context, gid, name, caption_id, embedding, signature
            )
            attempts = int(row.get("attempts") or 0) + 1
            await asyncio.to_thread(
                quote_db.tag_queue_set, gid, name, "done", attempts, ""
            )
            self._last = {
                "group_id": gid,
                "name": name,
                "ok": True,
                "cost": round(time.time() - started, 2),
                "at": time.time(),
            }
            self._error = ""
        except Exception as exc:
            attempts = int(row.get("attempts") or 0) + 1
            status = "failed" if attempts >= MAX_ATTEMPTS else "queued"
            await asyncio.to_thread(
                quote_db.tag_queue_set, gid, name, status, attempts, str(exc)[:300]
            )
            self._last = {
                "group_id": gid,
                "name": name,
                "ok": False,
                "error": str(exc)[:200],
                "at": time.time(),
            }
            self._error = str(exc)[:300]
            logger.warning(f"[quote] 自动打标签失败 {gid}/{name}：{exc}")
        finally:
            self._busy = False


AUTOTAG = AutoTagger()
