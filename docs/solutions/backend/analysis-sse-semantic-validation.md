---
title: Analysis SSE failures can combine model violations and abbreviation miscounts
date: 2026-10-01
area: backend
status: verified
---

## Problem

Android displayed `Analysis failed on the backend. Please try again.` while `/analyze?stream=progress` returned HTTP 200. The final SSE event was an error, and `analysis_runs` recorded `LLM_CLIPPINGS_INVALID_JSON` during `extracting_clippings`.

## Mistake and why it failed

Treating every explanation validation failure as model noncompliance hid a deterministic validator defect. A stronger-model comparison also failed because `sentence_count` treated the final period in `U.S.-China` and `U.S. Treasuries` as a sentence boundary. Valid one-sentence explanations were counted as two; regenerating them could not reliably correct that false feedback. Separate genuine brief-length and contextual-sentence violations also occurred with the original model.

## Verified approach

- Inspect the final SSE event and persisted `failureStage`, `errorCode`, and `safeErrorMessage`; HTTP 200 alone does not establish analysis success.
- Capture the generated explanation at the validation boundary and reproduce its sentence count directly before changing models or relaxing requirements.
- `backend-fastapi/app/explanation_validation.py` now protects directly attached hyphen compounds and `U.S. Treasury` / `U.S. Treasuries`, while preserving genuine sentence-ending abbreviations.
- Regression cases in `backend-fastapi/tests/test_llm_validation.py` cover both valid continuations and real boundaries. The focused validation, analysis, and enrichment suites passed 53 tests.
- With the corrected validator, an isolated full-video run using `gpt-4.1-mini` completed with 12 categories and 33 keywords. The original model still produced a genuine length violation. After explicit cost approval, the local backend model was changed and its active settings and health verified. Repository model defaults were not changed.

## Prevention

Keep the approved simple 1 / contextual 2–3 / detailed 3–5 sentence contract. Compare actual generated text with validator behavior; distinguish deterministic false rejections from genuine model violations. Docker Compose does not mount the backend source, so rebuild the image for code changes and recreate the service for environment changes. Model changes that increase API costs require explicit approval.
