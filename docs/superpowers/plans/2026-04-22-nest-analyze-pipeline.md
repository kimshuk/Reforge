# NestJS Analyze Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a NestJS backend that receives a YouTube URL, fetches + sanitizes the transcript via Python, sends it to OpenRouter, and streams the structured JSON result back to the client via SSE.

**Architecture:** Controller receives POST /analyze and writes SSE events; AnalyzeService orchestrates TranscriptService (Python subprocess + sanitizer) and LlmService (OpenRouter via native fetch); all config flows through NestJS ConfigModule.

**Tech Stack:** NestJS 10, TypeScript, Vitest, class-validator, native fetch (Node 18+), OpenRouter API, Python 3 + youtube-transcript-api

---

## File Map

| File | Responsibility |
|------|---------------|
| `backend-nest/scripts/fetch_transcript.py` | Python script — fetch YouTube transcript snippets |
| `backend-nest/src/main.ts` | Bootstrap — add global ValidationPipe |
| `backend-nest/src/app.module.ts` | Root module — ConfigModule already wired |
| `backend-nest/src/analyze/dto/analyze.dto.ts` | Request shape: `{ url, targetLanguage? }` |
| `backend-nest/src/analyze/transcript/transcript.service.ts` | Extract video ID, spawn Python, sanitize snippets |
| `backend-nest/src/analyze/transcript/transcript.service.spec.ts` | Unit tests for transcript service |
| `backend-nest/src/analyze/llm/llm.service.ts` | Build prompt, call OpenRouter, parse JSON result |
| `backend-nest/src/analyze/llm/llm.service.spec.ts` | Unit tests for LLM service |
| `backend-nest/src/analyze/analyze.service.ts` | Thin orchestrator: transcript → llm → response |
| `backend-nest/src/analyze/analyze.service.spec.ts` | Unit tests for analyze service |
| `backend-nest/src/analyze/analyze.controller.ts` | POST /analyze — SSE streaming |
| `backend-nest/src/analyze/analyze.controller.spec.ts` | Unit tests for controller |
| `backend-nest/src/analyze/analyze.module.ts` | Wire all providers |

---

## Prerequisites

- `backend-nest/` scaffolded with `nest new` (or recreated)
- `.env` at `backend-nest/.env` with `OPENROUTER_API_KEY` and `OPENROUTER_MODEL`
- `python3 -c "from youtube_transcript_api import YouTubeTranscriptApi; print('ok')"` passes
- `AppModule` already has `ConfigModule.forRoot({ isGlobal: true })`

---

## Task 1: Scaffold & Install Dependencies

**Files:**
- Modify: `backend-nest/package.json`
- Modify: `backend-nest/src/main.ts`

- [ ] **Step 1: Install packages**

```bash
cd backend-nest
npm install @nestjs/config class-validator class-transformer
```

Expected: no errors, packages appear in `node_modules/`

- [ ] **Step 2: Add global ValidationPipe in main.ts**

```ts
import { AppModule } from './app.module';
import { NestFactory } from '@nestjs/core';
import { ValidationPipe } from '@nestjs/common';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  app.useGlobalPipes(new ValidationPipe({ whitelist: true }));
  await app.listen(3000);
}

bootstrap();
```

- [ ] **Step 3: Verify app starts**

```bash
npm run dev
```

Expected: `Application is running on: http://[::1]:3000`

- [ ] **Step 4: Commit**

```bash
git add backend-nest/src/main.ts backend-nest/package.json backend-nest/package-lock.json
git commit -m "feat(backend-nest): install deps and add global ValidationPipe"
```

---

## Task 2: Copy Python Script

**Files:**
- Create: `backend-nest/scripts/fetch_transcript.py`

- [ ] **Step 1: Copy from old backend**

```bash
mkdir -p backend-nest/scripts
cp backend/scripts/fetch_transcript.py backend-nest/scripts/fetch_transcript.py
```

- [ ] **Step 2: Verify it runs**

```bash
python3 backend-nest/scripts/fetch_transcript.py dQw4w9WgXcQ
```

Expected: JSON printed to stdout with `transcriptSnippets` array

- [ ] **Step 3: Commit**

```bash
git add backend-nest/scripts/fetch_transcript.py
git commit -m "feat(backend-nest): add Python transcript fetch script"
```

---

## Task 3: Request DTO

**Files:**
- Create: `backend-nest/src/analyze/dto/analyze.dto.ts`

- [ ] **Step 1: Create the DTO**

