"""pytest 配置：将 src/ 加入 sys.path

edge-agent 的 src/ 下采用扁平导入（from adapters.base import ...），
与原 edge/edge-node 项目一致（Dockerfile 中 WORKDIR /app/src）。
此 conftest 确保 pytest 运行时也能找到 src 下的模块。

注意路径：本文件位于 edge-agent/ 根目录，故 src 就在同级。
此前写成 `dirname(__file__)/../src`，解析到仓库根的 smart-ward/src
（不存在），插入的是个无效路径——测试能跑全靠各测试文件自己
补 sys.path，这里等于空转。
"""

import os
import sys

SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "src"))
if os.path.isdir(SRC_DIR) and SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
