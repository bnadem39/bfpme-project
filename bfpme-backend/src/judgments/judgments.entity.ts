import { Column, CreateDateColumn, Entity, PrimaryGeneratedColumn } from 'typeorm';

export type JudgmentStatus = 'Valide' | 'En cours' | 'Anomalie';

export interface JudgmentExtractionResult {
  tribunal: string | null;
  numero_dossier: string | null;
  date_decision: string | null;
  parties: {
    demandeur: string | null;
    defendeur: string | null;
  };
  banque: string | null;
  entreprise: string | null;
  montant: string | null;
  references_juridiques: string[] | null;
  decision: string | null;
  decision_justification: string | null;
  resume: string | null;
}

@Entity('judgments')
export class Judgment {
  @PrimaryGeneratedColumn()
  id: number;

  @Column({ type: 'varchar', unique: true })
  ref: string;

  @Column({ type: 'varchar' })
  client: string;

  @CreateDateColumn()
  date: Date;

  @Column({ default: 'Valide' })
  status: JudgmentStatus;

  @Column({ type: 'varchar' })
  fileName: string;

  @Column({ type: 'varchar' })
  fileSize: string;

  @Column({ type: 'longblob', select: false })
  fileData: Buffer;

  @Column({ type: 'json', nullable: true })
  extractionResult: JudgmentExtractionResult | null;

  @Column({ type: 'varchar', nullable: true })
  aiModel: string | null;

  @Column({ type: 'varchar', nullable: true })
  pdfType: string | null;

  @Column({ type: 'varchar', nullable: true })
  extractionMethod: string | null;

  @Column({ type: 'text', nullable: true })
  errorMessage: string | null;
}
