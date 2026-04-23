import { Injectable } from '@nestjs/common';
import { spawn } from 'child_process';

@Injectable()
export class PythonHealthService {
  check(): Promise<{ ok: boolean; error?: string }> {
    const pythonBin = process.env.PYTHON_BIN || 'python3';

    return new Promise((resolve) => {
      const child = spawn(pythonBin, ['-c', 'import youtube_transcript_api']);

      let stderr = '';
      child.stderr.on('data', (chunk: Buffer) => {
        stderr += chunk.toString();
      });

      child.on('error', () => {
        resolve({ ok: false, error: 'Python runtime not found' });
      });

      child.on('close', (code) => {
        if (code === 0) {
          resolve({ ok: true });
        } else {
          resolve({ ok: false, error: stderr.trim() || 'youtube-transcript-api not installed' });
        }
      });
    });
  }
}
