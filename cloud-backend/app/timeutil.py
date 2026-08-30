"""统一时间口径。

数据库 DATETIME 列存的是**不带时区的 UTC** 值（边缘端上报 ISO 8601 `Z`，
经 `parse_ts()` 去掉 Z 后落库）。因此所有与 DATETIME 列比较或写入的时间，
必须同样是 naive UTC；对外（MQTT payload / API 响应）则统一带 `Z` 后缀。

此前 main.py / mqtt_handler.py 混用 `datetime.utcnow()`（naive）与
`datetime.now(timezone.utc)`（aware）做查询过滤，两个端点的 24 小时窗口
口径并不一致；`utcnow()` 亦已在 Python 3.12 起废弃。
"""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """当前 UTC 时间（naive），用于写入/比较 DATETIME 列。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utc_now_iso() -> str:
    """当前 UTC 时间（ISO 8601，Z 结尾），用于 MQTT payload 与 API 响应。"""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_ts(ts: str) -> datetime:
    """解析 ISO 8601 时间字符串为 naive UTC，兼容 Z 结尾与带偏移量的输入。"""
    if not ts:
        return utc_now()
    try:
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return utc_now()
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed
