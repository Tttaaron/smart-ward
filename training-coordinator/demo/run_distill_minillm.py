# MiniLLM reverse-KL vs Hinton forward-KL distillation demo.
#
# References:
#   MiniLLM: Gu et al. ICLR 2024, arXiv:2306.08543
#   Hinton KD: Hinton, Vinyals, Dean, 2015, arXiv:1503.02531
#
# L_reverseKL = E_q[ log q - log p_T ]  (mode-seeking, MiniLLM)
# L_forwardKL = T^2 * CE(p_T, q_T)      (classic KD, Hinton)
#
# Four routes on the SAME eval set:
#   A. teacher (large capacity)
#   B. student distilled with reverse KL (MiniLLM)
#   C. student distilled with forward KL (Hinton)
#   D. student trained from scratch (baseline)
#
# Usage:
#   python demo/run_distill_minillm.py
#   python demo/run_distill_minillm.py --data mnist

import argparse
import hashlib
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, recall_score, f1_score

SEED = 42
np.random.seed(SEED)

DATASET_VERSION = "synthetic-784-v1"
TEACHER_HIDDEN = 256
STUDENT_HIDDEN = 32
EPOCHS_TEACHER = 10
EPOCHS_STUDENT = 2
EPOCHS_DISTILL = 6
BATCH_SIZE = 128
LR = 0.01
TEMPERATURE = 2.0


def softmax(z, temperature=1.0):
    z = z / temperature
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


class MLP:
    # Two-layer MLP with ReLU (framework-agnostic, numpy).

    def __init__(self, input_dim, hidden, output_dim):
        rng = np.random.RandomState(SEED)
        scale = 1.0 / np.sqrt(input_dim)
        self.W1 = rng.uniform(-scale, scale, (hidden, input_dim)).astype(np.float32)
        self.b1 = np.zeros(hidden, dtype=np.float32)
        scale2 = 1.0 / np.sqrt(hidden)
        self.W2 = rng.uniform(-scale2, scale2, (output_dim, hidden)).astype(np.float32)
        self.b2 = np.zeros(output_dim, dtype=np.float32)

    def forward(self, x):
        h1 = np.maximum(0, x.dot(self.W1.T) + self.b1)
        logits = h1.dot(self.W2.T) + self.b2
        return logits, h1

    def predict(self, x):
        logits, _ = self.forward(x)
        return logits.argmax(axis=1)

    def weights(self):
        return [self.W1, self.b1, self.W2, self.b2]

    def hash(self):
        h = hashlib.sha256()
        for w in self.weights():
            h.update(np.ascontiguousarray(w).tobytes())
        return h.hexdigest()[:16]

    def apply_sgd(self, dW1, db1, dW2, db2, lr):
        self.W1 -= lr * dW1
        self.b1 -= lr * db1
        self.W2 -= lr * dW2
        self.b2 -= lr * db2


def synthetic_data(per_class=800, n_classes=10, dim=784, noise=5.0):
    # Class centroids + overlap noise -> teacher can fit, small student struggles.
    rng = np.random.RandomState(SEED)
    centroids = rng.randn(n_classes, dim).astype(np.float32)
    xs, ys = [], []
    for c in range(n_classes):
        xs.append(centroids[c] + noise * rng.randn(per_class, dim).astype(np.float32))
        ys.append(np.full(per_class, c, dtype=np.int64))
    return np.vstack(xs), np.concatenate(ys)


def load_data(source="synthetic"):
    if source == "mnist":
        try:
            from sklearn.datasets import fetch_openml
            print("[data] Loading MNIST...")
            X, y = fetch_openml("mnist_784", version=1, return_X_y=True,
                                as_frame=False, parser="pandas")
            y = y.astype(np.int64)
            n = int(X.shape[0] * 0.2)
            idx = np.random.permutation(X.shape[0])[:n]
            X, y = X[idx], y[idx]
            X = X.astype(np.float32) / 255.0
            global DATASET_VERSION
            DATASET_VERSION = "mnist-784-v1-0.2sub"
        except Exception as exc:
            print(f"[data] MNIST unavailable ({exc}); falling back to synthetic")
            X, y = synthetic_data()
    else:
        print("[data] Generating synthetic 10-class data (784 dims)...")
        X, y = synthetic_data()

    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, random_state=SEED)
    print(f"[data] train={X_tr.shape[0]} test={X_te.shape[0]} source={source}")
    return X_tr, y_tr, X_te, y_te


