# Daily Tasks — 2026-05-27
## Focus: NestJS Migration — Step 5 (close) → Step 6: LlmService

## Today's 3 Tasks

- [ ] **Close Step 5: wire up `sanitize()` in TranscriptSanitizer**
  - All the heavy lifting already lives as module-level functions above the class — `sanitize()` just needs to accept `(rawSnippets: RawSnippet[], options?: SegmentOptions)`, call `sanitizeSnippetList()` to clean and sort the raw snippets, then pass the result into `buildSegments()` and assemble the three-field `SanitizedTranscript` return value (`llmTranscriptText`, `segmentIndex`, `cleanedSnippetCount`).
  - `cleanedSnippetCount` should reflect the number of snippets that survived `sanitizeSnippetList()` — those with valid timestamps and non-empty text after normalization — since this is the coverage metric AnalyzeService will log upstream.
  - Done when `npm run build` and `npm test` both pass inside `backend-nest/` with zero type errors and the existing spec assertions green.

- [ ] **LlmService scaffold — output types, JSON schema constant, and prompt builder**
  - Define TypeScript interfaces directly in `llm.service.ts` for the structured LLM response: a top-level `AnalysisPayload` with `sourceType` and a `categories` array, each `Category` having `title` and `keywords`, each `Keyword` having `term`, `brief`, `level1`, `level2`, `level3`, and a `source` object with `type` and `ref` — these must exactly mirror the JSON Schema passed to the model so parsed responses are fully type-safe without casting.
  - Port `CATEGORY_EXTRACTION_SCHEMA` (the JSON Schema object handed to the model's structured-output parameter) and `buildCategoryExtractionPrompt()` (system + user message builder embedding `transcriptType`, `targetLanguage`, `youtubeUrl`, and `transcriptText`) from `backend/src/services/promptBuilder.js` as module-level exports — the prompt text is the behavioral contract with the model and any divergence silently degrades output quality.
  - Keeping types and prompt builder as module-level exports (not class methods) ensures `AnalyzeService` can import `AnalysisPayload` in Step 7 without creating a circular dependency between the two service classes. Done when `npm run build` passes with the new exports visible.

- [ ] **LlmService core — OpenRouter HTTP call, error mapping, and source resolution**
  - Rename the stub method to `analyzeCategories()` and implement it with a `fetch` call to OpenRouter's OpenAI-compatible endpoint (`https://openrouter.ai/api/v1/chat/completions`, model `openai/gpt-4o-mini`, temperature `0.2`), passing the JSON schema via `response_format: { type: 'json_schema', json_schema: CATEGORY_EXTRACTION_SCHEMA }`; strip markdown code fences from the response content before parsing, then validate that `sourceType` matches the `transcriptType` argument and that `categories` is a non-empty array before returning.
  - Map all HTTP and API error shapes to `AppException` codes matching those thrown by `backend/src/services/openaiService.js` — `OPENAI_AUTH_ERROR` (401/invalid_api_key), `OPENAI_QUOTA_OR_RATE_LIMIT` (429/quota/rate_limit), `OPENAI_CONTEXT_LENGTH_EXCEEDED` (context_length_exceeded), `OPENAI_BAD_REQUEST` (400), `OPENAI_ANALYZE_FAILED` (fallback) — these exact code strings are what the iOS client decodes into user-facing messages, so any mismatch silently breaks the app.
  - Port `resolveYoutubeSources()` as a private method: build a timestamp lookup map from `segmentIndex` keyed by formatted `MM:SS` string, validate each keyword's `source.ref` against the map using the same regex and existence checks in the Express service, replace valid refs with full YouTube timestamp URLs (`?t=<sec>s`), and throw `AppException(502, 'OPENAI_INVALID_SOURCE_REF', ...)` on any ref that fails — refer to `backend/src/services/openaiService.js` for the full validation sequence.

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
Step 5's `sanitize()` method is a one-task close since all the logic already exists as module-level helpers — wiring it up unlocks the typed `SanitizedTranscript` that LlmService and AnalyzeService depend on. Tasks 2 and 3 then front-load the two hardest surfaces of Step 6 (the prompt/schema/type contract and the HTTP + error-mapping logic) so that Step 7's AnalyzeService can wire everything together without revisiting LlmService internals.