```ts
import { IsOptional, IsString, IsUrl, Matches } from 'class-validator';

export class AnalyzeDto {
  @IsUrl()
  url: string;

  @IsOptional()
  @IsString()
  @Matches(/^[a-zA-Z]{2,3}(?:-[a-zA-Z]{4})?(?:-[a-zA-Z]{2}|\d{3})?$/)
  targetLanguage?: string;
}
```

- [ ] **Step 2: Commit**

```bash
git add backend-nest/src/analyze/dto/analyze.dto.ts
git commit -m "feat(backend-nest): add AnalyzeDto with URL and targetLanguage validation"
```

---

## Task 4: TranscriptService

> **Decision:** `/shorts/` URLs (`youtube.com/shorts/<id>`) are intentionally not supported. This server rejects them. Do not add shorts parsing to `extractVideoId`.

**Files:**
- Modify: `backend-nest/src/analyze/transcript/transcript.service.ts`
- Create: `backend-nest/src/analyze/transcript/transcript.service.spec.ts`

### Types used in this service

```ts
interface Snippet {
  startSec: number;
  endSec: number;
  durationSec: number;
  text: string;
}

export interface Segment {
  id: string;
  startSec: number;
  endSec: number;
  text: string;
}

export interface TranscriptResult {
  videoId: string;
  llmTranscriptText: string;
  segmentIndex: Segment[];
}
```

- [ ] **Step 1: Write failing tests**

```ts
// backend-nest/src/analyze/transcript/transcript.service.spec.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Test, TestingModule } from '@nestjs/testing';
import { ConfigService } from '@nestjs/config';
import { TranscriptService } from './transcript.service';
import * as child_process from 'child_process';
import { EventEmitter } from 'events';

function makeFakeChild(stdout: string, stderr = '', exitCode = 0) {
  const child = new EventEmitter() as any;
  child.stdout = new EventEmitter();
  child.stderr = new EventEmitter();
  setTimeout(() => {
    child.stdout.emit('data', stdout);
    child.stderr.emit('data', stderr);
    child.emit('close', exitCode);
  }, 0);
  return child;
}

describe('TranscriptService', () => {
  let service: TranscriptService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        TranscriptService,
        { provide: ConfigService, useValue: { get: vi.fn().mockReturnValue(undefined) } },
      ],
    }).compile();
    service = module.get(TranscriptService);
  });

  it('extracts video ID from watch URL', () => {
    const id = service.extractVideoId('https://www.youtube.com/watch?v=dQw4w9WgXcQ');
    expect(id).toBe('dQw4w9WgXcQ');
  });

  it('extracts video ID from short URL', () => {
    const id = service.extractVideoId('https://youtu.be/dQw4w9WgXcQ');
    expect(id).toBe('dQw4w9WgXcQ');
  });

  it('throws on invalid URL', () => {
    expect(() => service.extractVideoId('not-a-url')).toThrow();
  });

  it('fetches and returns transcript result', async () => {
    const payload = {
      transcriptSnippets: [{ start: 0, duration: 5, text: 'Hello world this is a test transcript line' }],
      languageCode: 'en',
      language: 'English',
      isGenerated: false,
    };
    vi.spyOn(child_process, 'spawn').mockReturnValue(makeFakeChild(JSON.stringify(payload)) as any);

    const result = await service.fetchAndSanitize('https://www.youtube.com/watch?v=abc123');
    expect(result.videoId).toBe('abc123');
    expect(result.llmTranscriptText).toContain('S001');
    expect(result.segmentIndex.length).toBeGreaterThan(0);
  });

  it('throws TRANSCRIPT_UNAVAILABLE when Python exits with stderr flag', async () => {
    vi.spyOn(child_process, 'spawn').mockReturnValue(
      makeFakeChild('', 'TRANSCRIPT_UNAVAILABLE', 1) as any,
    );
    await expect(service.fetchAndSanitize('https://www.youtube.com/watch?v=abc123')).rejects.toThrow('TRANSCRIPT_UNAVAILABLE');
  });
});
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend-nest && npx vitest run src/analyze/transcript/transcript.service.spec.ts
```

Expected: FAIL — `TranscriptService` methods not implemented

- [ ] **Step 3: Implement TranscriptService**

