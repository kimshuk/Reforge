import { json } from 'express';
import { AppModule } from './app.module';
import { NestFactory } from '@nestjs/core';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  app.use(json({ limit: '1mb' }));
  app.setGlobalPrefix('api', { exclude: ['health'] });
  await app.listen(process.env.PORT ?? 3000);
}
bootstrap();
