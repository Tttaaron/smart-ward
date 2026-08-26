"""智慧病房云端事件中心 API（应用装配层）

从教室"状态查询"改造为病房"事件中心"（对齐方案书 §6.2）：
- 新建事件状态机：new -> notified -> acknowledged -> resolved/false_positive/escalated
- 提供病区/床位/事件/告警确认/模型版本/节点健康 API
- WebSocket 推送增量事件，REST 用于查询和处置命令

本模块只负责应用装配：生命周期钩子、CORS、统一异常响应、WebSocket 与健康检查。
21 个业务端点按领域拆分在 `app/routers/` 下：

    wards   病区、床位、床位占用
    events  安全事件查询/处置/注入、观测数据
    system  节点健康、模型版本、系统统计、环境控制
    shifts  交接班摘要

`ws_manager` / `mqtt_handler` 定义在 `app/deps.py`，此处重新导出以保持
`app.main.mqtt_handler` 这一既有引用路径可用。
"""

import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .database import init_db
from .deps import ws_manager, mqtt_handler
from .logger import get_logger
from .routers import events, shifts, system, wards

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动/关闭钩子（替代已废弃的 @app.on_event，与 diffusion-service 一致）。"""
    init_db()
    # 在运行中的事件循环上取 loop，供 MQTT 回调线程 broadcast_sync 跨线程投递。
    ws_manager.loop = asyncio.get_running_loop()
    mqtt_handler.connect()
    logger.info("云端事件中心启动完成")
    yield
    mqtt_handler.disconnect()
    logger.info("云端事件中心已关闭")


app = FastAPI(title="智慧病房事件中心 API", version="0.3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": exc.detail, "data": None}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"未处理异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": "服务器内部错误", "data": None}
    )


app.include_router(wards.router)
app.include_router(events.router)
app.include_router(system.router)
app.include_router(shifts.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"message": "智慧病房事件中心 API 运行中"}


# ===================== WebSocket =====================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            msg = await websocket.receive_text()
            try:
                data = json.loads(msg)
                if data.get("type") == "pong":
                    await ws_manager.handle_pong(websocket)
            except (json.JSONDecodeError, Exception):
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
