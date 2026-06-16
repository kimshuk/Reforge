import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';

const DEFAULT_DATABASE_URL =
  'postgres://reforge:reforge@localhost:5432/reforge';

@Module({
  imports: [
    TypeOrmModule.forRoot({
      type: 'postgres',
      url: process.env.DATABASE_URL || DEFAULT_DATABASE_URL,
      autoLoadEntities: true,
      synchronize: false,
      migrationsRun: process.env.TYPEORM_MIGRATIONS_RUN === 'true',
      migrations: [__dirname + '/migrations/*{.ts,.js}'],
    }),
  ],
})
export class DatabaseModule {}
