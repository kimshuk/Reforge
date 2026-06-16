import { Injectable } from '@nestjs/common';
import { spawn } from 'child_process';
import * as path from 'path';

import { AppException } from '../common/app.exception';
import { YoutubeTranscriptResult } from './analyze.types';

interface TranscriptResult {
  transcriptText: string;
  transcriptSnippets: unknown[];
  languageCode: string | null;
  language: string | null;
  isGenerated: boolean | null;
}

@Injectable()
export class YoutubeService {
  async fetchTranscript(youtubeUrl: string): Promise<YoutubeTranscriptResult> {
    const videoId = this.extractVideoId(youtubeUrl);
    const result = await this.fetchTranscriptViaPython(videoId);

    if (!result.transcriptText.trim()) {
      throw new AppException(
        502,
        'TRANSCRIPT_UNAVAILABLE',
        'Transcript unavailable for this video',
      );
    }

    return { videoId, ...result };
  }

  private extractVideoId(youtubeUrl: string): string {
    let parsed: URL;
    try {
      parsed = new URL(youtubeUrl);
    } catch {
      throw new AppException(
        400,
        'INVALID_YOUTUBE_URL',
        'youtubeUrl must be a valid URL',
      );
    }

    const host = parsed.hostname.replace(/^www\./, '').toLowerCase();

    if (host === 'youtu.be') {
      const id = parsed.pathname.slice(1).trim();
      if (id) {
        return id;
      }
      throw new AppException(400, 'INVALID_YOUTUBE_URL', 'Missing video id in URL');
    }

    if (host === 'youtube.com' || host === 'm.youtube.com') {
      const watchId = parsed.searchParams.get('v');
      if (watchId) {
        return watchId;
      }

      if (parsed.pathname.startsWith('/shorts/')) {
        const shortId = parsed.pathname.split('/')[2];
        if (shortId) {
          return shortId;
        }
      }
    }

    throw new AppException(
      400,
      'INVALID_YOUTUBE_URL',
      'Unsupported YouTube URL format',
    );
  }

  private fetchTranscriptViaPython(videoId: string): Promise<TranscriptResult> {
    const pythonBin = process.env.PYTHON_BIN || 'python3';
    const scriptPath = path.resolve(__dirname, '../../script/fetch_transcript.py');

    return new Promise((resolve, reject) => {
      const child = spawn(pythonBin, [scriptPath, videoId]);
      let stdout = '';
      let stderr = '';
      let settled = false;

      child.stdout.on('data', (chunk: Buffer) => {
        stdout += chunk.toString();
      });

      child.stderr.on('data', (chunk: Buffer) => {
        stderr += chunk.toString();
      });

      child.on('error', () => {
        settled = true;
        reject(
          new AppException(
            502,
            'PYTHON_RUNTIME_ERROR',
            'Unable to execute Python runtime',
          ),
        );
      });

      child.on('close', (code) => {
        if (settled) {
          return;
        }

        if (code !== 0) {
          reject(this.toPythonError(stderr));
          return;
        }

        const parsed = this.parsePythonResponse(stdout);
        resolve(parsed);
      });
    });
  }

  private parsePythonResponse(stdout: string): TranscriptResult {
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(stdout) as Record<string, unknown>;
    } catch {
      throw new AppException(
        502,
        'TRANSCRIPT_PARSE_FAILED',
        'Invalid transcript response',
      );
    }

    return {
      transcriptText:
        typeof parsed.transcriptText === 'string' ? parsed.transcriptText : '',
      transcriptSnippets: Array.isArray(parsed.transcriptSnippets)
        ? parsed.transcriptSnippets
        : [],
      languageCode:
        typeof parsed.languageCode === 'string' ? parsed.languageCode : null,
      language: typeof parsed.language === 'string' ? parsed.language : null,
      isGenerated:
        typeof parsed.isGenerated === 'boolean' ? parsed.isGenerated : null,
    };
  }

  private toPythonError(stderr: string): AppException {
    const trimmed = stderr.trim();
    if (trimmed.includes('PY_DEP_MISSING')) {
      return new AppException(
        500,
        'PYTHON_DEPENDENCY_MISSING',
        'Python package youtube-transcript-api is not installed',
      );
    }

    if (trimmed.includes('TRANSCRIPT_UNAVAILABLE')) {
      return new AppException(
        502,
        'TRANSCRIPT_UNAVAILABLE',
        'Transcript unavailable for this video',
      );
    }

    return new AppException(
      502,
      'TRANSCRIPT_FETCH_FAILED',
      'Unable to fetch YouTube transcript',
    );
  }
}
