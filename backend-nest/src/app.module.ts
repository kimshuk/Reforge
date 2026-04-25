import { AnalyzeModule } from './analyze/analyze.module';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { HealthModule } from './health/health.module';
import { Module } from '@nestjs/common';

@Module({
  imports: [HealthModule, AnalyzeModule],
  controllers: [AppController],
  providers: [AppService],
})
export class AppModule {}
