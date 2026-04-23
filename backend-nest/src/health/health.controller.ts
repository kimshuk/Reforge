import { Controller, Get, HttpException, HttpStatus } from '@nestjs/common';

import { PythonHealthService } from './python-health.service';

@Controller('health')
export class HealthController {
  constructor(private readonly python: PythonHealthService) {}

  @Get()
  async check() {
    const python = await this.python.check();

    if (!python.ok) {
      throw new HttpException(
        { ok: false, python },
        HttpStatus.SERVICE_UNAVAILABLE,
      );
    }

    return { ok: true, python };
  }
}
