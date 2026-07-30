"""
Demo: FedAvg synchronous baseline with synthetic MNIST-like data.

Usage:
    python demo/run_fedavg.py

This verifies that the Federated Averaging aggregation loop converges
(increasing accuracy) over multiple rounds.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.scheduler import FedAvgScheduler
from src.models import mlp_mnist
from src.utils import (
    synthetic_client_data,
    simulate_local_training,
    evaluate_accuracy,
)

NUM_CLIENTS = 5
NUM_ROUNDS = 10
SAMPLES_PER_CLIENT = 128


def main():
    print("=" * 55)
    print("FedAvg Synchronous Baseline Demo")
    print("=" * 55)

    # Create synthetic IID data for each client
    clients_data = synthetic_client_data(
        NUM_CLIENTS, samples_per_client=SAMPLES_PER_CLIENT, seed=42
    )

    # Concatenate all client data for global eval
    all_x = np.concatenate([c[0] for c in clients_data])
    all_y = np.concatenate([c[1] for c in clients_data])

    # Initial model weights
    initial_weights = mlp_mnist()

    # Scheduler
    scheduler = FedAvgScheduler(
        initial_weights,
        num_clients=NUM_CLIENTS,
        client_fraction=1.0,
        seed=0,
    )

    # Eval function (global accuracy)
    def eval_fn(weights):
        return evaluate_accuracy(weights, all_x, all_y)

    # Baseline accuracy (random init)
    base_acc = eval_fn(initial_weights)
    print(f"\nInitial accuracy (random): {base_acc:.4f}")

    # Training loop
    print(f"\nRunning {NUM_ROUNDS} rounds with {NUM_CLIENTS} clients ...\n")
    for r in range(NUM_ROUNDS):

        def train_fn(cid, global_w):
            x_c, y_c = clients_data[cid]
            updated = simulate_local_training(
                global_w, x_c, y_c, lr=0.01, epochs=1
            )
            return updated, x_c.shape[0]

        record = scheduler.run_round(train_fn, eval_fn=eval_fn)
        print(
            f"  Round {record['round']:2d}  |  "
            f"clients: {record['num_clients']}  |  "
            f"acc: {record['metric']:.4f}  |  "
            f"took: {record['elapsed_sec']:.2f}s"
        )

    # Summary
    final_acc = eval_fn(scheduler.global_weights)
    print(f"\n{'─' * 55}")
    print(f"Baseline accuracy:  {base_acc:.4f}")
    print(f"Final accuracy:     {final_acc:.4f}")
    print(f"Improvement:        {final_acc - base_acc:+.4f}")
    print(f"{'─' * 55}")
    print("FedAvg demo completed successfully!")


if __name__ == "__main__":
    import numpy as np
    main()
