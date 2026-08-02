"""Model version registry, canary release and rollback management.

Version naming rules (P4 Zhenxin, T5):
  - Edge/node model:     edge-{model_name}-{semver}      e.g. edge-qwen1.5b-1.0.0
  - Aggregation version: agg-{job_id}-r{round_id}       e.g. agg-job001-r12
  - Teacher model:       teacher-{model_name}-{semver}   e.g. teacher-qwen14b-1.0.0
  - Student model:       student-{model_name}-{semver}   e.g. student-qwen1.5b-1.0.0
  - Release batch:       release-{YYYYMMDD}-{seq}        e.g. release-20260801-01

Every aggregation produces a model version. Releases go through
DRAFT -> GRAY -> ACTIVE with health confirmation from edge nodes;
failed releases roll back to the last known-good active version.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np


class ModelStatus(str, Enum):
    """Lifecycle status of a model version."""
    DRAFT = "draft"            # registered, not yet released
    GRAY = "gray"              # canary/gray release in progress
    ACTIVE = "active"          # full rollout, edge nodes load it
    ROLLED_BACK = "rolled_back"
    RETIRED = "retired"
    FAILED = "failed"


@dataclass
class ModelVersion:
    """Full metadata record for one model version."""
    model_name: str
    model_version: str
    model_hash: str
    artifact_path: str
    dataset_version: str
    train_params: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)
    status: ModelStatus = ModelStatus.DRAFT
    aggregation_version: str = ""
    base_version: str = ""
    release_batch: str = ""
    created_at: str = ""
    node_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "model_version": self.model_version,
            "model_hash": self.model_hash,
            "artifact_path": self.artifact_path,
            "dataset_version": self.dataset_version,
            "train_params": self.train_params,
            "metrics": self.metrics,
            "status": self.status.value,
            "aggregation_version": self.aggregation_version,
            "base_version": self.base_version,
            "release_batch": self.release_batch,
            "created_at": self.created_at,
            "node_ids": list(self.node_ids),
        }


def compute_model_hash(weights: List[np.ndarray]) -> str:
    """SHA-256 hash of flattened model weights (reproducible evidence)."""
    h = hashlib.sha256()
    for w in weights:
        h.update(np.ascontiguousarray(w, dtype=np.float32).tobytes())
    return h.hexdigest()[:16]


def make_semver(major: int, minor: int, patch: int) -> str:
    """Build a semantic version string: M.m.p."""
    return f"{major}.{minor}.{patch}"


def make_release_batch(dt: Optional[_dt.date] = None, seq: int = 1) -> str:
    """Release batch id: release-YYYYMMDD-{seq:02d}."""
    d = dt or _dt.date.today()
    return f"release-{d.strftime(chr(37) + chr(89) + chr(109) + chr(100))}-{seq:02d}"


class ModelRegistry:
    """In-memory model version registry (persist to DB in production)."""

    def __init__(self) -> None:
        self._versions: Dict[str, ModelVersion] = {}
        self._hash_index: Dict[str, str] = {}  # model_hash -> version

    def register(
        self,
        model_name: str,
        weights: List[np.ndarray],
        artifact_path: str,
        dataset_version: str,
        train_params: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, float]] = None,
        aggregation_version: str = "",
        base_version: str = "",
        model_version: Optional[str] = None,
    ) -> ModelVersion:
        """Register a new model version. Raises on duplicate hash."""
        h = compute_model_hash(weights)
        if h in self._hash_index:
            existing = self._versions[self._hash_index[h]]
            raise ValueError(
                f"Version conflict: hash {h} already registered as "
                f"{existing.model_version}"
            )

        if model_version is None:
            # Derive next version from latest registered for model_name
            versions = [v for v in self._versions.values() if v.model_name == model_name]
            if versions:
                latest = max(v.model_version for v in versions)
                try:
                    parts = latest.split("-")[-1].split(".")
                    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2]) + 1
                    model_version = f"edge-{model_name}-{major}.{minor}.{patch}"
                except (IndexError, ValueError):
                    model_version = f"edge-{model_name}-0.1.0"
            else:
                model_version = f"edge-{model_name}-0.1.0"

        now = _dt.datetime.now().isoformat(timespec="seconds")
        mv = ModelVersion(
            model_name=model_name,
            model_version=model_version,
            model_hash=h,
            artifact_path=artifact_path,
            dataset_version=dataset_version,
            train_params=train_params or {},
            metrics=metrics or {},
            aggregation_version=aggregation_version,
            base_version=base_version,
            created_at=now,
        )
        self._versions[model_version] = mv
        self._hash_index[h] = model_version
        return mv

    def get(self, model_version: str) -> Optional[ModelVersion]:
        return self._versions.get(model_version)

    def list(self) -> List[ModelVersion]:
        return list(self._versions.values())

    def active(self) -> Optional[ModelVersion]:
        for v in self._versions.values():
            if v.status == ModelStatus.ACTIVE:
                return v
        return None

    def previous_active(self, exclude: Optional[str] = None) -> Optional[ModelVersion]:
        """Last known-good version before the current active one.

        Args:
            exclude: Optionally skip a version (e.g. the one being rolled back).
        """
        active = self.active()
        candidates = [
            v for v in self._versions.values()
            if v.status in (ModelStatus.ACTIVE, ModelStatus.ROLLED_BACK, ModelStatus.GRAY)
        ]
        candidates.sort(key=lambda v: v.created_at, reverse=True)
        for v in candidates:
            if v.model_version == (active.model_version if active else None):
                continue
            if exclude and v.model_version == exclude:
                continue
            return v
        return None

    def next_release_seq(self) -> int:
        batches = [v.release_batch for v in self._versions.values() if v.release_batch]
        seqs = []
        for b in batches:
            try:
                seqs.append(int(b.split("-")[-1]))
            except (IndexError, ValueError):
                continue
        return (max(seqs) + 1) if seqs else 1


class ReleaseManager:
    """Canary release, health confirmation and rollback."""

    def __init__(self, registry: ModelRegistry, min_healthy_nodes: int = 1):
        self.registry = registry
        self.min_healthy_nodes = min_healthy_nodes
        self._health: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.release_log: List[Dict[str, Any]] = []

    def publish(
        self, model_version: str, gray_percent: float = 10.0
    ) -> Dict[str, Any]:
        """Move a DRAFT version to GRAY with a release batch."""
        mv = self.registry.get(model_version)
        if mv is None:
            raise KeyError(f"Unknown model version: {model_version}")
        if mv.status != ModelStatus.DRAFT:
            raise ValueError(f"Model {model_version} is {mv.status.value}, not draft")

        batch = make_release_batch(seq=self.registry.next_release_seq())
        mv.status = ModelStatus.GRAY
        mv.release_batch = batch
        self._health.setdefault(model_version, {})
        rec = {
            "action": "publish",
            "model_version": model_version,
            "release_batch": batch,
            "gray_percent": gray_percent,
            "timestamp": _dt.datetime.now().isoformat(timespec="seconds"),
        }
        self.release_log.append(rec)
        return rec

    def confirm_health(
        self, model_version: str, node_id: str, ok: bool,
        latency_ms: Optional[float] = None,
    ) -> bool:
        """Edge node reports health for a released version."""
        mv = self.registry.get(model_version)
        if mv is None:
            return False
        self._health.setdefault(model_version, {})[node_id] = {
            "ok": ok,
            "latency_ms": latency_ms,
            "timestamp": _dt.datetime.now().isoformat(timespec="seconds"),
        }
        if node_id not in mv.node_ids:
            mv.node_ids.append(node_id)
        healthy = sum(1 for r in self._health[model_version].values() if r["ok"])
        return healthy >= self.min_healthy_nodes

    def rollout(self, model_version: str) -> Dict[str, Any]:
        """Full rollout: GRAY -> ACTIVE after enough healthy nodes."""
        mv = self.registry.get(model_version)
        if mv is None:
            raise KeyError(f"Unknown model version: {model_version}")
        healthy = sum(1 for r in self._health.get(model_version, {}).values() if r["ok"])
        if healthy < self.min_healthy_nodes:
            raise RuntimeError(
                f"Not enough healthy nodes ({healthy}/{self.min_healthy_nodes}) "
                f"to rollout {model_version}"
            )

        # Demote current active to ROLLED_BACK (it is being replaced)
        current = self.registry.active()
        if current is not None and current.model_version != model_version:
            current.status = ModelStatus.ROLLED_BACK

        mv.status = ModelStatus.ACTIVE
        rec = {
            "action": "rollout",
            "model_version": model_version,
            "release_batch": mv.release_batch,
            "timestamp": _dt.datetime.now().isoformat(timespec="seconds"),
        }
        self.release_log.append(rec)
        return rec

    def rollback(self, model_version: str) -> Dict[str, Any]:
        """Roll a released version back to the last known-good one.

        If the version being rolled back is GRAY (never activated), the
        current ACTIVE version stays in place. If it is ACTIVE, the
        previous known-good version is re-activated.
        """
        mv = self.registry.get(model_version)
        if mv is None:
            raise KeyError(f"Unknown model version: {model_version}")
        if mv.status not in (ModelStatus.ACTIVE, ModelStatus.GRAY):
            raise ValueError(f"Model {model_version} is {mv.status.value}, cannot rollback")

        active = self.registry.active()
        mv.status = ModelStatus.ROLLED_BACK

        # Gray rollback: the current active version is still good
        if active is not None and active.model_version != model_version:
            fallback = active.model_version
        else:
            fallback_mv = self.registry.previous_active(exclude=model_version)
            fallback = fallback_mv.model_version if fallback_mv else None
            if fallback_mv is not None:
                fallback_mv.status = ModelStatus.ACTIVE

        rec = {
            "action": "rollback",
            "model_version": model_version,
            "fallback": fallback,
            "status": "ok" if fallback else "no_fallback_available",
            "timestamp": _dt.datetime.now().isoformat(timespec="seconds"),
        }
        self.release_log.append(rec)
        return rec

    def health_summary(self, model_version: str) -> Dict[str, Any]:
        reports = self._health.get(model_version, {})
        total = len(reports)
        ok = sum(1 for r in reports.values() if r["ok"])
        return {"total": total, "healthy": ok, "unhealthy": total - ok, "reports": reports}

    def log(self) -> List[Dict[str, Any]]:
        return list(self.release_log)
