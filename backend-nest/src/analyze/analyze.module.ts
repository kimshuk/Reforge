import { Module } from '@nestjs/common';

import { LlmModule } from '../llm/llm.module';
import { TranscriptModule } from '../transcript/transcript.module';
import { AnalyzeRequestParser } from './analyze-request.parser';
import { AnalyzeController } from './analyze.controller';
import { AnalyzeService } from './analyze.service';
import { TranscriptSanitizer } from './transcript.sanitizer';
import { YoutubeService } from './youtube.service';

@Module({
  imports: [LlmModule, TranscriptModule],
  controllers: [AnalyzeController],
  providers: [
    AnalyzeRequestParser,
    AnalyzeService,
    TranscriptSanitizer,
    YoutubeService,
  ],
})
export class AnalyzeModule {}
