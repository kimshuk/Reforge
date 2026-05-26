# Daily Tasks — 2026-05-26
## Focus: NestJS Migration — Step 5 (close) → Step 6: LlmService

## Today's 3 Tasks

- [ ] **Close Step 5: implement `sanitize()` in TranscriptSanitizer**
  - All the heavy lifting already lives as module-level functions above the class — `sanitize()` just needs to call `sanitizeSnippetList()` to clean and sort the raw snippets, then pass the result into `buildSegments()` and assemble the three-field `SanitizedTranscript` return value (`llmTranscriptText`, `segmentIndex`, `cleanedSnippetCount`).
  - `cleanedSnippetCount` should reflect the number of snippets that survived `sanitizeSnippetList()` (i.e. had valid timestamps and non-empty text after normalization) — this is the count LlmService will log as usable transcript coverage.
  - Done when `npm run build` and `npm test` both pass inside `backend-nest/` with zero type errors and the existing spec assertions green.

- [ ] **LlmService scaffold — output types, JSON schema constant, and prompt builder**
  - Define TypeScript interfaces for the structured LLM response directly in `llm.service.ts`: a top-level `AnalysisPayload` containing `sourceType` and a `categories` array, each `Category` having a `name`, `summary`, and `keywords` array, each `Keyword` having a `term`, `importance`, and an optional `source` object with `ref` and `quote` fields — these must exactly mirror the JSON Schema passed to the model so parsed responses are fully type-safe without casting.
  - Port `CATEGORY_EXTRACTION_SCHEMA` (the JSON Schema object handed to the model's structured-output parameter) and `buildCategoryExtractionPrompt()` (system + user message builder that embeds the video title, transcript type, and transcript text) from `backend/src/services/promptBuilder.js` as module-level exports — the prompt is the behavioral contract with the model and any divergence silently degrades output quality.
  - Keeping these as module-level exports (not class methods) ensures `AnalyzeService` can import the output types in Step 7 without creating a circular dependency between the two service classes. Done when `npm run build` passes with the new exports.

- [ ] **LlmService core — OpenRouter HTTP call, error mapping, and source resolution**
  - Rename the stub method to `analyzeCategories()` and implement it using OpenRouter's OpenAI-compatible endpoint (`https://openrouter.ai/api/v1`, model `openai/gpt-4o-mini`, temperature `0.2`), passing the JSON schema via the structured-output format parameter; strip any markdown code fences before JSON parsing, then validate that `sourceType` matches the `transcriptType` argument and that `categories` is a non-empty array before returning.
  - Map all HTTP and API error shapes to `AppException` codes that exactly match those thrown by `backend/src/services/openaiService.js` — `OPENAI_AUTH_ERROR`, `OPENAI_QUOTA_OR_RATE_LIMIT`, `OPENAI_CONTEXT_LENGTH_EXCEEDED`, `OPENAI_BAD_REQUEST`, `OPENAI_ANALYZE_FAILED` — these exact code strings are what the iOS client decodes into user-facing messages, so any mismatch silently breaks the app.
  - Port `resolveYoutubeSources()` as a private method: build a timestamp lookup from `segmentIndex`, validate each keyword's `source.ref` against the map, replace valid refs with full YouTube timestamp URLs (`?t=<sec>s`), and throw `AppException(502, 'OPENAI_INVALID_SOURCE_REF', ...)` on any ref that fails — refer to `backend/src/services/openaiService.js` for the full validation and URL-building sequence.

## Migration Progress
**Completed steps:**
- 1 — Bootstrap NestJS scaffold (health module, main.ts, tsconfig strict mode)
- 2 — Project structure (analyze/ and common/ stubs, AnalyzeModule wired into AppModule)
- 3 — AppException class (common/app.exception.ts)
- 4 — YoutubeService (Python subprocess, URL → transcript text, error classification)

**Current step:** 5 → 6 — TranscriptSanitizerService (`sanitize()` method remaining) → LlmService (OpenRouter call + structured output)

**Remaining steps:**
- 6 — LlmService (OpenRouter call + structured output) — *starting today*
- 7 — AnalyzeService (orchestrate URL → youtube → sanitize → llm, or text → sanitize → llm)
- 8 — AnalyzeController (POST /analyze with SSE streaming)
- 9 — AppExceptionFilter (finalize `{ error: { code, message } }` envelope + global registration)

## Why These Tasks
All three tasks from yesterday remain unimplemented in code — `sanitize()` is still a stub and `LlmService` is untouched — so today carries forward the same sequencing: Task 1 closes Step 5 (the typed `SanitizedTranscript` it produces is the upstream contract Tasks 2 and 3 depend on), while Tasks 2 and 3 build the two hardest surfaces of Step 6 (the prompt/schema/type contract and the HTTP + error-mapping logic) so that AnalyzeService in Step 7 can wire them together without revisiting LlmService internals.
