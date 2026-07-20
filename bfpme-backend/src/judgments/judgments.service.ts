import {
  BadGatewayException,
  GatewayTimeoutException,
  HttpException,
  Injectable,
  NotFoundException,
  OnModuleInit,
  ServiceUnavailableException,
  UnprocessableEntityException,
} from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Readable } from 'stream';
import { QueryFailedError, Repository } from 'typeorm';
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

const EMPTY_EXTRACTION_RESULT: JudgmentExtractionResult = {
  tribunal: null,
  numero_dossier: null,
  date_decision: null,
  type_jugement: null,
  role_bfpme: null,
  parties: {
    demandeur: null,
    defendeur: null,
  },
  montants_fixes: null,
  montants_variables: null,
  montant: null,
  explication_montant: null,
  montant_justification: null,
  references_juridiques: null,
  decision: null,
  decision_justification: null,
  resume: null,
};

@Injectable()
export class JudgmentsService implements OnModuleInit {
  constructor(
    @InjectRepository(Judgment)
    private readonly judgmentsRepo: Repository<Judgment>,
  ) {}

  async onModuleInit(): Promise<void> {
    await this.backfillExtractedColumns();
  }

  private normalizeStatus(status: string): Judgment['status'] {
    if (status === 'En cours' || status === 'Anomalie' || status === 'Valide') {
      return status;
    }
    return status.toLowerCase().includes('valid') ? 'Valide' : 'Anomalie';
  }

  private needsExtractedColumnBackfill(item: Judgment): boolean {
    return Boolean(
      item.extractionResult &&
        !item.tribunal &&
        !item.numeroDossier &&
        !item.montant &&
        !item.decision,
    );
  }

  async backfillExtractedColumns(): Promise<{ updated: number }> {
    const items = await this.judgmentsRepo.find();
    const backfillItems = items.filter((item) =>
      this.needsExtractedColumnBackfill(item),
    );

    if (backfillItems.length > 0) {
      await Promise.all(
        backfillItems.map((item) =>
          this.judgmentsRepo.update(
            item.id,
            this.getExtractedColumns(item.extractionResult),
          ),
        ),
      );
    }

    return { updated: backfillItems.length };
  }

  async findAll(): Promise<Judgment[]> {
    const items = await this.judgmentsRepo.find({
      order: { date: 'DESC' },
    });

    return items.map((item) => ({
      ...item,
      ...(this.needsExtractedColumnBackfill(item)
        ? this.getExtractedColumns(item.extractionResult)
        : {}),
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

  private async findOneWithFileData(id: number): Promise<Judgment> {
    const judgment = await this.judgmentsRepo
      .createQueryBuilder('judgment')
      .addSelect('judgment.fileData')
      .where('judgment.id = :id', { id })
      .getOne();

    if (!judgment || !judgment.fileData) {
      throw new NotFoundException(`Fichier du jugement #${id} introuvable`);
    }

    return judgment;
  }

  private getAiServiceUrl(): string {
    return process.env.AI_SERVICE_URL ?? 'http://127.0.0.1:8000/extract';
  }

  private getAiTimeoutMs(): number {
    return Number(process.env.AI_SERVICE_TIMEOUT_MS ?? '600000');
  }

  private getAiModelName(): string {
    return process.env.AI_MODEL_NAME ?? 'qwen/qwen3.5-9b';
  }

  private async generateRef(): Promise<string> {
    const year = new Date().getFullYear();
    const prefix = `D-${year}-`;
    const rows = await this.judgmentsRepo
      .createQueryBuilder('judgment')
      .select('judgment.ref', 'ref')
      .where('judgment.ref LIKE :prefix', { prefix: `${prefix}%` })
      .getRawMany<{ ref: string }>();

    const maxSequence = rows.reduce((max, row) => {
      const match = row.ref.match(/^D-\d{4}-(\d+)$/);
      if (!match) {
        return max;
      }
      return Math.max(max, Number(match[1]));
    }, 0);

    return `${prefix}${(maxSequence + 1).toString().padStart(4, '0')}`;
  }

  private isDuplicateRefError(error: unknown): boolean {
    if (!(error instanceof QueryFailedError)) {
      return false;
    }

    const driverError = error.driverError as {
      code?: string;
      errno?: number;
      message?: string;
    };

    return (
      driverError.code === 'ER_DUP_ENTRY' ||
      driverError.errno === 1062 ||
      Boolean(driverError.message?.includes('Duplicate entry'))
    );
  }

  private truncateErrorMessage(message: string | null): string | null {
    if (!message) {
      return null;
    }
    return message.length > 4000 ? `${message.slice(0, 3997)}...` : message;
  }

  private getErrorMessage(error: unknown): string {
    if (error instanceof HttpException) {
      const response = error.getResponse();
      if (
        typeof response === 'object' &&
        response !== null &&
        'message' in response
      ) {
        const message = (response as { message?: unknown }).message;
        if (typeof message === 'string') {
          return message;
        }
        if (Array.isArray(message)) {
          return message.join(', ');
        }
      }
      return error.message;
    }

    if (error instanceof Error) {
      return error.message;
    }

    return "Erreur inconnue lors de l'extraction IA.";
  }

  private getExtractedColumns(result: JudgmentExtractionResult | null): Pick<
    Judgment,
    | 'tribunal'
    | 'numeroDossier'
    | 'dateDecision'
    | 'demandeur'
    | 'defendeur'
    | 'montant'
    | 'explicationMontant'
    | 'referencesJuridiques'
    | 'decision'
    | 'decisionJustification'
    | 'resume'
  > {
    return {
      tribunal: result?.tribunal ?? null,
      numeroDossier: result?.numero_dossier ?? null,
      dateDecision: result?.date_decision ?? null,
      demandeur: result?.parties?.demandeur ?? null,
      defendeur: result?.parties?.defendeur ?? null,
      montant: result?.montant ?? null,
      explicationMontant:
        result?.explication_montant ?? result?.montant_justification ?? null,
      referencesJuridiques: result?.references_juridiques ?? null,
      decision: result?.decision ?? null,
      decisionJustification: result?.decision_justification ?? null,
      resume: result?.resume ?? null,
    };
  }

  private isExtractionSufficient(result: JudgmentExtractionResult): boolean {
    const meaningfulFields = [
      result.tribunal,
      result.numero_dossier,
      result.date_decision,
      result.parties?.demandeur,
      result.parties?.defendeur,
      result.montant,
      result.decision,
      result.decision_justification,
      ...(result.references_juridiques ?? []),
    ];

    return meaningfulFields.filter(
      (value) => typeof value === 'string' && value.trim().length > 0,
    ).length >= 3;
  }

  private getExtractionStatus(
    aiResponse: AiExtractionResponse | null,
    result: JudgmentExtractionResult,
  ): Judgment['status'] {
    return aiResponse?.status === 'success' && this.isExtractionSufficient(result)
      ? 'Valide'
      : 'Anomalie';
  }

  private getPartialExtractionMessage(
    aiResponse: AiExtractionResponse | null,
    result: JudgmentExtractionResult,
  ): string | null {
    if (aiResponse?.status === 'success' && this.isExtractionSufficient(result)) {
      return null;
    }
    return 'Extraction partielle : verification manuelle ou relance requise.';
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

  private buildStoredFile(judgment: Judgment): Express.Multer.File {
    return {
      fieldname: 'file',
      originalname: judgment.fileName,
      encoding: '7bit',
      mimetype: 'application/pdf',
      size: judgment.fileData.length,
      buffer: judgment.fileData,
      destination: '',
      filename: judgment.fileName,
      path: '',
      stream: Readable.from(judgment.fileData),
    };
  }

  private async reloadWithoutFileData(id: number): Promise<Judgment> {
    const stored = await this.judgmentsRepo.findOne({
      where: { id },
    });

    if (!stored) {
      throw new NotFoundException(`Jugement #${id} introuvable`);
    }

    return {
      ...stored,
      status: this.normalizeStatus(stored.status),
    };
  }

  async retryExtraction(id: number): Promise<Judgment> {
    const judgment = await this.findOneWithFileData(id);

    await this.judgmentsRepo.update(id, {
      status: 'En cours',
      errorMessage: null,
      extractionMethod: 'retrying',
    });

    let aiResponse: AiExtractionResponse | null = null;
    let extractionError: string | null = null;

    try {
      aiResponse = await this.extractWithAi(this.buildStoredFile(judgment));
    } catch (error) {
      extractionError = this.getErrorMessage(error);
    }

    const extractionResult = aiResponse?.result ?? EMPTY_EXTRACTION_RESULT;
    const partialExtractionMessage = this.getPartialExtractionMessage(
      aiResponse,
      extractionResult,
    );
    await this.judgmentsRepo.update(id, {
      status: this.getExtractionStatus(aiResponse, extractionResult),
      extractionResult,
      ...this.getExtractedColumns(extractionResult),
      aiModel: this.getAiModelName(),
      pdfType: aiResponse?.pdf_type ?? 'unknown',
      extractionMethod: aiResponse?.extraction_method ?? 'failed',
      errorMessage: this.truncateErrorMessage(
        extractionError ?? partialExtractionMessage,
      ),
    });

    return this.reloadWithoutFileData(id);
  }

  async create(client: string, file: Express.Multer.File): Promise<Judgment> {
    const sizeInKB = file.size / 1024;
    const readableSize =
      sizeInKB > 1024
        ? `${(sizeInKB / 1024).toFixed(1)} MB`
        : `${sizeInKB.toFixed(0)} KB`;

    let aiResponse: AiExtractionResponse | null = null;
    let extractionError: string | null = null;

    try {
      aiResponse = await this.extractWithAi(file);
    } catch (error) {
      extractionError = this.getErrorMessage(error);
    }

    let saved: Judgment | null = null;
    for (let attempt = 0; attempt < 5; attempt += 1) {
      const ref = await this.generateRef();
      const extractionResult = aiResponse?.result ?? EMPTY_EXTRACTION_RESULT;
      const partialExtractionMessage = this.getPartialExtractionMessage(
        aiResponse,
        extractionResult,
      );
      const newJudgment = this.judgmentsRepo.create({
        ref,
        client: client.toUpperCase(),
        fileName: file.originalname,
        fileSize: readableSize,
        fileData: file.buffer,
        status: this.getExtractionStatus(aiResponse, extractionResult),
        extractionResult,
        ...this.getExtractedColumns(extractionResult),
        aiModel: this.getAiModelName(),
        pdfType: aiResponse?.pdf_type ?? 'unknown',
        extractionMethod: aiResponse?.extraction_method ?? 'failed',
        errorMessage: this.truncateErrorMessage(
          extractionError ?? partialExtractionMessage,
        ),
      });

      try {
        saved = await this.judgmentsRepo.save(newJudgment);
        break;
      } catch (error) {
        if (!this.isDuplicateRefError(error) || attempt === 4) {
          throw error;
        }
      }
    }

    if (!saved) {
      throw new ServiceUnavailableException(
        'Impossible de generer une reference unique pour le jugement.',
      );
    }

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
