import { HttpException } from '@nestjs/common';

export class AppException extends HttpException {
  constructor(
    statusCode: number,
    public readonly code: string,
    message: string,
  ) {
    super(message, statusCode);
  }
}
