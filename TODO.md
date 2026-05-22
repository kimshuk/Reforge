# Daily Tasks — 2026-05-22
## Focus: NestJS Migration — Step 5 (close) → Step 6: LlmService

## Today's 3 Tasks

- [ ] **Close Step 5: wire the `sanitize()` method on TranscriptSanitizer**
  - All helper functions (`sanitizeSnippetList`, `buildSegments`, `normalizeText`) are already implemented — this task is a single method body that calls them in sequence and assembles the return value. The complete pipeline is: call `sanitizeSnippetList(rawSnippets)` to get cleaned snippets, capture the count, pass the result to `buildSegments()`, and return all three pieces (`llmTranscriptText`, `segmentIndex`, `cleanedSnippetCount`) as a `SanitizedTranscript`.
  - The `sanitize(rawSnippets: RawSnippet[]): SanitizedTranscript` signature must match the already-exported interface exactly — this is the only surface `AnalyzeService` will ever call, and a wrong return shape creates a silent breaking contract violation two steps later.
  - Gate: run `npm run build` and `npm test` inside `backend-nest/` with zero errors and all spec assertions passing before moving to Step 6 — a green build is what formally closes Step 5.

- [ ] **Step 6 scaffold: output types, JSON schema constant, and prompt builder**
  - Define TypeScript interfaces for the structured LLM output (`AnalysisPayload`, `Category`, `Keyword`, `KeywordSource`) inside `llm.service.ts`; the shape must mirror `backend/src/services/promptBuilder.js`'s `CATEGORY_EXTRACTION_SCHEMA` so that parsed responses are type-safe end-to-end without casting.
  - Port `CATEGORY_EXTRACTION_SCHEMA` (the JSON Schema object handed to the model's structured-output parameter) and `buildCategoryExtractionPrompt()` (the system + user message builder) from the Express `promptBuilder.js` as module-level exports in `llm.service.ts` — the system prompt is the behavioral contract with the model, and any divergence silently degrades output quality.
  - Keep both as non-class exports in the same file so `LlmService` methods can reference them directly and so the output types can be imported by `AnalyzeService` in Step 7 without a circular dependency.

- [ ] **Step 6 core: OpenRouter HTTP call, error mapping, and source resolution**
  - Implement `analyzeCategories()` on `LlmService` using OpenRouter's OpenAI-compatible HTTP API (base URL `https://openrouter.ai/api/v1`, model `openai/gpt-4o-mini`, temperature `0.2`) with the JSON schema passed via the structured-output format parameter; strip markdown code fences before parsing the response, then validate that `sourceType` matches the `transcriptType` argument and that `categories` is a non-empty array before returning.
  - Map all HTTP and API error shapes to `AppException` codes matching those thrown by Express `openaiService.js`: `OPENAI_AUTH_ERROR`, `OPENAI_QUOTA_OR_RATE_LIMIT`, `OPENAI_CONTEXT_LENGTH_EXCEEDED`, `OPENAI_BAD_REQUEST`, and `OPENAI_ANALYZE_FAILED` — these codes are the exact contract the iOS client decodes into user-facing messages, so any mismatch silently breaks the app.
  - Port `resolveYoutubeSources()` as a private method: build a `formatTimestamp(startSec) → segmentIndexEntry` lookup from the `segmentIndex`, validate each keyword's `source.ref` format and existence in the map, replace valid refs with full YouTube timestamp URLs (`?t=<sec>s`), and throw `AppException(502, 'OPENAI_INVALID_SOURCE_REF', ...)` on any ref that fails — refer to `openaiService.js` for the full validation sequence (format check, map lookup, type check).

## Migration Progress
**Completed steps:**
- 1 — Bootstrap NestJS scaffold (health module, main.ts, tsconfig strict mode)
- 2 — Project structure (analyze/ and common/ stubs, AnalyzeModule wired into AppModule)
- 3 — AppException class (common/app.exception.ts)
- 4 — YoutubeService (Python subprocess, URL → transcript text, error classification)

**Current step:** 5 → 6 — TranscriptSanitizerService (one stub remaining: `sanitize()`) → LlmService (OpenRouter call + structured output)

**Remaining steps:**
- 6 — LlmService (OpenRouter call + structured output) — *starting today*
- 7 — AnalyzeService (orchestrate URL → youtube → sanitize → llm, or text → sanitize → llm)
- 8 — AnalyzeController (POST /analyze with SSE streaming)
- 9 — AppExceptionFilter (finalize `{ error: { code, message } }` envelope + global registration)

## Why These Tasks
Task 1 is a one-method closing move whose output shape is the typed contract between the sanitizer and every downstream caller — it must be green before LlmService can safely import from it. Tasks 2 and 3 front-load the two hardest surfaces of Step 6 (the prompt/schema contract and the source-resolution logic) so that AnalyzeService in Step 7 can wire them without revisiting LlmService internals.
