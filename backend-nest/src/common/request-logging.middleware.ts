import { Injectable, Logger, NestMiddleware } from '@nestjs/common';
import { randomUUID } from 'crypto';
import { NextFunction, Request, Response } from 'express';

@Injectable()
export class RequestLoggingMiddleware implements NestMiddleware {
  private readonly logger = new Logger(RequestLoggingMiddleware.name);

  use(
    req: Request & { requestId?: string },
    res: Response,
    next: NextFunction,
  ) {
    req.requestId = randomUUID();
    const start = Date.now();

    res.on('finish', () => {
      this.logger.log({
        event: 'http.request',
        requestId: req.requestId,
        method: req.method,
        path: req.originalUrl,
        statusCode: res.statusCode,
        durationMs: Date.now() - start,
      });
    });

    next();
  }
}
