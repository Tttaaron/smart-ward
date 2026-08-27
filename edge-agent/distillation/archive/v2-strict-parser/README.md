# v2 严格格式评分历史归档

这里保存的是 Qwen2.5-1.5B-Ward-v2 的历史实验输出。

其中 `general-comparison-full.md/json` 使用旧版严格 `FINAL:` 格式解析器，曾得到 128.24% 宏平均保留率。该数字混入了不同模型输出格式合规率的影响，已经废弃，不得作为当前模型验收结论。

当前统一宽松语义抽取后的原始 1.5B 基线，以及最终 v4-Q6_K、14B 教师的同题报告位于：

```text
datasets/ward-nlu-500-v1/distillation/general-retention-v1/
datasets/ward-nlu-500-v1/distillation/v4/
```

归档文件仅用于复现实验演进和解释旧报告来源。

