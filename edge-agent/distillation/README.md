# Qwen2.5-1.5B-Ward-v4 训练与评测

当前推荐产物为 `Qwen2.5-1.5B-Ward-v4-Q6_K`。旧 v2/Q4_K_M 与旧严格格式评分报告保留在 `archive/v2-strict-parser/`，仅用于历史追溯，不再作为当前验收结论。

## 方法概述

该模型以 `Qwen2.5-1.5B-Instruct` 为底座，结合两类训练信号：

1. Qwen2.5-14B 教师生成并经项目规则校准的智慧病房任务数据；
2. GSM8K 训练数据和 MBPP 派生代码输出推理数据，用于缓解窄领域训练造成的通用能力遗忘。

v4.1 混合训练集共 5,000 条：病房任务 2,000 条、GSM8K 1,500 条、MBPP 派生代码推理 1,500 条。训练完成后融合病房 LoRA 与通用能力 LoRA，最终选择病房权重 `0.50`、通用权重 `0.75`，合并并量化为 Q6_K GGUF。

固定 600 题评测集未用于训练或融合系数选择。构建器检查到与冻结 GSM8K 测试题的精确重合数为 0，CRUXEval-O 未作为训练来源。

## 关键脚本

- `generate_teacher_data.py`：生成 14B 教师响应数据。
- `prepare_student_data.py`：构造学生训练数据。
- `build_mixed_v4.py`：构建 v4.1 混合训练集。
- `train_lora.py`：训练 LoRA。
- `combine_lora_adapters.py`：按权重融合病房与通用 LoRA。
- `merge_lora.py`：合并底座与 LoRA。
- `evaluate_general_retention.py`：统一评测 GSM8K、CRUXEval-O 与 BBH。
- `rescore_general_retention_v2.py`：使用相同宽松语义抽取器修正旧格式偏差。
- `evaluate_model.py`：评测病房任务。
- `build_ward50_eval.py`：构建新增 50 条病房测试。

## 最终模型元数据

```text
模型：Qwen2.5-1.5B-Ward-v4-Q6_K
文件：qwen2.5-1.5b-ward-v4-q6_k.gguf
大小：1,272,739,456 bytes（1.273 GB / 1213.78 MiB）
量化：Q6_K
SHA-256：f7ffc9751378a8f67bed3a6a8872f0f20c40b48cc4223b5560e225bd547ca8a0
```

GGUF 权重不存放在普通 Git 提交中，下载链接应填写在 `edge-agent/models/qwen2.5-1.5b-ward-distilled-v4/README.md`。

## 通用能力：固定 600 题

所有模型使用同一题库哈希、temperature 0 和同一宽松语义答案抽取器。

| 模型 | GSM8K（200） | CRUXEval-O（200） | BBH（200） | 宏平均 |
|---|---:|---:|---:|---:|
| 原始 Qwen2.5-1.5B | 69.0% | 26.0% | 31.0% | 42.0% |
| 最终 Ward-v4-Q6_K | 60.0% | 25.0% | 35.0% | 40.0% |
| Qwen2.5-14B 教师 | 94.0% | 52.5% | 54.0% | 66.83% |

最终模型相对原始 1.5B 的宏平均保留率为 `95.24%`；相对 14B 教师的宏平均保留率为 `59.85%`。因此不能宣称已保留 14B 的 80% 至 90% 通用能力。

## 病房任务

固定 200 条测试（100 个场景，每个场景包含云端研判和事件增强）：

| 指标 | 结果 |
|---|---:|
| 云端研判准确率 | 99.00% |
| 云端研判 Macro-F1 | 99.14% |
| 事件紧急度准确率 | 82.00% |
| 输出格式合规率 | 100.00% |
| 平均参考答案文字相似度 | 0.4673 |

新增 50 条独立测试（25 个新场景，和已有训练/测试提示精确重复数为 0）：

| 指标 | 结果 |
|---|---:|
| 云端研判准确率 | 68.00% |
| 云端研判 Macro-F1 | 60.47% |
| 事件紧急度准确率 | 88.00% |
| 输出格式合规率 | 100.00% |
| 平均参考答案文字相似度 | 0.4054 |

新增测试暴露出 `reject` 召回率仅 12.5%，模型偏向保守地触发人工复核。模型适合作为辅助提醒器，不宜在无人复核情况下自动关闭或确认病房告警。

## 部署口径

当前验证配置：Q6_K、20 层 GPU 卸载、4096 上下文、单槽、KV Cache 为 Q8_0。显存约 1.44 GiB。现有延迟记录为完整请求延迟，不等同于流式 TTFT；统一条件下的配对 TTFT 专项测试尚未完成。

```bash
qwen-start-v4
qwen-status
qwen-chat 'B07患者疑似跌倒，置信度0.93，网络断开，请给出简洁处置建议。'
```

OpenAI 兼容接口：`http://127.0.0.1:8000/v1`。

## 证据位置

- `datasets/ward-nlu-500-v1/distillation/v4/manifest-v4.1.0.json`
- `datasets/ward-nlu-500-v1/distillation/v4/general-v4-q6-full.json`
- `datasets/ward-nlu-500-v1/distillation/v4/general-v4-q6-full.samples.jsonl`
- `datasets/ward-nlu-500-v1/distillation/v4/domain-v4-q6-full.json`
- `datasets/ward-nlu-500-v1/distillation/v4/general-teacher-14b-full.json`
- `datasets/ward-nlu-500-v1/distillation/v4/general-comparison-v4-q6-vs-teacher14b.md`
- `datasets/ward-nlu-500-v1/evaluation/ward-task-50-v1/REPORT.md`

参考答案文字相似度只是字符二元组 Dice 相似度，不代表护理建议的临床正确率。本模型只提供护理辅助建议，不替代医护人员诊断与决策。

