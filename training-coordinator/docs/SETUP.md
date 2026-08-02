# Federated Learning 搭建指南

> training-coordinator 模块 — 智慧病房云边协同系统
> 作者：振鑫 (P4) — 协同训练底层调度
> 协作：建鸿 (P3) — 项目统筹

---

## 一、项目概况

本模块有两个层次：

| 层次 | 负责人 | 说明 |
|------|--------|------|
| 编排层 TrainingScheduler | 建鸿 | 作业生命周期、MQTT、REST API |
| 算法层 FedAvgScheduler / SemiAsyncScheduler | 振鑫 | FedAvg 聚合、半异步陈旧度加权 |

## 二、环境要求

### 2.1 Python 版本
Python 3.9 ~ 3.12 均可。

### 2.2 依赖安装

`ash
cd smart-ward/training-coordinator
pip install -r requirements.txt
pip install scikit-learn
`

> 当前 demo 用纯 NumPy 实现 MLP 训练，不依赖 PyTorch 或 FederatedScope，任何环境都能跑。

### 2.3 FederatedScope 安装（可选 — 后续阶段）

推荐用 Linux 或 conda 环境（Python 3.9/3.10）：

`ash
git clone https://github.com/alibaba/FederatedScope.git --depth 1
cd FederatedScope
pip install -e .
cd ..
`

Windows 直接装 PyTorch 可能遇到路径超限问题，建议用 conda。

## 三、运行 Demo

### 3.1 克隆 + 安装

`ash
git clone https://github.com/Tttaaron/smart-ward.git
cd smart-ward/training-coordinator
pip install -r requirements.txt
pip install scikit-learn
`

### 3.2 MNIST FedAvg 最小 demo

5 个客户端在 MNIST 上联邦学习，验证梯度聚合流程。

`ash
python demo/run_mnist_fedavg.py
`

首次运行会自动下载 MNIST（约 11MB），后续缓存。预期输出：

`
Baseline (random):  0.0775
Round  1/20  |  0.3704  |  +0.2929
Round 10/20  |  0.6879  |  +0.6104
Round 20/20  |  0.8425  |  +0.7650
`

20 轮 ~20 秒，精度从 7.75% 升到 84.25% — 梯度聚合流程验证通过。

### 3.3 其他 Demo

`ash
# 合成数据 FedAvg（更快，不依赖网络）
python demo/run_fedavg.py

# 半异步陈旧度加权
python demo/run_semi_async.py
`

### 3.4 单元测试

`ash
python -m unittest tests.test_scheduler -v
`

预期 8 项全通过。

## 四、代码结构

`
training-coordinator/
  app/
    main.py           FastAPI 入口（建鸿）
    scheduler.py      核心调度器（振鑫 + 建鸿合并）
  demo/
    run_mnist_fedavg.py    MNIST FedAvg demo
    run_fedavg.py          合成数据 FedAvg
    run_semi_async.py      半异步 demo
  tests/
    test_scheduler.py      8 项测试
  docs/
    SETUP.md              本指南
  Dockerfile
  requirements.txt
`

### scheduler.py 核心类

| 类 | 方法 | 说明 |
|------|------|------|
| FedAvgScheduler | aggregate(updates) | FedAvg 加权平均 |
| FedAvgScheduler | select_clients() | 选择本轮客户端 |
| FedAvgScheduler | run_round(train_fn) | 执行一轮训练 |
| SemiAsyncScheduler | receive_update(...) | 接收异步更新 |
| SemiAsyncScheduler | trigger_aggregation() | 强制聚合 |
| TrainingScheduler | start_round / collect_update / aggregate | 编排层 |

### 数据流

`
MNIST -> IID 分给 5 个客户端 -> 本地训练 2 epoch
-> Fwd/Backward (784-128-10 MLP)
-> 权重 + 样本数 -> FedAvgScheduler.aggregate()
-> 加权平均更新全局模型 -> 测试集评估
-> 重复 20 轮
`

## 五、常见问题

**Q: pip 报 numpy 版本冲突？**
A: 用 Python 3.9/3.10，当前 numpy 2.x 在 Python 3.12 上没问题。

**Q: MNIST 下载慢？**
A: 首次需下载 11MB，后续缓存。或用 demo/run_fedavg.py 合成数据。

**Q: 代码冲突？**
A: git pull 后再 push，有冲突商量着解决。

## 六、里程碑

| 阶段 | 截止 | 负责人 | 状态 |
|------|------|--------|------|
| T8: FedAvg 同步基线 | 7/30 | 振鑫 | 已完成 |
| T9: 半异步陈旧度加权 | 8/15 | 振鑫 | 待启动 |
| 同步/异步速度对比 | 下周 | 振鑫 | 待启动 |
| FederatedScope 集成 | 待定 | 振鑫+建鸿 | 环境就绪 |

---
有问题群里 @振鑫 / @建鸿

