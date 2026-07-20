import axios from 'axios';

function getApiBaseUrl() {
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL;
  }

  if (typeof window !== 'undefined') {
    const protocol = window.location.protocol;
    const hostname = window.location.hostname;
    return `${protocol}//${hostname}:3001`;
  }

  return 'http://127.0.0.1:3001';
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
  montants_fixes?: Array<{
    libelle_original: string | null;
    valeur_originale: string | null;
    valeur_millimes: number | null;
    accorde_bfpme: boolean | null;
    fixe: boolean | null;
    include_dans_total: boolean | null;
    raison_inclusion_exclusion: string | null;
  }> | null;
  montants_variables?: Array<{
    libelle_original: string | null;
    formule_originale: string | null;
    raison_non_calculable: string | null;
  }> | null;
  montant: string | null;
  explication_montant: string | null;
  montant_justification: string | null;
  references_juridiques: string[] | null;
  decision: string | null;
  decision_justification: string | null;
  resume: string | null;
}

export interface Judgment {
  id: number;
  ref: string;
  client: string;
  date: string;
  status: 'Valide' | 'En cours' | 'Anomalie';
  fileName: string;
  fileSize: string;
  extractionResult: JudgmentExtractionResult | null;
  tribunal: string | null;
  numeroDossier: string | null;
  dateDecision: string | null;
  demandeur: string | null;
  defendeur: string | null;
  montant: string | null;
  explicationMontant: string | null;
  referencesJuridiques: string[] | null;
  decision: string | null;
  decisionJustification: string | null;
  resume: string | null;
  aiModel: string | null;
  pdfType: string | null;
  extractionMethod: string | null;
  errorMessage: string | null;
}

export interface Stats {
  total: number;
  valide: number;
  enCours: number;
  anomalie: number;
}

function createApiClient() {
  return axios.create({
    baseURL: getApiBaseUrl(),
    timeout: 610000,
  });
}

export const judgementsApi = {
  getAll: () =>
    createApiClient()
      .get<Judgment[]>('/judgments')
      .then((r) => r.data),

  getStats: () =>
    createApiClient()
      .get<Stats>('/judgments/stats')
      .then((r) => r.data),

  upload: (client: string, file: File) => {
    const formData = new FormData();
    formData.append('client', client);
    formData.append('file', file);

    return createApiClient()
      .post<Judgment>('/judgments/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data);
  },

  retryExtraction: (id: number) =>
    createApiClient()
      .post<Judgment>(`/judgments/${id}/retry-extraction`)
      .then((r) => r.data),

  getFileUrl: (id: number) => `${getApiBaseUrl()}/judgments/${id}/file`,

  remove: (id: number) => createApiClient().delete(`/judgments/${id}`),
};
