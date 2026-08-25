# P7 MQTT Fault-Tolerance Acceptance Evidence

## Scope

This directory contains the unified P1 edge-side and P6 cloud-side evidence for the six MQTT fault-tolerance scenarios. The acceptance count for this run is **20 target cases per scenario**. The historical MQTT sync template counts (25/26/28) are not used as hard gates for this project run.

## Common environment

- Edge node: `EDGE-W01-B02`
- Edge commit: `54f0dbc` (`origin/p1/edge-timeout-fix`)
- Cloud service: `cloud-llm-service`, `LLM_MODE=mock`, uvicorn `:8004`
- Broker: real Mosquitto, forwarded local port `1883`
- Protocol: MQTT 3.1.1, QoS 1

## Acceptance summary

| Stage | Scenario | Target | Result | Evidence |
|---|---|---:|---:|---|
| 1 | Duplicate request deduplication | 20 identical requests | 1 real inference, 19 `duplicate_reused`, 20 responses | `stage1/` |
| 2 | Duplicate response idempotency | 1 request + 20 responses | 1 state update, 19 `status=duplicate`, one SQLite row | `stage2/` |
| 3 | Invalid `judgment` | 20 distinct events | 20/20 `fallback_edge/invalid_judgment`, 0 completed | `stage3/` |
| 4 | Unknown `event_id` | 20 unknown responses | 20/20 ignored, 0 SQLite rows, known event unaffected | `stage4/` |
| 5 | Trace mismatch | 20 wrong-trace responses | 20/20 `trace_mismatch`, then timeout fallback, 0 completed | `stage5/` |
| 6 | Cloud unavailable / timeout | 20 target requests | 20/20 timeout fallback, 0 completed | `stage6/` |

## Stage 6 counting note

P6's `phase6_offline_requests_captured.log` contains the 20 target requests used for acceptance. The P1 edge log and SQLite snapshot contain 25 timeout/fallback records because the edge scenario driver produced five additional events during the same offline window. Those five are incidental background events and are excluded from the target denominator. The formal result is therefore **20/20 target requests passed**; the raw P1 total of 25 is retained in `stage6/p1-sqlite-timeout.txt` for auditability.

After cloud recovery, P1 also verified one new request completed normally with `status=completed`, `state=notified`, and `synced=1`; see the recovery files in `stage6/`.

## Interpretation boundaries

- Stage 1 proves cloud-side request deduplication. Its externally injected responses can be logged as `unknown` by the edge and do not prove edge response idempotency.
- Stage 2 is the edge idempotency proof: the first response updates the real pending event and the 19 byte-identical replays are ignored.
- Stages 3-6 use controlled response injection or cloud outage; they are resilience tests, not vLLM quality tests.
- The evidence files are copied from the P1/P6 submissions. Temporary source directories under `docs/temp-evidence/` remain untracked and must not be committed.
