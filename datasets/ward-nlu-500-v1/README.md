# Ward NLU 500 v1.0.0

智慧病房 13 类安全事件 NLU 数据集。规范来源为
`docs/20-NLU数据集构建说明-P5.md`，用于边缘、云边协同、纯云端三种路线的统一训练与评测。

## 数据规模

- 主数据：500 条，`train=400`、`test=100`
- Qwen 多任务训练视图：训练 800 条、测试 200 条（每个主样本派生两个任务）
- 项目云端推理请求：100 条测试夹具
- 所有床位、时间和事件均为脱敏模拟数据，不包含真实患者身份信息

事件分布见 `manifest.json`。重点事件 `fall_suspected`、`seizure`、
`fall_prediction` 各 50 条，其余事件按项目使用频率分配，共计 500 条。

## 文件说明

| 文件 | 用途 |
|---|---|
| `nlu-dataset-v1.0.0.jsonl` | 500 条主数据，一行一条 JSON |
| `nlu-dataset-v1.0.0.json` | 相同主数据的 JSON 数组版本 |
| `train-v1.0.0.jsonl` | 400 条训练集 |
| `test-v1.0.0.jsonl` | 100 条独立测试集，不得用于训练或蒸馏 |
| `qwen-sft-train-v1.0.0.jsonl` | 800 条 Qwen ChatML 训练记录 |
| `qwen-sft-test-v1.0.0.jsonl` | 200 条 Qwen ChatML 测试记录 |
| `project-inference-test-v1.0.0.jsonl` | 对齐 `cloud-llm-service` 的 100 条请求及期望标签 |
| `schema-v1.0.0.json` | 主数据 JSON Schema |
| `manifest.json` | 版本、随机种子和数据分布 |
| `LABEL_SPEC.md` | 标签定义和标注规则 |
| `reports/validation-report.json` | 完整性、泄漏和项目兼容测试结果 |
| `reports/mock-baseline-report.json` | 当前项目 mock 规则基线指标 |
| `reports/mock-baseline-raw.jsonl` | 逐样本原始预测日志 |

## Qwen 训练视图

每个主样本派生两个任务，但主数据样本数仍为 500：

1. `event_enhancement`：输入项目 `LLMAdvisor._build_event_prompt` 风格的结构化事件，输出自然语言状况和护理建议。
2. `cloud_judgment`：输入 `cloud-llm-service` 风格的研判 prompt，输出 `judgment|confidence|advice`。

这两个视图分别对齐边缘端 `enhance_event/nursing_advice` 与云端二次研判。

## 复现与验证

在项目根目录执行：

```bash
python scripts/generate_ward_nlu_dataset.py
python scripts/validate_ward_nlu_dataset.py
python scripts/evaluate_ward_nlu_dataset.py
python -m unittest tests.test_ward_nlu_dataset -v
```

生成器固定随机种子 `20260809`，重复运行会得到相同内容。

## 当前基线结果

- 所有结构、数量、枚举、划分和项目兼容检查通过
- 训练集与测试集：ID、完整描述、场景族均零交叉
- `TaskRouter` 联网路由输出均合法；模拟断网时 100/100 请求保留边缘处理
- 云端 mock 研判：准确率 0.7400，macro-F1 0.6511

mock 只根据优先级和置信度判断，不读取完整自然语言，因此该分数只作为
“数据能够进入现有项目链路”的基线，不能代表 Qwen 的模型质量。

## 限制

v1.0.0 是基于项目规则和人工设计场景模板生成的初版数据。虽然包含遮挡、
传感器冲突、正常护理活动和设备异常等难例，但在用于正式医疗场景或发布
模型前，仍必须由具备资质的护理人员进行人工审核。测试集不得进入蒸馏。
