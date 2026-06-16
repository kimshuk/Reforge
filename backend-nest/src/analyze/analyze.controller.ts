import { Body, Controller, Post, Query, Req, Res } from '@nestjs/common';
import { Request, Response } from 'express';

import { AppException } from '../common/app.exception';
import { AnalyzeService } from './analyze.service';

@Controller('analyze')
export class AnalyzeController {
  constructor(private readonly analyzeService: AnalyzeService) {}

  @Post()
  async analyze(
    @Body() body: unknown,
    @Query('stream') stream: string | undefined,
    @Req() req: Request & { requestId?: string },
    @Res() res: Response,
  ) {
    if (!this.wantsProgressStream(req, stream)) {
      const response = await this.analyzeService.analyze(body, req.requestId);
      res.status(200).json(response);
      return;
    }

    this.startSse(res);
    try {
      const response = await this.analyzeService.analyze(
        body,
        req.requestId,
        (event, payload) => this.writeSseEvent(res, event, payload),
      );
      this.writeSseEvent(res, 'result', response);
    } catch (error) {
      const appError =
        error instanceof AppException
          ? error
          : new AppException(500, 'INTERNAL_SERVER_ERROR', 'Unexpected server error');
      this.writeSseEvent(res, 'error', {
        stage: 'error',
        statusCode: appError.getStatus(),
        code: appError.code,
        message: appError.message,
      });
    } finally {
      res.end();
    }
  }

  private wantsProgressStream(req: Request, stream?: string): boolean {
    const accept = String(req.get('accept') || '').toLowerCase();
    return accept.includes('text/event-stream') || String(stream).toLowerCase() === 'progress';
  }

  private startSse(res: Response) {
    res.status(200);
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache, no-transform');
    res.setHeader('Connection', 'keep-alive');
    res.setHeader('X-Accel-Buffering', 'no');
    res.flushHeaders();
  }

  private writeSseEvent(res: Response, event: string, data: unknown) {
    res.write(`event: ${event}\n`);
    res.write(`data: ${JSON.stringify(data)}\n\n`);
  }
}
