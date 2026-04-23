import { AppModule } from './app.module';
import { NestFactory } from '@nestjs/core';
import { json } from 'express';

async function bootstrap() {
  const app = await NestFactory.create(AppModule, { bodyParser: false });
  app.use(json({ limit: '1mb' }));
  app.setGlobalPrefix('api', { exclude: ['health'] });
  const port = process.env.PORT ?? 3000;
  await app.listen(port);
  console.log(`server.started at: ${port}`);
}
bootstrap();
