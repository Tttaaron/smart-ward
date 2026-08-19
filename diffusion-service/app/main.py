"""扩散模型服务 - FastAPI 接口

提供困难样本生成、数据集导出、任务管理等 REST API。

端点:
    GET  /health              健康检查（含 GPU 状态）
    POST /generate             单张图像生成
    POST /generate/batch       批量生成
    POST /generate/event/{type} 指定事件类型批量生成
    POST /generate/all         所有事件类型混合生成
    GET  /datasets             数据集列表
    GET  /datasets/{name}      数据集详情
    POST /datasets/{name}/export  导出指定数据集为 zip
    DELETE /datasets/{name}    删除数据集
"""

import gc
import json
import logging
import time
import threading
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

import torch
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field

from .config import (
    OUTPUT_DIR,
    IMAGES_DIR,
    LABELS_DIR,
    DATASETS_DIR,
    DEFAULT_BATCH_COUNT,
    MQTT_BROKER,
    MQTT_PORT,
    AUTO_GENERATE,
    GENERATION_BATCH_SIZE,
    DB_PATH,
)
from .generator import DiffusionGenerator, get_generator
from .exporter import export_dataset, export_multi_event_dataset
from .curator import QualityCurator
from .database import Database
from .mqtt_handler import MqttHandler
from .logger import get_logger
from config.pose_templates import (
    ALL_EVENT_TYPES,
    EVENT_CATEGORY_IDS,
    get_templates_for_event,
)

logging.basicConfig(level=logging.INFO)
logger = get_logger(__name__)

curator = QualityCurator()

# 误报回流：SQLite 记录 + MQTT 订阅
db = Database(str(DB_PATH))


def _handle_false_positive(fp_event: dict):
    """MQTT 收到误报确认 → 自动生成困难样本（后台线程执行）"""
    event_id = fp_event.get("event_id", "unknown")
    event_type = fp_event.get("event_type", "unknown")
    if event_type not in ALL_EVENT_TYPES:
        logger.warning(f"误报事件类型未知，跳过生成: {event_type}")
        return

    gen = get_generator()
    try:
        logger.info(f"误报回流触发生成: event_id={event_id} event_type={event_type}")
        gen.load_models()
        results = gen.generate_batch(
            event_type=event_type,
            count=GENERATION_BATCH_SIZE,
            night_ratio=0.3,
            steps=25,
        )
        passed, report = curator.filter(results)
        dataset_path = None
        if passed:
            dataset_path = export_dataset(
                passed,
                f"fp-{event_id[:8]}",
                category_id=EVENT_CATEGORY_IDS.get(event_type, 0),
            )
        db.mark_processed(event_id, report["passed"])
        logger.info(
            f"误报生成完成: event_id={event_id} generated={len(results)} "
            f"passed={report['passed']} dataset={dataset_path}"
        )
    except Exception as e:
        logger.exception(f"误报回流生成失败: {e}")
    finally:
        gen.unload_models()


