import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { Judgment } from './judgments.entity';
import { JudgmentsController } from './judgments.controller';
import { JudgmentsService } from './judgments.service';

@Module({
  imports: [TypeOrmModule.forFeature([Judgment])],
  controllers: [JudgmentsController],
  providers: [JudgmentsService],
  exports: [JudgmentsService],
})
export class JudgmentsModule {}
