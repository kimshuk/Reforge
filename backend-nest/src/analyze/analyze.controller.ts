import { Controller, Post } from '@nestjs/common';

@Controller('analyze')
export class AnalyzeController {
  @Post()
  analyze() {
    return { ok: true };
  }
}
