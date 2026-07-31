"""边缘侧云端推理请求生命周期管理。

只负责请求关联和超时状态，不依赖 MQTT 或数据库，便于在 MQTT 回调线程
和主循环之间安全共享。event_id 是业务幂等键，trace_id 用于校验响应来源。
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PendingInference:
    event_id: str
    trace_id: str
    target: str
    mode: str
    event_payload: Dict[str, Any]
    sent_at: float
    deadline: float


@dataclass
class InferenceResolution:
    status: str
    request: Optional[PendingInference] = None


class InferenceTracker:
    """跟踪云端请求，保证响应只消费一次。"""

    def __init__(self, finished_ttl_s: float = 300.0):
        self.finished_ttl_s = max(1.0, finished_ttl_s)
        self._pending: Dict[str, PendingInference] = {}
        self._finished: Dict[str, float] = {}
        self._lock = threading.Lock()

    def register(self, event_id: str, trace_id: str, target: str, mode: str,
                 event_payload: Dict[str, Any], timeout_s: float,
                 now: Optional[float] = None) -> Optional[PendingInference]:
        """登记请求；同一 event_id 已在处理中时返回 None。"""
        now = time.monotonic() if now is None else now
        with self._lock:
            self._cleanup_finished(now)
            if event_id in self._pending:
                return None
            request = PendingInference(
                event_id=event_id,
                trace_id=trace_id,
                target=target,
                mode=mode,
                event_payload=dict(event_payload),
                sent_at=now,
                deadline=now + max(0.01, timeout_s),
            )
            self._pending[event_id] = request
            return request

    def resolve(self, event_id: str, trace_id: Optional[str] = None,
                now: Optional[float] = None) -> InferenceResolution:
        """消费一次响应；trace_id 不匹配时拒绝消费 pending。"""
        now = time.monotonic() if now is None else now
        with self._lock:
            self._cleanup_finished(now)
            request = self._pending.get(event_id)
            if request is None:
                if event_id in self._finished:
                    return InferenceResolution("duplicate")
                return InferenceResolution("unknown")
            if trace_id and trace_id != request.trace_id:
                return InferenceResolution("trace_mismatch")
            self._pending.pop(event_id, None)
            self._finished[event_id] = now + self.finished_ttl_s
            return InferenceResolution("completed", request)

    def cancel(self, event_id: str, trace_id: Optional[str] = None,
               now: Optional[float] = None) -> Optional[PendingInference]:
        """取消发送失败的请求，并将其标记为已结束，防止迟到响应重复处理。"""
        now = time.monotonic() if now is None else now
        with self._lock:
            request = self._pending.get(event_id)
            if request is None or (trace_id and request.trace_id != trace_id):
                return None
            self._pending.pop(event_id, None)
            self._finished[event_id] = now + self.finished_ttl_s
            return request

    def expire(self, now: Optional[float] = None) -> List[PendingInference]:
        """取出已超时请求，并标记为结束。"""
        now = time.monotonic() if now is None else now
        expired = []
        with self._lock:
            self._cleanup_finished(now)
            for event_id, request in list(self._pending.items()):
                if request.deadline <= now:
                    expired.append(request)
                    self._pending.pop(event_id, None)
                    self._finished[event_id] = now + self.finished_ttl_s
        return expired

    def get_status(self) -> Dict[str, int]:
        with self._lock:
            now = time.monotonic()
            self._cleanup_finished(now)
            return {"pending": len(self._pending), "finished_cache": len(self._finished)}

    def _cleanup_finished(self, now: float) -> None:
        for event_id, expires_at in list(self._finished.items()):
            if expires_at <= now:
                self._finished.pop(event_id, None)
