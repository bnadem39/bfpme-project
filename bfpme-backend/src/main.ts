import { NestFactory } from '@nestjs/core';
import * as mysql from 'mysql2/promise';
import { AppModule } from './app.module';

async function bootstrap() {
  const connection = await mysql.createConnection({
    host: process.env.DB_HOST ?? 'localhost',
    port: Number(process.env.DB_PORT ?? 3306),
    user: process.env.DB_USER ?? 'root',
    password: process.env.DB_PASSWORD ?? '',
  });
  await connection.query(
    `CREATE DATABASE IF NOT EXISTS \`${process.env.DB_NAME ?? 'bfpme_db'}\`;`,
  );
  await connection.end();

  const app = await NestFactory.create(AppModule);
  app.enableCors();
  await app.listen(process.env.PORT ?? 3000);
}

bootstrap();
