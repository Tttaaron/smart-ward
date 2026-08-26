"""真实视觉链路活动识别接线测试

回归防护：ActivityRecognizer 必须吃 BehaviorAnalyzer 的汇总 track
（含平滑后 posture）。曾因误喂 IoUTracker 的原始 track（无 posture 字段），
导致 lying/standing/sleeping 等依赖姿态的分支永远不可达。

用躺姿关键点序列验证两种接线的输出差异，防止将来改回去。
"""

import os
import sys
import unittest

SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from adapters.yolo_camera import build_activity_entry
from behavior import BehaviorAnalyzer
from tracking import IoUTracker
from activity_tracker import ActivityRecognizer


def lying_keypoints():
    """横躺姿态：关键点 x 方向展开远大于 y（spread_x > spread_y * 1.15）"""
    return [[0.15 + i * 0.04, 0.50 + (0.01 if i % 2 else -0.01), 0.9]
            for i in range(17)]


def standing_keypoints():
    """直立姿态：y 方向展开远大于 x（spread_y > spread_x * 1.35）"""
    return [[0.50 + (0.005 if i % 2 else -0.005), 0.10 + i * 0.05, 0.9]
            for i in range(17)]


def make_detection(keypoints):
    return {
        "class": "person",
        "confidence": 0.9,
        # 归一化 bbox：竖长条/横长条与关键点姿态一致即可，
        # estimate_posture 优先信关键点，bbox 只做兜底
        "bbox": [0.1, 0.1, 0.3, 0.8],
        "keypoints": keypoints,
    }


class ActivityWiringTest(unittest.TestCase):
    """识别器应从 BehaviorAnalyzer 汇总结果取 posture"""

    def _run_frames(self, keypoints_factory, frames, step_seconds=0.5,
                   wiring="fixed"):
        tracker = IoUTracker()
        analyzer = BehaviorAnalyzer()
        recognizer = ActivityRecognizer(confirm_frames=5)
        entry, last, since = None, None, 0.0
        for i in range(frames):
            tracked = tracker.update([make_detection(keypoints_factory())])
            behavior = analyzer.update(tracked, timestamp=i * step_seconds)
            if wiring == "fixed":
                feed = behavior.get("tracks") or []
            else:  # 旧接线：喂原始 tracked（无 posture），用于对照
                feed = tracked
            recognizer.update(feed, timestamp=i * step_seconds)
            entry, last, since = build_activity_entry(
                feed, last, since, i * step_seconds)
        return entry

    def test_lying_recognized_via_behavior_tracks(self):
        """躺姿关键点 -> BehaviorAnalyzer 得 posture=lying -> 活动 lying"""
        entry = self._run_frames(lying_keypoints, frames=8)
        self.assertEqual(entry["label"], "lying")

    def test_standing_needs_held_duration(self):
        """站姿需主姿态保持 >=5s 才确认 standing（滞回防抖）"""
        early = self._run_frames(standing_keypoints, frames=4)
        self.assertEqual(early["label"], "unknown")
        late = self._run_frames(standing_keypoints, frames=16)
        self.assertEqual(late["label"], "standing")

    def test_old_wiring_loses_posture(self):
        """回归对照：旧接线（原始 tracked 无 posture）下 lying 不可达"""
        entry = self._run_frames(lying_keypoints, frames=8, wiring="legacy")
        self.assertEqual(entry["label"], "unknown")


if __name__ == "__main__":
    unittest.main()
