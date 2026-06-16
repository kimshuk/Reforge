import { Injectable, OnModuleDestroy } from '@nestjs/common';
import Redis from 'ioredis';

const DEFAULT_REDIS_URL = 'redis://localhost:6379';

@Injectable()
export class RedisService implements OnModuleDestroy {
  private readonly client = new Redis(process.env.REDIS_URL || DEFAULT_REDIS_URL, {
    lazyConnect: true,
    maxRetriesPerRequest: 1,
  });

  async ping(): Promise<string> {
    if (this.client.status === 'wait') {
      await this.client.connect();
    }
    return this.client.ping();
  }

  async onModuleDestroy() {
    this.client.disconnect();
  }
}
