"""采集适配器接口

智慧病房边缘端通过四类适配器采集多源观测数据：
- CameraAdapter：RGB 摄像头（人体/床位/区域检测 + 姿态关键点）
- BedSensorAdapter：床垫压力/床位状态
- InfusionAdapter：输液滴速/液位
- EnvironmentAdapter：温湿度/光照/CO₂/门磁

模拟器和真实硬件共用同一接口，接入真实硬件时只替换适配器实现，
不改动 fusion/inference/mqtt_client/main。
"""