```ts
// backend-nest/src/analyze/transcript/transcript.service.ts
import { Injectable, HttpException, HttpStatus } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { spawn } from 'child_process';
import * as path from 'path';

export interface Segment {
  id: string;
  startSec: number;
  endSec: number;
  text: string;
}

export interface TranscriptResult {
  videoId: string;
  llmTranscriptText: string;
  segmentIndex: Segment[];
}

interface RawSnippet {
  start: number;
  duration: number;
  text: string;
}

interface CleanSnippet {
  startSec: number;
  endSec: number;
  durationSec: number;
  text: string;
}

const BRACKET_NOISE = /^(music|applause|laugh(?:ter)?|noise|silence|bgm|audience|clap|박수|웃음|음악)$/i;

const DEFAULTS = {
  minSegmentSeconds: 20,
  maxSegmentSeconds: 35,
  hardMaxSegmentSeconds: 45,
  minSegmentChars: 180,
  maxSegmentChars: 320,
  hardMaxSegmentChars: 420,
  pauseSplitSeconds: 2.5,
};

@Injectable()
export class TranscriptService {
  constructor(private readonly config: ConfigService) {}

  extractVideoId(url: string): string {
    let parsed: URL;
    try {
      parsed = new URL(url);
    } catch {
      throw new HttpException('INVALID_YOUTUBE_URL', HttpStatus.BAD_REQUEST);
    }

    const host = parsed.hostname.replace(/^www\./, '').toLowerCase();

    if (host === 'youtu.be') {
      const id = parsed.pathname.slice(1).trim();
      if (!id) throw new HttpException('INVALID_YOUTUBE_URL', HttpStatus.BAD_REQUEST);
      return id;
    }

    if (host === 'youtube.com' || host === 'm.youtube.com') {
      // /shorts/ URLs are intentionally not supported — this server rejects them
      const v = parsed.searchParams.get('v');
      if (v) return v;
    }

    throw new HttpException('INVALID_YOUTUBE_URL', HttpStatus.BAD_REQUEST);
  }

  private spawnPython(videoId: string): Promise<RawSnippet[]> {
    const pythonBin = this.config.get<string>('PYTHON_BIN') ?? 'python3';
    const scriptPath = path.resolve(__dirname, '../../../scripts/fetch_transcript.py');

    return new Promise((resolve, reject) => {
      const child = spawn(pythonBin, [scriptPath, videoId]);
      let stdout = '';
      let stderr = '';

      child.stdout.on('data', (chunk: Buffer) => { stdout += chunk.toString(); });
      child.stderr.on('data', (chunk: Buffer) => { stderr += chunk.toString(); });

      child.on('error', () => reject(new HttpException('PYTHON_RUNTIME_ERROR', HttpStatus.BAD_GATEWAY)));

      child.on('close', (code) => {
        if (code !== 0) {
          const msg = stderr.trim();
          if (msg.includes('PY_DEP_MISSING'))
            return reject(new HttpException('PYTHON_DEPENDENCY_MISSING', HttpStatus.INTERNAL_SERVER_ERROR));
          if (msg.includes('TRANSCRIPT_UNAVAILABLE'))
            return reject(new HttpException('TRANSCRIPT_UNAVAILABLE', HttpStatus.BAD_GATEWAY));
          return reject(new HttpException('TRANSCRIPT_FETCH_FAILED', HttpStatus.BAD_GATEWAY));
        }

        let parsed: any;
        try { parsed = JSON.parse(stdout); }
        catch { return reject(new HttpException('TRANSCRIPT_PARSE_FAILED', HttpStatus.BAD_GATEWAY)); }

        const snippets: RawSnippet[] = Array.isArray(parsed?.transcriptSnippets) ? parsed.transcriptSnippets : [];
        resolve(snippets);
      });
    });
  }

  private normalizeText(input: unknown): string {
    if (typeof input !== 'string') return '';
    let text = input;
    text = text.replace(/^\s*>+\s*/g, ' ');
    text = text.replace(/\[([^\]]{1,30})\]/g, (m, c) => BRACKET_NOISE.test(c.trim()) ? ' ' : m);
    text = text.replace(/\(([^)]{1,30})\)/g, (m, c) => BRACKET_NOISE.test(c.trim()) ? ' ' : m);
    text = text.replace(/(ㅋ){3,}/g, 'ㅋㅋ').replace(/(ㅎ){3,}/g, 'ㅎㅎ');
    text = text.replace(/([!?.,~])\1{2,}/g, '$1$1');
    text = text.replace(/\s+/g, ' ').trim();
    if (/^[>|~\-_=.,!?]+$/.test(text)) return '';
    return text;
  }

  private sanitizeSnippets(raw: RawSnippet[]): CleanSnippet[] {
    const out: CleanSnippet[] = [];
    for (const item of raw) {
      const startSec = Number(item?.start);
      if (!Number.isFinite(startSec) || startSec < 0) continue;
      const durationSec = Number.isFinite(Number(item?.duration)) && Number(item?.duration) > 0 ? Number(item.duration) : 0;
      const text = this.normalizeText(item?.text);
      if (!text) continue;
      out.push({ startSec, endSec: startSec + durationSec, durationSec, text });
    }
    out.sort((a, b) => a.startSec - b.startSec);
    return out;
  }

  private formatTimestamp(totalSeconds: number): string {
    const s = Math.max(0, Math.floor(totalSeconds));
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
    return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
  }

  private buildSegments(snippets: CleanSnippet[]): { llmTranscriptText: string; segmentIndex: Segment[] } {
    const cfg = DEFAULTS;
    const segments: { startSec: number; endSec: number; text: string }[] = [];
    let cur: { startSec: number; endSec: number; parts: string[]; charCount: number; duration: number } | null = null;

    const finalize = () => {
      if (!cur?.parts.length) { cur = null; return; }
      const text = cur.parts.join(' ').replace(/\s+/g, ' ').trim();
      if (text) segments.push({ startSec: cur.startSec, endSec: cur.endSec, text });
      cur = null;
    };

    for (const sn of snippets) {
      if (!cur) {
        cur = { startSec: sn.startSec, endSec: sn.endSec, parts: [sn.text], charCount: sn.text.length, duration: sn.endSec - sn.startSec };
        continue;
      }
      const pause = sn.startSec - cur.endSec;
      const nextEnd = Math.max(cur.endSec, sn.endSec);
      const nextDur = nextEnd - cur.startSec;
      const nextChars = cur.charCount + 1 + sn.text.length;
      let split = pause > cfg.pauseSplitSeconds;
      if (!split && (nextDur > cfg.maxSegmentSeconds || nextChars > cfg.maxSegmentChars)) {
        split = cur.duration >= cfg.minSegmentSeconds || cur.charCount >= cfg.minSegmentChars;
        if (!split) split = nextDur > cfg.hardMaxSegmentSeconds || nextChars > cfg.hardMaxSegmentChars;
      }
      if (split) { finalize(); cur = { startSec: sn.startSec, endSec: sn.endSec, parts: [sn.text], charCount: sn.text.length, duration: sn.endSec - sn.startSec }; continue; }
      cur.parts.push(sn.text);
      cur.endSec = Math.max(cur.endSec, sn.endSec);
      cur.charCount += 1 + sn.text.length;
      cur.duration = cur.endSec - cur.startSec;
    }
    finalize();

    const segmentIndex: Segment[] = segments.map((seg, i) => ({
      id: `S${String(i + 1).padStart(3, '0')}`,
      startSec: seg.startSec,
      endSec: seg.endSec,
      text: seg.text,
    }));

    const llmTranscriptText = segmentIndex
      .map(seg => `${seg.id} | ${this.formatTimestamp(seg.startSec)} | ${seg.text}`)
      .join('\n');

    return { llmTranscriptText, segmentIndex };
  }

  async fetchAndSanitize(url: string): Promise<TranscriptResult> {
    const videoId = this.extractVideoId(url);
    const rawSnippets = await this.spawnPython(videoId);
    const clean = this.sanitizeSnippets(rawSnippets);
    if (!clean.length) throw new HttpException('TRANSCRIPT_UNAVAILABLE', HttpStatus.BAD_GATEWAY);
    const { llmTranscriptText, segmentIndex } = this.buildSegments(clean);
    const trimmed = llmTranscriptText.trim();
    if (!trimmed || trimmed.length < 80) throw new HttpException('SHORT_TRANSCRIPT', HttpStatus.BAD_GATEWAY);
    return { videoId, llmTranscriptText: trimmed, segmentIndex };
  }
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
npx vitest run src/analyze/transcript/transcript.service.spec.ts
```

Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend-nest/src/analyze/transcript/
git commit -m "feat(backend-nest): implement TranscriptService with Python spawn and sanitizer"
```

---

## Task 5: LlmService

**Files:**
- Create: `backend-nest/src/analyze/llm/llm.service.ts`
- Create: `backend-nest/src/analyze/llm/llm.service.spec.ts`

### Response shape (JSON schema enforced by prompt)

```ts
export interface AnalysisResult {
  sourceType: 'youtube' | 'manual';
  categories: Array<{
    title: string;
    keywords: Array<{
      term: string;
      brief: string;
      level1: string;
      level2: string;
      level3: string;
      source: { type: 'youtube' | 'manual'; ref: string };
    }>;
  }>;
}
```

- [ ] **Step 1: Write failing tests**

```ts
// backend-nest/src/analyze/llm/llm.service.spec.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Test, TestingModule } from '@nestjs/testing';
import { ConfigService } from '@nestjs/config';
import { LlmService } from './llm.service';
import type { Segment } from '../transcript/transcript.service';

