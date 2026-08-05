# UR Fall Detection Dataset 与跌倒评测说明

> 对应任务书方案：YOLOv8 检测 person + ShuffleNetV2+SA 跌倒二分类
> （论文在 UR Fall Detection Dataset 上 95.85%）

## 一、数据集来源

- 公开数据集：**UR Fall Detection Dataset**（Kwolek & Kepski, 2014），
  由波兰 Rzeszow 大学发布，包含 30 个跌倒片段（fall-01~30）与 40 个日常活动
  片段（adl-01~40），双 Kinect 相机（cam0/cam1）+ 加速度计。
- 本项目使用 **cam0 RGB 帧序列**（`*_cam0_rgb` 目录，PNG 帧）。
- 帧序列体积约数 GB，**不入版本库**（见 `.gitignore`）；评测前从公开渠道
  下载 `UR_fall_detection_dataset_cam0_rgb/` 目录并放在仓库根目录即可。
- 标签文件 `labels.txt`（片段名 + 跌倒起止帧，1-indexed）已随仓库跟踪，
  是评测 ground truth 的唯一来源。

## 二、评测命令（可复现）

```bash
# 规则基线（无权重，bbox 宽高比粗判）
python edge-agent/scripts/eval_ur_fall.py \
    --dataset "UR_fall_detection_dataset_cam0_rgb" --stride 1 --conf 0.6

# ShuffleNetV2+SA 神经判定（需训练权重，见训练脚本）
FALL_MODEL_PATH="edge-agent/models/shufflenetv2-sa-fall.pt" \
python edge-agent/scripts/eval_ur_fall.py \
    --dataset "UR_fall_detection_dataset_cam0_rgb" --stride 1 --conf 0.5
```

输出：控制台汇总 + `edge-agent/data/ur-fall-eval-report.json`（正式报告）。

## 三、指标口径（重要，答辩必须讲清）

- **帧级指标**：只对实际推理的帧计算（`--stride N` 跳过帧不参与），
  指标为准确率 / 精确率 / 召回率 / F1。
- **片段级指标**：fall 片段内任一方检测到 TP 即"检出"；adl 片段 FP=0 即
  "零误报"。临床告警语义按片段级理解。
- 注意：早期评测版本把 stride 跳过的帧记为 non-fall 参与指标计算，
  导致帧级召回率被腰斩（41.53%），**该口径已废弃**，正式报告以修复后为准。

## 四、当前评测结果（2026-08-05，ShuffleNetV2+SA 权重，CUDA）

| 口径 | 准确率 | 精确率 | 召回率 | F1 |
|---|---|---|---|---|
| 规则基线（stride=1） | 63.31% | - | 33.71% | 0.1505 |
| 神经判定（stride=1 全量 11936 帧） | **95.78%** | 78.45% | **77.50%** | 0.7797 |

- 片段级：fall 30/30 全部检出，adl 40/40 零误报（100%）。
- 帧级准确率 95.78% 与论文宣称 95.85% 一致。
- 帧级召回率 77.50% 与"逐帧精确时间戳"的严格口径对应；如需更高召回，
  可降阈值（--conf 0.4）或增加训练轮数，代价是误报增加。

## 五、证据文件

- 正式报告：`edge-agent/data/ur-fall-eval-report.json`（stride=1 全量）
- 对比存档：`docs/evidence/ur-fall-eval-*.json`（修复前后口径对比）
- 训练脚本：`edge-agent/scripts/train_fall_detector.py`
- 评测脚本：`edge-agent/scripts/eval_ur_fall.py`
- 检测器：`edge-agent/src/fall_detector.py`（ShuffleNetV2+SA，无权重时回退规则）
