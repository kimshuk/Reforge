# Daily Tasks — 2026-05-19
## Focus: NestJS Migration — Step 5 (finish) → Step 6: LlmService (start)

## Today's 3 Tasks

- [ ] **Complete Step 5: Wire `sanitize()` and verify clean build**
  - Replace the `sanitize()` throw-stub in `TranscriptSanitizer` with a real implementation that accepts `RawSnippet[]`, passes it through `sanitizeSnippetList` and then `buildSegments`, and returns a `SanitizedTranscript` — this is the only public surface `AnalyzeService` will call, so getting its shape right now avoids a breaking change later.
  - Confirm `formatTimestamp` remains exported at module level (not enclosed in the class), since `LlmService` will import it as a standalone utility for source resolution in Step 6.
  - Run `npm run build` and `npm test` in `backend-nest/` with zero errors and all tests green — this is the hard gate that closes Step 5 and unlocks Step 6.

- [ ] **Step 6 scaffold: define output types, JSON schema, and prompt builder**
  - Define TypeScript interfaces for the structured LLM output — `AnalysisPayload`, `Category`, `Keyword`, and `Source` — mirroring the shape described in the Express `promptBuilder.js` JSON schema (`CATEGORY_EXTRACTION_SCHEMA`). These types are the contract between `LlmService` and `AnalyzeService`.
  - Implement `CATEGORY_EXTRACTION_SCHEMA` as a typed constant and `buildCategoryExtractionPrompt()` as a module-level function in `llm.service.ts`, replicating the system prompt and user message structure from the Express reference exactly — the prompt text itself is what drives model output quality, so divergence here silently degrades results.
  - Keep both the schema and prompt builder as non-class exports within `llm.service.ts` (no separate file needed), so `LlmService` can import them directly in Task 3.

- [ ] **Step 6 core: implement OpenRouter call and YouTube source resolution**
  - Implement the main `analyzeCategories()` method on `LlmService` using OpenRouter's OpenAI-compatible HTTP API (base URL `https://openrouter.ai/api/v1`, model `openai/gpt-4o-mini`); structure the call to use JSON schema structured output the same way the Express backend does via `text.format`, and map HTTP/API error shapes (401, 429, `context_length_exceeded`, 400, other) to the corresponding `AppException` codes (`OPENAI_AUTH_ERROR`, `OPENAI_QUOTA_OR_RATE_LIMIT`, `OPENAI_CONTEXT_LENGTH_EXCEEDED`, `OPENAI_BAD_REQUEST`).
  - Implement `resolveYoutubeSources()` as a private method: build a lookup map from `formatTimestamp(segment.startSec)` → segment, then for every keyword in the payload validate that `source.type === 'youtube'`, that `source.ref` matches the `MM:SS` or `H:MM:SS` timestamp pattern, and that the timestamp exists in the map — throw `AppException(502, 'OPENAI_INVALID_SOURCE_REF', ...)` on any violation. Replace `source.ref` with the full YouTube timestamp URL (`?t=<sec>s`) before returning.
  - Validate the final payload: confirm `sourceType` matches the input `transcriptType`, that `categories` is a non-empty array, and that `parseStructuredOutput()` strips any markdown code fences before JSON parsing — these guards prevent silent garbage from reaching the iOS client.

## Migration Progress
**Completed steps:**
- 1 — Bootstrap NestJS scaffold (health module, main.ts, tsconfig strict mode)
- 2 — Project structure (analyze/ and common/ stubs, AnalyzeModule wired into AppModule)
- 3 — AppException class (common/app.exception.ts)
- 4 — YoutubeService (Python subprocess, URL → transcript text, error classification)

**Current step:** 5 → 6 — TranscriptSanitizerService (one stub remaining: `sanitize()`) → LlmService (OpenRouter call + structured output)

**Remaining steps:**
- 6 — LlmService (OpenRouter call + structured output: categories + keywords) — *started today*
- 7 — AnalyzeService (orchestrate URL → youtube → sanitize → llm, or text → sanitize → llm)
- 8 — AnalyzeController (POST /analyze with SSE streaming)
- 9 — AppExceptionFilter (finalize { error: { code, message } } envelope + global registration)

## Why These Tasks
Task 1 is a single-file finishing move that closes Step 5 and unlocks the rest of the pipeline. Tasks 2 and 3 front-load Step 6's two hardest surfaces — the prompt contract and the source resolution logic — so that AnalyzeService (Step 7) can wire them together without revisiting LlmService internals.
