import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { Judgment } from './judgments/judgments.entity';
import { JudgmentsModule } from './judgments/judgments.module';

@Module({
  imports: [
    TypeOrmModule.forRoot({
      type: 'mysql',
      host: process.env.DB_HOST ?? 'localhost',
      port: Number(process.env.DB_PORT ?? 3306),
      username: process.env.DB_USER ?? 'root',
      password: process.env.DB_PASSWORD ?? '',
      database: process.env.DB_NAME ?? 'bfpme_db',
      entities: [Judgment],
      autoLoadEntities: true,
      synchronize: true,
    }),
    JudgmentsModule,
  ],
  controllers: [AppController],
  providers: [AppService],
})
export class AppModule {}
