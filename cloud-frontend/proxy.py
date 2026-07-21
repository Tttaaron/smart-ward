import asyncio
import os
import aiohttp
from aiohttp import web, WSMsgType

BACKEND = "http://cloud-backend:8000"
DIST_DIR = "/app/dist"


async def api_proxy(request):
    path = request.match_info.get("path", "")
    url = f"{BACKEND}/api/{path}"
    if request.query_string:
        url += "?" + request.query_string
    data = await request.read()
    headers = {k: v for k, v in request.headers.items() if k.lower() != "host"}
    async with aiohttp.ClientSession() as session:
        async with session.request(
            request.method, url, headers=headers, data=data
        ) as resp:
            body = await resp.read()
            return web.Response(
                body=body, status=resp.status, headers=dict(resp.headers)
            )


async def ws_proxy(request):
    ws_client = web.WebSocketResponse()
    await ws_client.prepare(request)
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(f"{BACKEND}/ws") as ws_backend:
            async def to_client():
                async for msg in ws_backend:
                    if msg.type == WSMsgType.TEXT:
                        await ws_client.send_str(msg.data)
                    elif msg.type == WSMsgType.BINARY:
                        await ws_client.send_bytes(msg.data)

            async def to_backend():
                async for msg in ws_client:
                    if msg.type == WSMsgType.TEXT:
                        await ws_backend.send_str(msg.data)
                    elif msg.type == WSMsgType.BINARY:
                        await ws_backend.send_bytes(msg.data)

            await asyncio.gather(to_client(), to_backend())
    return ws_client


async def static(request):
    path = request.match_info.get("path", "")
    file_path = os.path.join(DIST_DIR, path)
    if path and os.path.exists(file_path) and os.path.isfile(file_path):
        return web.FileResponse(file_path)
    return web.FileResponse(os.path.join(DIST_DIR, "index.html"))


app = web.Application()
app.router.add_get("/ws", ws_proxy)
app.router.add_route("*", "/api/{path:.*}", api_proxy)
app.router.add_get("/{path:.*}", static)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=80)
