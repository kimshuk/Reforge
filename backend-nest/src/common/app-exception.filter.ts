import {
  ArgumentsHost,
  Catch,
  ExceptionFilter,
  HttpException,
  HttpStatus,
  Logger,
} from '@nestjs/common';
import { Request, Response } from 'express';

import { AppException } from './app.exception';

@Catch()
export class AppExceptionFilter implements ExceptionFilter {
  private readonly logger = new Logger(AppExceptionFilter.name);

  catch(exception: unknown, host: ArgumentsHost) {
    const ctx = host.switchToHttp();
    const response = ctx.getResponse<Response>();
    const request = ctx.getRequest<Request & { requestId?: string }>();

    const statusCode =
      exception instanceof HttpException
        ? exception.getStatus()
        : HttpStatus.INTERNAL_SERVER_ERROR;
    const appCode =
      exception instanceof AppException
        ? exception.code
        : statusCode === HttpStatus.NOT_FOUND
          ? 'NOT_FOUND'
          : 'INTERNAL_SERVER_ERROR';
    const rawMessage =
      exception instanceof Error ? exception.message : 'Unexpected server error';
    const message =
      statusCode >= 500 && !(exception instanceof AppException)
        ? 'Internal server error'
        : rawMessage;

    this.logger.error('request.error', {
      requestId: request.requestId,
      method: request.method,
      path: request.url,
      statusCode,
      code: appCode,
      message: rawMessage,
    });

    response.status(statusCode).json({
      error: {
        code: appCode,
        message,
      },
    });
  }
}
