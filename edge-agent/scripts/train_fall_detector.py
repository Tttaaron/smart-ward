"""训练 ShuffleNetV2+SA 跌倒分类器（UR Fall Detection Dataset）。

训练完成后自动跑评测，输出准确率/召回率/F1 对比基线（规则回退 63.31%）。

用法::

    python edge-agent/scripts/train_fall_detector.py --dataset "UR_fall_detection_dataset_cam0_rgb"

训练参数:
    --epochs 训练轮数（默认 30）
    --batch batch 大小（默认 32）
    --lr 学习率（默认 0.001）
    --stride 采样步长（默认 2，加速训练）
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
import torchvision.models as tv_models

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "edge-agent" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fall_detector import FallDetector, ShuffleNetV2SA
from eval_ur_fall import parse_labels, ground_truth_for_clip, compute_metrics


# ─── SA 通道注意力（与 FallDetector 一致）───

class SAChannelAttention(nn.Module):
    def __init__(self, channels: int, reduction: int = 8) -> None:
        super().__init__()
        self.fc1 = nn.Conv2d(channels, max(channels // reduction, 1), 1)
        self.fc2 = nn.Conv2d(max(channels // reduction, 1), channels, 1)

    def forward(self, x):
        b, c, _, _ = x.shape
        q = x.mean(dim=(2, 3), keepdim=True)
        k = x
        v = x
        attn = torch.softmax(
            (q * k).mean(dim=1, keepdim=True) / max(c**0.5, 1), dim=1)
        out = v * attn
        out = self.fc2(torch.relu(self.fc1(out)))
        return x + out


class ShuffleNetV2SA(nn.Module):
    """ShuffleNetV2 + SA 通道注意力，fall/non-fall 二分类。"""

    def __init__(self, num_classes: int = 2, pretrained: bool = True):
        super().__init__()
        base = tv_models.shufflenet_v2_x1_0(
            weights="DEFAULT" if pretrained else None)
        # 取 backbone 特征（去掉分类头）
        self.backbone = nn.Sequential(*list(base.children())[:-1])
        # SA 注意力
        self.sa = SAChannelAttention(1024)
        # 全局池化 + 分类头
        self.gap = nn.AdaptiveAvgPool2d(1)
        self.dropout = nn.Dropout(0.3)
        self.fc = nn.Linear(1024, num_classes)

    def forward(self, x):
        x = self.backbone(x)
        x = self.sa(x)
        x = self.gap(x).flatten(1)
        x = self.dropout(x)
        return self.fc(x)


# ─── 数据集 ───

class URFallDataset(Dataset):
    """UR Fall Detection 帧序列数据集。"""

    def __init__(self, dataset_dir: Path, labels: Dict[str, List[Tuple[int, int]]],
                 clip_names: List[str], transform, target_size=(224, 224),
                 stride: int = 1):
        self.samples: List[Tuple[str, int, int]] = []  # (clip, frame_1idx, label)
        self.transform = transform
        self.target_size = target_size
        self.dataset_dir = dataset_dir

        for clip_name in clip_names:
            clip_dir = dataset_dir / clip_name
            fall_events = labels.get(clip_name, [])
            total = len(list(clip_dir.glob("*.png")))
            gt = ground_truth_for_clip(clip_name, total, fall_events)
            for frame_idx in range(0, total, stride):
                self.samples.append((clip_name, frame_idx + 1, gt[frame_idx]))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        clip_name, frame_1idx, label = self.samples[idx]
        path = self.dataset_dir / clip_name / f"{clip_name}-{frame_1idx:03d}.png"
        img = cv2.imread(str(path))
        if img is None:
            img = np.zeros((224, 224, 3), dtype=np.uint8)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = self.transform(img)
        return img, label


# ─── 训练 ───

def train(dataset_dir: Path, epochs: int, batch_size: int,
          lr: float, stride: int, output: Path) -> None:
    labels = parse_labels(dataset_dir / "labels.txt")
    clip_dirs = sorted([d.name for d in dataset_dir.iterdir()
                        if d.is_dir() and d.name.endswith("-cam0-rgb")])

    # 70:30 训练/测试划分（按片段，不混合帧）
    split = int(len(clip_dirs) * 0.7)
    train_clips = clip_dirs[:split]
    test_clips = clip_dirs[split:]

    print(f"训练片段: {len(train_clips)}  测试片段: {len(test_clips)}")
    print(f"采样步长: {stride}")

    transform = transforms.Compose([
        transforms.ToPILImage(),
        transforms.Resize((224, 224)),
        transforms.RandomHorizontalFlip(p=0.3),
        transforms.RandomRotation(5),
        transforms.ColorJitter(brightness=0.1, contrast=0.1),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    val_transform = transforms.Compose([
        transforms.ToPILImage(),
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    train_dataset = URFallDataset(dataset_dir, labels, train_clips,
                                  transform, stride=stride)
    test_dataset = URFallDataset(dataset_dir, labels, test_clips,
                                 val_transform, stride=1)

    train_loader = DataLoader(train_dataset, batch_size=batch_size,
                              shuffle=True, num_workers=0)
    test_loader = DataLoader(test_dataset, batch_size=batch_size,
                             shuffle=False, num_workers=0)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"设备: {device}  训练集: {len(train_dataset)} 帧  测试集: {len(test_dataset)} 帧")

    model = ShuffleNetV2SA(num_classes=2, pretrained=True).to(device)
    criterion = nn.CrossEntropyLoss(weight=torch.tensor([1.0, 3.0]).to(device))
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    best_acc = 0.0
    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0
        correct = 0
        total = 0
        t0 = time.time()
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * images.size(0)
            _, preds = torch.max(outputs, 1)
            correct += (preds == labels).sum().item()
            total += labels.size(0)
        scheduler.step()

        train_acc = correct / total if total else 0
        train_loss_avg = train_loss / total if total else 0

        # 测试
        model.eval()
        test_correct = 0
        test_total = 0
        with torch.no_grad():
            for images, labels in test_loader:
                images, labels = images.to(device), labels.to(device)
                outputs = model(images)
                _, preds = torch.max(outputs, 1)
                test_correct += (preds == labels).sum().item()
                test_total += labels.size(0)
        test_acc = test_correct / test_total if test_total else 0
        elapsed = time.time() - t0

        if test_acc > best_acc:
            best_acc = test_acc
            torch.save(model.state_dict(), str(output))
            print(f"  Epoch {epoch:2d}: train_loss={train_loss_avg:.4f} "
                  f"train_acc={train_acc:.2%} test_acc={test_acc:.2%} "
                  f"(best, saved) ({elapsed:.1f}s)")
        else:
            print(f"  Epoch {epoch:2d}: train_loss={train_loss_avg:.4f} "
                  f"train_acc={train_acc:.2%} test_acc={test_acc:.2%} "
                  f"({elapsed:.1f}s)")

    print(f"\n训练完成。最佳测试准确率: {best_acc:.2%}")
    print(f"权重已保存: {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description="训练 ShuffleNetV2+SA 跌倒分类器")
    parser.add_argument("--dataset", required=True, help="数据集根目录")
    parser.add_argument("--epochs", type=int, default=30, help="训练轮数")
    parser.add_argument("--batch", type=int, default=32, help="batch 大小")
    parser.add_argument("--lr", type=float, default=0.001, help="学习率")
    parser.add_argument("--stride", type=int, default=2, help="训练采样步长")
    parser.add_argument("--output", default=None,
                        help="权重输出路径（默认 edge-agent/models/shufflenetv2-sa-fall.pt）")
    args = parser.parse_args()

    dataset_dir = Path(args.dataset)
    if not dataset_dir.exists():
        print(f"数据集目录不存在: {dataset_dir}")
        return 2

    output = Path(args.output) if args.output else (
        REPO_ROOT / "edge-agent" / "models" / "shufflenetv2-sa-fall.pt")
    output.parent.mkdir(parents=True, exist_ok=True)

    train(dataset_dir, args.epochs, args.batch, args.lr, args.stride, output)

    # 训练完成后自动跑评测
    print("\n" + "=" * 60)
    print("训练完成，自动运行评测...")
    print("=" * 60)
    os.environ["FALL_MODEL_PATH"] = str(output)
    from eval_ur_fall import run as eval_run
    eval_run(dataset_dir, output.with_suffix(".json"), conf_threshold=0.5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
