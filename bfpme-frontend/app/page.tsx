'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle,
  Clock,
  FileText,
  FolderOpen,
  Loader2,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Judgment, Stats, judgementsApi } from '@/lib/api';

export default function Home() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [recents, setRecents] = useState<Judgment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [statsData, allData] = await Promise.all([
          judgementsApi.getStats(),
          judgementsApi.getAll(),
        ]);
        setStats(statsData);
        setRecents(allData.slice(0, 5));
      } finally {
        setLoading(false);
      }
    };

    load();
  }, []);

  const getStatusBadge = (status: Judgment['status']) => {
    switch (status) {
      case 'Valide':
        return (
          <span className="rounded-full bg-green-100 px-2.5 py-1 text-xs font-medium text-green-700">
            Valide
          </span>
        );
      case 'En cours':
        return (
          <span className="rounded-full bg-orange-100 px-2.5 py-1 text-xs font-medium text-orange-700">
            En cours
          </span>
        );
      case 'Anomalie':
        return (
          <span className="rounded-full bg-red-100 px-2.5 py-1 text-xs font-medium text-red-700">
            Anomalie
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Apercu de l&apos;activite</h1>
        <p className="mt-1 text-gray-500">
          Suivi des extractions de jugements juridiques.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="flex items-center p-6">
            <div className="mr-4 flex h-12 w-12 items-center justify-center rounded-full bg-blue-100 text-blue-600">
              <FileText className="h-6 w-6" />
            </div>
            <div>
              <p className="text-sm font-medium text-gray-500">Dossiers extraits</p>
              {loading ? (
                <Loader2 className="mt-1 h-5 w-5 animate-spin text-gray-400" />
              ) : (
                <h4 className="text-2xl font-bold text-foreground">
                  {stats?.total ?? 0}
                </h4>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex items-center p-6">
            <div className="mr-4 flex h-12 w-12 items-center justify-center rounded-full bg-orange-100 text-orange-600">
              <Clock className="h-6 w-6" />
            </div>
            <div>
              <p className="text-sm font-medium text-gray-500">En cours</p>
              {loading ? (
                <Loader2 className="mt-1 h-5 w-5 animate-spin text-gray-400" />
              ) : (
                <h4 className="text-2xl font-bold text-foreground">
                  {stats?.enCours ?? 0}
                </h4>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex items-center p-6">
            <div className="mr-4 flex h-12 w-12 items-center justify-center rounded-full bg-green-100 text-green-600">
              <CheckCircle className="h-6 w-6" />
            </div>
            <div>
              <p className="text-sm font-medium text-gray-500">Valides</p>
              {loading ? (
                <Loader2 className="mt-1 h-5 w-5 animate-spin text-gray-400" />
              ) : (
                <h4 className="text-2xl font-bold text-foreground">
                  {stats?.valide ?? 0}
                </h4>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex items-center p-6">
            <div className="mr-4 flex h-12 w-12 items-center justify-center rounded-full bg-red-100 text-red-600">
              <AlertTriangle className="h-6 w-6" />
            </div>
            <div>
              <p className="text-sm font-medium text-gray-500">Anomalies</p>
              {loading ? (
                <Loader2 className="mt-1 h-5 w-5 animate-spin text-gray-400" />
              ) : (
                <h4 className="text-2xl font-bold text-foreground">
                  {stats?.anomalie ?? 0}
                </h4>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Extractions recentes</CardTitle>
            <Link
              href="/extractions"
              className="flex items-center gap-1 text-sm text-primary hover:underline"
            >
              Voir tout <ArrowRight className="h-4 w-4" />
            </Link>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-border bg-gray-50 text-xs uppercase text-gray-500">
                  <tr>
                    <th className="px-6 py-3">Ref.</th>
                    <th className="px-6 py-3">Client</th>
                    <th className="px-6 py-3">Date</th>
                    <th className="px-6 py-3">Statut</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr>
                      <td colSpan={4} className="py-10 text-center">
                        <Loader2 className="mx-auto h-5 w-5 animate-spin text-primary" />
                      </td>
                    </tr>
                  ) : recents.length > 0 ? (
                    recents.map((ext) => (
                      <tr
                        key={ext.id}
                        className="border-b border-border transition-colors hover:bg-gray-50/50"
                      >
                        <td className="px-6 py-4 font-medium text-foreground">
                          {ext.ref}
                        </td>
                        <td className="px-6 py-4">{ext.client}</td>
                        <td className="px-6 py-4">
                          {new Date(ext.date).toLocaleDateString('fr-FR')}
                        </td>
                        <td className="px-6 py-4">{getStatusBadge(ext.status)}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={4} className="py-10 text-center text-sm text-gray-400">
                        Aucune extraction enregistree.
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
            <CardTitle>Actions rapides</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <Link
              href="/extractions?new=true"
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-center text-sm font-medium text-white transition-colors hover:bg-primary-hover"
            >
              <FileText className="h-4 w-4" />
              Nouvelle Extraction
            </Link>
            <Link
              href="/dossiers"
              className="flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-white px-4 py-2.5 text-center text-sm font-medium text-foreground transition-colors hover:bg-gray-50"
            >
              <FolderOpen className="h-4 w-4" />
              Consulter un Dossier
            </Link>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
