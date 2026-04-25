import { Injectable } from '@nestjs/common';

@Injectable()
export class YoutubeService {
  fetchTranscript(url: string): Promise<string> {
    throw new Error('not implemented');
  }
}
