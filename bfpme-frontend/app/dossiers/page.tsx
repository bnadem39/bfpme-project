'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Search, Folder, Calendar, User, FileText, ArrowRight, X } from 'lucide-react';

interface Dossier {
  id: string;
  clientName: string;
  creationDate: string;
  responsible: string;
  documentCount: number;
  status: 'Actif' | 'En attente' | 'Archivé';
  description?: string;
}

const initialDossiers: Dossier[] = [
  { id: '1', clientName: 'SOCIETE TEXTILE DU NORD', creationDate: '2026-01-15', responsible: 'Amine Ben Salem', documentCount: 5, status: 'Actif', description: "Dossier de crédit d'investissement pour l'extension de l'usine textile." },
  { id: '2', clientName: 'AGRO ALIMENTAIRE PLUS', creationDate: '2026-03-22', responsible: 'Sonia Trabelsi', documentCount: 3, status: 'Actif', description: "Demande de financement de fonds de roulement pour l'achat de matières premières." },
  { id: '3', clientName: 'TECH SOLUTIONS SA', creationDate: '2026-05-10', responsible: 'Mohamed Ali', documentCount: 8, status: 'En attente', description: "Dossier d'acquisition d'équipements technologiques et serveurs." },
  { id: '4', clientName: 'COMPLEXE TOURISTIQUE MED', creationDate: '2025-11-02', responsible: 'Amine Ben Salem', documentCount: 12, status: 'Archivé', description: "Rénovation de l'infrastructure hôtelière principale." },
];

export default function DossiersPage() {
  const [dossiers] = useState<Dossier[]>(initialDossiers);
  const [search, setSearch] = useState('');
  const [selectedDossier, setSelectedDossier] = useState<Dossier | null>(null);

  const filteredDossiers = dossiers.filter(dos =>
    dos.clientName.toLowerCase().includes(search.toLowerCase()) ||
    dos.responsible.toLowerCase().includes(search.toLowerCase())
  );

  const getStatusBadge = (status: Dossier['status']) => {
    switch (status) {
      case 'Actif':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-700">Actif</span>;
      case 'En attente':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-orange-100 text-orange-700">En attente</span>;
      case 'Archivé':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-gray-100 text-gray-700">Archivé</span>;
    }
  };

  return (
    <div className="space-y-6 relative min-h-[calc(100vh-8rem)]">
      <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Gestion des Dossiers Clients</h1>
          <p className="text-gray-500 mt-1">Consultez et gérez les dossiers juridiques associés aux clients BFPME.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Rechercher par client ou responsable..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2.5 bg-surface border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all shadow-sm"
            />
          </div>

          <div className="grid grid-cols-1 gap-4">
            {filteredDossiers.length > 0 ? (
              filteredDossiers.map(dos => (
                <Card
                  key={dos.id}
                  className={`hover:border-primary transition-all cursor-pointer ${selectedDossier?.id === dos.id ? 'border-primary ring-1 ring-primary' : ''}`}
                >
                  <CardContent className="p-5 flex flex-col sm:flex-row justify-between sm:items-center gap-4" onClick={() => setSelectedDossier(dos)}>
                    <div className="flex items-start gap-4">
                      <div className="w-10 h-10 rounded-lg bg-primary/5 flex items-center justify-center text-primary mt-1">
                        <Folder className="w-5 h-5" />
                      </div>
                      <div>
                        <h3 className="font-bold text-foreground hover:text-primary transition-colors text-base">
                          {dos.clientName}
                        </h3>
                        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-xs text-gray-500">
                          <span className="flex items-center gap-1">
                            <Calendar className="w-3.5 h-3.5" />
                            Créé le {dos.creationDate}
                          </span>
                          <span className="flex items-center gap-1">
                            <User className="w-3.5 h-3.5" />
                            Géré par {dos.responsible}
                          </span>
                          <span className="flex items-center gap-1">
                            <FileText className="w-3.5 h-3.5" />
                            {dos.documentCount} document(s)
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 self-end sm:self-center">
                      {getStatusBadge(dos.status)}
                      <ArrowRight className="w-4 h-4 text-gray-400" />
                    </div>
                  </CardContent>
                </Card>
              ))
            ) : (
              <Card>
                <CardContent className="text-center py-8 text-gray-500">
                  Aucun dossier trouvé.
                </CardContent>
              </Card>
            )}
          </div>
        </div>

        <div className="lg:col-span-1">
          {selectedDossier ? (
            <Card className="sticky top-24 border-primary/20 shadow-md">
              <CardHeader className="flex justify-between items-center">
                <CardTitle className="text-base flex items-center gap-2">
                  <Folder className="w-5 h-5 text-primary" />
                  Détail du Dossier
                </CardTitle>
                <button
                  onClick={() => setSelectedDossier(null)}
                  className="p-1 text-gray-400 hover:text-gray-600 rounded transition-colors cursor-pointer"
                >
                  <X className="w-4 h-4" />
                </button>
              </CardHeader>
              <CardContent className="p-6 space-y-4">
                <div>
                  <h4 className="text-xs font-semibold text-gray-500 uppercase">Nom du client</h4>
                  <p className="text-base font-bold text-foreground mt-1">{selectedDossier.clientName}</p>
                </div>

                <div>
                  <h4 className="text-xs font-semibold text-gray-500 uppercase">Description du projet</h4>
                  <p className="text-sm text-gray-600 mt-1 leading-relaxed">
                    {selectedDossier.description || 'Aucune description disponible.'}
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-4 pt-2">
                  <div>
                    <h4 className="text-xs font-semibold text-gray-500 uppercase">Créé le</h4>
                    <p className="text-sm font-medium text-foreground mt-1">{selectedDossier.creationDate}</p>
                  </div>
                  <div>
                    <h4 className="text-xs font-semibold text-gray-500 uppercase">Statut du dossier</h4>
                    <div className="mt-1">{getStatusBadge(selectedDossier.status)}</div>
                  </div>
                </div>

                <div className="pt-2">
                  <h4 className="text-xs font-semibold text-gray-500 uppercase">Responsable juridique</h4>
                  <p className="text-sm font-medium text-foreground mt-1">{selectedDossier.responsible}</p>
                </div>

                <div className="pt-4 border-t border-border flex flex-col gap-2">
                  <button className="w-full bg-primary hover:bg-primary-hover text-white py-2 px-4 rounded-lg font-medium text-sm transition-colors cursor-pointer">
                    Voir les documents
                  </button>
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card className="h-64 flex flex-col items-center justify-center p-6 text-center border-dashed border-2">
              <Folder className="w-10 h-10 text-gray-300 mb-2" />
              <p className="text-sm font-medium text-gray-500">Sélectionnez un dossier pour afficher les informations détaillées.</p>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
