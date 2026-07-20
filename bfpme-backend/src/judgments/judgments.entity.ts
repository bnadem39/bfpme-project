import { Column, CreateDateColumn, Entity, PrimaryGeneratedColumn } from 'typeorm';

export type JudgmentStatus = 'Valide' | 'En cours' | 'Anomalie';

export interface JudgmentFixedAmount {
  libelle_original: string | null;
  valeur_originale: string | null;
  valeur_millimes: number | null;
  accorde_bfpme: boolean | null;
  fixe: boolean | null;
  include_dans_total: boolean | null;
  raison_inclusion_exclusion: string | null;
}

export interface JudgmentVariableAmount {
  libelle_original: string | null;
  formule_originale: string | null;
  raison_non_calculable: string | null;
}

export interface JudgmentExtractionResult {
  tribunal: string | null;
  numero_dossier: string | null;
  date_decision: string | null;
  type_jugement?: string | null;
  role_bfpme?: string | null;
  parties: {
    demandeur: string | null;
    defendeur: string | null;
  };
  montants_fixes?: JudgmentFixedAmount[] | null;
  montants_variables?: JudgmentVariableAmount[] | null;
  montant: string | null;
  explication_montant: string | null;
  montant_justification: string | null;
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
  tribunal: string | null;

  @Column({ type: 'varchar', nullable: true })
  numeroDossier: string | null;

  @Column({ type: 'varchar', nullable: true })
  dateDecision: string | null;

  @Column({ type: 'text', nullable: true })
  demandeur: string | null;

  @Column({ type: 'text', nullable: true })
  defendeur: string | null;

  @Column({ type: 'varchar', nullable: true })
  montant: string | null;

  @Column({ type: 'text', nullable: true })
  explicationMontant: string | null;

  @Column({ type: 'json', nullable: true })
  referencesJuridiques: string[] | null;

  @Column({ type: 'varchar', nullable: true })
  decision: string | null;

  @Column({ type: 'text', nullable: true })
  decisionJustification: string | null;

  @Column({ type: 'text', nullable: true })
  resume: string | null;

  @Column({ type: 'varchar', nullable: true })
  aiModel: string | null;

  @Column({ type: 'varchar', nullable: true })
  pdfType: string | null;

  @Column({ type: 'varchar', nullable: true })
  extractionMethod: string | null;

  @Column({ type: 'text', nullable: true })
  errorMessage: string | null;
}
