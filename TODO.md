# Daily Tasks — 2026-05-21
## Focus: NestJS Migration — Step 5 (finish) → Step 6: LlmService

## Today's 3 Tasks

- [ ] **Close Step 5: implement `sanitize()` on TranscriptSanitizer**
  - The method is still a throw-stub; wire it by calling `sanitizeSnippetList(rawSnippets)` to get the cleaned snippets, capturing its length as `cleanedSnippetCount`, then passing the result to `buildSegments()` and returning `{ llmTranscriptText, segmentIndex, cleanedSnippetCount }` — all three pieces are needed by downstream callers.
  - The public `sanitize(rawSnippets: RawSnippet[]): SanitizedTranscript` signature must match the already-exported `SanitizedTranscript` interface exactly — this is the only surface `AnalyzeService` will ever call, and getting the return shape wrong now creates a silent breaking change in Step 7.
  - Gate: run `npm run build` and `npm test` inside `backend-nest/` with zero errors and all tests green before moving on — a passing build is what formally closes Step 5.

- [ ] **Step 6 scaffold: output types, JSON schema constant, and prompt builder**
  - Define TypeScript interfaces for the structured LLM output — `AnalysisPayload`, `Category`, `Keyword`, and `KeywordSource` — inside `llm.service.ts`; the shape must mirror the JSON Schema in `backend/src/services/promptBuilder.js` so that parsed responses are type-safe end-to-end.
  - Port `CATEGORY_EXTRACTION_SCHEMA` (the JSON Schema object passed to the model's `text.format` parameter) and `buildCategoryExtractionPrompt()` (the system prompt builder) from the Express `promptBuilder.js` as module-level exports within `llm.service.ts` — the system prompt is the exact behavioral contract with the model, so any divergence silently changes output quality.
  - Keep both as non-class exports in the same file so `LlmService` methods can reference them directly, and so the types are importable by `AnalyzeService` without a circular dependency.

- [ ] **Step 6 core: OpenRouter HTTP call, error mapping, and source resolution**
  - Implement `analyzeCategories()` on `LlmService` using OpenRouter's OpenAI-compatible HTTP API (base URL `https://openrouter.ai/api/v1`, model `openai/gpt-4o-mini`) with the JSON schema passed via `text.format`; strip any markdown code fences before JSON-parsing the response, and confirm the returned `sourceType` matches the `transcriptType` argument and that `categories` is a non-empty array before returning.
  - Map all HTTP and API error shapes to `AppException` codes matching what the Express `openaiService.js` throws: `OPENAI_AUTH_ERROR`, `OPENAI_QUOTA_OR_RATE_LIMIT`, `OPENAI_CONTEXT_LENGTH_EXCEEDED`, `OPENAI_BAD_REQUEST`, and `OPENAI_ANALYZE_FAILED` — these codes are the contract the iOS client decodes into user-facing messages.
  - Port `resolveYoutubeSources()` as a private method: build a `formatTimestamp(startSec) → segmentIndexEntry` lookup map from the passed `segmentIndex`, validate each keyword's `source.ref` against that map, replace valid refs with full YouTube timestamp URLs (`?t=<sec>s`), and throw `AppException(502, 'OPENAI_INVALID_SOURCE_REF', ...)` on any ref that fails validation.

## Migration Progress
**Completed steps:**
- 1 — Bootstrap NestJS scaffold (health module, main.ts, tsconfig strict mode)
- 2 — Project structure (analyze/ and common/ stubs, AnalyzeModule wired into AppModule)
- 3 — AppException class (common/app.exception.ts)
- 4 — YoutubeService (Python subprocess, URL → transcript text, error classification)

**Current step:** 5 → 6 — TranscriptSanitizerService (one stub remaining: `sanitize()`) → LlmService (OpenRouter call + structured output)

**Remaining steps:**
- 6 — LlmService (OpenRouter call + structured output: categories + keywords) — *starting today*
- 7 — AnalyzeService (orchestrate URL → youtube → sanitize → llm, or text → sanitize → llm)
- 8 — AnalyzeController (POST /analyze with SSE streaming)
- 9 — AppExceptionFilter (finalize `{ error: { code, message } }` envelope + global registration)

## Why These Tasks
Task 1 is the only thing blocking Step 5 from closing — `sanitize()` is a one-method finishing move whose output shape gates every downstream step. Tasks 2 and 3 front-load the two hardest surfaces of Step 6 (the prompt contract and source-resolution logic) so that AnalyzeService in Step 7 can wire them without revisiting LlmService internals.
