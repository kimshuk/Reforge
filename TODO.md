# Daily Tasks — 2026-05-25
## Focus: NestJS Migration — Step 5 (close) → Step 6: LlmService

## Today's 3 Tasks

- [ ] **Close Step 5: wire `sanitize()` in TranscriptSanitizer**
  - All the heavy logic (`sanitizeSnippetList`, `buildSegments`, `normalizeText`) already lives above the class as module-level functions — `sanitize()` just needs to call them in order, forwarding the raw snippet array in and assembling the three-field `SanitizedTranscript` return value.
  - The return type (`llmTranscriptText`, `segmentIndex`, `cleanedSnippetCount`) is the typed contract that both LlmService and AnalyzeService will consume in Steps 6–7; a mismatched shape here creates a silent breaking mismatch two steps downstream.
  - Done when `npm run build` and `npm test` both pass inside `backend-nest/` with zero type errors and all spec assertions green.

- [ ] **LlmService scaffold — output types, JSON schema constant, and prompt builder**
  - Define TypeScript interfaces for the structured LLM response (`AnalysisPayload`, `Category`, `Keyword`, `KeywordSource`) directly in `llm.service.ts`; these must mirror the JSON Schema handed to the model so parsed responses are fully type-safe without casting anywhere downstream.
  - Port `CATEGORY_EXTRACTION_SCHEMA` (the JSON Schema object passed to the model's structured-output parameter) and `buildCategoryExtractionPrompt()` (the system + user message builder) from the Express `promptBuilder.js` as non-class module-level exports — the system prompt is the behavioral contract with the model and any divergence silently degrades output quality.
  - Keeping these as module-level exports (not class methods) ensures `AnalyzeService` can import the output types in Step 7 without creating a circular dependency between the two service classes.

- [ ] **LlmService core — OpenRouter HTTP call, error mapping, and source resolution**
  - Implement `analyzeCategories()` using OpenRouter's OpenAI-compatible HTTP API (base URL `https://openrouter.ai/api/v1`, model `openai/gpt-4o-mini`, temperature `0.2`) passing the JSON schema via the structured-output format parameter; strip markdown code fences before parsing, then validate that `sourceType` matches the `transcriptType` argument and that `categories` is a non-empty array before returning.
  - Map all HTTP and API error shapes to `AppException` codes that exactly match those thrown by Express `openaiService.js` — `OPENAI_AUTH_ERROR`, `OPENAI_QUOTA_OR_RATE_LIMIT`, `OPENAI_CONTEXT_LENGTH_EXCEEDED`, `OPENAI_BAD_REQUEST`, `OPENAI_ANALYZE_FAILED` — these exact strings are what the iOS client decodes into user-facing messages, so any mismatch silently breaks the app.
  - Port `resolveYoutubeSources()` as a private method: build a timestamp lookup from `segmentIndex`, validate each keyword's `source.ref` against the map, replace valid refs with full YouTube timestamp URLs (`?t=<sec>s`), and throw `AppException(502, 'OPENAI_INVALID_SOURCE_REF', ...)` on any ref that fails — refer to `backend/src/services/openaiService.js` for the full validation sequence.

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
Task 1 is the single closing move for Step 5 — its typed return shape is the upstream contract that LlmService and AnalyzeService both depend on, so it must be green before any LlmService work begins. Tasks 2 and 3 front-load the two hardest surfaces of Step 6 (the prompt/schema/type contract and the HTTP + error-mapping logic) so that AnalyzeService in Step 7 can wire them together without revisiting LlmService internals.
