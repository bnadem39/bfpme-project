import {
  BadGatewayException,
  GatewayTimeoutException,
  Injectable,
  NotFoundException,
  ServiceUnavailableException,
  UnprocessableEntityException,
} from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import {
  Judgment,
  JudgmentExtractionResult,
} from './judgments.entity';

interface AiErrorDetail {
  code?: string;
  message?: string;
  raw?: string;
}

interface AiExtractionResponse {
  status: string;
  file_name: string;
  pdf_type: string;
  extraction_method: string;
  result: JudgmentExtractionResult;
}

@Injectable()
export class JudgmentsService {
  constructor(
    @InjectRepository(Judgment)
    private readonly judgmentsRepo: Repository<Judgment>,
  ) {}

  private normalizeStatus(status: string): Judgment['status'] {
    if (status === 'En cours' || status === 'Anomalie' || status === 'Valide') {
      return status;
    }
    return status.toLowerCase().includes('valid') ? 'Valide' : 'Anomalie';
  }

  async findAll(): Promise<Judgment[]> {
    const items = await this.judgmentsRepo.find({
      order: { date: 'DESC' },
    });
    return items.map((item) => ({
      ...item,
      status: this.normalizeStatus(item.status),
    }));
  }

  async getStats(): Promise<{
    total: number;
    valide: number;
    enCours: number;
    anomalie: number;
  }> {
    const all = await this.judgmentsRepo.find();
    return {
      total: all.length,
      valide: all.filter((j) => this.normalizeStatus(j.status) === 'Valide')
        .length,
      enCours: all.filter((j) => this.normalizeStatus(j.status) === 'En cours')
        .length,
      anomalie: all.filter(
        (j) => this.normalizeStatus(j.status) === 'Anomalie',
      ).length,
    };
  }

  async getFile(id: number): Promise<{ fileName: string; fileData: Buffer }> {
    const judgment = await this.judgmentsRepo
      .createQueryBuilder('judgment')
      .addSelect('judgment.fileData')
      .where('judgment.id = :id', { id })
      .getOne();

    if (!judgment || !judgment.fileData) {
      throw new NotFoundException(`Fichier du jugement #${id} introuvable`);
    }
    return { fileName: judgment.fileName, fileData: judgment.fileData };
  }

  private getAiServiceUrl(): string {
    return process.env.AI_SERVICE_URL ?? 'http://127.0.0.1:8000/extract';
  }

  private getAiTimeoutMs(): number {
    return Number(process.env.AI_SERVICE_TIMEOUT_MS ?? '180000');
  }

  private getAiModelName(): string {
    return process.env.AI_MODEL_NAME ?? 'qwen2.5-7b-instruct-1m';
  }

  private async extractWithAi(
    file: Express.Multer.File,
  ): Promise<AiExtractionResponse> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.getAiTimeoutMs());

    try {
      const formData = new FormData();
      formData.append(
        'file',
        new Blob([new Uint8Array(file.buffer)], { type: file.mimetype }),
        file.originalname,
      );
      formData.append('model', this.getAiModelName());

      const response = await fetch(this.getAiServiceUrl(), {
        method: 'POST',
        body: formData,
        signal: controller.signal,
      });

      const payload = (await response.json().catch(() => null)) as
        | AiExtractionResponse
        | { detail?: AiErrorDetail }
        | null;

      if (!response.ok) {
        const detail =
          payload && 'detail' in payload ? payload.detail : undefined;
        const message =
          detail?.message ??
          `Le service IA a retourne le statut ${response.status}.`;

        if (response.status === 400 || response.status === 422) {
          throw new UnprocessableEntityException(message);
        }
        if (response.status === 503) {
          throw new ServiceUnavailableException(message);
        }
        if (response.status === 504) {
          throw new GatewayTimeoutException(message);
        }
        throw new BadGatewayException(message);
      }

      if (!payload || !('result' in payload)) {
        throw new BadGatewayException(
          'Le service IA a retourne une reponse invalide.',
        );
      }

      return payload;
    } catch (error) {
      if (
        error instanceof UnprocessableEntityException ||
        error instanceof ServiceUnavailableException ||
        error instanceof GatewayTimeoutException ||
        error instanceof BadGatewayException
      ) {
        throw error;
      }

      if (error instanceof Error && error.name === 'AbortError') {
        throw new GatewayTimeoutException(
          "Le service d'extraction IA a depasse le delai autorise.",
        );
      }

      throw new ServiceUnavailableException(
        "Le service d'extraction IA est indisponible.",
      );
    } finally {
      clearTimeout(timeout);
    }
  }

  async create(client: string, file: Express.Multer.File): Promise<Judgment> {
    const year = new Date().getFullYear();
    const count = await this.judgmentsRepo.count();
    const ref = `D-${year}-${(count + 1).toString().padStart(4, '0')}`;

    const sizeInKB = file.size / 1024;
    const readableSize =
      sizeInKB > 1024
        ? `${(sizeInKB / 1024).toFixed(1)} MB`
        : `${sizeInKB.toFixed(0)} KB`;

    const aiResponse = await this.extractWithAi(file);

    const newJudgment = this.judgmentsRepo.create({
      ref,
      client: client.toUpperCase(),
      fileName: file.originalname,
      fileSize: readableSize,
      fileData: file.buffer,
      status: 'Valide',
      extractionResult: aiResponse.result,
      aiModel: this.getAiModelName(),
      pdfType: aiResponse.pdf_type,
      extractionMethod: aiResponse.extraction_method,
      errorMessage: null,
    });

    const saved = await this.judgmentsRepo.save(newJudgment);
    const stored = await this.judgmentsRepo.findOne({
      where: { id: saved.id },
    });

    if (!stored) {
      throw new NotFoundException(`Jugement #${saved.id} introuvable`);
    }

    return stored;
  }

  async remove(id: number): Promise<void> {
    const result = await this.judgmentsRepo.delete(id);
    if (result.affected === 0) {
      throw new NotFoundException(`Jugement #${id} introuvable`);
    }
  }
}
