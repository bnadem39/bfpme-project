import axios from 'axios';

export const API_BASE_URL = 'http://localhost:3000';

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 190000,
});

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

export interface Judgment {
  id: number;
  ref: string;
  client: string;
  date: string;
  status: 'Valide' | 'En cours' | 'Anomalie';
  fileName: string;
  fileSize: string;
  extractionResult: JudgmentExtractionResult | null;
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

export const judgementsApi = {
  getAll: () => api.get<Judgment[]>('/judgments').then((r) => r.data),

  getStats: () => api.get<Stats>('/judgments/stats').then((r) => r.data),

  upload: (client: string, file: File) => {
    const formData = new FormData();
    formData.append('client', client);
    formData.append('file', file);
    return api
      .post<Judgment>('/judgments/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data);
  },

  getFileUrl: (id: number) => `${API_BASE_URL}/judgments/${id}/file`,

  remove: (id: number) => api.delete(`/judgments/${id}`),
};