mqtt_handler = MqttHandler(
    db=db,
    on_false_positive=_handle_false_positive if AUTO_GENERATE else None,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    mqtt_handler.connect()
    logger.info(f"扩散服务启动 (auto_generate={AUTO_GENERATE}, mqtt={MQTT_BROKER}:{MQTT_PORT})")
    yield
    mqtt_handler.disconnect()
    logger.info("扩散服务停止")


app = FastAPI(
    title="智慧病房扩散模型服务",
    description="基于 Stable Diffusion + ControlNet 的困难样本生成与数据集扩充（含误报回流）",
    version="0.2.0",
    lifespan=lifespan,
)

# ─── 请求/响应模型 ───


class GenerateRequest(BaseModel):
    event_type: str = Field(..., description="事件类型", examples=["fall_suspected"])
    seed: Optional[int] = Field(None, description="随机种子")
    night_mode: bool = Field(False, description="夜间低照度模式")
    steps: int = Field(25, ge=10, le=50, description="推理步数")
    guidance_scale: float = Field(7.5, ge=1.0, le=20.0, description="CFG 引导系数")
    controlnet_scale: float = Field(0.85, ge=0.0, le=1.5, description="ControlNet 条件强度")


class BatchGenerateRequest(BaseModel):
    event_type: str = Field(..., description="事件类型")
    count: int = Field(4, ge=1, le=200, description="生成数量")
    night_ratio: float = Field(0.3, ge=0.0, le=1.0, description="夜间模式比例")
    steps: int = Field(25, ge=10, le=50, description="推理步数")
    export_dataset: bool = Field(True, description="是否自动导出为 YOLO 数据集")


class AllEventsRequest(BaseModel):
    count_per_event: int = Field(4, ge=1, le=50, description="每类事件生成数量")
    night_ratio: float = Field(0.3, ge=0.0, le=1.0)
    steps: int = Field(25, ge=10, le=50)
    export_dataset: bool = Field(True)


class GenerateResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: dict


class TaskStatus(BaseModel):
    task_id: str
    status: str  # running / completed / failed
    progress: int
    total: int
    results: Optional[list] = None


# ─── 内存任务跟踪 ───
_tasks: Dict[str, dict] = {}


# ─── 端点 ───


@app.get("/health")
async def health():
    """健康检查 + GPU 状态"""
    gpu_info = {}
    if torch.cuda.is_available():
        gpu_info = {
            "device": torch.cuda.get_device_name(0),
            "vram_total_gb": round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1),
            "vram_allocated_gb": round(torch.cuda.memory_allocated() / 1e9, 2),
            "vram_reserved_gb": round(torch.cuda.memory_reserved() / 1e9, 2),
            "cuda_version": torch.version.cuda,
        }
    return {
        "status": "ok",
        "service": "diffusion-service",
        "version": "0.2.0",
        "gpu": gpu_info,
        "models_loaded": get_generator()._loaded,
    }


@app.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest):
    """单张图像生成"""
    if req.event_type not in ALL_EVENT_TYPES:
        raise HTTPException(400, f"Unknown event_type: {req.event_type}. "
                                  f"Valid: {ALL_EVENT_TYPES}")

    templates = get_templates_for_event(req.event_type)
    if not templates:
        raise HTTPException(404, f"No templates for event_type={req.event_type}")

    gen = get_generator()
    gen.load_models()

    template = templates[0]
    result = gen.generate_single(
        event_type=req.event_type,
        template=template,
        seed=req.seed,
        night_mode=req.night_mode,
        steps=req.steps,
        guidance_scale=req.guidance_scale,
        controlnet_scale=req.controlnet_scale,
    )

    # 质量评估
    quality = curator.assess(result["image"])

    return GenerateResponse(data={
        "event_type": result["event_type"],
        "label": result["label"],
        "seed": result["seed"],
        "night_mode": result["night_mode"],
        "generation_time_ms": result["generation_time_ms"],
        "quality": quality,
    })


@app.post("/generate/batch")
async def generate_batch(req: BatchGenerateRequest, background: BackgroundTasks):
    """批量生成（异步）"""
    import uuid
    task_id = str(uuid.uuid4())[:8]

    if req.event_type not in ALL_EVENT_TYPES:
        raise HTTPException(400, f"Unknown event_type: {req.event_type}")

    _tasks[task_id] = {"status": "running", "progress": 0, "total": req.count}

    def _run():
        try:
            gen = get_generator()
            gen.load_models()
            results = gen.generate_batch(
                event_type=req.event_type,
                count=req.count,
                night_ratio=req.night_ratio,
                steps=req.steps,
            )
            # 质量筛选
            passed, report = curator.filter(results)

            dataset_path = None
            if req.export_dataset and passed:
                dataset_path = export_dataset(
                    passed,
                    f"{req.event_type}-{task_id}",
                    category_id=EVENT_CATEGORY_IDS.get(req.event_type, 0),
                )

            _tasks[task_id] = {
                "status": "completed",
                "progress": req.count,
                "total": req.count,
                "result": {
                    "generated": len(results),
                    "passed": report["passed"],
                    "failed": report["failed"],
                    "pass_rate": report["pass_rate"],
                    "dataset_path": str(dataset_path) if dataset_path else None,
                },
            }
        except Exception as e:
            logger.exception(f"Batch generation failed: {e}")
            _tasks[task_id] = {"status": "failed", "error": str(e)}
        finally:
            gen.unload_models()

    background.add_task(_run)
    return {"code": 0, "message": "task started", "data": {"task_id": task_id}}


