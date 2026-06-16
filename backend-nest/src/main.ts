import 'dotenv/config';

import { NestFactory } from '@nestjs/core';
import { json } from 'express';

import { AppModule } from './app.module';
import { AppExceptionFilter } from './common/app-exception.filter';

async function bootstrap() {
  const app = await NestFactory.create(AppModule, { bodyParser: false });
  app.use(json({ limit: '1mb' }));
  app.useGlobalFilters(new AppExceptionFilter());

  const port = Number(process.env.PORT ?? 3000);
  await app.listen(port);
  console.log(`server.started at: ${port}`);
}

bootstrap();
