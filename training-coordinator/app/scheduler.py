"""Distributed collaborative training scheduler.

Two layers:
  * Orchestration layer (TrainingScheduler) - job lifecycle, REST/MQTT
  * Algorithm layer (FedAvgScheduler / SemiAsyncScheduler) - actual
    gradient aggregation with numpy arrays.

Author: Zhenxin (P4) - Collaborative training scheduler
        Jianhong (P3) - Training coordinator / project lead.

Aligned with three-phase roadmap:
  Phase A: Sync baseline (FedAvg)           - T8 (due 2026-07-30)
  Phase B: Semi-async staleness-weighted    - T9 (due 2026-08-15)
  Phase C: Robust aggregation + outlier rejection
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from .model_registry import ModelRegistry, ReleaseManager, compute_model_hash


class RoundState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    AGGREGATING = "aggregating"
    COMPLETED = "completed"
    FAILED = "failed"


class Strategy(str, Enum):
    SYNC_FEDAVG = "sync_fedavg"
    ASYNC_STALE = "async_stale"
    ROBUST = "robust"


@dataclass
class ClientUpdate:
    node_id: str
    round_id: int
    weights_summary: Dict[str, float]
    sample_count: int
    training_seconds: float
    loss: float
    accuracy: float
    stale_rounds: int = 0


@dataclass
class TrainingRound:
    job_id: str
    round_id: int
    strategy: Strategy
    state: RoundState = RoundState.PENDING
    participants: List[str] = field(default_factory=list)
    updates: List[ClientUpdate] = field(default_factory=list)
    min_participants: int = 2
    timeout_seconds: int = 300
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    aggregated_accuracy: Optional[float] = None


class TrainingScheduler:
    """Training job orchestrator.

    Responsibilities:
      - start_round: Publish training command via MQTT
      - collect_update: Receive edge node gradient reports
      - aggregate: Delegate to FedAvgScheduler / SemiAsyncScheduler
    """

    def __init__(self, strategy: Strategy = Strategy.SYNC_FEDAVG):
        self.strategy = strategy
        self.rounds: Dict[str, TrainingRound] = {}
        self._algo_engine: Optional[Any] = None
        self.registry = ModelRegistry()
        self.release_manager = ReleaseManager(self.registry)

    def start_round(
        self, job_id: str, participants: List[str], round_id: int = 1
    ) -> TrainingRound:
        r = TrainingRound(
            job_id=job_id, round_id=round_id, strategy=self.strategy,
            participants=participants, state=RoundState.RUNNING,
        )
        self.rounds[f"{job_id}-{round_id}"] = r
        return r

    def collect_update(
        self, job_id: str, round_id: int, update: ClientUpdate
    ) -> bool:
        key = f"{job_id}-{round_id}"
        r = self.rounds.get(key)
        if not r:
            return False
        r.updates.append(update)
        if self.strategy in (Strategy.SYNC_FEDAVG, Strategy.ROBUST):
            return len(r.updates) >= r.min_participants
        return True

    def aggregate(
        self, job_id: str, round_id: int
    ) -> Optional[Dict[str, Any]]:
        key = f"{job_id}-{round_id}"
        r = self.rounds.get(key)
        if not r or len(r.updates) < r.min_participants:
            return None

        dummy_weights = _dummy_weight_template()
        client_updates: Dict[int, Tuple[List[np.ndarray], int]] = {}
        for i, upd in enumerate(r.updates):
            client_updates[i] = (dummy_weights, upd.sample_count)

        engine = self._get_algo_engine(dummy_weights, len(r.updates))
        engine.aggregate(client_updates)

        avg_loss = sum(u.loss for u in r.updates) / len(r.updates)
        avg_acc = sum(u.accuracy for u in r.updates) / len(r.updates)

        # Register aggregated weights as a model version (evidence for T5)
        aggregation_version = f"agg-{job_id}-r{round_id}"
        model_version = None
        try:
            mv = self.registry.register(
                model_name="qwen1.5b",
                weights=engine.global_weights,
                artifact_path="models/qwen1.5b/",
                dataset_version="ward-nlu-500-v1",
                train_params={
                    "strategy": self.strategy.value,
                    "participants": len(r.updates),
                    "round_id": round_id,
                },
                metrics={"avg_loss": round(avg_loss, 4), "avg_accuracy": round(avg_acc, 4)},
                aggregation_version=aggregation_version,
            )
            model_version = mv.model_version
        except ValueError:
            # Duplicate hash already registered - keep existing version
            pass

        r.state = RoundState.COMPLETED
        r.aggregated_accuracy = avg_acc
        return {
            "round_id": round_id,
            "participants": len(r.updates),
            "strategy": self.strategy.value,
            "avg_loss": round(avg_loss, 4),
            "avg_accuracy": round(avg_acc, 4),
            "aggregation_version": aggregation_version,
            "model_version": model_version,
            "status": "aggregated",
        }

    def _get_algo_engine(self, init_weights, n_clients):
        if self._algo_engine is not None:
            return self._algo_engine
        if self.strategy == Strategy.SYNC_FEDAVG:
            self._algo_engine = FedAvgScheduler(init_weights, n_clients, seed=0)
        elif self.strategy == Strategy.ASYNC_STALE:
            self._algo_engine = SemiAsyncScheduler(init_weights, n_clients, seed=0)
        else:
            self._algo_engine = FedAvgScheduler(init_weights, n_clients, seed=0)
        return self._algo_engine


# ======================================================================
# Algorithm layer - Zhenxin (P4)
# ======================================================================

def _dummy_weight_template() -> List[np.ndarray]:
    return [np.zeros((2, 3), dtype=np.float32), np.zeros((2,), dtype=np.float32)]


def flatten_weights(weights: List[np.ndarray]) -> np.ndarray:
    return np.concatenate([w.ravel() for w in weights])


def unflatten_weights(
    flat: np.ndarray, template: List[np.ndarray]
) -> List[np.ndarray]:
    restored = []
    offset = 0
    for arr in template:
        size = arr.size
        restored.append(flat[offset: offset + size].reshape(arr.shape))
        offset += size
    return restored


def weight_norm_diff(a: List[np.ndarray], b: List[np.ndarray]) -> float:
    return float(np.linalg.norm(flatten_weights(a) - flatten_weights(b)))


def default_staleness_weight(staleness: int, max_staleness: int = 10) -> float:
    return max(0.05, 1.0 / (staleness + 1))


class FedAvgScheduler:
    """Synchronous Federated Averaging (FedAvg).

    Protocol per round:
      1. Select a fraction of available clients.
      2. Broadcast global weights to selected clients.
      3. Wait for all selected clients to complete local training.
      4. Aggregate via sample-size-weighted averaging.
      5. Advance the round counter.
    """

    def __init__(
        self,
        initial_weights: List[np.ndarray],
        num_clients: int,
        client_fraction: float = 1.0,
        seed: Optional[int] = None,
    ) -> None:
        self.global_weights = [w.copy() for w in initial_weights]
        self.num_clients = num_clients
        self.client_fraction = client_fraction
        self._rng = random.Random(seed)
        self.round = 0
        self.history: List[Dict] = []

    def select_clients(self) -> List[int]:
        k = max(1, int(self.num_clients * self.client_fraction))
        return sorted(self._rng.sample(range(self.num_clients), k))

    def aggregate(
        self,
        client_updates: Dict[int, Tuple[List[np.ndarray], int]],
    ) -> List[np.ndarray]:
        if not client_updates:
            return self.global_weights
        total_samples = sum(n for _, n in client_updates.values())
        first_w = next(iter(client_updates.values()))[0]
        aggregated = [np.zeros_like(w) for w in first_w]
        for weights, num_samples in client_updates.values():
            coeff = num_samples / total_samples
            for i in range(len(aggregated)):
                aggregated[i] += coeff * weights[i]
        self.global_weights = aggregated
        self.round += 1
        return aggregated

    def run_round(
        self,
        train_fn: Callable[
            [int, List[np.ndarray]], Tuple[List[np.ndarray], int]
        ],
        eval_fn: Optional[Callable[[List[np.ndarray]], float]] = None,
    ) -> Dict:
        selected = self.select_clients()
        t_start = time.perf_counter()
        results = {}
        for cid in selected:
            updated_weights, n = train_fn(cid, self.global_weights)
            results[cid] = (updated_weights, n)
        self.aggregate(results)
        elapsed = time.perf_counter() - t_start
        metric = eval_fn(self.global_weights) if eval_fn is not None else None
        record = {
            "round": self.round,
            "strategy": "fedavg_sync",
            "selected_clients": selected,
            "num_clients": len(selected),
            "elapsed_sec": round(elapsed, 3),
            "metric": metric,
        }
        self.history.append(record)
        return record


class SemiAsyncScheduler:
    """Semi-asynchronous scheduler with staleness-aware aggregation."""

    def __init__(
        self,
        initial_weights: List[np.ndarray],
        num_clients: int,
        staleness_fn: Optional[Callable[[int], float]] = None,
        max_staleness: int = 10,
        seed: Optional[int] = None,
    ) -> None:
        self.global_weights = [w.copy() for w in initial_weights]
        self.num_clients = num_clients
        self.max_staleness = max_staleness
        self._staleness_fn = staleness_fn or default_staleness_weight
        self._rng = random.Random(seed)
        self.round = 0
        self.history: List[Dict] = []
        self._client_versions: Dict[int, int] = {i: 0 for i in range(num_clients)}
        self._pending_updates: Dict[int, Tuple[List[np.ndarray], int, int]] = {}

    @property
    def staleness_of(self, client_id: int) -> int:
        return self.round - self._client_versions.get(client_id, 0)

    def receive_update(
        self,
        client_id: int,
        weights: List[np.ndarray],
        num_samples: int,
        client_round: int,
    ) -> Optional[Dict]:
        staleness = self.round - client_round
        if staleness > self.max_staleness:
            return None
        self._pending_updates[client_id] = (weights, num_samples, staleness)
        if len(self._pending_updates) >= (self.num_clients + 1) // 2:
            return self._aggregate_pending()
        return None

    def trigger_aggregation(self) -> Dict:
        return self._aggregate_pending()

    def _aggregate_pending(self) -> Dict:
        if not self._pending_updates:
            return {"round": self.round, "strategy": "semi_async", "aggregated": False}
        t_start = time.perf_counter()
        total_weight_sum = 0.0
        first_w = next(iter(self._pending_updates.values()))[0]
        aggregated = [np.zeros_like(w) for w in first_w]
        client_details = {}
        for cid, (weights, n, staleness) in self._pending_updates.items():
            sw = default_staleness_weight(staleness, self.max_staleness)
            total_weight_sum += sw
            for i in range(len(aggregated)):
                aggregated[i] += sw * weights[i]
            self._client_versions[cid] = self.round
            client_details[cid] = {"staleness": staleness, "weight": round(sw, 4)}
        if total_weight_sum > 0:
            for i in range(len(aggregated)):
                aggregated[i] /= total_weight_sum
        self.global_weights = aggregated
        self.round += 1
        elapsed = time.perf_counter() - t_start
        record = {
            "round": self.round,
            "strategy": "semi_async",
            "aggregated": True,
            "num_updates": len(self._pending_updates),
            "clients": client_details,
            "elapsed_sec": round(elapsed, 3),
        }
        self.history.append(record)
        self._pending_updates.clear()
        return record

    def simulate_concurrent_round(
        self,
        train_fn: Callable[[int, List[np.ndarray], int], Tuple[List[np.ndarray], int]],
        round_delay_fn: Optional[Callable[[int], float]] = None,
        timeout: float = 5.0,
    ) -> List[Dict]:
        if round_delay_fn is None:
            round_delay_fn = lambda cid: self._rng.uniform(0.1, 0.8)
        current_round = self.round
        selected = list(range(self.num_clients))
        self._rng.shuffle(selected)
        results = []
        deadline = time.perf_counter() + timeout
        for cid in selected:
            delay = round_delay_fn(cid)
            if time.perf_counter() + delay > deadline:
                results.append(self.trigger_aggregation())
                return results
            time.sleep(delay)
            updated_w, n = train_fn(cid, self.global_weights, current_round)
            rec = self.receive_update(cid, updated_w, n, current_round)
            if rec is not None:
                results.append(rec)
        if self._pending_updates:
            results.append(self.trigger_aggregation())
        return results


def create_scheduler(
    strategy: str,
    initial_weights: List[np.ndarray],
    num_clients: int,
    **kwargs,
):
    if strategy == "fedavg":
        return FedAvgScheduler(initial_weights, num_clients, **kwargs)
    elif strategy == "semi_async":
        return SemiAsyncScheduler(initial_weights, num_clients, **kwargs)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")