const mockResult = {
  sourceType: 'youtube',
  categories: [{
    title: 'Test Category Here',
    keywords: [{
      term: 'test keyword here',
      brief: 'brief text',
      level1: 'level one text',
      level2: 'level two text',
      level3: 'level three text',
      source: { type: 'youtube', ref: '00:00' },
    }],
  }],
};

const segments: Segment[] = [{ id: 'S001', startSec: 0, endSec: 30, text: 'test' }];

describe('LlmService', () => {
  let service: LlmService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        LlmService,
        {
          provide: ConfigService,
          useValue: {
            get: vi.fn((key: string) => {
              if (key === 'OPENROUTER_API_KEY') return 'test-key';
              if (key === 'OPENROUTER_MODEL') return 'openai/gpt-4o-mini';
              return undefined;
            }),
          },
        },
      ],
    }).compile();
    service = module.get(LlmService);
  });

  it('calls OpenRouter and returns parsed categories', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        choices: [{ message: { content: JSON.stringify(mockResult) } }],
      }),
    }) as any;

    const result = await service.analyze({
      transcriptText: 'S001 | 00:00 | test content',
      segmentIndex: segments,
      youtubeUrl: 'https://www.youtube.com/watch?v=abc123',
      targetLanguage: 'en',
    });

    expect(result.sourceType).toBe('youtube');
    expect(result.categories).toHaveLength(1);
  });

  it('throws when OpenRouter returns non-ok response', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ error: { message: 'Unauthorized' } }),
    }) as any;

    await expect(
      service.analyze({ transcriptText: 'x', segmentIndex: segments, youtubeUrl: 'https://www.youtube.com/watch?v=abc', targetLanguage: 'en' })
    ).rejects.toThrow();
  });

  it('resolves source ref timestamp to full URL', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        choices: [{ message: { content: JSON.stringify(mockResult) } }],
      }),
    }) as any;

    const result = await service.analyze({
      transcriptText: 'S001 | 00:00 | test',
      segmentIndex: segments,
      youtubeUrl: 'https://www.youtube.com/watch?v=abc123',
      targetLanguage: 'en',
    });

    expect(result.categories[0].keywords[0].source.ref).toContain('youtube.com');
  });
});
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
npx vitest run src/analyze/llm/llm.service.spec.ts
```

Expected: FAIL — `LlmService` not found

- [ ] **Step 3: Implement LlmService**

```ts
// backend-nest/src/analyze/llm/llm.service.ts
import { Injectable, HttpException, HttpStatus } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import type { Segment } from '../transcript/transcript.service';

