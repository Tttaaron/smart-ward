"""按领域拆分的 API 路由模块。

原先 21 个端点全部挤在 app/main.py（790 行）；此处按病区/事件/系统/交班
四个领域拆开，main.py 只保留应用装配、异常处理、WebSocket 与健康检查。
合并 master 后新增 edge_agent 领域（边缘 Agent 交接班/问答）。
"""
