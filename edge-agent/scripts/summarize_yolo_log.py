"""Compress a YOLO session log into a compact, LLM-friendly summary.

The raw viewer log records every frame snapshot (throttled to ~0.5 s) plus
every behavior/activity change, which can easily be thousands of lines for a
few minutes of video.  This script drops the FRAME noise, merges consecutive
changes, aggregates per-activity durations, and emits a structured timeline
small enough to hand directly to an LLM.

Compression strategy:
  * header lines (also timestamped) become ``meta``;
  * FRAME snapshots are dropped entirely;
  * BEHAVIOR_CHANGE rows are folded into *activity segments* — consecutive
    rows sharing the same activity become one ``[start→end] activity=...
    held=Ns`` entry, absorbing per-frame persons/action flicker;
  * EVENT / CONTROL / ERROR / SESSION_END lines are kept as-is.

Usage::

    python edge-agent/scripts/summarize_yolo_log.py [LOG_FILE] [--json]

Without LOG_FILE the most recent ``edge-agent/data/yolo-logs/yolo_session_*.txt``
is used.  Output goes to stdout by default; add ``--out FILE`` to write to a
``*_llm.txt`` file next to the source log.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ─── Parsing ───

_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3})\s*\|\s*(?P<body>.*)$"
)


def _parse_line(line: str) -> Optional[Tuple[float, str, str]]:
    """Return (epoch_seconds, kind, details); None for non-timestamped lines."""
    m = _LINE_RE.match(line.strip())
    if not m:
        return None
    ts = datetime.fromisoformat(m.group("ts")).timestamp()
    body = m.group("body")
    kind, _, details = body.partition(" ")
    return ts, kind.strip(), details.strip()


_META_KEYS = ("started_at", "source", "model", "device")


def _field(details: str, key: str) -> Optional[str]:
    """Extract ``key=value`` from a details string."""
    for token in details.split():
        if token.startswith(f"{key}="):
            return token[len(key) + 1:]
    return None


# ─── Summary builder ───

def build_summary(log_path: Path) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "source_log": log_path.name,
        "meta": {},
        "segments": [],
        "fall_events": [],
        "controls": [],
        "warnings": [],
        "stats": {},
    }

    start_ts: Optional[float] = None
    end_ts: Optional[float] = None
    frames = 0
    fps_sum = 0.0
    fps_count = 0
    events: List[Tuple[float, str, str]] = []

    with log_path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            parsed = _parse_line(raw)
            if parsed is None:
                continue
            ts, kind, details = parsed
            if kind in _META_KEYS:
                # Header lines are timestamped in this format: "source=0"
                summary["meta"][kind] = details
                continue
            events.append((ts, kind, details))
            if start_ts is None:
                start_ts = ts
            end_ts = ts

            if kind == "FRAME":
                frames += 1
                fps_val = _field(details, "fps")
                if fps_val is not None:
                    fps_sum += float(fps_val)
                    fps_count += 1

    if start_ts is None:
        raise ValueError(f"empty or unparseable log: {log_path}")

    # ─── Activity segments: fold BEHAVIOR_CHANGE rows by activity ───
    segments: List[Dict[str, Any]] = []
    current_activity: Optional[str] = None
    seg_start: Optional[float] = None
    fall_peak = 0.0
    action_first: Optional[str] = None

    def _flush_segment(until: float) -> None:
        nonlocal current_activity, seg_start, fall_peak, action_first
        if current_activity is not None and seg_start is not None:
            segments.append({
                "start": _fmt_time(seg_start, start_ts),
                "end": _fmt_time(until, start_ts),
                "activity": current_activity,
                "held_s": round(max(0.0, until - seg_start), 1),
                "fall_peak": round(fall_peak, 2),
                "action": action_first,
            })
        current_activity = None
        seg_start = None
        fall_peak = 0.0
        action_first = None

    for ts, kind, details in events:
        if kind == "BEHAVIOR_CHANGE":
            activity = _field(details, "activity") or "unknown"
            if activity != current_activity:
                _flush_segment(ts)
                current_activity = activity
                seg_start = ts
                action_first = _field(details, "action")
            fall = _num(_field(details, "fall_score")) or 0.0
            fall_peak = max(fall_peak, fall)
        elif kind == "SESSION_END":
            _flush_segment(ts)
            end_ts = ts
            summary["stats"]["end_reason"] = _field(details, "reason") or "?"
            summary["stats"]["fall_events"] = _num(_field(details, "fall_events")) or 0
        elif kind == "EVENT":
            _flush_segment(ts)
            # Keep fall_suspected but strip the long posture sequence; the
            # LLM only needs type/confidence/frame.
            if "fall_recovered" in details:
                summary["fall_events"].append(
                    {"t": _fmt_time(ts, start_ts), "detail": "fall_recovered"}
                )
            else:
                short = f"fall_suspected conf={_field(details, 'confidence')} frame={_field(details, 'frame')}"
                summary["fall_events"].append(
                    {"t": _fmt_time(ts, start_ts), "detail": short}
                )
        elif kind == "CONTROL":
            _flush_segment(ts)
            summary["controls"].append(
                {"t": _fmt_time(ts, start_ts), "detail": details}
            )
        elif kind == "ERROR":
            _flush_segment(ts)
            summary["warnings"].append({"t": _fmt_time(ts, start_ts), "detail": details})
    _flush_segment(end_ts or start_ts)

    # Fold transient segments (< 0.3 s, no fall) into the previous one.
    # A confirmed activity needs ≥5 frames (~0.17 s), so shorter bursts are
    # almost certainly keypoint noise, not real activity.  Also merges the
    # 0.0 s stubs produced when an EVENT splits a segment.
    merged: List[Dict[str, Any]] = []
    for seg in segments:
        if merged and seg["held_s"] < 0.3 and seg["fall_peak"] == 0.0:
            merged[-1]["end"] = seg["end"]
            merged[-1]["held_s"] = round(
                merged[-1]["held_s"] + seg["held_s"], 1)
            continue
        merged.append(seg)
    summary["segments"] = merged

    # ─── Stats ───
    elapsed = round((end_ts or start_ts) - start_ts, 1)
    durations: Dict[str, float] = {}
    for seg in segments:
        durations[seg["activity"]] = durations.get(seg["activity"], 0.0) + seg["held_s"]
    summary["activity_durations"] = {
        k: round(v, 1) for k, v in sorted(durations.items(), key=lambda kv: -kv[1])
    }
    summary["stats"].update({
        "elapsed_seconds": elapsed,
        "frame_snapshots": frames,
        "avg_fps": round(fps_sum / fps_count, 1) if fps_count else 0.0,
        "segments": len(segments),
        "fall_events": summary["stats"].get("fall_events", len(summary["fall_events"])),
    })
    return summary


def _fmt_time(ts: float, start_ts: float) -> str:
    """Relative time as [+mm:ss.d] from session start."""
    delta = max(0.0, ts - start_ts)
    minutes, seconds = divmod(int(delta), 60)
    return f"+{minutes:02d}:{seconds:02d}.{int((delta % 1) * 10)}"


def _num(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except ValueError:
        return None


# ─── Text rendering (LLM-friendly) ───

def render_text(summary: Dict[str, Any]) -> str:
    meta = summary["meta"]
    stats = summary["stats"]
    lines: List[str] = []
    lines.append("YOLO SESSION SUMMARY (compressed from " + summary["source_log"] + ")")
    if meta:
        lines.append(
            "meta: " + " ".join(f"{k}={v}" for k, v in meta.items())
        )
    lines.append(
        f"stats: elapsed={stats['elapsed_seconds']}s frames={stats['frame_snapshots']} "
        f"avg_fps={stats['avg_fps']} fall_events={int(stats['fall_events'])} "
        f"end={stats.get('end_reason', '?')}"
    )

    durations = summary["activity_durations"]
    total = sum(durations.values()) or 1.0
    if durations:
        lines.append("activity_durations (seconds, % of session):")
        for activity, seconds in durations.items():
            lines.append(
                f"  - {activity}: {seconds:.1f}s ({seconds / total * 100:.0f}%)"
            )

    lines.append("activity_segments:")
    for seg in summary["segments"]:
        lines.append(
            f"  [{seg['start']} -> {seg['end']}] activity={seg['activity']} "
            f"held={seg['held_s']}s fall_peak={seg['fall_peak']}"
        )

    if summary["fall_events"]:
        lines.append("fall_events:")
        for event in summary["fall_events"]:
            lines.append(f"  [{event['t']}] {event['detail']}")

    if summary["controls"]:
        lines.append("controls:")
        for control in summary["controls"]:
            lines.append(f"  [{control['t']}] {control['detail']}")

    if summary["warnings"]:
        lines.append("warnings:")
        for warn in summary["warnings"]:
            lines.append(f"  [{warn['t']}] {warn['detail']}")
    return "\n".join(lines)


def render_json(summary: Dict[str, Any]) -> str:
    return json.dumps(summary, ensure_ascii=False, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compress YOLO session log for LLM")
    parser.add_argument("log", nargs="?", help="path to yolo_session_*.txt (default: newest)")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    parser.add_argument("--out", help="write to this file instead of stdout")
    args = parser.parse_args()

    if args.log:
        log_path = Path(args.log)
    else:
        log_dir = Path(__file__).resolve().parents[2] / "edge-agent" / "data" / "yolo-logs"
        candidates = sorted(log_dir.glob("yolo_session_*.txt"))
        if not candidates:
            print("no log files found under", log_dir, file=sys.stderr)
            return 2
        log_path = candidates[-1]

    try:
        summary = build_summary(log_path)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    output = render_json(summary) if args.json else render_text(summary)
    if args.out:
        Path(args.out).write_text(output + "\n", encoding="utf-8")
        print(f"written: {args.out} ({len(output)} chars)")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
