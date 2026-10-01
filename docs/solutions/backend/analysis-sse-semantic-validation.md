---
title: Analysis SSE failures can combine model violations and abbreviation miscounts
date: 2026-10-01
area: backend
status: verified
---

## Problem

Android displayed `Analysis failed on the backend. Please try again.` while `/analyze?stream=progress` returned HTTP 200. The final SSE event was an error, and `analysis_runs` recorded `LLM_CLIPPINGS_INVALID_JSON` during `extracting_clippings`.

## Mistake and why it failed

Treating every explanation validation failure as model noncompliance hid a deterministic validator defect. A stronger-model comparison also failed because `sentence_count` treated the final period in `U.S.-China` and `U.S. Treasuries` as a sentence boundary. Valid one-sentence explanations were counted as two; regenerating them could not reliably correct that false feedback. Separate genuine brief-length and contextual-sentence violations also occurred with the original model. A subsequent phone retry showed that one successful stronger-model run did not establish reliable recovery; contextual sentence violations still occurred. Sequential topic extraction and whole-batch correction made these failures expensive to wait for.

## Verified approach

- Inspect the final SSE event and persisted `failureStage`, `errorCode`, and `safeErrorMessage`; HTTP 200 alone does not establish analysis success.
- Capture the generated explanation at the validation boundary and reproduce its sentence count directly before changing models or relaxing requirements.
- `backend-fastapi/app/explanation_validation.py` now protects directly attached hyphen compounds and `U.S. Treasury` / `U.S. Treasuries`, and comma/colon/semicolon continuations such as `U.S.,`, while preserving genuine sentence-ending abbreviations.
- `backend-fastapi/app/prompts.py` requests contextual and detailed explanations as bounded arrays of single sentences. `normalize_candidate_sentences` in `app/llm.py` checks item counts, sentence boundaries, and joined lengths before returning the existing public string fields and running semantic validation. This makes sentence counts structural rather than relying only on prose instructions.
- `app/analysis.py` extracts up to three independent topic chunks concurrently, gathers results in transcript order, and cancels/drains pending tasks on failure. It does not share the database session across provider calls.
- A subsequent HTTP replay reached grouping but failed its exact occurrence-ID partition. `generate_keyword_categories` now allows up to three semantic correction attempts with the original occurrence list and explicit required IDs. Provider errors are not retried.
- Regression tests cover sentence normalization, punctuation, concurrency bounds, stable order, cancellation, and category repair. The full backend suite passed 191 tests with one skipped test.
- Final verification used the actual Android Analyze flow for the same video: the backend recorded completion in 59 seconds and the device displayed result categories. The earlier isolated successful run took 243 seconds. These are measured runs, not a guarantee for every video.
- With the corrected validator, an isolated full-video run using `gpt-4.1-mini` completed with 12 categories and 33 keywords. The original model still produced a genuine length violation. After explicit cost approval, the local backend model was changed and its active settings and health verified. Repository model defaults were not changed.

## Prevention

Keep the approved simple 1 / contextual 2–3 / detailed 3–5 sentence contract. Compare actual generated text with validator behavior; distinguish deterministic false rejections from genuine model violations. Docker Compose does not mount the backend source, so rebuild the image for code changes and recreate the service for environment changes. Model changes that increase API costs require explicit approval. Do not treat a single isolated model success as proof that the phone flow is fixed; verify the real HTTP final event and actual device result. Keep correction retries bounded and preserve all occurrence IDs instead of dropping unassigned keywords.
