# Daily Tasks — 2026-05-08
## Focus: NestJS Migration — Step 4: YoutubeService (Python subprocess)

## Today's 3 Tasks

- [ ] **Declare `TranscriptResult` interface and update return type**
  - Define the shape of what a successful transcript fetch returns: the video ID, the full transcript text, the raw snippet array from Python, and nullable metadata fields for language code, language name, and whether it was auto-generated
  - Update `fetchTranscript`'s return type signature to return this interface instead of a plain string, so callers get structured data they can work with
  - YouTube Shorts URLs are intentionally not supported — no need to handle them

- [ ] **Implement `fetchTranscriptViaPython` private method**
  - This method is the core of the service: it takes a video ID, spawns the Python script as a child process, and streams its stdout/stderr
  - On a spawn error, it means the Python runtime itself couldn't start — surface that clearly as a 502
  - On a non-zero exit code, inspect stderr to distinguish between a missing dependency, an unavailable transcript, and a generic fetch failure — each maps to a different error code
  - On a clean exit, parse the JSON stdout and normalize each field with defensive type checks before resolving

- [ ] **Wire `fetchTranscript` public method and verify build**
  - Connect the pieces: extract the video ID from the URL, call the private Python method, and guard against an empty transcript (an empty string from Python counts as a failure)
  - Return the combined result with the video ID merged in
  - Run `npm run build` in `backend-nest/` and confirm zero TypeScript errors before calling this step done

## Migration Progress
**Completed steps:**
- 1 — Bootstrap NestJS scaffold (health module, main.ts, tsconfig strict mode)
- 2 — Project structure (analyze/ and common/ stubs, AnalyzeModule wired into AppModule)
- 3 — AppException class (common/app.exception.ts)

**Current step:** 4 — YoutubeService (extractVideoId partial; /shorts/ branch, Python subprocess, and public method wiring still missing)

**Remaining steps:**
- 5 — TranscriptSanitizerService (sanitize raw transcript snippets → cleaned text)
- 6 — LlmService (OpenRouter call + structured output: categories + keywords)
- 7 — AnalyzeService (orchestrate URL → youtube → sanitize → llm, or text → sanitize → llm)
- 8 — AnalyzeController (POST /analyze with SSE streaming)
- 9 — AppExceptionFilter (finalize { error: { code, message } } envelope + global registration)

## Why These Tasks
All three Step 4 sub-tasks remain unstarted against an unchanged stub; they are ordered by compile dependency (type contract first, then private impl, then public wiring + build gate) so each task compiles cleanly before the next begins.