export interface AnalysisResult {
  sourceType: 'youtube';
  categories: Array<{
    title: string;
    keywords: Array<{
      term: string;
      brief: string;
      level1: string;
      level2: string;
      level3: string;
      source: { type: 'youtube'; ref: string };
    }>;
  }>;
}

const OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions';

const RESPONSE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['sourceType', 'categories'],
  properties: {
    sourceType: { type: 'string', enum: ['youtube'] },
    categories: {
      type: 'array', minItems: 1, maxItems: 6,
      items: {
        type: 'object', additionalProperties: false,
        required: ['title', 'keywords'],
        properties: {
          title: { type: 'string', minLength: 3, maxLength: 80 },
          keywords: {
            type: 'array', minItems: 3, maxItems: 8,
            items: {
              type: 'object', additionalProperties: false,
              required: ['term', 'brief', 'level1', 'level2', 'level3', 'source'],
              properties: {
                term: { type: 'string', minLength: 2, maxLength: 60 },
                brief: { type: 'string', maxLength: 60 },
                level1: { type: 'string', maxLength: 120 },
                level2: { type: 'string', maxLength: 240 },
                level3: { type: 'string', maxLength: 320 },
                source: {
                  type: 'object', additionalProperties: false,
                  required: ['type', 'ref'],
                  properties: {
                    type: { type: 'string', enum: ['youtube'] },
                    ref: { type: 'string', maxLength: 240 },
                  },
                },
              },
            },
          },
        },
      },
    },
  },
};

@Injectable()
export class LlmService {
  constructor(private readonly config: ConfigService) {}

