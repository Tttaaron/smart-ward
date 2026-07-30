"""
Federated Learning Scheduler

Implements FedAvg synchronous baseline and semi-asynchronous
staleness-weighted scheduling for cloud-edge collaborative training.

Part of smart-ward cloud-edge collaborative system.
振鑫 (P4) - Collaborative training scheduler (scheduler.py)

Dependencies:
  - numpy (core computation)
"""

from __future__ import annotations

import random
import time
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np


# ------------------------------------------------------------------
# Weight helpers (framework-agnostic)
# ------------------------------------------------------------------

def flatten_weights(weights: List[np.ndarray]) -> np.ndarray:
    """Flatten a list of parameter arrays into a single 1-D array."""
    return np.concatenate([w.ravel() for w in weights])


def unflatten_weights(
    flat: np.ndarray, template: List[np.ndarray]
) -> List[np.ndarray]:
    """Restore a flat array back into the shape structure of *template*."""
    restored = []
    offset = 0
    for arr in template:
        size = arr.size
        restored.append(flat[offset : offset + size].reshape(arr.shape))
        offset += size
    return restored


def weight_norm_diff(a: List[np.ndarray], b: List[np.ndarray]) -> float:
    """L2 norm of the difference between two weight sets."""
    return float(np.linalg.norm(flatten_weights(a) - flatten_weights(b)))


# ------------------------------------------------------------------
# FedAvg - Synchronous baseline
# ------------------------------------------------------------------

