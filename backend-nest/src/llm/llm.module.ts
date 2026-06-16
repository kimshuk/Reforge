import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';

import { ClaudeAdapter } from './adapters/claude.adapter';
import { GeminiAdapter } from './adapters/gemini.adapter';
import { OpenAiAdapter } from './adapters/openai.adapter';
import { EvalRunEntity } from './eval-run.entity';
import { LlmConfigService } from './llm-config.service';
import { LLM_ADAPTERS, LlmService } from './llm.service';

@Module({
  imports: [TypeOrmModule.forFeature([EvalRunEntity])],
  providers: [
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
  exports: [LlmConfigService, LlmService],
})
export class LlmModule {}
