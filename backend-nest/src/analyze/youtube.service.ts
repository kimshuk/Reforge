import * as path from 'path';

import { AppException } from './../common/app.exception';
import { Injectable } from '@nestjs/common';
import { spawn } from 'child_process';

interface TranscriptResult {
  transcriptText: string;
  transcriptSnippets: unknown[];
  languageCode: string | null;
  language: string | null;
  isGenerated: boolean | null;
}

interface VideoTranscript extends TranscriptResult {
  videoId: string;
}

@Injectable()
export class YoutubeService {
  async fetchTranscript(url: string): Promise<VideoTranscript> {
    const videoId = this.extractVideoId(url);
    const result = await this.fetchTranscriptViaPython(videoId);

    if (!result.transcriptText.trim()) {
      throw new AppException(
        502,
        'TRANSCRIPT_UNAVAILABLE',
        'Transcript unavailable for this video',
      );
    }

    return {
      videoId,
      ...result,
    };
  }

  private fetchTranscriptViaPython(videoId: string): Promise<TranscriptResult> {
    const pythonBin = process.env.PYTHON_BIN ?? 'python3';
    const scriptPath = path.resolve(
      __dirname,
      '../../script/fetch_transcript.py',
    );

    return new Promise((resolve, reject) => {
      const child = spawn(pythonBin, [scriptPath, videoId]);

      let stdout = '';
      let stderr = '';

      child.stdout.on('data', (chunk: Buffer) => {
        stdout += chunk.toString();
      });

      child.stderr.on('data', (chunk: Buffer) => {
        stderr += chunk.toString();
      });

      let settled = false;
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
        if (settled) return;
        if (code !== 0) {
          const trimmed = stderr.trim();

          if (trimmed.includes('PY_DEP_MISSING')) {
            reject(
              new AppException(
                500,
                'PYTHON_DEPENDENCY_MISSING',
                'Python package youtube-transcript-api is not installed',
              ),
            );
            return;
          }

          if (trimmed.includes('TRANSCRIPT_UNAVAILABLE')) {
            reject(
              new AppException(
                502,
                'TRANSCRIPT_UNAVAILABLE',
                'Transcript unavailable for this video',
              ),
            );
            return;
          }

          reject(
            new AppException(
              502,
              'TRANSCRIPT_FETCH_FAILED',
              'Unable to fetch YouTube transcript',
            ),
          );
          return;
        }

        let parsed: Record<string, unknown>;
        try {
          parsed = JSON.parse(stdout) as Record<string, unknown>;
        } catch {
          reject(
            new AppException(
              502,
              'TRANSCRIPT_PARSE_FAILED',
              'Invalid transcript response',
            ),
          );
          return;
        }

        const transcriptText =
          typeof parsed.transcriptText === 'string'
            ? parsed.transcriptText
            : '';
        const transcriptSnippets = Array.isArray(parsed.transcriptSnippets)
          ? parsed.transcriptSnippets
          : [];
        const languageCode =
          typeof parsed.languageCode === 'string' ? parsed.languageCode : null;
        const language =
          typeof parsed.language === 'string' ? parsed.language : null;
        const isGenerated =
          typeof parsed.isGenerated === 'boolean' ? parsed.isGenerated : null;

        resolve({
          transcriptText,
          transcriptSnippets,
          languageCode,
          language,
          isGenerated,
        });
      });
    });
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
