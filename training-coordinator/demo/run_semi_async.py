"""
Demo: Semi-asynchronous staleness-weighted scheduling.

Usage:
    python demo/run_semi_async.py

Simulates clients with heterogeneous compute speeds (variable delays)
and demonstrates staleness-aware aggregation.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.scheduler import SemiAsyncScheduler, default_staleness_weight
from src.models import mlp_mnist
from src.utils import (
    synthetic_client_data,
    simulate_local_training,
    evaluate_accuracy,
)

NUM_CLIENTS = 5
NUM_ROUNDS = 8
SAMPLES_PER_CLIENT = 128


def main():
    print("=" * 55)
    print("Semi-asynchronous Staleness-weighted Demo")
    print("=" * 55)

    # Create synthetic IID data
    clients_data = synthetic_client_data(
        NUM_CLIENTS, samples_per_client=SAMPLES_PER_CLIENT, seed=42
    )
    all_x = np.concatenate([c[0] for c in clients_data])
    all_y = np.concatenate([c[1] for c in clients_data])

    initial_weights = mlp_mnist()

    scheduler = SemiAsyncScheduler(
        initial_weights,
        num_clients=NUM_CLIENTS,
        max_staleness=5,
        seed=0,
    )

    def eval_fn(weights):
        return evaluate_accuracy(weights, all_x, all_y)

    base_acc = eval_fn(initial_weights)
    print(f"\nInitial accuracy (random): {base_acc:.4f}")

    # Simulate heterogeneous clients:
    #   client 0-1: fast  (0.05s - 0.15s)
    #   client 2-3: medium (0.2s - 0.5s)
    #   client 4  : slow  (0.6s - 1.2s) -- potential straggler
    def delay_fn(cid):
        rng = scheduler._rng
        if cid < 2:
            return rng.uniform(0.05, 0.15)
        elif cid < 4:
            return rng.uniform(0.2, 0.5)
        else:
            return rng.uniform(0.6, 1.2)

    print(f"\nRunning {NUM_ROUNDS} rounds with heterogeneous delays ...\n")

    for r in range(NUM_ROUNDS):

        def train_fn(cid, global_w, client_round):
            x_c, y_c = clients_data[cid]
            updated = simulate_local_training(
                global_w, x_c, y_c, lr=0.01, epochs=1
            )
            return updated, x_c.shape[0]

        records = scheduler.simulate_concurrent_round(
            train_fn,
            round_delay_fn=delay_fn,
            timeout=3.0,
        )
        for rec in records:
            if rec.get("aggregated", True):
                acc = eval_fn(scheduler.global_weights)
                stalenesses = [
                    d["staleness"] for d in rec.get("clients", {}).values()
                ]
                print(
                    f"  Round {rec['round']:2d}  |  "
                    f"updates: {rec['num_updates']}  |  "
                    f"stale: {stalenesses}  |  "
                    f"acc: {acc:.4f}  |  "
                    f"took: {rec['elapsed_sec']:.2f}s"
                )

    final_acc = eval_fn(scheduler.global_weights)
    print(f"\n{'─' * 55}")
    print(f"Baseline accuracy:     {base_acc:.4f}")
    print(f"Final accuracy:        {final_acc:.4f}")
    print(f"Improvement:           {final_acc - base_acc:+.4f}")
    print(f"Total rounds executed: {scheduler.round}")
    print(f"{'─' * 55}")
    print("Semi-async demo completed successfully!")


if __name__ == "__main__":
    import numpy as np
    main()
