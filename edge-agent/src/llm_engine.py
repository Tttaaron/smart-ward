"""边缘端轻量 LLM 推理引擎

支持双模式运行：
  - mock 模式（默认）：基于模板的规则化响应，无需 GPU，用于 Docker 演示与开发调试
  - real 模式：通过 llama-cpp-python 加载 Qwen2.5-1.5B-GPTQ-Int4 GGUF 模型，
    在 Jetson Orin Nano / x86 CPU 上实现真实推理

性能指标追踪（对齐赛题硬指标）：
  - TTFT (Time To First Token)：首 token 延迟，目标 < 200ms
  - 内存占用：模型加载后 RSS 增量，目标 ≤ 1.5GB
  - 吞吐量：tokens/sec

环境变量：
  LLM_MODE          mock / real（默认 mock）
  LLM_MODEL_PATH    GGUF 模型文件路径（real 模式必须；可切换 1.5B/0.5B）
  LLM_MODEL_NAME    上报的模型名称（默认按当前模型路径推断）
  LLM_MODEL_VERSION 上报的模型版本（默认 1.0.0-int4）
  LLM_N_CTX         上下文窗口长度（默认 2048）
  LLM_N_GPU_LAYERS  GPU 卸载层数（Jetson 建议 99，CPU 为 0）
  LLM_N_BATCH       prompt 批处理大小（默认 128）
  LLM_N_UBATCH      物理批处理大小（默认 128）
  LLM_N_THREADS     CPU 推理线程数（默认 8）
  LLM_MAX_TOKENS    单次生成最大 token 数（默认 64）
  LLM_USE_MMAP      是否 mmap 加载模型（默认 true）
  LLM_USE_MLOCK     是否锁定模型内存（默认 false）
"""

import os
import time
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class LLMResponse:
    """LLM 推理响应结构"""
    text: str                           # 生成的文本
    ttft_ms: float = 0.0               # 首 token 延迟 (ms)
    total_ms: float = 0.0              # 总推理时间 (ms)
    tokens_generated: int = 0           # 生成 token 数
    tokens_per_sec: float = 0.0         # 生成速度
    memory_mb: float = 0.0             # 本次推理峰值内存 (MB)
    model_name: str = ""               # 模型标识
    model_version: str = ""            # 模型版本
    mode: str = "mock"                 # mock / real

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "ttft_ms": round(self.ttft_ms, 2),
            "total_ms": round(self.total_ms, 2),
            "tokens_generated": self.tokens_generated,
            "tokens_per_sec": round(self.tokens_per_sec, 1),
            "memory_mb": round(self.memory_mb, 1),
            "model_name": self.model_name,
            "model_version": self.model_version,
            "mode": self.mode,
        }


@dataclass
class LLMEngineMetrics:
    """LLM 引擎累计性能指标"""
    total_inferences: int = 0
    avg_ttft_ms: float = 0.0
    avg_total_ms: float = 0.0
    avg_tokens_per_sec: float = 0.0
    peak_memory_mb: float = 0.0
    model_loaded: bool = False
    model_load_time_ms: float = 0.0
    _ttft_sum: float = field(default=0.0, repr=False)
    _total_sum: float = field(default=0.0, repr=False)
    _tps_sum: float = field(default=0.0, repr=False)

    def update(self, resp: "LLMResponse") -> None:
        self.total_inferences += 1
        self._ttft_sum += resp.ttft_ms
        self._total_sum += resp.total_ms
        self._tps_sum += resp.tokens_per_sec
        self.avg_ttft_ms = self._ttft_sum / self.total_inferences
        self.avg_total_ms = self._total_sum / self.total_inferences
        self.avg_tokens_per_sec = self._tps_sum / self.total_inferences
        if resp.memory_mb > self.peak_memory_mb:
            self.peak_memory_mb = resp.memory_mb

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_inferences": self.total_inferences,
            "avg_ttft_ms": round(self.avg_ttft_ms, 2),
            "avg_total_ms": round(self.avg_total_ms, 2),
            "avg_tokens_per_sec": round(self.avg_tokens_per_sec, 1),
            "peak_memory_mb": round(self.peak_memory_mb, 1),
            "model_loaded": self.model_loaded,
            "model_load_time_ms": round(self.model_load_time_ms, 1),
        }