@app.get("/generate/task/{task_id}")
async def get_task(task_id: str):
    """查询批量任务状态"""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return {"code": 0, "data": task}


@app.post("/generate/event/{event_type}")
async def generate_by_event(
    event_type: str,
    count: int = Query(4, ge=1, le=200),
    night_ratio: float = Query(0.3, ge=0.0, le=1.0),
    steps: int = Query(25, ge=10, le=50),
    export: bool = Query(True),
    background: BackgroundTasks = None,
):
    """按事件类型批量生成"""
    import uuid
    task_id = str(uuid.uuid4())[:8]

    if event_type not in ALL_EVENT_TYPES:
        raise HTTPException(400, f"Unknown event_type: {event_type}")

    _tasks[task_id] = {"status": "running", "progress": 0, "total": count}

    def _run():
        try:
            gen = get_generator()
            gen.load_models()
            results = gen.generate_batch(
                event_type=event_type,
                count=count,
                night_ratio=night_ratio,
                steps=steps,
            )
            passed, report = curator.filter(results)

            dataset_path = None
            if export and passed:
                dataset_path = export_dataset(
                    passed,
                    f"{event_type}-{task_id}",
                    category_id=EVENT_CATEGORY_IDS.get(event_type, 0),
                )

            _tasks[task_id] = {
                "status": "completed",
                "progress": count,
                "total": count,
                "result": {
                    "event_type": event_type,
                    "generated": len(results),
                    "passed": report["passed"],
                    "pass_rate": report["pass_rate"],
                    "dataset_path": str(dataset_path) if dataset_path else None,
                },
            }
        except Exception as e:
            logger.exception(f"Generate {event_type} failed: {e}")
            _tasks[task_id] = {"status": "failed", "error": str(e)}
        finally:
            gen.unload_models()

    background.add_task(_run)
    return {"code": 0, "message": "task started", "data": {"task_id": task_id}}


@app.post("/generate/all")
async def generate_all(
    req: AllEventsRequest,
    background: BackgroundTasks,
):
    """所有事件类型批量生成"""
    import uuid
    task_id = str(uuid.uuid4())[:8]

    total = len(ALL_EVENT_TYPES) * req.count_per_event
    _tasks[task_id] = {"status": "running", "progress": 0, "total": total}

    def _run():
        try:
            gen = get_generator()
            gen.load_models()

            all_results = {}
            progress = 0
            for event_type in ALL_EVENT_TYPES:
                results = gen.generate_batch(
                    event_type=event_type,
                    count=req.count_per_event,
                    night_ratio=req.night_ratio,
                    steps=req.steps,
                )
                passed, _ = curator.filter(results)
                if passed:
                    all_results[event_type] = passed
                progress += req.count_per_event
                _tasks[task_id]["progress"] = progress

            dataset_path = None
            if req.export_dataset and all_results:
                dataset_path = export_multi_event_dataset(
                    all_results, f"smart-ward-full-{task_id}"
                )

            total_passed = sum(len(v) for v in all_results.values())
            _tasks[task_id] = {
                "status": "completed",
                "progress": total,
                "total": total,
                "result": {
                    "total_images": total_passed,
                    "events_generated": list(all_results.keys()),
                    "dataset_path": str(dataset_path) if dataset_path else None,
                },
            }
        except Exception as e:
            logger.exception(f"Generate all failed: {e}")
            _tasks[task_id] = {"status": "failed", "error": str(e)}
        finally:
            gen.unload_models()

    background.add_task(_run)
    return {"code": 0, "message": "task started", "data": {"task_id": task_id}}


