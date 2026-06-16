import 'dotenv/config';

import { INestApplicationContext, Module } from '@nestjs/common';
import { NestFactory } from '@nestjs/core';
import { readFileSync } from 'fs';
import * as path from 'path';

import { AnalyzeRequestParser } from '../analyze/analyze-request.parser';
import { TranscriptSanitizer } from '../analyze/transcript.sanitizer';
import { YoutubeService } from '../analyze/youtube.service';
import { AppException } from '../common/app.exception';
import { ClaudeAdapter } from '../llm/adapters/claude.adapter';
import { GeminiAdapter } from '../llm/adapters/gemini.adapter';
import { OpenAiAdapter } from '../llm/adapters/openai.adapter';
import { LlmConfigService } from '../llm/llm-config.service';
import { LLM_ADAPTERS, LlmService } from '../llm/llm.service';
import { LlmRequestOverrides, TranscriptType } from '../llm/llm.types';

interface CliArgs extends LlmRequestOverrides {
  type?: TranscriptType;
  file?: string;
  text?: string;
  youtubeUrl?: string;
  targetLanguage?: string;
  includeRawText?: boolean;
}

@Module({
  providers: [
    AnalyzeRequestParser,
    TranscriptSanitizer,
    YoutubeService,
    LlmConfigService,
    OpenAiAdapter,
    GeminiAdapter,
    ClaudeAdapter,
    {
      provide: LLM_ADAPTERS,
      useFactory: (
        openAi: OpenAiAdapter,
        gemini: GeminiAdapter,
        claude: ClaudeAdapter,
      ) => [openAi, gemini, claude],
      inject: [OpenAiAdapter, GeminiAdapter, ClaudeAdapter],
    },
    LlmService,
  ],
})
class SummaryCliModule {}

async function main() {
  const args = parseArgs(process.argv.slice(2));

  if (args.help) {
    printUsage();
    return;
  }

  const app = await NestFactory.createApplicationContext(SummaryCliModule, {
    logger: false,
  });

  try {
    const result = await runSummary(app, args);
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  } finally {
    await app.close();
  }
}

async function runSummary(app: INestApplicationContext, args: CliArgs) {
  const type = args.type;
  if (type !== 'manual' && type !== 'youtube') {
    throw new AppException(
      400,
      'INVALID_TYPE',
      "--type must be either 'manual' or 'youtube'",
    );
  }

  const targetLanguage = normalizeTargetLanguage(args.targetLanguage);
  const llmConfig = app.get(LlmConfigService, { strict: false });
  const llmService = app.get(LlmService, { strict: false });
  const options = llmConfig.resolve(args);

  if (type === 'manual') {
    const transcriptText = resolveManualTranscript(args);
    return llmService.summarizeTranscript({
      transcriptText,
      transcriptType: 'manual',
      targetLanguage,
      options,
      includeRawText: args.includeRawText,
    });
  }

  if (!args.youtubeUrl) {
    throw new AppException(
      400,
      'INVALID_YOUTUBE_URL',
      '--youtube-url is required for --type youtube',
    );
  }

  const youtubeService = app.get(YoutubeService, { strict: false });
  const sanitizer = app.get(TranscriptSanitizer, { strict: false });
  const youtubeResult = await youtubeService.fetchTranscript(args.youtubeUrl);
  const sanitized = sanitizer.sanitize(youtubeResult.transcriptSnippets);

  return llmService.summarizeTranscript({
    transcriptText: sanitized.llmTranscriptText,
    transcriptType: 'youtube',
    targetLanguage,
    youtubeUrl: args.youtubeUrl,
    segmentIndex: sanitized.segmentIndex,
    options,
    includeRawText: args.includeRawText,
  });
}

function parseArgs(argv: string[]): CliArgs & { help?: boolean } {
  const args: CliArgs & { help?: boolean } = {};

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--help' || arg === '-h') {
      args.help = true;
      continue;
    }

    if (!arg.startsWith('--')) {
      throw new AppException(400, 'INVALID_CLI_ARG', `Unexpected argument: ${arg}`);
    }

    const key = arg.slice(2);
    if (key === 'include-raw-text') {
      args.includeRawText = true;
      continue;
    }

    const value = argv[index + 1];
    if (!value || value.startsWith('--')) {
      throw new AppException(400, 'INVALID_CLI_ARG', `Missing value for ${arg}`);
    }
    index += 1;

    switch (key) {
      case 'type':
        args.type = value as TranscriptType;
        break;
      case 'file':
        args.file = value;
        break;
      case 'text':
        args.text = value;
        break;
      case 'youtube-url':
        args.youtubeUrl = value;
        break;
      case 'target-language':
        args.targetLanguage = value;
        break;
      case 'provider':
        args.provider = value;
        break;
      case 'model':
        args.model = value;
        break;
      case 'temperature':
        args.temperature = Number(value);
        break;
      case 'max-output-tokens':
        args.maxOutputTokens = Number(value);
        break;
      default:
        throw new AppException(400, 'INVALID_CLI_ARG', `Unknown option: ${arg}`);
    }
  }

  return args;
}

function resolveManualTranscript(args: CliArgs): string {
  if (args.file && args.text) {
    throw new AppException(
      400,
      'INVALID_CLI_ARG',
      'Use either --file or --text, not both',
    );
  }

  if (args.file) {
    return readFileSync(path.resolve(args.file), 'utf8').trim();
  }

  if (args.text?.trim()) {
    return args.text.trim();
  }

  throw new AppException(
    400,
    'INVALID_TEXT',
    'Manual summaries require --file or --text',
  );
}

function normalizeTargetLanguage(value: unknown): string {
  return new AnalyzeRequestParser().parse({
    type: 'manual',
    text: 'placeholder transcript for target language validation',
    targetLanguage: value ?? 'en',
  }).targetLanguage;
}

function printUsage() {
  process.stdout.write(`Usage:
  npm run llm:test-summary -- --type manual --file ./transcript.txt --provider openai --model gpt-4o-mini
  npm run llm:test-summary -- --type youtube --youtube-url "https://youtube.com/watch?v=..." --provider gemini --model gemini-1.5-pro

Options:
  --type manual|youtube
  --file <path>
  --text <text>
  --youtube-url <url>
  --target-language <code>
  --provider openai|gemini|claude
  --model <model>
  --temperature <number>
  --max-output-tokens <integer>
  --include-raw-text
`);
}

main().catch((error: unknown) => {
  if (error instanceof AppException) {
    process.stderr.write(
      `${JSON.stringify(
        {
          error: {
            code: error.code,
            message: error.message,
          },
        },
        null,
        2,
      )}\n`,
    );
    process.exitCode = 1;
    return;
  }

  process.stderr.write(
    `${JSON.stringify(
      {
        error: {
          code: 'INTERNAL_ERROR',
          message: error instanceof Error ? error.message : 'Unexpected error',
        },
      },
      null,
      2,
    )}\n`,
  );
  process.exitCode = 1;
});
