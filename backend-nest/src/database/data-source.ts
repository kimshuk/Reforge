import 'dotenv/config';

import { DataSource } from 'typeorm';

const DEFAULT_DATABASE_URL =
  'postgres://reforge:reforge@localhost:5432/reforge';

export default new DataSource({
  type: 'postgres',
  url: process.env.DATABASE_URL || DEFAULT_DATABASE_URL,
  entities: [__dirname + '/../**/*.entity{.ts,.js}'],
  migrations: [__dirname + '/migrations/*{.ts,.js}'],
  synchronize: false,
});