def train_supervised(model, X, y, epochs, lr, batch_size):
    # Standard cross-entropy training.
    n = X.shape[0]
    for ep in range(epochs):
        idx = np.random.permutation(n)
        total_loss = 0.0
        steps = 0
        for s in range(0, n, batch_size):
            bi = idx[s:s + batch_size]
            xb, yb = X[bi], y[bi]
            logits, h1 = model.forward(xb)
            probs = softmax(logits, 1.0) + 1e-12
            bs = xb.shape[0]
            grad = probs.copy()
            grad[np.arange(bs), yb] -= 1.0
            grad /= bs
            dW2 = grad.T.dot(h1)
            db2 = grad.sum(axis=0)
            dh1 = grad.dot(model.W2)
            dh1 *= (h1 > 0)
            dW1 = dh1.T.dot(xb)
            db1 = dh1.sum(axis=0)
            model.apply_sgd(dW1, db1, dW2, db2, lr)
            total_loss += -np.log(probs[np.arange(bs), yb]).mean()
            steps += 1
        print(f"    epoch {ep+1}/{epochs}  ce_loss={total_loss/steps:.4f}")


def train_reverse_kl(student, teacher, X, epochs, lr, batch_size, temperature):
    # MiniLLM: minimize reverse KL from student q to teacher p_T.
    #   L = E_q[ log q - log p_T ]
    # Exact gradient for a small label space:
    #   dL/dz = q * ((log q - log p_T) - E_q[log q - log p_T])
    n = X.shape[0]
    for ep in range(epochs):
        idx = np.random.permutation(n)
        total_loss = 0.0
        steps = 0
        for s in range(0, n, batch_size):
            bi = idx[s:s + batch_size]
            xb = X[bi]
            logits_s, h1 = student.forward(xb)
            logits_t, _ = teacher.forward(xb)
            q = softmax(logits_s, 1.0) + 1e-12
            p = softmax(logits_t, temperature) + 1e-12
            log_q = np.log(q)
            log_p = np.log(p)
            rkl = (q * (log_q - log_p)).sum(axis=1)
            total_loss += rkl.mean()
            term = q * (log_q - log_p)
            g = term - q * term.sum(axis=1, keepdims=True)
            bs = xb.shape[0]
            g = np.clip(g, -3.0, 3.0) / bs
            dW2 = g.T.dot(h1)
            db2 = g.sum(axis=0)
            dh1 = g.dot(student.W2)
            dh1 *= (h1 > 0)
            dW1 = dh1.T.dot(xb)
            db1 = dh1.sum(axis=0)
            student.apply_sgd(dW1, db1, dW2, db2, lr)
            steps += 1
        print(f"    epoch {ep+1}/{epochs}  reverse_kl={total_loss/steps:.4f}")


def train_forward_kl(student, teacher, X, epochs, lr, batch_size, temperature):
    # Hinton KD: minimize T^2 * CE(p_T, q_T) (forward KL).
    # Gradient wrt student logits z_s: T * (q_T - p_T).
    n = X.shape[0]
    for ep in range(epochs):
        idx = np.random.permutation(n)
        total_loss = 0.0
        steps = 0
        for s in range(0, n, batch_size):
            bi = idx[s:s + batch_size]
            xb = X[bi]
            logits_s, h1 = student.forward(xb)
            logits_t, _ = teacher.forward(xb)
            q_t = softmax(logits_s, temperature) + 1e-12
            p_t = softmax(logits_t, temperature) + 1e-12
            # Numerically stable forward KL: sum p * log(p/q) with clipped ratio
            ratio = np.clip(p_t / q_t, 1e-12, 1e12)
            kl = (p_t * np.log(ratio)).sum(axis=1)
            total_loss += kl.mean()
            bs = xb.shape[0]
            g = np.clip(temperature * (q_t - p_t), -3.0, 3.0) / bs
            dW2 = g.T.dot(h1)
            db2 = g.sum(axis=0)
            dh1 = g.dot(student.W2)
            dh1 *= (h1 > 0)
            dW1 = dh1.T.dot(xb)
            db1 = dh1.sum(axis=0)
            student.apply_sgd(dW1, db1, dW2, db2, lr)
            steps += 1
        print(f"    epoch {ep+1}/{epochs}  forward_kl={total_loss/steps:.4f}")


def evaluate(model, X, y):
    preds = model.predict(X)
    return {
        "accuracy": round(float(accuracy_score(y, preds)), 4),
        "recall_macro": round(float(recall_score(y, preds, average="macro")), 4),
        "f1_macro": round(float(f1_score(y, preds, average="macro")), 4),
    }