  private buildMessages(transcriptText: string, youtubeUrl: string, targetLanguage: string) {
    return [
      {
        role: 'system',
        content: `
You are a transcript topic–structure extraction engine.

Your task is to organize transcript content into topic-based categories and related keywords.

CATEGORIES

A category represents a major topic discussed in the transcript. Categories group keywords that belong to the same topic area.

A transcript may contain:
- 1 category if the discussion is tightly focused.
- 2–4 categories when multiple topics appear.
- Up to 6 categories only when clearly supported.

CATEGORY RULES

- Title: 2–6 words.
- Must describe a clear topic discussed in the transcript.
- Categories must differ in subject matter, not abstraction level.
- Do not collapse multiple topics into one umbrella category.

KEYWORDS

- 3–5 keywords per category.
- 2–6 words each.
- Transcript-specific phrases.
- No duplication or rephrasing.

DESCRIPTIONS (per keyword)

brief: 5–12 words. Hint only.
level1: ≤15 words. Direct factual statement.
level2: ≤30 words. Add explicit transcript details.
level3: ≤40 words. Most detailed reconstruction using only transcript content.

SOURCE

Transcript lines are formatted as: "S### | MM:SS | text"

- Set source.type = "youtube".
- Set source.ref to the MM:SS timestamp of the segment where the keyword is discussed (example: "13:38").
- Use only timestamps that exist in the transcript.
- Never invent timestamps.
- If you cannot find a valid timestamp for a candidate keyword, do not output that keyword.

OUTPUT LANGUAGE: Write all model-generated text in: ${targetLanguage}

Return only valid structured JSON matching the provided schema.
`,
      },
      {
        role: 'user',
        content: `YouTube URL: ${youtubeUrl}\nTarget language: ${targetLanguage}\nTranscript:\n${transcriptText}`,
      },
    ];
  }

  private formatTimestamp(totalSeconds: number): string {
    const s = Math.max(0, Math.floor(totalSeconds));
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
    return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
  }

  private resolveSourceRefs(result: AnalysisResult, youtubeUrl: string, segmentIndex: Segment[]): void {
    const byTimestamp = new Map<string, Segment>();
    for (const seg of segmentIndex) {
      byTimestamp.set(this.formatTimestamp(seg.startSec), seg);
    }

    for (const category of result.categories) {
      for (const keyword of category.keywords) {
        const ref = keyword.source.ref?.trim() ?? '';
        if (!/^\d{1,2}:\d{2}(:\d{2})?$/.test(ref)) {
          throw new HttpException('LLM_INVALID_SOURCE_REF', HttpStatus.BAD_GATEWAY);
        }
        const seg = byTimestamp.get(ref);
        if (!seg) {
          throw new HttpException(`LLM_UNKNOWN_TIMESTAMP: ${ref}`, HttpStatus.BAD_GATEWAY);
        }
        const url = new URL(youtubeUrl);
        url.searchParams.set('t', `${Math.max(0, Math.floor(seg.startSec))}s`);
        keyword.source.ref = url.toString();
      }
    }
  }

