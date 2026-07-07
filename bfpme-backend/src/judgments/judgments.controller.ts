import {
  Controller,
  Get,
  Post,
  Delete,
  Param,
  Body,
  UploadedFile,
  UseInterceptors,
  Res,
  HttpCode,
  HttpStatus,
  ParseIntPipe,
  BadRequestException,
} from '@nestjs/common';
import { FileInterceptor } from '@nestjs/platform-express';
import { memoryStorage } from 'multer';
import type { Response } from 'express';
import { JudgmentsService } from './judgments.service';

@Controller('judgments')
export class JudgmentsController {
  constructor(private readonly judgmentsService: JudgmentsService) {}

  /** GET /judgments - Liste tous les jugements (sans binaire) */
  @Get()
  findAll() {
    return this.judgmentsService.findAll();
  }

  /** GET /judgments/stats - Statistiques pour le tableau de bord */
  @Get('stats')
  getStats() {
    return this.judgmentsService.getStats();
  }

  /** POST /judgments/upload - Upload d'un PDF et enregistrement en base */
  @Post('upload')
  @HttpCode(HttpStatus.CREATED)
  @UseInterceptors(
    FileInterceptor('file', {
      storage: memoryStorage(),
      fileFilter: (_req, file, callback) => {
        if (file.mimetype !== 'application/pdf') {
          return callback(
            new BadRequestException('Seuls les fichiers PDF sont acceptés'),
            false,
          );
        }
        callback(null, true);
      },
      limits: { fileSize: 10 * 1024 * 1024 }, // 10 MB max
    }),
  )
  async uploadFile(
    @Body('client') client: string,
    @UploadedFile() file: Express.Multer.File,
  ) {
    if (!client || !client.trim()) {
      throw new BadRequestException('Le nom du client est requis');
    }
    if (!file) {
      throw new BadRequestException('Un fichier PDF est requis');
    }
    return this.judgmentsService.create(client, file);
  }

  /** GET /judgments/:id/file - Télécharge / affiche le PDF depuis la base */
  @Get(':id/file')
  async getFile(
    @Param('id', ParseIntPipe) id: number,
    @Res() res: Response,
  ) {
    const { fileName, fileData } = await this.judgmentsService.getFile(id);
    res.setHeader('Content-Type', 'application/pdf');
    res.setHeader(
      'Content-Disposition',
      `inline; filename="${encodeURIComponent(fileName)}"`,
    );
    res.send(fileData);
  }

  /** DELETE /judgments/:id - Supprime un jugement */
  @Delete(':id')
  @HttpCode(HttpStatus.NO_CONTENT)
  async remove(@Param('id', ParseIntPipe) id: number) {
    await this.judgmentsService.remove(id);
  }
}
