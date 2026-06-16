import 'dotenv/config';

import { NestFactory } from '@nestjs/core';
import { DataSource } from 'typeorm';

import { AppModule } from '../app.module';
import { formatTimestamp } from '../analyze/transcript.sanitizer';
import { EvalRunEntity } from '../llm/eval-run.entity';
import { LlmConfigService } from '../llm/llm-config.service';
import { LlmService } from '../llm/llm.service';
import { TranscriptStoreService } from '../transcript/transcript-store.service';
import { TranscriptEntity } from '../transcript/transcript.entity';

function arg(name: string): string | undefined {
  const prefix = `--${name}=`;
  const value = process.argv.find((item) => item.startsWith(prefix));
  return value?.slice(prefix.length);
}

async function main() {
  const transcriptId = arg('transcript-id');
  if (!transcriptId) {
    throw new Error('Missing --transcript-id=<uuid>');
  }

  const app = await NestFactory.createApplicationContext(AppModule, {
    logger: false,
  });

  try {
    const dataSource = app.get(DataSource);
    const transcriptStore = app.get(TranscriptStoreService);
    const llmConfig = app.get(LlmConfigService);
    const llmService = app.get(LlmService);
    const transcript = await dataSource
      .getRepository(TranscriptEntity)
      .findOneBy({ id: transcriptId });

    if (!transcript) {
      throw new Error(`Transcript not found: ${transcriptId}`);
    }

    const segments = await transcriptStore.listSegments(transcriptId);
    const options = llmConfig.resolve({
      provider: arg('provider'),
      model: arg('model'),
      temperature: arg('temperature'),
      maxOutputTokens: arg('max-output-tokens'),
    });

    const startedAt = Date.now();
    const validationErrors: string[] = [];
    let rawOutput: unknown = null;

    try {
      rawOutput = await llmService.generateTopicChunks({
        transcriptSegments: segments
          .map(
            (segment) =>
              `${segment.id} | ${formatTimestamp(segment.startTime)} | ${segment.text}`,
          )
          .join('\n'),
        targetLanguage: arg('target-language') || 'en',
        options,
      });
    } catch (error) {
      validationErrors.push(error instanceof Error ? error.message : String(error));
      rawOutput = {
        error: error instanceof Error ? error.message : String(error),
      };
    }

    const evalRun = await dataSource.getRepository(EvalRunEntity).save({
      provider: options.provider,
      model: options.model,
      promptVersion: 'topic-chunking-v1',
      schemaVersion: 'topic-chunking-v1',
      transcriptHash: transcript.transcriptHash,
      latencyMs: Date.now() - startedAt,
      estimatedCost: null,
      validationErrors,
      rawOutput,
      review: {
        schemaValidity: null,
        majorTopicCoverage: null,
        candidateUsefulness: null,
        neutrality: null,
        sourceGrounding: null,
        redundancy: null,
        titleClarity: null,
        explanationFaithfulness: null,
        latencyCost: null,
      },
    });

    console.log(JSON.stringify({ evalRunId: evalRun.id, validationErrors }, null, 2));
  } finally {
    await app.close();
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
