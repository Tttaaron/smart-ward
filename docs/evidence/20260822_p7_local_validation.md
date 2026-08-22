# P7 本地回归验证记录

> 日期：2026-08-22
> 代码基线：`feature/cloud-llm-p7` @ `5801d19`
> 范围：云端 LLM 服务、边缘云协同与 SQLite 回归

## 云端

运行命令：

```powershell
Set-Location D:\smart-ward-repo\cloud-llm-service
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

结果：

```text
Ran 18 tests in 0.514s
OK
```

覆盖内容包括 MQTT handler、请求/响应 schema、重复请求幂等、mock 慢 adapter 超时、`inference_timeout`、vLLM 配置与 readiness。

## 边缘

运行命令：

```powershell
Set-Location D:\smart-ward-repo\edge-agent
${env:PYTHONPATH} = 'D:\smart-ward-repo\cloud-llm-service\.venv\Lib\site-packages'
python -m unittest discover -s tests -v
```

结果：

```text
Ran 100 tests in 1.352s
OK
```

覆盖内容包括 CLOUD/HYBRID request_mode 契约、独立超时 worker、云端 timeout response、SQLite observations 表迁移、响应幂等和 MQTT topic 分发。

## 环境说明

边缘专用虚拟环境创建成功，但当前网络无法下载其 `requirements.txt` 中锁定的依赖，因此本次回归复用了云端虚拟环境中已安装的 MQTT 依赖。该结果用于代码回归，不替代 Jetson 目标环境验收。

## 尚待现场验证

- 真实 MQTT Broker 下的 `inference_timeout`、`status=timeout` 和 SQLite 回写证据；
- 当前 `5801d19` 分支的真实 vLLM E2E；
- Jetson 部署及 CLOUD/HYBRID 双路径验收。

