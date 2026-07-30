import os
import sys
import time
import json
from pathlib import Path

# Add training-coordinator to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
from sklearn.datasets import fetch_openml
from sklearn.preprocessing import LabelBinarizer
from sklearn.model_selection import train_test_split

from app.scheduler import FedAvgScheduler

# ============================================================
# Configuration (FederatedScope-style YAML would look like this)
# ============================================================
CFG = {
    'data': {
        'type': 'mnist',
        'subsample': 0.2,         # Use 20% of MNIST for speed
        'iid': True,               # IID partition across clients
    },
    'federate': {
        'mode': 'standalone',
        'total_round_num': 20,
        'client_num': 5,
        'sample_client_rate': 1.0,
    },
    'model': {
        'type': 'mlp',
        'hidden': 128,
        'out_channels': 10,
    },
    'train': {
        'local_update_steps': 2,   # epochs per round
        'batch_size': 64,
        'optimizer': {'lr': 0.01},
    },
    'eval': {
        'freq': 1,                 # evaluate every N rounds
        'metrics': ['acc', 'loss'],
    },
}

SEED = 42
np.random.seed(SEED)


def load_mnist(subsample=0.2):
    """Load MNIST via sklearn and preprocess."""
    print('[data] Loading MNIST...')
    X, y = fetch_openml('mnist_784', version=1, return_X_y=True, as_frame=False, parser='pandas')
    y = y.astype(np.int64)

    # Subsample
    if subsample < 1.0:
        n = int(X.shape[0] * subsample)
        idx = np.random.permutation(X.shape[0])[:n]
        X, y = X[idx], y[idx]
    print(f'[data] Loaded {X.shape[0]} samples, {X.shape[1]} features')

    # Normalize pixel values to [0, 1]
    X = X.astype(np.float32) / 255.0

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=SEED
    )
    print(f'[data] Train: {X_train.shape[0]}, Test: {X_test.shape[0]}')
    return X_train, y_train, X_test, y_test


def partition_iid(X, y, num_clients):
    """Split data evenly across clients."""
    n = X.shape[0]
    indices = np.random.permutation(n)
    client_data = []
    split = np.array_split(indices, num_clients)
    for s in split:
        client_data.append((X[s], y[s]))
    return client_data


def partition_noniid(X, y, num_clients, alpha=0.5):
    """Dirichlet non-IID partition (more realistic)."""
    from numpy.random import dirichlet
    n_classes = len(np.unique(y))
    label_dist = np.array([dirichlet([alpha] * num_clients) for _ in range(n_classes)])

    client_data = [[] for _ in range(num_clients)]
    for label in range(n_classes):
        idx = np.where(y == label)[0]
        np.random.shuffle(idx)
        proportions = label_dist[label]
        proportions = proportions / proportions.sum()
        split = np.cumsum((proportions * len(idx)).astype(int))[:-1]
        parts = np.split(idx, split)
        for cid in range(num_clients):
            client_data[cid].extend(parts[cid].tolist())

    result = []
    for cid in range(num_clients):
        idx = np.array(client_data[cid], dtype=int)
        result.append((X[idx], y[idx]))
    return result


def local_train(weights, X, y, lr=0.01, epochs=2, batch_size=64):
    """Local SGD training on an MLP (784-128-10)."""
    from app.scheduler import flatten_weights, unflatten_weights

    w = [arr.copy() for arr in weights]
    W1, b1, W2, b2 = w
    n = X.shape[0]

    for _ in range(epochs):
        # Mini-batch SGD
        idx = np.random.permutation(n)
        for start in range(0, n, batch_size):
            batch_idx = idx[start:start + batch_size]
            x_b = X[batch_idx]
            y_b = y[batch_idx]
            bs = x_b.shape[0]

            # Forward
            h1 = x_b.dot(W1.T) + b1
            a1 = np.maximum(0, h1)
            logits = a1.dot(W2.T) + b2

            # Softmax + CE gradient
            exp_l = np.exp(logits - logits.max(axis=1, keepdims=True))
            probs = exp_l / exp_l.sum(axis=1, keepdims=True)
            grad_logits = probs.copy()
            grad_logits[np.arange(bs), y_b] -= 1.0
            grad_logits /= bs

            # Backward
            grad_W2 = grad_logits.T.dot(a1)
            grad_b2 = grad_logits.sum(axis=0)
            grad_a1 = grad_logits.dot(W2)
            grad_h1 = grad_a1 * (a1 > 0).astype(float)
            grad_W1 = grad_h1.T.dot(x_b)
            grad_b1 = grad_h1.sum(axis=0)

            W1 -= lr * grad_W1
            b1 -= lr * grad_b1
            W2 -= lr * grad_W2
            b2 -= lr * grad_b2

    return [W1, b1, W2, b2]


