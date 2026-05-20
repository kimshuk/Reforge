# Daily Tasks — 2026-05-20
## Focus: NestJS Migration — Step 5 (finish) → Step 6: LlmService

## Today's 3 Tasks

- [ ] **Complete Step 5: implement `sanitize()` and close the step**
  - Wire the `sanitize(rawSnippets: RawSnippet[]): SanitizedTranscript` method body by calling the private `sanitizeSnippetList` → `buildSegments` pipeline already implemented in the file, and returning `{ llmTranscriptText, segmentIndex, cleanedSnippetCount }` — where `cleanedSnippetCount` is the length of the array returned by `sanitizeSnippetList`, captured before it's passed to `buildSegments`.
  - The public `sanitize()` is the only surface `AnalyzeService` will ever call; everything else in the file is internal — getting the return shape right now prevents a breaking change when the pipeline is wired in Step 7.
  - Run `npm run build` and `npm test` inside `backend-nest/` with zero errors and all tests green — this is the hard gate that closes Step 5 and unlocks Step 6.

- [ ] **Step 6 scaffold: output types, JSON schema constant, and prompt builder**
  - Define TypeScript interfaces for the structured LLM output — `AnalysisPayload`, `Category`, `Keyword`, and `KeywordSource` — mirroring the shape of `CATEGORY_EXTRACTION_SCHEMA` in `backend/src/services/promptBuilder.js`; these types are the contract between `LlmService` and `AnalyzeService`.
  - Port `CATEGORY_EXTRACTION_SCHEMA` (the JSON Schema object) and `buildCategoryExtractionPrompt()` from the Express `promptBuilder.js` into `llm.service.ts` as module-level exports — the system prompt text is the exact behavioral contract with the model, so any divergence silently degrades output quality.
  - Keep both as non-class exports within `llm.service.ts` (no separate file) so `LlmService` can reference them directly when making the API call in Task 3.

- [ ] **Step 6 core: OpenRouter HTTP call, error mapping, and source resolution**
  - Implement `analyzeCategories()` on `LlmService` using OpenRouter's OpenAI-compatible HTTP API (base URL `https://openrouter.ai/api/v1`, model `openai/gpt-4o-mini`), structured output via `text.format` with the JSON schema, and map HTTP/API error shapes to `AppException` codes matching the Express `openaiService.js` (`OPENAI_AUTH_ERROR`, `OPENAI_QUOTA_OR_RATE_LIMIT`, `OPENAI_CONTEXT_LENGTH_EXCEEDED`, `OPENAI_BAD_REQUEST`, `OPENAI_ANALYZE_FAILED`).
  - Port `resolveYoutubeSources()` as a private method: build a `formatTimestamp(segment.startSec) → segment` lookup map, validate each keyword's `source.type === 'youtube'` and that `source.ref` matches the `MM:SS` or `H:MM:SS` pattern and exists in the map, and replace `source.ref` with a full YouTube timestamp URL (`?t=<sec>s`) before returning — throw `AppException(502, 'OPENAI_INVALID_SOURCE_REF', ...)` on any violation.
  - Add the final payload guards: confirm `sourceType` matches the input `transcriptType`, that `categories` is a non-empty array, and that `parseStructuredOutput()` strips markdown code fences before JSON parsing — these prevent silent garbage from reaching `AnalyzeService`.

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
- 9 — AppExceptionFilter (finalize { error: { code, message } } envelope + global registration)

## Why These Tasks
Task 1 is a single-method finishing move that unblocks everything downstream — `sanitize()` is the only gap between a complete Step 5 and a verified build. Tasks 2 and 3 front-load the two hardest surfaces of Step 6 (the prompt contract and the source-resolution logic) so that AnalyzeService (Step 7) can wire them without revisiting `LlmService` internals.