class FedAvgScheduler:
    """Synchronous Federated Averaging scheduler.

    Protocol per round:
      1. Select a fraction of available clients.
      2. Broadcast global weights to selected clients.
      3. Wait for all selected clients to complete local training.
      4. Aggregate received updates via sample-size-weighted averaging.
      5. Advance the round counter.

    Parameters
    ----------
    initial_weights : List[np.ndarray]
        Initial global model parameters.
    num_clients : int
        Total number of clients in the system.
    client_fraction : float, optional
        Fraction of clients selected per round (default 1.0).
    seed : int, optional
        Random seed for reproducible client selection.
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

    # -- public API -------------------------------------------------

    def select_clients(self) -> List[int]:
        """Return a sorted list of client indices for the current round."""
        k = max(1, int(self.num_clients * self.client_fraction))
        return sorted(self._rng.sample(range(self.num_clients), k))

    def aggregate(
        self,
        client_updates: Dict[int, Tuple[List[np.ndarray], int]],
    ) -> List[np.ndarray]:
        """FedAvg: weighted average of client parameters by sample count.

        Args:
            client_updates: ``{client_id: (weights_list, num_samples)}``

        Returns:
            Updated global weights.
        """
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
        """Execute one complete round of FedAvg.

        Args:
            train_fn: ``(client_id, global_weights) -> (updated_weights, n)``
            eval_fn: Optional ``(global_weights) -> metric`` for logging.

        Returns:
            Dict with round metadata.
        """
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


# ------------------------------------------------------------------
# Semi-asynchronous staleness-weighted scheduling
# ------------------------------------------------------------------

def default_staleness_weight(staleness: int, max_staleness: int = 10) -> float:
    """Inverse-linear staleness weighting.

    A client that is ``staleness`` rounds behind the global version
    receives weight ``max(0.05, 1 / (staleness + 1))``.
    """
    return max(0.05, 1.0 / (staleness + 1))


class SemiAsyncScheduler:
    """Semi-asynchronous scheduler with staleness-aware aggregation.

    Unlike FedAvg, clients are **not** required to synchronize at a
    barrier.  The server accepts updates as they arrive and weights
    each contribution by a **staleness factor**: the number of global
    rounds the client's snapshot is behind the current global version.
    This tolerates stragglers while still penalising stale updates.

    Parameters
    ----------
    initial_weights : List[np.ndarray]
        Initial global model parameters.
    num_clients : int
        Total number of clients.
    staleness_fn : callable, optional
        ``(staleness) -> weight``.  Defaults to inverse-linear.
    max_staleness : int, optional
        Updates with staleness above this threshold are discarded.
    seed : int, optional
    """

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

        # Track the global version at which each client last contributed
        self._client_versions: Dict[int, int] = {
            i: 0 for i in range(num_clients)
        }
        # Buffer for in-flight updates in the same logical round
        self._pending_updates: Dict[
            int, Tuple[List[np.ndarray], int, int]
        ] = {}

    # -- public API -------------------------------------------------

    @property
    def staleness_of(self, client_id: int) -> int:
        """Return how many rounds behind *client_id* is."""
        return self.round - self._client_versions.get(client_id, 0)

    def receive_update(
        self,
        client_id: int,
        weights: List[np.ndarray],
        num_samples: int,
        client_round: int,
    ) -> Optional[Dict]:
        """Receive a client update and attempt aggregation.

        Args:
            client_id: Which client is reporting.
            weights: The locally trained weights.
            num_samples: Number of training samples used.
            client_round: The global round version this client trained on.

        Returns:
            A result dict if aggregation was triggered, else ``None``.
        """
        staleness = self.round - client_round

        if staleness > self.max_staleness:
            return None  # Discard overly stale updates

        self._pending_updates[client_id] = (weights, num_samples, staleness)

        # Trigger when we have heard from >= ceil(num_clients/2) clients
        if len(self._pending_updates) >= (self.num_clients + 1) // 2:
            return self._aggregate_pending()
        return None

    def trigger_aggregation(self) -> Dict:
        """Force aggregation of all pending updates (e.g. on timeout)."""
        return self._aggregate_pending()

    def _aggregate_pending(self) -> Dict:
        """Aggregate all pending updates with staleness weighting."""
        if not self._pending_updates:
            return {
                "round": self.round,
                "strategy": "semi_async",
                "aggregated": False,
                "reason": "no_pending_updates",
            }

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
            client_details[cid] = {
                "staleness": staleness,
                "weight": round(sw, 4),
            }

        # Normalise
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
        train_fn: Callable[
            [int, List[np.ndarray], int], Tuple[List[np.ndarray], int]
        ],
        round_delay_fn: Optional[Callable[[int], float]] = None,
        timeout: float = 5.0,
    ) -> List[Dict]:
        """Simulate one round of semi-asynchronous training.

        All clients train concurrently (simulated sequentially here
        for reproducibility) with variable latency.
        Aggregation triggers when enough clients report or a timeout.

        Args:
            train_fn: ``(cid, global_weights, client_round) -> (weights, n)``
            round_delay_fn: ``(cid) -> seconds`` simulating compute/delay.
            timeout: Max seconds before force-aggregating.

        Returns:
            List of record dicts.
        """
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
                rec = self.trigger_aggregation()
                results.append(rec)
                return results

            time.sleep(delay)
            updated_w, n = train_fn(cid, self.global_weights, current_round)
            rec = self.receive_update(cid, updated_w, n, current_round)
            if rec is not None:
                results.append(rec)

        if self._pending_updates:
            results.append(self.trigger_aggregation())

        return results


# ------------------------------------------------------------------
# Convenience factory
# ------------------------------------------------------------------

def create_scheduler(
    strategy: str,
    initial_weights: List[np.ndarray],
    num_clients: int,
    **kwargs,
):
    """Factory: return a ``FedAvgScheduler`` or ``SemiAsyncScheduler``.

    Args:
        strategy: ``"fedavg"`` or ``"semi_async"``.
        initial_weights: Initial model parameters.
        num_clients: Number of clients.
        **kwargs: Passed through to the scheduler constructor.
    """
    if strategy == "fedavg":
        return FedAvgScheduler(initial_weights, num_clients, **kwargs)
    elif strategy == "semi_async":
        return SemiAsyncScheduler(initial_weights, num_clients, **kwargs)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")
