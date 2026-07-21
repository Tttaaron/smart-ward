"""pytest 配置：将 src/ 加入 sys.path

edge-agent 的 src/ 下采用扁平导入（from adapters.base import ...），
与原 edge/edge-node 项目一致（Dockerfile 中 WORKDIR /app/src）。
此 conftest 确保 pytest 运行时也能找到 src 下的模块。
"""

import os
import sys

SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")
SRC_DIR = os.path.abspath(SRC_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
