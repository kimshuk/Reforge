import { AnalyzeController } from './analyze.controller';
import { AnalyzeService } from './analyze.service';
import { LlmService } from './llm.service';
import { Module } from '@nestjs/common';
import { TranscriptSanitizer } from './transcript.sanitizer';
import { YoutubeService } from './youtube.service';

@Module({
  controllers: [AnalyzeController],
  providers: [AnalyzeService, TranscriptSanitizer, LlmService, YoutubeService],
})
export class AnalyzeModule {}
