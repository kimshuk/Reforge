import { Controller, Get } from '@nestjs/common';
import { execFile } from 'child_process';
import { promisify } from 'util';
import { DataSource } from 'typeorm';

import { RedisService } from '../redis/redis.service';

const execFileAsync = promisify(execFile);

@Controller('health')
export class HealthController {
  constructor(
    private readonly dataSource: DataSource,
    private readonly redis: RedisService,
  ) {}

  @Get()
  async health() {
    const checks = {
      backend: true,
      postgres: await this.checkPostgres(),
      redis: await this.checkRedis(),
      python: await this.checkPython(),
    };

    return {
      ok: Object.values(checks).every(Boolean),
      checks,
    };
  }

  private async checkPostgres(): Promise<boolean> {
    try {
      await this.dataSource.query('SELECT 1');
      return true;
    } catch {
      return false;
    }
  }

  private async checkRedis(): Promise<boolean> {
    try {
      return (await this.redis.ping()) === 'PONG';
    } catch {
      return false;
    }
  }

  private async checkPython(): Promise<boolean> {
    try {
      await execFileAsync(process.env.PYTHON_BIN || 'python3', [
        '-c',
        'import youtube_transcript_api',
      ]);
      return true;
    } catch {
      return false;
    }
  }
}