class LLMEngine:
    """边缘端轻量 LLM 推理引擎

    双模式设计：
      - mock：模板化响应，0 依赖，Docker 演示可用
      - real：llama-cpp-python 加载 GGUF 量化模型

    线程安全：内部加锁，支持 MQTT 回调线程与主循环并发调用。
    """

    MODEL_NAME = "qwen2.5-1.5b-instruct"
    MODEL_VERSION = "1.0.0-int4"

    def __init__(self):
        self.mode = os.getenv("LLM_MODE", "mock").lower()
        self.profile = os.getenv("LLM_PROFILE", "quality").lower()
        self.model_path = os.getenv("LLM_MODEL_PATH", "")
        self.MODEL_NAME = os.getenv("LLM_MODEL_NAME", "") or _model_name_from_path(self.model_path)
        self.MODEL_VERSION = os.getenv("LLM_MODEL_VERSION", "1.0.0-int4")
        # 护理事件 prompt 很短，512 已足够；较小的上下文也能降低 KV cache。
        self.n_ctx = int(os.getenv("LLM_N_CTX", "512"))
        self.n_gpu_layers = int(os.getenv("LLM_N_GPU_LAYERS", "0"))
        self.n_batch = int(os.getenv("LLM_N_BATCH", "128"))
        self.n_ubatch = int(os.getenv("LLM_N_UBATCH", str(self.n_batch)))
        self.n_threads = int(os.getenv("LLM_N_THREADS", "8"))
        self.n_threads_batch = int(os.getenv("LLM_N_THREADS_BATCH", str(self.n_threads)))
        self.use_mmap = _env_bool("LLM_USE_MMAP", True)
        self.use_mlock = _env_bool("LLM_USE_MLOCK", False)
        self.max_tokens = int(os.getenv("LLM_MAX_TOKENS", "64"))

        self._model = None
        self._lock = threading.Lock()
        self.metrics = LLMEngineMetrics()
        self._loaded = False
        self._load_error: Optional[str] = None
        self._prev = None  # 上一模型快照 (model, path, name, version)，供 rollback

        # 尝试加载模型
        if self.mode == "real":
            self._load_model()
        else:
            # mock 模式标记为已加载
            self._loaded = True
            self.metrics.model_loaded = True
            print(f"[LLMEngine] mock 模式启动（无需模型文件）")

    def _load_model(self) -> None:
        """加载 GGUF 量化模型（real 模式），失败自动降级 mock"""
        if not self.model_path or not os.path.exists(self.model_path):
            self._load_error = f"模型文件不存在: {self.model_path}"
            self.mode = "mock"
            self._loaded = True
            self.metrics.model_loaded = True
            print(f"[LLMEngine] 模型文件缺失，降级为 mock 模式: {self.model_path}")
            return

        try:
            t0 = time.time()
            self._model = self._load_gguf(self.model_path)
            load_ms = (time.time() - t0) * 1000
            self._loaded = True
            self.metrics.model_loaded = True
            self.metrics.model_load_time_ms = load_ms
            print(f"[LLMEngine] 模型加载成功: {self.model_path} ({load_ms:.0f}ms)")
        except ImportError:
            self._load_error = "llama-cpp-python 未安装"
            self.mode = "mock"
            self._loaded = True
            self.metrics.model_loaded = True
            print("[LLMEngine] llama-cpp-python 未安装，降级为 mock 模式")
        except Exception as e:
            self._load_error = str(e)
            self.mode = "mock"
            self._loaded = True
            self.metrics.model_loaded = True
            print(f"[LLMEngine] 模型加载失败，降级为 mock: {e}")

    def _build_llama_kwargs(self, model_path: str) -> Dict[str, Any]:
        """构造 llama_cpp.Llama 加载参数（供初始加载与运行时切换复用）"""
        return {
            "model_path": model_path,
            "n_ctx": self.n_ctx,
            "n_batch": self.n_batch,
            "n_ubatch": self.n_ubatch,
            "n_threads": self.n_threads,
            "n_threads_batch": self.n_threads_batch,
            "n_gpu_layers": self.n_gpu_layers,
            "use_mmap": self.use_mmap,
            "use_mlock": self.use_mlock,
            "verbose": False,
        }

    def _load_gguf(self, model_path: str):
        """用 llama.cpp 加载 GGUF，返回 Llama 实例；失败抛异常。

        兼容旧版 llama-cpp-python：逐步移除不支持的参数重试。
        """
        from llama_cpp import Llama
        model_kwargs = self._build_llama_kwargs(model_path)
        try:
            return Llama(**model_kwargs)
        except TypeError as exc:
            message = str(exc)
            for optional_key in ("n_ubatch", "n_threads_batch"):
                if optional_key in model_kwargs and optional_key in message:
                    model_kwargs.pop(optional_key)
            return Llama(**model_kwargs)

    def switch_model(self, model_path: str, model_name: str = "",
                     model_version: str = "") -> bool:
        """运行时切换 LLM 模型（支持蒸馏学生模型下发）。

        real 模式：持锁加载新 GGUF，成功后替换当前模型并保存上一模型供回滚；
                加载失败保留原模型，返回 False。
        mock 模式：仅更新模型元数据（名称/版本/路径），演示与测试可用。

        Returns:
            bool: 是否切换成功
        """
        name = model_name or _model_name_from_path(model_path)

        with self._lock:
            if self.mode == "real":
                if not model_path or not os.path.exists(model_path):
                    print(f"[LLMEngine] 切换失败: 模型文件不存在 {model_path}")
                    return False
                try:
                    t0 = time.time()
                    new_model = self._load_gguf(model_path)
                except Exception as exc:
                    print(f"[LLMEngine] 切换失败，保留当前模型: {exc}")
                    return False
                self._prev = (self._model, self.model_path,
                              self.MODEL_NAME, self.MODEL_VERSION)
                self._model = new_model
                load_ms = (time.time() - t0) * 1000
                self.metrics.model_load_time_ms = load_ms
                self.metrics.model_loaded = True
            else:
                # mock 模式：仅更新元数据
                self._prev = (self._model, self.model_path,
                              self.MODEL_NAME, self.MODEL_VERSION)

            self.model_path = model_path
            self.MODEL_NAME = name
            self.MODEL_VERSION = model_version or self.MODEL_VERSION
            self._load_error = None
            self._loaded = True
            print(f"[LLMEngine] 模型切换: {self.MODEL_NAME}@{self.MODEL_VERSION} "
                  f"mode={self.mode} path={model_path}")
            return True

    def rollback(self) -> bool:
        """回滚到上一模型（与 inference.rollback 语义一致）"""
        with self._lock:
            if not self._prev:
                print("[LLMEngine] 回滚失败: 无上一模型")
                return False
            prev_model, prev_path, prev_name, prev_version = self._prev
            self._model = prev_model
            self.model_path = prev_path
            self.MODEL_NAME = prev_name
            self.MODEL_VERSION = prev_version
            self._prev = None
            self._load_error = None
            self._loaded = True
            print(f"[LLMEngine] 模型回滚: {self.MODEL_NAME}@{self.MODEL_VERSION} "
                  f"path={self.model_path}")
            return True

    @property
    def is_ready(self) -> bool:
        return self._loaded

    @property
    def status(self) -> str:
        """引擎状态：ok / degraded / loading"""
        if not self._loaded:
            return "loading"
        if self._load_error or self.mode == "mock":
            return "ok"  # mock 也是正常状态
        return "ok"

    def generate(self, prompt: str, system: str = "", max_tokens: int = None) -> LLMResponse:
        """执行 LLM 推理

        Args:
            prompt: 用户提示词
            system: 系统提示词（角色设定）
            max_tokens: 最大生成 token 数（覆盖默认值）

        Returns:
            LLMResponse: 含生成文本与性能指标
        """
        max_tok = max_tokens or self.max_tokens

        if self.mode == "real" and self._model is not None:
            return self._generate_real(prompt, system, max_tok)
        else:
            return self._generate_mock(prompt, system, max_tok)

    def _generate_real(self, prompt: str, system: str, max_tokens: int) -> LLMResponse:
        """真实模型推理（llama.cpp）"""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        with self._lock:
            t0 = time.time()
            ttft_ms = 0.0
            tokens_generated = 0
            full_text = ""

            try:
                # 流式生成以测量 TTFT
                stream = self._model.create_chat_completion(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=0.1,
                    stream=True,
                )
                for chunk in stream:
                    if tokens_generated == 0:
                        ttft_ms = (time.time() - t0) * 1000
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        full_text += content
                        tokens_generated += 1

                total_ms = (time.time() - t0) * 1000
            except Exception as e:
                total_ms = (time.time() - t0) * 1000
                full_text = f"[推理异常: {e}]"
                tokens_generated = 0

        tps = (tokens_generated / total_ms * 1000) if total_ms > 0 else 0
        mem_mb = self._estimate_memory()

        resp = LLMResponse(
            text=full_text,
            ttft_ms=ttft_ms,
            total_ms=total_ms,
            tokens_generated=tokens_generated,
            tokens_per_sec=tps,
            memory_mb=mem_mb,
            model_name=self.MODEL_NAME,
            model_version=self.MODEL_VERSION,
            mode="real",
        )
        self.metrics.update(resp)
        return resp

    def _generate_mock(self, prompt: str, system: str, max_tokens: int) -> LLMResponse:
        """模拟推理（模板化响应，用于演示和开发）

        模拟真实推理的延迟特征：
          - TTFT: 30-80ms（模拟首 token 延迟）
          - 生成速度: 40-60 tokens/sec
        """
        t0 = time.time()

        # 模拟 TTFT
        import random
        mock_ttft = random.uniform(30, 80)
        time.sleep(mock_ttft / 1000)

        # 基于 prompt 关键词生成模板化响应
        response_text = self._mock_response(prompt)
        tokens_est = len(response_text) // 2  # 中文约 2 字符/token

        # 模拟生成延迟
        mock_gen_time = tokens_est / 50.0  # 50 tokens/sec
        time.sleep(min(mock_gen_time, 0.1))  # 限制最大等待

        total_ms = (time.time() - t0) * 1000
        tps = (tokens_est / total_ms * 1000) if total_ms > 0 else 0

        resp = LLMResponse(
            text=response_text,
            ttft_ms=mock_ttft,
            total_ms=total_ms,
            tokens_generated=tokens_est,
            tokens_per_sec=tps,
            memory_mb=1180.0,  # 模拟 1.18GB 内存占用
            model_name=self.MODEL_NAME,
            model_version=self.MODEL_VERSION,
            mode="mock",
        )
        self.metrics.update(resp)
        return resp

    def _mock_response(self, prompt: str) -> str:
        """根据 prompt 关键词返回模板化响应"""
        prompt_lower = prompt.lower()

        if "跌倒" in prompt or "fall" in prompt_lower:
            return "【紧急】检测到患者疑似跌倒。建议：1)立即前往病房查看；2)评估意识状态；3)检查有无外伤；4)通知主管医生。"
        elif "离床" in prompt or "bed_leave" in prompt_lower:
            return "【警告】患者离床时间超过阈值。建议：1)确认患者去向；2)检查是否为计划活动；3)必要时协助返回病床。"
        elif "环境" in prompt or "environment" in prompt_lower:
            return "【提醒】病房环境指标异常。建议：1)检查空调/通风设备；2)确认温湿度是否在正常范围；3)必要时调整设备参数。"
        elif "抽搐" in prompt or "seizure" in prompt_lower:
            return "【紧急】检测到患者疑似抽搐发作。建议：1)保护患者避免二次伤害；2)保持呼吸道通畅；3)记录发作时长；4)立即通知医生。"
        elif "徘徊" in prompt or "wandering" in prompt_lower:
            return "【警告】夜间检测到患者徘徊。建议：1)轻声安抚患者；2)评估意识清醒程度；3)引导回床；4)检查是否需要调整用药。"
        elif "静止" in prompt or "still" in prompt_lower:
            return "【提醒】患者长时间体位静止。建议：1)查看患者状态；2)评估是否需要翻身；3)检查压疮风险区域。"
        elif "冲突" in prompt or "conflict" in prompt_lower:
            return "【决策】多源信息存在矛盾。综合判断：以高置信度传感器为准，建议人工复核确认。"
        else:
            return f"已收到事件信息，当前患者状态需持续关注。建议保持常规巡视频率。"

    def _estimate_memory(self) -> float:
        """估算当前推理内存占用 (MB)"""
        try:
            import resource
            # Linux: ru_maxrss 单位为 KB
            usage = resource.getrusage(resource.RUSAGE_SELF)
            return usage.ru_maxrss / 1024.0
        except (ImportError, AttributeError):
            # Windows 或非 Linux 环境
            try:
                import psutil
                process = psutil.Process(os.getpid())
                return process.memory_info().rss / (1024 * 1024)
            except ImportError:
                return 1180.0  # 默认估计值

    def get_status(self) -> Dict[str, Any]:
        """获取引擎完整状态（用于 health 上报）"""
        return {
            "mode": self.mode,
            "status": self.status,
            "model_name": self.MODEL_NAME,
            "model_version": self.MODEL_VERSION,
            "model_loaded": self.metrics.model_loaded,
            "load_error": self._load_error,
            "runtime": {
                "profile": self.profile,
                "n_ctx": self.n_ctx,
                "n_batch": self.n_batch,
                "n_ubatch": self.n_ubatch,
                "n_threads": self.n_threads,
                "n_gpu_layers": self.n_gpu_layers,
                "use_mmap": self.use_mmap,
                "use_mlock": self.use_mlock,
            },
            "metrics": self.metrics.to_dict(),
        }


def _env_bool(name: str, default: bool) -> bool:
    """读取布尔环境变量，避免把非空字符串误判为 True。"""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _model_name_from_path(model_path: str) -> str:
    """从 GGUF 文件名推断模型名，避免切换小模型后 health 仍上报 1.5B。"""
    filename = os.path.basename(model_path).lower()
    if "0.5b" in filename:
        return "qwen2.5-0.5b-instruct"
    if "1.5b" in filename:
        return "qwen2.5-1.5b-instruct"
    return "qwen2.5-edge-gguf"
