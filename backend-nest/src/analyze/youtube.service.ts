import { AppException } from './../common/app.exception';
import { Injectable } from '@nestjs/common';

@Injectable()
export class YoutubeService {
  fetchTranscript(url: string): Promise<string> {
    const videoId = this.extractVideoId(url);
    // TODO: run from transcript fetcher to retrieve the transcript
    throw new Error('not implemented');
  }

  private extractVideoId(url: string): string {
    let parsed: URL;
    try {
      parsed = new URL(url);
    } catch {
      throw new AppException(
        400,
        'INVALID_YOUTUBE_URL',
        'youtubeURL must be a valid URL',
      );
    }

    const host = parsed.hostname.replace(/^www\./, '').toLowerCase();

    if (host === 'youtu.be') {
      const id = parsed.pathname.slice(1).trim();
      if (!id)
        throw new AppException(
          400,
          'INVALID_YOUTUBE_URL',
          'Missing video id in URL',
        );
      return id;
    }

    if (host === 'youtube.com' || host === 'm.youtube.com') {
      const watchId = parsed.searchParams.get('v');
      if (watchId) return watchId;
    }

    throw new AppException(
      400,
      'INVALID_YOUTUBE_URL',
      'Unsupported YouTube URL format',
    );
  }
}
