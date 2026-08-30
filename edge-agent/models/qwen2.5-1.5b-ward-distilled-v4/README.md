# Qwen2.5-1.5B Ward Distilled v4 Balanced

## Final deployable model

- GGUF: `/root/autodl-tmp/qwen/models/Qwen2.5-1.5B-Ward-Distilled-v4-GGUF/qwen2.5-1.5b-ward-v4-q6_k.gguf`
- Quantization: `Q6_K`
- File size: `1,272,739,456 bytes` (`1.273 GB`, `1213.78 MiB`)
- SHA-256: `f7ffc9751378a8f67bed3a6a8872f0f20c40b48cc4223b5560e225bd547ca8a0`
- SHA-256 short form: `f7ffc9751378a8f6`

The previous v3 model remains available and was not overwritten.

## What changed

1. Built a leakage-free 5,000-row mixed training set (`v4.1.0`):
   - 2,000 ward-domain rows
   - 1,500 official GSM8K training rows
   - 1,500 MBPP-derived code execution/output reasoning rows
2. Trained a general-capability LoRA from the original Qwen2.5-1.5B-Instruct base.
3. Fused the established ward LoRA and the new general LoRA by exact rank concatenation.
4. Screened multiple fusion weights. The selected balance is:
   - ward delta weight: `0.50`
   - general delta weight: `0.75`
5. Merged the selected adapter and converted it to Q6_K GGUF.

The frozen 600-question benchmark was not used as training data. The builder
reported zero exact overlap with the frozen GSM8K test questions, and CRUXEval
was not used as a training source.

## Full evaluation results

All general-capability figures below use the same frozen 600-question benchmark,
temperature 0, and the same symmetric relaxed answer extractor.

| Model | GSM8K (200) | CRUXEval-O (200) | BBH (200) | Macro |
|---|---:|---:|---:|---:|
| Original Qwen2.5-1.5B | 69.0% | 26.0% | 31.0% | 42.0% |
| Previous ward v3 Q6_K | 47.5% | 16.5% | 41.0% | 35.0% |
| New ward v4 Q6_K | 60.0% | 25.0% | 35.0% | 40.0% |

New v4 versus original 1.5B retention:

- Math: `86.96%`
- Code: `96.15%`
- Natural-language/logic: `112.90%`
- Macro retention: `95.24%`

New v4 versus previous v3 Q6_K:

- Math: `+12.5 percentage points`
- Code: `+8.5 percentage points`
- BBH: `-6.0 percentage points`
- Macro: `+5.0 percentage points`

Ward-domain full evaluation (200 samples):

- Cloud judgment accuracy: `99.0%`
- Cloud judgment macro-F1: `99.14%`
- Event urgency accuracy: `82.0%`
- Format valid rate: `100.0%`
- Mean reference similarity: `0.4673`

This is a trade-off model: math and code improved substantially over v3, while
BBH and ward urgency are slightly lower than v3. The core ward judgment remains
99% accurate on this test set.

## Memory and speed check

Strict single-instance deployment profile:

```bash
--n-gpu-layers 20 --ctx-size 4096 --parallel 1 \
--cache-type-k q8_0 --cache-type-v q8_0
```

- Idle GPU memory: `1438 MiB`
- GPU memory after one request: `1442 MiB`
- One short ward request total time: `0.370 s`
- Prompt processing: `89 ms`
- Generation: about `44.4 tokens/s`

The test establishes runtime GPU memory below 1.5 GiB for this exact profile.
It does not establish a 75% TTFT reduction because a paired original-model TTFT
test has not yet been run.

## Start and use

```bash
qwen-start-v4
qwen-status
qwen-chat 'B07患者疑似跌倒，置信度0.93，网络断开，请给出简洁处置建议。'
```

Stop the service with:

```bash
qwen-stop
```

OpenAI-compatible endpoint: `http://127.0.0.1:8000/v1`.

## Evidence files

- General Q6 full report: `datasets/ward-nlu-500-v1/distillation/v4/general-v4-q6-full.json`
- General Q6 raw samples: `datasets/ward-nlu-500-v1/distillation/v4/general-v4-q6-full.samples.jsonl`
- Ward Q6 full report: `datasets/ward-nlu-500-v1/distillation/v4/domain-v4-q6-full.json`
- Selected pre-quantization full report: `datasets/ward-nlu-500-v1/distillation/v4/general-combo-a050-full.json`
- Selected pre-quantization ward report: `datasets/ward-nlu-500-v1/distillation/v4/domain-combo-a050-full.json`
- Mixed-data manifest: `datasets/ward-nlu-500-v1/distillation/v4/manifest-v4.1.0.json`
- Adapter fusion manifest: `/root/autodl-tmp/qwen/models/Qwen2.5-1.5B-Ward-LoRA-v4-combo-a050/combination_manifest.json`
