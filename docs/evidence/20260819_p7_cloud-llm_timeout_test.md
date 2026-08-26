# P7 云端推理超时验证证据

日期：2026-08-19  
分支：`feature/cloud-llm-p7`  
代码基线：`efcf757` + 当前工作区超时修复

## 验证命令

```powershell
cd D:\smart-ward-repo\cloud-llm-service
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

## 结果

```text
Ran 14 tests in 0.014s
OK
```

新增场景：慢 adapter（80ms）+ 请求 `timeout_ms=10`。

预期与实际：

- 云端在请求 deadline 到期后记录结构化日志 stage `inference_timeout`。
- response `judgment=escalate`。
- response `status=timeout`。
- response `latency_ms=10.0`，advice 含 timeout 说明和 edge fallback 提示。
- 边缘侧仍可根据自身 pending/timeout 机制执行第二道回退。

## 当前边界

该证据验证的是云端服务端 deadline 和 mock 慢 adapter。真实 vLLM 的网络超时还需在 P6 提供 endpoint 后补一次真实 Broker 运行证据。
