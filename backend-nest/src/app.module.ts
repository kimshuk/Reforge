import { MiddlewareConsumer, Module, NestModule } from '@nestjs/common';

import { AnalyzeModule } from './analyze/analyze.module';
import { RequestLoggingMiddleware } from './common/request-logging.middleware';
import { DatabaseModule } from './database/database.module';
import { HealthModule } from './health/health.module';
import { LlmModule } from './llm/llm.module';
import { RedisModule } from './redis/redis.module';
import { TranscriptModule } from './transcript/transcript.module';

@Module({
  imports: [
    DatabaseModule,
    RedisModule,
    HealthModule,
    LlmModule,
    TranscriptModule,
    AnalyzeModule,
  ],
})
export class AppModule implements NestModule {
  configure(consumer: MiddlewareConsumer) {
    consumer.apply(RequestLoggingMiddleware).forRoutes('*');
  }
}
