'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Save, User, Bell, Shield, CheckCircle } from 'lucide-react';

export default function ParametresPage() {
  const [name, setName] = useState('Agent BFPME');
  const [email, setEmail] = useState('agent.juridique@bfpme.com.tn');
  const [service, setService] = useState('Service Juridique');
  
  const [emailNotif, setEmailNotif] = useState(true);
  const [smsNotif, setSmsNotif] = useState(false);
  
  const [showToast, setShowToast] = useState(false);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setShowToast(true);
    setTimeout(() => {
      setShowToast(false);
    }, 3000);
  };

  return (
    <div className="space-y-6 max-w-4xl relative">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Paramètres de l'Application</h1>
        <p className="text-gray-500 mt-1">Configurez votre profil d'utilisateur et vos préférences d'alerte.</p>
      </div>

      {showToast && (
        <div className="fixed bottom-6 right-6 bg-green-600 text-white px-4 py-3 rounded-lg shadow-xl flex items-center gap-2 z-50 animate-bounce">
          <CheckCircle className="w-5 h-5" />
          <span className="text-sm font-semibold">Paramètres enregistrés avec succès !</span>
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-6">
        {/* Profile Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <User className="w-5 h-5 text-primary" />
              Informations Personnelles
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-gray-500 uppercase">Nom complet</label>
                <input 
                  type="text" 
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full px-3 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                  required
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-gray-500 uppercase">Adresse Email</label>
                <input 
                  type="email" 
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-3 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                  required
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-gray-500 uppercase">Département / Service</label>
                <input 
                  type="text" 
                  value={service}
                  onChange={(e) => setService(e.target.value)}
                  className="w-full px-3 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                  required
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-gray-500 uppercase">Poste</label>
                <input 
                  type="text" 
                  value="Analyste Juridique"
                  disabled
                  className="w-full px-3 py-2 bg-gray-50 border border-border rounded-lg text-sm text-gray-500"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Notifications Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Bell className="w-5 h-5 text-primary" />
              Préférences de Notification
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between py-2">
              <div>
                <p className="text-sm font-semibold text-foreground">Alertes par email</p>
                <p className="text-xs text-gray-500 mt-0.5">Recevoir un rapport par email après chaque extraction de contrat.</p>
              </div>
              <input 
                type="checkbox" 
                checked={emailNotif}
                onChange={() => setEmailNotif(!emailNotif)}
                className="w-4 h-4 text-primary border-gray-300 rounded focus:ring-primary"
              />
            </div>
            
            <div className="flex items-center justify-between py-2 border-t border-border/50">
              <div>
                <p className="text-sm font-semibold text-foreground">Notifications SMS</p>
                <p className="text-xs text-gray-500 mt-0.5">Recevoir une alerte instantanée sur mobile en cas d'anomalie détectée.</p>
              </div>
              <input 
                type="checkbox" 
                checked={smsNotif}
                onChange={() => setSmsNotif(!smsNotif)}
                className="w-4 h-4 text-primary border-gray-300 rounded focus:ring-primary"
              />
            </div>
          </CardContent>
        </Card>

        {/* Security Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Shield className="w-5 h-5 text-primary" />
              Sécurité & Authentification
            </CardTitle>
          </CardHeader>
          <CardContent>
            <button 
              type="button" 
              onClick={() => alert("Demande de changement de mot de passe envoyée")}
              className="px-4 py-2 border border-border hover:bg-gray-50 text-foreground font-medium text-sm rounded-lg transition-colors cursor-pointer"
            >
              Changer mon mot de passe
            </button>
          </CardContent>
        </Card>

        <div className="flex justify-end pt-2">
          <button 
            type="submit" 
            className="flex items-center justify-center gap-2 bg-primary hover:bg-primary-hover text-white px-5 py-2.5 rounded-lg font-medium transition-colors cursor-pointer"
          >
            <Save className="w-4 h-4" />
            Enregistrer les modifications
          </button>
        </div>
      </form>
    </div>
  );
}
