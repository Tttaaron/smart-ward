# Qwen2.5-14B → Qwen2.5-1.5B 智慧病房蒸馏

这里采用“离线教师响应蒸馏 + BF16 LoRA”：14B 根据人工核验事件生成七类任务答案，1.5B 只学习 assistant 答案 token。固定的 100 条测试事件不进入教师生成和训练。

模型学习的任务：事件语义增强、护理建议、云端研判、离线决策、活动播报、YOLO 日志摘要、时段摘要。云端卸载判定和云请求 prompt 构造仍保留为确定性项目逻辑，不交给生成模型替代。

服务器上的标准产物：

- 教师数据：`datasets/ward-nlu-500-v1/distillation/teacher-train-v1.jsonl`
- 校准训练集：`datasets/ward-nlu-500-v1/distillation/student-train-v2.jsonl`
- 最终 LoRA：`/root/autodl-tmp/qwen/models/Qwen2.5-1.5B-Ward-LoRA-v2`
- 最终合并模型：`/root/autodl-tmp/qwen/models/Qwen2.5-1.5B-Ward-Distilled-v2`
- 项目 GGUF：`edge-agent/models/qwen2.5-1.5b-ward-distilled/qwen2.5-1.5b-ward-q4_k_m.gguf`
- 评测：`datasets/ward-nlu-500-v1/distillation/reports/`

所有生成脚本都可断点续跑；已有事件不会重复请求教师。

## 结果

固定 200 条测试提示（对应 100 条完全隔离的事件）结果：

| 指标 | 原始 1.5B | 蒸馏 1.5B v2 |
|---|---:|---:|
| 云端研判准确率 | 0% | 100% |
| 云端研判 Macro-F1 | 0% | 100% |
| 紧急程度准确率 | 0% | 100% |
| 格式合规率 | 0% | 100% |
| 平均参考答案相似度 | 0.095 | 0.543 |
| 平均 API 延迟 | 0.310 秒 | 0.156 秒 |

另外，七类任务烟雾测试为 7/7，通过相关边缘端单元测试 11/11。100% 是当前模板化测试集上的结果，不代表真实病房中的临床准确率；模型只提供护理建议，不应替代医护人员判断。

## 使用

启动蒸馏模型 API：

```bash
qwen-start ward
qwen-status
qwen-chat "床位B01于14:32从睡眠中醒来坐起，请生成一句活动播报"
```

切回原模型：

```bash
qwen-start 1.5b
# 或
qwen-start 14b
```

项目 Docker/llama.cpp 模式使用 `.env.ward-distilled`：

```bash
cd /root/autodl-tmp/smart-ward-master
docker compose build --build-arg INSTALL_LLM=true edge-bed-01 edge-bed-02 edge-bed-03
docker compose --env-file .env.ward-distilled up -d
```

如果只做接口联调，直接使用正在运行的 OpenAI 兼容地址 `http://127.0.0.1:8000/v1`，模型名为 `qwen2.5-1.5b-ward`。