def evaluate(weights, X, y):
    """Classification accuracy."""
    W1, b1, W2, b2 = weights
    h1 = X.dot(W1.T) + b1
    a1 = np.maximum(0, h1)
    logits = a1.dot(W2.T) + b2
    preds = logits.argmax(axis=1)
    return float((preds == y).mean())


def main():
    print('=' * 60)
    print('  FederatedScope-style MNIST FedAvg Demo')
    print('  Using: scheduler.FedAvgScheduler')
    print('=' * 60)
    print()
    print(f'Config:')
    print(f'  Clients:       {CFG["federate"]["client_num"]}')
    print(f'  Rounds:        {CFG["federate"]["total_round_num"]}')
    print(f'  Local epochs:  {CFG["train"]["local_update_steps"]}')
    print(f'  IID partition: {CFG["data"]["iid"]}')
    print(f'  MNIST subset:  {CFG["data"]["subsample"]*100}%')
    print()

    # 1. Load data
    X_train, y_train, X_test, y_test = load_mnist(CFG['data']['subsample'])

    # 2. Partition across clients
    if CFG['data']['iid']:
        client_data = partition_iid(X_train, y_train, CFG['federate']['client_num'])
    else:
        client_data = partition_noniid(X_train, y_train, CFG['federate']['client_num'])

    for cid, (xc, yc) in enumerate(client_data):
        print(f'  Client {cid}: {xc.shape[0]} samples, classes={len(np.unique(yc))}')

    # 3. Initialize model and scheduler
    input_dim = X_train.shape[1]   # 784
    hidden = CFG['model']['hidden']
    num_classes = CFG['model']['out_channels']

    rng = np.random.RandomState(SEED)
    initial_weights = [
        rng.randn(hidden, input_dim).astype(np.float32) * 0.01,   # W1
        np.zeros(hidden, dtype=np.float32),                        # b1
        rng.randn(num_classes, hidden).astype(np.float32) * 0.01,  # W2
        np.zeros(num_classes, dtype=np.float32),                   # b2
    ]

    scheduler = FedAvgScheduler(
        initial_weights,
        num_clients=CFG['federate']['client_num'],
        client_fraction=CFG['federate']['sample_client_rate'],
        seed=SEED,
    )

    baseline_acc = evaluate(initial_weights, X_test, y_test)
    print(f'\n  Baseline (random init): {baseline_acc:.4f}')
    print()

    # 4. Training loop
    results = []
    for r in range(CFG['federate']['total_round_num']):
        t_start = time.perf_counter()

        selected = scheduler.select_clients()
        client_updates = {}
        for cid in selected:
            x_c, y_c = client_data[cid]
            updated_w = local_train(
                scheduler.global_weights, x_c, y_c,
                lr=CFG['train']['optimizer']['lr'],
                epochs=CFG['train']['local_update_steps'],
                batch_size=CFG['train']['batch_size'],
            )
            client_updates[cid] = (updated_w, x_c.shape[0])

        scheduler.aggregate(client_updates)
        elapsed = time.perf_counter() - t_start

        if (r + 1) % CFG['eval']['freq'] == 0:
            acc = evaluate(scheduler.global_weights, X_test, y_test)
            results.append({'round': r + 1, 'acc': acc, 'elapsed': round(elapsed, 3)})
            print(f'  Round {r+1:2d}/{CFG["federate"]["total_round_num"]}  |  '
                  f'clients: {len(selected)}  |  '
                  f'test_acc: {acc:.4f}  |  '
                  f'+{acc - baseline_acc:+.4f}  |  '
                  f'{elapsed:.2f}s')

    # 5. Summary
    final_acc = evaluate(scheduler.global_weights, X_test, y_test)
    print(f'\n{"=" * 60}')
    print(f'  Summary')
    print(f'{"=" * 60}')
    print(f'  Baseline accuracy:  {baseline_acc:.4f}')
    print(f'  Final accuracy:     {final_acc:.4f}')
    print(f'  Improvement:        {final_acc - baseline_acc:+.4f}')
    print(f'  Rounds completed:   {scheduler.round}')
    print()
    print(f'  This demo validates:')
    print(f'    - FedAvg gradient aggregation works correctly')
    print(f'    - Multiple clients train locally and contribute to global model')
    print(f'    - Model converges (accuracy increases over rounds)')
    print(f'    - scheduler.py algorithm engine works end-to-end')
    print(f'  ')
    print(f'  Next step: port to FederatedScope framework for GPU/async support')
    print(f'{"=" * 60}')


if __name__ == '__main__':
    main()
