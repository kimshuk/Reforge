import { Controller, Get, Logger, Param, Req } from '@nestjs/common';
import { Request } from 'express';

import { AppException } from '../common/app.exception';
import { TranscriptStoreService } from './transcript-store.service';

const UUID_V4_REGEX =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

@Controller('transcript')
export class TranscriptController {
  private readonly logger = new Logger(TranscriptController.name);

  constructor(private readonly transcriptStore: TranscriptStoreService) {}

  @Get(':transcriptId')
  async getTranscript(
    @Param('transcriptId') transcriptId: string,
    @Req() req: Request & { requestId?: string },
  ) {
    if (!UUID_V4_REGEX.test(transcriptId)) {
      throw new AppException(
        400,
        'INVALID_TRANSCRIPT_ID',
        'transcriptId must be a valid UUID v4',
      );
    }

    const cached = await this.transcriptStore.getTranscript(transcriptId);
    if (!cached) {
      throw new AppException(
        404,
        'TRANSCRIPT_NOT_FOUND',
        'transcriptId not found or expired',
      );
    }

    this.logger.log({
      event: 'transcript.fetch',
      requestId: req.requestId,
      transcriptId,
      videoId: cached.videoId,
    });

    return {
      transcriptId,
      videoId: cached.videoId,
      createdAt: new Date(cached.createdAt).toISOString(),
      expiresAt: new Date(cached.expiresAt).toISOString(),
      transcriptText: cached.transcriptText,
    };
  }
}