  async analyze(params: {
    transcriptText: string;
    segmentIndex: Segment[];
    youtubeUrl: string;
    targetLanguage: string;
  }): Promise<AnalysisResult> {
    const apiKey = this.config.get<string>('OPENROUTER_API_KEY');
    const model = this.config.get<string>('OPENROUTER_MODEL') ?? 'openai/gpt-4o-mini';

    if (!apiKey) throw new HttpException('OPENROUTER_API_KEY not configured', HttpStatus.INTERNAL_SERVER_ERROR);

    const messages = this.buildMessages(params.transcriptText, params.youtubeUrl, params.targetLanguage);

    let res: Response;
    try {
      res = await fetch(OPENROUTER_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${apiKey}`,
        },
        body: JSON.stringify({
          model,
          temperature: 0.2,
          messages,
          response_format: {
            type: 'json_schema',
            json_schema: { name: 'category_extraction', strict: true, schema: RESPONSE_SCHEMA },
          },
        }),
      });
    } catch {
      throw new HttpException('OPENROUTER_REQUEST_FAILED', HttpStatus.BAD_GATEWAY);
    }

    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as any;
      throw new HttpException(
        body?.error?.message ?? 'OPENROUTER_ERROR',
        HttpStatus.BAD_GATEWAY,
      );
    }

    const data = await res.json() as any;
    const raw = data?.choices?.[0]?.message?.content ?? '';

    let parsed: AnalysisResult;
    try {
      parsed = JSON.parse(raw.replace(/^```json\s*/i, '').replace(/\s*```$/, '').trim());
    } catch {
      throw new HttpException('LLM_INVALID_JSON', HttpStatus.BAD_GATEWAY);
    }

    if (!Array.isArray(parsed?.categories) || parsed.categories.length === 0) {
      throw new HttpException('LLM_EMPTY_RESULT', HttpStatus.BAD_GATEWAY);
    }

    this.resolveSourceRefs(parsed, params.youtubeUrl, params.segmentIndex);

    return parsed;
  }
}
```

- [ ] **Step 4: Run tests**

```bash
npx vitest run src/analyze/llm/llm.service.spec.ts
```

Expected: all 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend-nest/src/analyze/llm/
git commit -m "feat(backend-nest): implement LlmService with OpenRouter and source ref resolution"
```

---

## Task 6: AnalyzeService

**Files:**
- Modify: `backend-nest/src/analyze/analyze.service.ts`
- Modify: `backend-nest/src/analyze/analyze.service.spec.ts`

- [ ] **Step 1: Write failing test**

```ts
// backend-nest/src/analyze/analyze.service.spec.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Test, TestingModule } from '@nestjs/testing';
import { AnalyzeService } from './analyze.service';
import { TranscriptService } from './transcript/transcript.service';
import { LlmService } from './llm/llm.service';

const mockTranscript = {
  videoId: 'abc123',
  llmTranscriptText: 'S001 | 00:00 | hello world',
  segmentIndex: [{ id: 'S001', startSec: 0, endSec: 30, text: 'hello world' }],
};

const mockAnalysis = {
  sourceType: 'youtube' as const,
  categories: [{ title: 'Test Category', keywords: [] }],
};

describe('AnalyzeService', () => {
  let service: AnalyzeService;
  let transcriptService: TranscriptService;
  let llmService: LlmService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        AnalyzeService,
        { provide: TranscriptService, useValue: { fetchAndSanitize: vi.fn().mockResolvedValue(mockTranscript) } },
        { provide: LlmService, useValue: { analyze: vi.fn().mockResolvedValue(mockAnalysis) } },
      ],
    }).compile();

    service = module.get(AnalyzeService);
    transcriptService = module.get(TranscriptService);
    llmService = module.get(LlmService);
  });

  it('orchestrates transcript fetch then LLM analyze', async () => {
    const result = await service.analyze({ url: 'https://youtube.com/watch?v=abc123', targetLanguage: 'en' });
    expect(transcriptService.fetchAndSanitize).toHaveBeenCalledWith('https://youtube.com/watch?v=abc123');
    expect(llmService.analyze).toHaveBeenCalled();
    expect(result.categories).toHaveLength(1);
  });
});
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
npx vitest run src/analyze/analyze.service.spec.ts
```

Expected: FAIL

- [ ] **Step 3: Implement AnalyzeService**

```ts
// backend-nest/src/analyze/analyze.service.ts
import { Injectable } from '@nestjs/common';
import { TranscriptService } from './transcript/transcript.service';
import { LlmService, AnalysisResult } from './llm/llm.service';

@Injectable()
export class AnalyzeService {
  constructor(
    private readonly transcript: TranscriptService,
    private readonly llm: LlmService,
  ) {}

  async analyze(params: { url: string; targetLanguage?: string }): Promise<AnalysisResult> {
    const { videoId, llmTranscriptText, segmentIndex } = await this.transcript.fetchAndSanitize(params.url);
    return this.llm.analyze({
      transcriptText: llmTranscriptText,
      segmentIndex,
      youtubeUrl: params.url,
      targetLanguage: params.targetLanguage ?? 'en',
    });
  }
}
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
npx vitest run src/analyze/analyze.service.spec.ts
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend-nest/src/analyze/analyze.service.ts backend-nest/src/analyze/analyze.service.spec.ts
git commit -m "feat(backend-nest): implement AnalyzeService orchestrator"
```

---

## Task 7: Wire AnalyzeModule

**Files:**
- Modify: `backend-nest/src/analyze/analyze.module.ts`

- [ ] **Step 1: Update module to include LlmService**

```ts
// backend-nest/src/analyze/analyze.module.ts
import { Module } from '@nestjs/common';
import { AnalyzeController } from './analyze.controller';
import { AnalyzeService } from './analyze.service';
import { TranscriptService } from './transcript/transcript.service';
import { LlmService } from './llm/llm.service';

