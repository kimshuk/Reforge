# Daily Tasks — 2026-05-24
## Focus: NestJS Migration — Step 5 (close) → Step 6: LlmService

## Today's 3 Tasks

- [ ] **Close Step 5: implement the `sanitize()` method body in TranscriptSanitizer**
  - All helper logic (`sanitizeSnippetList`, `buildSegments`) is already fully implemented above the class — the `sanitize()` method just needs to call them in sequence: run raw snippets through `sanitizeSnippetList()`, capture the count, pass the result to `buildSegments()`, and return the three-field `SanitizedTranscript` object.
  - The return shape (`llmTranscriptText`, `segmentIndex`, `cleanedSnippetCount`) is the typed contract that AnalyzeService will consume in Step 7 — a wrong shape here creates a silent breaking mismatch two steps downstream.
  - Gate: `npm run build` and `npm test` inside `backend-nest/` must pass with zero errors and all spec assertions green before Step 6 begins.

- [ ] **LlmService scaffold — output types, JSON schema constant, and prompt builder**
  - Define TypeScript interfaces for the structured LLM output (`AnalysisPayload`, `Category`, `Keyword`, `KeywordSource`) in `llm.service.ts`; these must mirror the JSON schema handed to the model so parsed responses are type-safe end-to-end without casting. Cross-reference `backend/src/services/promptBuilder.js` for the exact schema shape.
  - Port `CATEGORY_EXTRACTION_SCHEMA` (the JSON Schema object passed to the model's structured-output parameter) and `buildCategoryExtractionPrompt()` (the system + user message builder) from Express `promptBuilder.js` as module-level exports alongside the class — the system prompt is the behavioral contract with the model and any divergence silently degrades output quality.
  - Keep both as non-class module-level exports so `LlmService` methods reference them directly and `AnalyzeService` can import the output types in Step 7 without creating a circular dependency.

- [ ] **LlmService core — OpenRouter HTTP call, error mapping, and source resolution**
  - Implement `analyzeCategories()` using OpenRouter's OpenAI-compatible HTTP API (base URL `https://openrouter.ai/api/v1`, model `openai/gpt-4o-mini`, temperature `0.2`), passing the JSON schema via the structured-output format parameter; strip markdown code fences before parsing, then validate that `sourceType` matches the `transcriptType` argument and that `categories` is a non-empty array before returning.
  - Map all HTTP and API error shapes to `AppException` codes that match those thrown by Express `openaiService.js` — `OPENAI_AUTH_ERROR`, `OPENAI_QUOTA_OR_RATE_LIMIT`, `OPENAI_CONTEXT_LENGTH_EXCEEDED`, `OPENAI_BAD_REQUEST`, `OPENAI_ANALYZE_FAILED` — these exact codes are what the iOS client decodes into user-facing messages, so any mismatch silently breaks the app.
  - Port `resolveYoutubeSources()` as a private method: build a timestamp lookup from `segmentIndex`, validate each keyword's `source.ref` format and existence in the map, replace valid refs with full YouTube timestamp URLs (`?t=<sec>s`), and throw `AppException(502, 'OPENAI_INVALID_SOURCE_REF', ...)` on any ref that fails — refer to `backend/src/services/openaiService.js` for the full validation sequence.

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
Task 1 is the single closing move for Step 5 — its typed return shape is the upstream contract that LlmService and AnalyzeService both depend on, so it must be green before the LlmService work begins. Tasks 2 and 3 front-load the two hardest surfaces of Step 6 (the prompt/schema/type contract and the HTTP + error-mapping logic) so that AnalyzeService in Step 7 can wire them without revisiting LlmService internals.
