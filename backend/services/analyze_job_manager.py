"""
异步分析任务管理器 —— 内存 Job 存储，支持实时进度、日志、指标和取消
"""

import asyncio
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


# ── 任务数据模型 ─────────────────────────────────────

class ProgressTracker:
    """进度跟踪器 —— 由 workflow 每一步调用，线程安全"""

    def __init__(self, job_id: str, total_steps: int = 6) -> None:
        self.job_id = job_id
        self._lock = threading.Lock()
        self._data: Dict[str, Any] = {
            "job_id": job_id,
            "status": "running",
            "current_step": "initializing",
            "current_step_label": "正在初始化",
            "step_index": 0,
            "total_steps": total_steps,
            "percent": 0,
            "elapsed_seconds": 0,
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "logs": [],
            "metrics": {},
            "result": None,
            "error": None,
            "cancel_requested": False,
        }

    # ── 进度操作 ───────────────────────────────────

    def update_step(self, current_step: str, label: str,
                    step_index: int, percent: int) -> None:
        with self._lock:
            self._data["current_step"] = current_step
            self._data["current_step_label"] = label
            self._data["step_index"] = step_index
            self._data["percent"] = percent
            self._data["elapsed_seconds"] = int(
                time.time() - datetime.fromisoformat(self._data["started_at"]).timestamp()
            )
            self._data["updated_at"] = datetime.now().isoformat(timespec="seconds")

    def log(self, message: str, level: str = "info") -> None:
        with self._lock:
            entry = {
                "time": datetime.now().strftime("%H:%M:%S"),
                "level": level,
                "message": message,
            }
            self._data["logs"].append(entry)
            if len(self._data["logs"]) > 100:
                self._data["logs"] = self._data["logs"][-100:]
            self._data["updated_at"] = datetime.now().isoformat(timespec="seconds")

    def metric(self, key: str, value: Any) -> None:
        with self._lock:
            self._data["metrics"][key] = value

    # ── 结果操作 ───────────────────────────────────

    def set_result(self, result: Dict) -> None:
        with self._lock:
            self._data["result"] = result
            self._data["status"] = "completed"
            self._data["current_step"] = "completed"
            self._data["current_step_label"] = "分析完成"
            self._data["step_index"] = self._data["total_steps"]
            self._data["percent"] = 100
            self._data["elapsed_seconds"] = int(
                time.time() - datetime.fromisoformat(self._data["started_at"]).timestamp()
            )
            self._data["updated_at"] = datetime.now().isoformat(timespec="seconds")

    def set_error(self, error_message: str) -> None:
        with self._lock:
            self._data["error"] = error_message
            self._data["status"] = "failed"
            self._data["current_step"] = "failed"
            self._data["current_step_label"] = "分析失败"
            self._data["updated_at"] = datetime.now().isoformat(timespec="seconds")
            self._data["elapsed_seconds"] = int(
                time.time() - datetime.fromisoformat(self._data["started_at"]).timestamp()
            )

    def is_cancelled(self) -> bool:
        with self._lock:
            return self._data["cancel_requested"]

    def cancel(self) -> None:
        with self._lock:
            self._data["cancel_requested"] = True
            self._data["status"] = "cancelled"
            self._data["current_step_label"] = "任务已取消"
            self._data["updated_at"] = datetime.now().isoformat(timespec="seconds")

    # ── 读取 ───────────────────────────────────────

    def snapshot(self) -> Dict:
        with self._lock:
            import copy
            return copy.deepcopy(self._data)

    def result(self) -> Optional[Dict]:
        with self._lock:
            return self._data["result"]

    def status(self) -> str:
        with self._lock:
            return self._data["status"]


# ── 全局任务管理器 ───────────────────────────────────

class AnalyzeJobManager:
    """分析任务管理器（单例）"""

    _instance: Optional["AnalyzeJobManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "AnalyzeJobManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._jobs: Dict[str, ProgressTracker] = {}
                    cls._instance._tasks: Dict[str, asyncio.Task] = {}
        return cls._instance

    def create_job(self, total_steps: int = 6) -> ProgressTracker:
        job_id = str(uuid.uuid4())[:12]
        tracker = ProgressTracker(job_id, total_steps)
        with self._lock:
            self._jobs[job_id] = tracker
        return tracker

    def get_progress(self, job_id: str) -> Optional[Dict]:
        tracker = self._jobs.get(job_id)
        if tracker is None:
            return None
        return tracker.snapshot()

    def get_result(self, job_id: str) -> Optional[Dict]:
        tracker = self._jobs.get(job_id)
        if tracker is None:
            return None
        return tracker.result()

    def cancel_job(self, job_id: str) -> bool:
        tracker = self._jobs.get(job_id)
        if tracker is None:
            return False
        tracker.cancel()
        # 取消对应的 asyncio task
        task = self._tasks.get(job_id)
        if task and not task.done():
            task.cancel()
        return True

    def register_task(self, job_id: str, task: asyncio.Task) -> None:
        with self._lock:
            self._tasks[job_id] = task

    def get_tracker(self, job_id: str) -> Optional[ProgressTracker]:
        return self._jobs.get(job_id)

    def cleanup_old_jobs(self, max_age_seconds: int = 3600) -> int:
        """清理超过 max_age_seconds 的已完成/失败/取消任务"""
        now = time.time()
        removed = 0
        with self._lock:
            to_remove = []
            for jid, tracker in self._jobs.items():
                snap = tracker.snapshot()
                if snap["status"] in ("completed", "failed", "cancelled"):
                    try:
                        started = datetime.fromisoformat(snap["started_at"])
                        if now - started.timestamp() > max_age_seconds:
                            to_remove.append(jid)
                    except (ValueError, KeyError):
                        to_remove.append(jid)
            for jid in to_remove:
                del self._jobs[jid]
                if jid in self._tasks:
                    del self._tasks[jid]
                removed += 1
        return removed


def get_job_manager() -> AnalyzeJobManager:
    return AnalyzeJobManager()