@Module({
  controllers: [AnalyzeController],
  providers: [AnalyzeService, TranscriptService, LlmService],
})
export class AnalyzeModule {}
```

- [ ] **Step 2: Commit**

```bash
git add backend-nest/src/analyze/analyze.module.ts
git commit -m "feat(backend-nest): wire LlmService into AnalyzeModule"
```

---

## Task 8: AnalyzeController with SSE Streaming

**Files:**
- Modify: `backend-nest/src/analyze/analyze.controller.ts`
- Modify: `backend-nest/src/analyze/analyze.controller.spec.ts`

- [ ] **Step 1: Write failing test**

```ts
// backend-nest/src/analyze/analyze.controller.spec.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Test, TestingModule } from '@nestjs/testing';
import { AnalyzeController } from './analyze.controller';
import { AnalyzeService } from './analyze.service';

const mockResult = { sourceType: 'youtube', categories: [] };

describe('AnalyzeController', () => {
  let controller: AnalyzeController;
  let analyzeService: AnalyzeService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      controllers: [AnalyzeController],
      providers: [
        { provide: AnalyzeService, useValue: { analyze: vi.fn().mockResolvedValue(mockResult) } },
      ],
    }).compile();

    controller = module.get(AnalyzeController);
    analyzeService = module.get(AnalyzeService);
  });

  it('is defined', () => {
    expect(controller).toBeDefined();
  });

  it('calls AnalyzeService.analyze with url and targetLanguage', async () => {
    const res = {
      setHeader: vi.fn(),
      status: vi.fn(),
      flushHeaders: vi.fn(),
      write: vi.fn(),
      end: vi.fn(),
    } as any;

    await controller.analyze({ url: 'https://youtube.com/watch?v=abc', targetLanguage: 'en' }, res);

    expect(analyzeService.analyze).toHaveBeenCalledWith({ url: 'https://youtube.com/watch?v=abc', targetLanguage: 'en' });
    expect(res.end).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
npx vitest run src/analyze/analyze.controller.spec.ts
```

Expected: FAIL

- [ ] **Step 3: Implement AnalyzeController**

```ts
// backend-nest/src/analyze/analyze.controller.ts
import { Body, Controller, Post, Res } from '@nestjs/common';
import { Response } from 'express';
import { AnalyzeService } from './analyze.service';
import { AnalyzeDto } from './dto/analyze.dto';

@Controller('analyze')
export class AnalyzeController {
  constructor(private readonly analyzeService: AnalyzeService) {}

  @Post()
  async analyze(@Body() dto: AnalyzeDto, @Res() res: Response): Promise<void> {
    res.status(200);
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache, no-transform');
    res.setHeader('Connection', 'keep-alive');
    res.setHeader('X-Accel-Buffering', 'no');
    (res as any).flushHeaders?.();

    const write = (event: string, data: unknown) => {
      res.write(`event: ${event}\n`);
      res.write(`data: ${JSON.stringify(data)}\n\n`);
    };

    try {
      write('progress', { stage: 'fetching_transcript', message: 'Fetching YouTube transcript' });
      const result = await this.analyzeService.analyze({ url: dto.url, targetLanguage: dto.targetLanguage });
      write('result', result);
    } catch (err: any) {
      write('error', {
        stage: 'failed',
        code: err?.message ?? 'INTERNAL_SERVER_ERROR',
        statusCode: err?.status ?? 500,
      });
    }

    res.end();
  }
}
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
npx vitest run src/analyze/analyze.controller.spec.ts
```

Expected: PASS

- [ ] **Step 5: End-to-end smoke test**

```bash
npm run dev
# In another terminal:
curl -N -X POST http://localhost:3000/analyze \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","targetLanguage":"en"}'
```

Expected: SSE events printed to terminal, ending with `event: result` containing categories JSON

- [ ] **Step 6: Commit**

```bash
git add backend-nest/src/analyze/analyze.controller.ts backend-nest/src/analyze/analyze.controller.spec.ts
git commit -m "feat(backend-nest): implement AnalyzeController with SSE streaming"
```

---

## Self-Review

**Spec coverage:**
- [x] Receive YouTube URL from client → `AnalyzeDto.url` + `POST /analyze`
- [x] Run Python to fetch transcript → `TranscriptService.spawnPython`
- [x] Sanitize transcript → `TranscriptService.sanitizeSnippets` + `buildSegments`
- [x] Build prompt → `LlmService.buildMessages`
- [x] Send to OpenRouter → `LlmService.analyze` with native fetch
- [x] Receive structured JSON → parsed in `LlmService.analyze`
- [x] Return to client → SSE stream in `AnalyzeController`

**No placeholders found.**

**Type consistency:** `Segment` exported from `transcript.service.ts` and imported in `llm.service.ts`, `analyze.service.ts`, and specs consistently.
