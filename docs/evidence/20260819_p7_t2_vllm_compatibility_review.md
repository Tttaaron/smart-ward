# P7/T2 Real vLLM Compatibility Review

Date: 2026-08-19  
P7 baseline: `feature/cloud-llm-p7` after `7b4f120`  
External reference: T2 delivery package dated 2026-08-12 (kept outside Git under `docs/temp-evidence/`)

## Evidence Reviewed

The supplied T2 package contains a real MQTT and Qwen2.5-14B/vLLM E2E record:

- request topic: `ward/W-01/node/EDGE-W01-B01/inference/request`
- response topic: `node/EDGE-W01-B01/inference/response`
- request/response `event_id` and `trace_id` both round-trip
- model: `qwen2.5-14b` / `Qwen2.5-14B-Instruct-AWQ`
- end-to-end latency: 410.4 ms; model latency: 406.5 ms
- acceptance record: 18 tests passed, 0 failures, 0 errors, 0 skipped

The E2E record is a supplied artifact, not a rerun in the current P7 environment. It must not be used to claim that the current branch has independently completed real 14B acceptance.

| External file | SHA-256 |
| --- | --- |
| `app/llm_client.py` | `C2EC3451FE0B79294DCC6B11692FA070F2FEB7FA66D5C34571F18EBAE14444FA` |
| `app/mqtt_handler.py` | `96BD774DBCDE1F03BB93B3766E1F42F50C6D7398235CB10FEF62CF36BE9B9528` |
| `app/schemas.py` | `B3C59B0C576FAD1D39495F737310FDC380705AC39C498CB187C73D44F93F9FF6` |
| `t2-cloud-llm-real-e2e.json` | `DD94AABA5EBC396A243E44C9E1E474818C4FDCA668C829EFF1FD54F8A299BF49` |
| `t2-cloud-llm-acceptance.json` | `8B20646318A8456857EA64E0C87C6AC78DEC01CB314C9A486A65EE7AA19CAB06` |

## Compatibility Result

The MQTT topics, `cloud`/`hybrid` request modes, envelope fields, and core inference request/response fields are compatible. No protocol-breaking conflict was found.

T2 has stronger real-vLLM deployment behavior: Base URL normalization, API-key headers, model readiness probing, and a default prohibition on silently returning mock output after vLLM failure. P7 has stronger cloud-edge runtime behavior: structured stage logs, duplicate response reuse, service-side `timeout_ms` enforcement, `status=timeout`, and edge SQLite timeout handling.

The current P7 implementation therefore selectively adopts the T2 vLLM configuration behavior while retaining the P7 MQTT handler and timeout contract. The T2 MQTT handler was not copied because it lacks the P7 timeout/status/logging behavior.

## Remaining Acceptance Work

1. P6 must provide the current vLLM endpoint and permitted runtime credentials through environment variables, never Git.
2. Run `GET /ready` against the configured endpoint and confirm `qwen2.5-14b` is listed by `/models`.
3. Re-run MQTT E2E from the current P7 commit, preserving request/response, cloud log, edge log, and SQLite results.
4. Run the controlled mock timeout scenario separately; the supplied T2 E2E uses `timeout_ms=90000` and does not prove the P7 `status=timeout` path.
