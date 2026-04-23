import { HealthController } from './health.controller';
import { PythonHealthService } from './python-health.service';
import { Module } from '@nestjs/common';

@Module({
  controllers: [HealthController],
  providers: [PythonHealthService],
})
export class HealthModule {}