def log_experiment(route, model, metrics, params):
    record = {
        "route": route,
        "model_version": route,
        "model_hash": model.hash(),
        "dataset_version": DATASET_VERSION,
        "metrics": metrics,
        "params": params,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    print(f"  [log] {json.dumps(record, ensure_ascii=False)}")
    return record


def main(source="synthetic"):
    print("=" * 64)
    print("  MiniLLM Reverse-KL vs Hinton Forward-KL Distillation")
    print("  teacher 256 -> student 32 | synthetic 784d, offline")
    print("=" * 64)

    X_tr, y_tr, X_te, y_te = load_data(source)

    print("")
    print("[teacher] training large model (stands in for 14B)...")
    teacher = MLP(X_tr.shape[1], TEACHER_HIDDEN, 10)
    train_supervised(teacher, X_tr, y_tr, EPOCHS_TEACHER, LR, BATCH_SIZE)
    metrics_t = evaluate(teacher, X_te, y_te)
    print(f"[teacher] {metrics_t}")
    log_experiment("teacher", teacher, metrics_t, {"hidden": TEACHER_HIDDEN})

    print("")
    print("[student baseline] train from scratch...")
    student_base = MLP(X_tr.shape[1], STUDENT_HIDDEN, 10)
    train_supervised(student_base, X_tr, y_tr, EPOCHS_STUDENT, LR, BATCH_SIZE)
    metrics_b = evaluate(student_base, X_te, y_te)
    print(f"[student baseline] {metrics_b}")
    log_experiment("student_baseline", student_base, metrics_b, {"hidden": STUDENT_HIDDEN})

    print("")
    print("[student distilled] reverse KL (MiniLLM)...")
    student_rev = MLP(X_tr.shape[1], STUDENT_HIDDEN, 10)
    train_reverse_kl(student_rev, teacher, X_tr, EPOCHS_DISTILL, LR, BATCH_SIZE, TEMPERATURE)
    metrics_r = evaluate(student_rev, X_te, y_te)
    print(f"[student reverse-KL] {metrics_r}")
    log_experiment("student_reverse_kl", student_rev, metrics_r,
                  {"hidden": STUDENT_HIDDEN, "temperature": TEMPERATURE})

    print("")
    print("[student distilled] forward KL (Hinton KD)...")
    student_fwd = MLP(X_tr.shape[1], STUDENT_HIDDEN, 10)
    train_forward_kl(student_fwd, teacher, X_tr, EPOCHS_DISTILL, LR, BATCH_SIZE, TEMPERATURE)
    metrics_f = evaluate(student_fwd, X_te, y_te)
    print(f"[student forward-KL] {metrics_f}")
    log_experiment("student_forward_kl", student_fwd, metrics_f,
                  {"hidden": STUDENT_HIDDEN, "temperature": TEMPERATURE})

    acc_t = metrics_t["accuracy"]
    acc_r = metrics_r["accuracy"]
    acc_f = metrics_f["accuracy"]
    acc_b = metrics_b["accuracy"]
    f1_t = metrics_t["f1_macro"]
    f1_r = metrics_r["f1_macro"]
    f1_f = metrics_f["f1_macro"]
    f1_b = metrics_b["f1_macro"]

    print("")
    print("=" * 64)
    print("  Four-route comparison (same eval set)")
    print("=" * 64)
    print(f"  A. teacher             acc={acc_t:.4f}  f1={f1_t:.4f}")
    print(f"  B. reverse-KL distill  acc={acc_r:.4f}  f1={f1_r:.4f}")
    print(f"  C. forward-KL distill  acc={acc_f:.4f}  f1={f1_f:.4f}")
    print(f"  D. baseline student    acc={acc_b:.4f}  f1={f1_b:.4f}")
    print(f"")
    print(f"  MiniLLM reverse-KL gain vs baseline (F1): {f1_r - f1_b:+.4f}")
    print(f"  Hinton forward-KL gain vs baseline (F1): {f1_f - f1_b:+.4f}")
    print(f"  Dataset version: {DATASET_VERSION}")
    print("  Logs contain model_hash + params + metrics (T5 evidence).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Distillation demo (MiniLLM reverse-KL vs Hinton KD)")
    parser.add_argument("--data", choices=["synthetic", "mnist"], default="synthetic",
                        help="synthetic (default, no network) or real MNIST")
    args = parser.parse_args()
    main(source=args.data)
