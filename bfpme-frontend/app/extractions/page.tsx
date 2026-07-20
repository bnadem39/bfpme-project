'use client';

import { Suspense, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import {
  AlertTriangle,
  CheckCircle,
  Clock,
  Eye,
  FileText,
  Loader2,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  UploadCloud,
  X,
} from 'lucide-react';
import axios from 'axios';
import { Judgment, JudgmentExtractionResult, judgementsApi } from '@/lib/api';

function ExtractionsContent() {
  const searchParams = useSearchParams();
  const [extractions, setExtractions] = useState<Judgment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<
    'All' | 'Valide' | 'En cours' | 'Anomalie'
  >('All');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [clientName, setClientName] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [selectedResult, setSelectedResult] = useState<Judgment | null>(null);
  const [retryingId, setRetryingId] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadExtractions = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await judgementsApi.getAll();
      setExtractions(data);
    } catch {
      setError(
        'Impossible de contacter le backend. Verifiez que NestJS est demarre.',
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadExtractions();
  }, []);

  useEffect(() => {
    if (searchParams.get('new') === 'true') {
      setIsModalOpen(true);
    }
  }, [searchParams]);

  const validatePdf = (file: File) => {
    if (file.type !== 'application/pdf') {
      return 'Seuls les fichiers PDF sont acceptes.';
    }
    if (file.size > 10 * 1024 * 1024) {
      return 'La taille du fichier ne doit pas depasser 10 MB.';
    }
    return null;
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const validationError = validatePdf(file);
    if (validationError) {
      setUploadError(validationError);
      setSelectedFile(null);
      return;
    }

    setUploadError(null);
    setSelectedFile(file);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (!file) return;

    const validationError = validatePdf(file);
    if (validationError) {
      setUploadError(validationError);
      return;
    }

    setUploadError(null);
    setSelectedFile(file);
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!clientName.trim()) {
      setUploadError('Le nom du client est requis.');
      return;
    }
    if (!selectedFile) {
      setUploadError('Veuillez selectionner un fichier PDF.');
      return;
    }

    setIsUploading(true);
    setUploadError(null);

    try {
      const created = await judgementsApi.upload(clientName, selectedFile);
      setExtractions((prev) => [created, ...prev]);
      setSelectedResult(created);
      setIsModalOpen(false);
      setClientName('');
      setSelectedFile(null);
      setSuccessMsg(
        created.status === 'Anomalie'
          ? `Document ${created.ref} enregistre avec une anomalie.`
          : `Extraction ${created.ref} terminee.`,
      );
      setTimeout(() => setSuccessMsg(null), 5000);
    } catch (err: unknown) {
      let msg = "Erreur lors de l'upload.";
      if (axios.isAxiosError(err)) {
        msg =
          (typeof err.response?.data?.message === 'string' &&
            err.response.data.message) ||
          err.message ||
          msg;
      } else if (err instanceof Error) {
        msg = err.message;
      }
      setUploadError(msg);
    } finally {
      setIsUploading(false);
    }
  };

  const handleCloseModal = () => {
    if (isUploading) return;
    setIsModalOpen(false);
    setClientName('');
    setSelectedFile(null);
    setUploadError(null);
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Voulez-vous vraiment supprimer ce document ?')) return;
    try {
      await judgementsApi.remove(id);
      setExtractions((prev) => prev.filter((e) => e.id !== id));
      if (selectedResult?.id === id) {
        setSelectedResult(null);
      }
    } catch {
      alert('Erreur lors de la suppression.');
    }
  };

  const replaceExtraction = (updated: Judgment) => {
    setExtractions((prev) =>
      prev.map((extraction) =>
        extraction.id === updated.id ? updated : extraction,
      ),
    );
    setSelectedResult((current) =>
      current?.id === updated.id ? updated : current,
    );
  };

  const getAxiosMessage = (err: unknown, fallback: string) => {
    if (axios.isAxiosError(err)) {
      return (
        (typeof err.response?.data?.message === 'string' &&
          err.response.data.message) ||
        err.message ||
        fallback
      );
    }
    if (err instanceof Error) {
      return err.message;
    }
    return fallback;
  };

  const handleRetryExtraction = async (judgment: Judgment) => {
    if (retryingId !== null) return;

    setRetryingId(judgment.id);
    setError(null);
    setSuccessMsg(null);

    try {
      const updated = await judgementsApi.retryExtraction(judgment.id);
      replaceExtraction(updated);

      if (updated.status === 'Valide') {
        setSuccessMsg(`Extraction ${updated.ref} relancee avec succes.`);
        setTimeout(() => setSuccessMsg(null), 5000);
      } else {
        setError(
          `Relance terminee avec anomalie pour ${updated.ref}. Consultez le detail de l'erreur.`,
        );
      }
    } catch (err: unknown) {
      setError(
        getAxiosMessage(
          err,
          "Erreur lors de la relance de l'extraction.",
        ),
      );
    } finally {
      setRetryingId(null);
    }
  };

  const handleViewFile = (id: number) => {
    window.open(judgementsApi.getFileUrl(id), '_blank');
  };

  const filteredExtractions = extractions.filter((ext) => {
    const query = search.toLowerCase();
    const matchesSearch =
      ext.client.toLowerCase().includes(query) ||
      ext.ref.toLowerCase().includes(query) ||
      ext.fileName.toLowerCase().includes(query);
    const matchesFilter = statusFilter === 'All' || ext.status === statusFilter;
    return matchesSearch && matchesFilter;
  });

  const getStatusBadge = (status: Judgment['status']) => {
    switch (status) {
      case 'Valide':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-green-100 px-2.5 py-1 text-xs font-medium text-green-700">
            <CheckCircle className="h-3 w-3" />
            Valide
          </span>
        );
      case 'En cours':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-orange-100 px-2.5 py-1 text-xs font-medium text-orange-700">
            <Clock className="h-3 w-3" />
            En cours
          </span>
        );
      case 'Anomalie':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-red-100 px-2.5 py-1 text-xs font-medium text-red-700">
            <AlertTriangle className="h-3 w-3" />
            Anomalie
          </span>
        );
    }
  };

  const renderField = (
    label: string,
    value: string | null | string[] | undefined,
  ) => {
    const content = Array.isArray(value)
      ? value.length > 0
        ? value.join(', ')
        : '-'
      : value || '-';

    return (
      <div className="space-y-1">
        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
          {label}
        </p>
        <p className="text-sm text-foreground">{content}</p>
      </div>
    );
  };

  const getDisplayExtractionResult = (
    judgment: Judgment,
  ): JudgmentExtractionResult | null => {
    if (judgment.extractionResult) {
      return judgment.extractionResult;
    }

    const hasExtractedColumns = Boolean(
      judgment.tribunal ||
        judgment.numeroDossier ||
        judgment.dateDecision ||
        judgment.demandeur ||
        judgment.defendeur ||
        judgment.montant ||
        judgment.explicationMontant ||
        judgment.referencesJuridiques ||
        judgment.decision ||
        judgment.decisionJustification ||
        judgment.resume,
    );

    if (!hasExtractedColumns) {
      return null;
    }

    return {
      tribunal: judgment.tribunal,
      numero_dossier: judgment.numeroDossier,
      date_decision: judgment.dateDecision,
      parties: {
        demandeur: judgment.demandeur,
        defendeur: judgment.defendeur,
      },
      montant: judgment.montant,
      explication_montant: judgment.explicationMontant,
      montant_justification: judgment.explicationMontant,
      references_juridiques: judgment.referencesJuridiques,
      decision: judgment.decision,
      decision_justification: judgment.decisionJustification,
      resume: judgment.resume,
    };
  };

  const renderExtractionResult = (result: JudgmentExtractionResult | null) => {
    if (!result) {
      return (
        <p className="text-sm text-gray-500">
          Aucun resultat d&apos;extraction disponible.
        </p>
      );
    }

    return (
      <div className="grid gap-4 md:grid-cols-2">
        {renderField('Tribunal', result.tribunal)}
        {renderField('Numero dossier', result.numero_dossier)}
        {renderField('Date decision', result.date_decision)}
        {renderField('Montant', result.montant)}
        {renderField('Demandeur', result.parties.demandeur)}
        {renderField('Defendeur', result.parties.defendeur)}
        {renderField('Decision', result.decision)}
        <div className="space-y-1 md:col-span-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            Explication du montant
          </p>
          <p className="text-sm text-foreground">
            {result.explication_montant || result.montant_justification || '-'}
          </p>
        </div>
        <div className="space-y-1 md:col-span-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            References juridiques
          </p>
          {Array.isArray(result.references_juridiques) &&
          result.references_juridiques.length > 0 ? (
            <ul className="space-y-2 text-sm text-foreground">
              {result.references_juridiques.map((reference) => (
                <li
                  key={reference}
                  className="rounded-lg border border-border bg-gray-50 px-3 py-2"
                >
                  {reference}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-foreground">-</p>
          )}
        </div>
        <div className="space-y-1 md:col-span-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            Justification
          </p>
          <p className="text-sm text-foreground">
            {result.decision_justification || '-'}
          </p>
        </div>
        <div className="space-y-1 md:col-span-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            Resume
          </p>
          <p className="text-sm text-foreground">{result.resume || '-'}</p>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">
            Extractions Juridiques
          </h1>
          <p className="mt-1 text-gray-500">
            Importez un jugement PDF et consultez le JSON extrait.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={loadExtractions}
            title="Actualiser"
            className="cursor-pointer rounded-lg p-2 text-gray-500 transition-colors hover:bg-gray-100 hover:text-primary"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          <button
            onClick={() => setIsModalOpen(true)}
            className="flex cursor-pointer items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 font-medium text-white transition-colors hover:bg-primary-hover"
          >
            <Plus className="h-4 w-4" />
            Nouvelle Extraction
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <AlertTriangle className="h-4 w-4 flex-shrink-0" />
          <span>{error}</span>
          <button
            onClick={loadExtractions}
            className="ml-auto cursor-pointer font-medium underline hover:no-underline"
          >
            Reessayer
          </button>
        </div>
      )}

      {successMsg && (
        <div className="flex items-center gap-3 rounded-lg border border-green-200 bg-green-50 p-4 text-sm text-green-700">
          <CheckCircle className="h-4 w-4 flex-shrink-0" />
          <span>{successMsg}</span>
          <button
            onClick={() => setSuccessMsg(null)}
            className="ml-auto cursor-pointer text-green-500 hover:text-green-700"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader className="flex-col items-stretch gap-4 sm:flex-row sm:items-center">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                placeholder="Rechercher par reference, client, fichier..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full rounded-lg border border-border bg-gray-50 py-2 pl-9 pr-4 text-sm transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <div className="flex gap-2">
              {(['All', 'Valide', 'En cours', 'Anomalie'] as const).map(
                (filter) => (
                  <button
                    key={filter}
                    onClick={() => setStatusFilter(filter)}
                    className={`cursor-pointer rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                      statusFilter === filter
                        ? 'bg-primary text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {filter === 'All' ? 'Tous' : filter}
                  </button>
                ),
              )}
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-border bg-gray-50 text-xs uppercase text-gray-500">
                  <tr>
                    <th className="px-6 py-3">Ref.</th>
                    <th className="px-6 py-3">Client</th>
                    <th className="px-6 py-3">Date</th>
                    <th className="px-6 py-3">Fichier</th>
                    <th className="px-6 py-3">Statut</th>
                    <th className="px-6 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr>
                      <td colSpan={6} className="py-12 text-center">
                        <Loader2 className="mx-auto mb-2 h-6 w-6 animate-spin text-primary" />
                        <span className="text-sm text-gray-500">
                          Chargement...
                        </span>
                      </td>
                    </tr>
                  ) : filteredExtractions.length > 0 ? (
                    filteredExtractions.map((ext) => (
                      <tr
                        key={ext.id}
                        className={`border-b border-border transition-colors hover:bg-gray-50/50 ${
                          selectedResult?.id === ext.id ? 'bg-blue-50/60' : ''
                        }`}
                      >
                        <td className="px-6 py-4 font-medium text-foreground">
                          {ext.ref}
                        </td>
                        <td className="px-6 py-4">{ext.client}</td>
                        <td className="px-6 py-4">
                          {new Date(ext.date).toLocaleDateString('fr-FR')}
                        </td>
                        <td
                          className="max-w-[180px] truncate px-6 py-4 text-gray-500"
                          title={ext.fileName}
                        >
                          {ext.fileName}
                        </td>
                        <td className="px-6 py-4">
                          {getStatusBadge(
                            retryingId === ext.id ? 'En cours' : ext.status,
                          )}
                        </td>
                        <td className="flex items-center justify-end gap-1 px-6 py-4 text-right">
                          <button
                            onClick={() => setSelectedResult(ext)}
                            title="Voir le JSON"
                            className="cursor-pointer rounded p-1.5 text-gray-500 transition-colors hover:bg-blue-50 hover:text-primary"
                          >
                            <FileText className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => handleViewFile(ext.id)}
                            title="Voir le PDF"
                            className="cursor-pointer rounded p-1.5 text-gray-500 transition-colors hover:bg-blue-50 hover:text-primary"
                          >
                            <Eye className="h-4 w-4" />
                          </button>
                          {ext.status === 'Anomalie' && (
                            <button
                              onClick={() => handleRetryExtraction(ext)}
                              disabled={retryingId !== null}
                              title="Relancer l'extraction"
                              className="inline-flex cursor-pointer items-center gap-1 rounded px-2 py-1.5 text-xs font-medium text-orange-600 transition-colors hover:bg-orange-50 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              {retryingId === ext.id ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <RefreshCw className="h-4 w-4" />
                              )}
                              Relancer
                            </button>
                          )}
                          <button
                            onClick={() => handleDelete(ext.id)}
                            title="Supprimer"
                            className="cursor-pointer rounded p-1.5 text-gray-500 transition-colors hover:bg-red-50 hover:text-red-600"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={6} className="py-12 text-center text-gray-500">
                        Aucune extraction trouvee.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-bold text-foreground">
                  Resultat extrait
                </h2>
                <p className="text-sm text-gray-500">
                  {selectedResult
                    ? `${selectedResult.ref} • ${selectedResult.fileName}`
                    : 'Selectionnez une extraction'}
                </p>
              </div>
              {selectedResult &&
                getStatusBadge(
                  retryingId === selectedResult.id
                    ? 'En cours'
                    : selectedResult.status,
                )}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {selectedResult ? (
              <>
                <div className="grid gap-3 sm:grid-cols-2">
                  {renderField('Client', selectedResult.client)}
                  {renderField('Modele', selectedResult.aiModel)}
                  {renderField('Type PDF', selectedResult.pdfType)}
                  {renderField('Methode', selectedResult.extractionMethod)}
                </div>
                {selectedResult.errorMessage && (
                  <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-700">
                    <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" />
                    <span>{selectedResult.errorMessage}</span>
                  </div>
                )}
                {renderExtractionResult(
                  getDisplayExtractionResult(selectedResult),
                )}
              </>
            ) : (
              <p className="text-sm text-gray-500">
                Aucun document selectionne.
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-lg overflow-hidden rounded-xl border border-border bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-border px-6 py-4">
              <div className="flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10">
                  <FileText className="h-4 w-4 text-primary" />
                </div>
                <h2 className="text-lg font-bold text-foreground">
                  Importer un jugement PDF
                </h2>
              </div>
              <button
                onClick={handleCloseModal}
                disabled={isUploading}
                className="cursor-pointer text-gray-400 transition-colors hover:text-gray-600 disabled:opacity-50"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleUpload} className="space-y-5 p-6">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                  Nom du client
                </label>
                <input
                  type="text"
                  placeholder="Ex: SOCIETE EXEMPLE SA"
                  value={clientName}
                  onChange={(e) => setClientName(e.target.value)}
                  required
                  disabled={isUploading}
                  className="w-full rounded-lg border border-border px-3 py-2.5 text-sm transition-all focus:outline-none focus:ring-2 focus:ring-primary disabled:bg-gray-50 disabled:text-gray-400"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                  Fichier PDF
                </label>
                <div
                  onClick={() => !isUploading && fileInputRef.current?.click()}
                  onDrop={handleDrop}
                  onDragOver={(e) => e.preventDefault()}
                  className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-all ${
                    selectedFile
                      ? 'border-primary bg-blue-50/40'
                      : 'border-border hover:border-primary hover:bg-blue-50/20'
                  } ${isUploading ? 'pointer-events-none opacity-60' : ''}`}
                >
                  {selectedFile ? (
                    <>
                      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
                        <FileText className="h-5 w-5 text-primary" />
                      </div>
                      <p className="text-sm font-semibold text-foreground">
                        {selectedFile.name}
                      </p>
                      <p className="mt-1 text-xs text-gray-400">
                        {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                      </p>
                    </>
                  ) : (
                    <>
                      <UploadCloud className="mb-3 h-10 w-10 text-gray-300" />
                      <p className="text-sm font-medium text-foreground">
                        Glissez un fichier ici ou cliquez
                      </p>
                      <p className="mt-1 text-xs text-gray-400">
                        PDF uniquement, 10 MB maximum
                      </p>
                    </>
                  )}
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="application/pdf"
                  onChange={handleFileChange}
                  className="hidden"
                />
              </div>

              {uploadError && (
                <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-600">
                  <AlertTriangle className="h-4 w-4 flex-shrink-0" />
                  {uploadError}
                </div>
              )}

              {isUploading && (
                <div className="flex flex-col items-center gap-3 py-2">
                  <div className="flex items-center gap-2 text-sm font-medium text-primary">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Analyse et extraction en cours...
                  </div>
                  <div className="h-1.5 w-full rounded-full bg-gray-100">
                    <div className="h-1.5 w-3/4 animate-pulse rounded-full bg-primary" />
                  </div>
                </div>
              )}

              <div className="flex justify-end gap-3 border-t border-border pt-2">
                <button
                  type="button"
                  onClick={handleCloseModal}
                  disabled={isUploading}
                  className="cursor-pointer rounded-lg border border-border px-4 py-2 text-sm font-medium transition-colors hover:bg-gray-50 disabled:opacity-50"
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  disabled={isUploading || !selectedFile || !clientName.trim()}
                  className="flex cursor-pointer items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isUploading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <UploadCloud className="h-4 w-4" />
                  )}
                  {isUploading ? 'Traitement...' : 'Lancer extraction'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ExtractionsPage() {
  return (
    <Suspense fallback={<div className="text-sm text-gray-500">Chargement...</div>}>
      <ExtractionsContent />
    </Suspense>
  );
}
