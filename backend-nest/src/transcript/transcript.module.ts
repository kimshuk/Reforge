import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';

import { AnalysisRunEntity } from '../analyze/analysis-run.entity';
import { CandidateClippingEntity } from '../analyze/candidate-clipping.entity';
import { CoverageWarningEntity } from '../analyze/coverage-warning.entity';
import { TopicChunkEntity } from '../analyze/topic-chunk.entity';
import { SourceEntity } from './source.entity';
import { TranscriptController } from './transcript.controller';
import { TranscriptSegmentEntity } from './transcript-segment.entity';
import { TranscriptStoreService } from './transcript-store.service';
import { TranscriptEntity } from './transcript.entity';

@Module({
  imports: [
    TypeOrmModule.forFeature([
      AnalysisRunEntity,
      CandidateClippingEntity,
      CoverageWarningEntity,
      SourceEntity,
      TopicChunkEntity,
      TranscriptEntity,
      TranscriptSegmentEntity,
    ]),
  ],
  controllers: [TranscriptController],
  providers: [TranscriptStoreService],
  exports: [TranscriptStoreService],
})
export class TranscriptModule {}
