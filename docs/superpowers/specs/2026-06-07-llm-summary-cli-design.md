# LLM Summary CLI Design

## Context

The Nest backend needs a simple way to compare transcript summary quality across
LLM providers and model settings. The tool should be faster to use than an HTTP
endpoint, easy to redirect to files, and isolated from the production
`/analyze` API.

## Goals

- Provide a terminal command for summarizing manual or YouTube transcripts.
- Allow per-run selection of provider, model, temperature, and max output
  tokens.
- Return JSON that can be saved and compared across providers.
- Reuse the backend's provider-neutral LLM adapters.
- Reuse YouTube fetching and transcript sanitization for timestamped inputs.

## Non-Goals

- No model-quality scoring or ranking in this first version.
- No batch comparison mode yet.
- No HTTP API or iOS UI integration yet.
- No persistent experiment database.

## User Flow

Manual transcript:

```bash
npm run llm:test-summary -- \
  --type manual \
  --file ./sample-transcript.txt \
  --provider claude \
  --model claude-3-5-sonnet-latest \
  --temperature 0.2 \
  --max-output-tokens 1200
```

YouTube transcript:

```bash
npm run llm:test-summary -- \
  --type youtube \
  --youtube-url "https://www.youtube.com/watch?v=..." \
  --provider gemini \
  --model gemini-1.5-pro
```

Comparison output can be saved with shell redirection:

```bash
npm run llm:test-summary -- --type manual --file ./sample.txt --provider openai --model gpt-4o-mini > openai-summary.json
```

## Input Contract

Required:

- `--type manual|youtube`
- For manual input: exactly one of `--file <path>` or `--text <text>`
- For YouTube input: `--youtube-url <url>`

Optional:

- `--target-language <code>`, default `en`
- `--provider openai|gemini|claude`, default from `LLM_PROVIDER` or `openai`
- `--model <model>`, default from `LLM_MODEL` or provider default
- `--temperature <number>`, default from `LLM_TEMPERATURE` or `0.2`
- `--max-output-tokens <integer>`, default from `LLM_MAX_OUTPUT_TOKENS`
- `--include-raw-text`

## Output Contract

The command writes JSON to stdout:

```json
{
  "summary": "Concise transcript summary.",
  "timestamps": [
    {
      "time": "03:12",
      "seconds": 192,
      "title": "Main point",
      "summary": "Short explanation of the moment.",
      "url": "https://www.youtube.com/watch?v=...&t=192s"
    }
  ],
  "llm": {
    "provider": "gemini",
    "model": "gemini-1.5-pro",
    "temperature": 0.2,
    "maxOutputTokens": 1200
  }
}
```

`url` is included for YouTube timestamps. `rawText` is included only when
`--include-raw-text` is passed.

## Architecture

Add a CLI entry point at `backend-nest/src/cli/test-summary.ts`.

The CLI creates a Nest application context and reuses existing services:

- `YoutubeService` fetches YouTube transcripts.
- `TranscriptSanitizer` converts YouTube snippets to `S### | MM:SS | text`
  segments.
- `LlmConfigService` resolves provider/model/generation settings.
- `LlmService` calls the selected provider adapter and normalizes JSON output.

Add `backend-nest/src/llm/transcript-summary.prompt.ts` for the summary-specific
prompt. Keep it separate from category extraction so summary experiments cannot
change production analysis behavior.

## Error Handling

CLI validation errors should use the same `AppException` shape as the backend:

```json
{
  "error": {
    "code": "INVALID_CLI_ARG",
    "message": "Missing value for --model"
  }
}
```

Provider configuration errors should clearly name the missing key, for example
`OPENAI_API_KEY`, `GEMINI_API_KEY`, or `ANTHROPIC_API_KEY`.

## Testing

Verification should include:

- `npm run llm:test-summary -- --help`
- `npm test`
- `npm run build`

Live provider calls are intentionally not part of automated verification because
they require API keys and spend provider credits.

## Future Extensions

- Add batch mode with multiple runs in one command.
- Add cost, latency, and token usage when providers expose it.
- Add a scoring file format for manual or rubric-based evaluation.
- Add an HTTP endpoint only if the iOS app or a future web UI needs it.
