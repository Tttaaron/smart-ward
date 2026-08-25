# 2026-08-26 Current Delivery Status

This addendum is the current status reference for the P7 cloud/edge delivery. Older progress documents retain their historical snapshots and should not be read as the latest acceptance result.

## Completed P7 delivery

- `cloud-llm-service` MQTT consumer, schema validation, request deduplication, timeout response, structured stages, `/ready`, `/health`, and `/stats`.
- Local cloud regression: 18/18 tests passed.
- Edge regression: 100/100 tests passed in the dedicated dependency environment.
- Real Qwen2.5-14B/vLLM CLOUD and HYBRID MQTT acceptance completed with model `Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4` (`gptq-int4`).
- SQLite raw-query evidence completed for the real vLLM CLOUD/HYBRID events.
- MQTT fault-tolerance stages 1-6 completed with a 20-case target per stage. Evidence is in `20260825_p7_fault_tolerance/`.
- The stage-6 target denominator is 20. Five additional timeout records produced by the background scenario driver are retained as incidental records and excluded from the target result.
- Latest P7 branch commit: `bb955af` (`docs(p7): archive six MQTT fault-tolerance stages`).

## Still open for the overall project

These are project-level items, not blockers for the P7 cloud evidence itself:

- Merge the reviewed `feature/cloud-llm-p7` PR into `master`.
- Jetson Orin Nano hardware measurements: TTFT, RSS, throughput, and concurrent vision/LLM resource usage.
- Formal 1.5B/0.5B/14B comparison report and 500+ sample NLU evaluation, if required by the final submission rubric.
- Final technical report/PPT consistency freeze, demonstration video, and final submission package.

## Evidence policy

`docs/temp-evidence/` is source material only and must not be committed. The formal six-stage archive and the vLLM acceptance archive under `docs/evidence/` are the reviewable records.