@app.get("/datasets")
async def list_datasets():
    """列出所有已生成的数据集"""
    if not DATASETS_DIR.exists():
        return {"code": 0, "data": []}

    datasets = []
    for d in sorted(DATASETS_DIR.iterdir(), reverse=True):
        if d.is_dir():
            manifest_file = d / "manifest.json"
            meta = {}
            if manifest_file.exists():
                meta = json.loads(manifest_file.read_text(encoding="utf-8"))
            datasets.append({
                "name": d.name,
                "path": str(d),
                "total_images": meta.get("total_images", 0),
                "created_at": meta.get("created_at", ""),
                "categories": meta.get("categories", {}),
            })
    return {"code": 0, "data": datasets}


@app.get("/datasets/{name}")
async def get_dataset(name: str):
    """数据集详情"""
    dataset_dir = DATASETS_DIR / name
    if not dataset_dir.exists():
        raise HTTPException(404, "Dataset not found")

    manifest_file = dataset_dir / "manifest.json"
    if manifest_file.exists():
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        return {"code": 0, "data": manifest}
    return {"code": 0, "data": {"name": name, "total_images": 0}}


@app.delete("/datasets/{name}")
async def delete_dataset(name: str):
    """删除数据集"""
    import shutil
    dataset_dir = DATASETS_DIR / name
    if not dataset_dir.exists():
        raise HTTPException(404, "Dataset not found")
    shutil.rmtree(dataset_dir)
    return {"code": 0, "message": f"Dataset {name} deleted"}


@app.get("/")
async def root():
    return {
        "service": "智慧病房扩散模型服务",
        "version": "0.2.0",
        "docs": "/docs",
        "endpoints": {
            "health": "/health",
            "generate_single": "/generate",
            "generate_batch": "/generate/batch",
            "generate_by_event": "/generate/event/{event_type}",
            "generate_all": "/generate/all",
            "datasets": "/datasets",
            "false_positives": "/api/false-positives",
            "stats": "/api/stats",
            "generate_from_fp": "/api/events/{event_id}/generate",
        },
    }


# ─── 误报回流端点 ───


@app.get("/api/false-positives")
async def list_false_positives(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """误报事件列表（来自护士站 false_positive 标记）"""
    items, total = db.list_false_positives(limit, offset)
    return {"code": 0, "data": {"items": items, "total": total}}


@app.get("/api/stats")
async def get_stats():
    """误报回流统计"""
    return {"code": 0, "data": db.get_stats()}


@app.post("/api/events/{event_id}/generate")
async def generate_from_fp(
    event_id: str,
    background: BackgroundTasks,
    count: int = Query(4, ge=1, le=50),
):
    """根据误报事件手动触发生成困难样本"""
    fp = db.get_false_positive(event_id)
    if not fp:
        raise HTTPException(404, f"误报事件 {event_id} 不存在")
    event_type = fp.get("event_type", "unknown")
    if event_type not in ALL_EVENT_TYPES:
        raise HTTPException(400, f"误报事件类型未知: {event_type}")

    def _run():
        try:
            gen = get_generator()
            gen.load_models()
            results = gen.generate_batch(
                event_type=event_type,
                count=count,
                night_ratio=0.3,
                steps=25,
            )
            passed, report = curator.filter(results)
            dataset_path = None
            if passed:
                dataset_path = export_dataset(
                    passed,
                    f"fp-{event_id[:8]}",
                    category_id=EVENT_CATEGORY_IDS.get(event_type, 0),
                )
            db.mark_processed(event_id, report["passed"])
            logger.info(
                f"误报手动生成完成: event_id={event_id} passed={report['passed']} "
                f"dataset={dataset_path}"
            )
        except Exception as e:
            logger.exception(f"误报手动生成失败: {e}")
        finally:
            gen.unload_models()

    background.add_task(_run)
    return {"code": 0, "message": "task started",
            "data": {"event_id": event_id, "event_type": event_type, "count": count}}
