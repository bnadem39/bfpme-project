'use client';

import { useState } from 'react';
import { usePathname } from 'next/navigation';
import { Bell, Search, User, LogOut, Settings } from 'lucide-react';
import Link from 'next/link';

export default function Header() {
  const pathname = usePathname();
  const [showNotifications, setShowNotifications] = useState(false);
  const [showProfileMenu, setShowProfileMenu] = useState(false);

  // Dynamic breadcrumbs mapping
  const getBreadcrumbs = () => {
    switch (pathname) {
      case '/':
        return <span className="text-foreground font-medium">Tableau de bord</span>;
      case '/extractions':
        return (
          <>
            <Link href="/" className="hover:text-primary transition-colors">Accueil</Link>
            <span>/</span>
            <span className="text-foreground font-medium">Extractions</span>
          </>
        );
      case '/dossiers':
        return (
          <>
            <Link href="/" className="hover:text-primary transition-colors">Accueil</Link>
            <span>/</span>
            <span className="text-foreground font-medium">Dossiers</span>
          </>
        );
      case '/parametres':
        return (
          <>
            <Link href="/" className="hover:text-primary transition-colors">Accueil</Link>
            <span>/</span>
            <span className="text-foreground font-medium">Paramètres</span>
          </>
        );
      default:
        return <span className="text-foreground font-medium">Accueil</span>;
    }
  };

  return (
    <header className="h-16 bg-surface border-b border-border flex items-center justify-between px-6 sticky top-0 z-10 w-full">
      <div className="flex items-center gap-2 text-sm text-gray-500">
        {getBreadcrumbs()}
      </div>
      
      <div className="flex items-center gap-6">
        <div className="relative">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input 
            type="text" 
            placeholder="Rechercher un dossier..." 
            className="pl-9 pr-4 py-2 bg-gray-50 border border-border rounded-full text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent w-64 transition-all"
          />
        </div>
        
        {/* Notifications Dropdown */}
        <div className="relative">
          <button 
            onClick={() => {
              setShowNotifications(!showNotifications);
              setShowProfileMenu(false);
            }}
            className="relative p-2 text-gray-500 hover:text-primary transition-colors cursor-pointer"
          >
            <Bell className="w-5 h-5" />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full border-2 border-white"></span>
          </button>

          {showNotifications && (
            <div className="absolute right-0 mt-2 w-80 bg-white border border-border rounded-xl shadow-lg py-2 z-50">
              <div className="px-4 py-2 border-b border-border font-semibold text-sm text-foreground">
                Notifications
              </div>
              <div className="max-h-60 overflow-y-auto">
                <div className="px-4 py-3 hover:bg-gray-50 border-b border-border/50 transition-colors">
                  <p className="text-xs font-semibold text-primary">Extraction réussie</p>
                  <p className="text-xs text-foreground mt-0.5">SOCIETE TEXTILE DU NORD a été traité.</p>
                  <p className="text-[10px] text-gray-400 mt-1">Il y a 5 min</p>
                </div>
                <div className="px-4 py-3 hover:bg-gray-50 transition-colors">
                  <p className="text-xs font-semibold text-red-600">Anomalie détectée</p>
                  <p className="text-xs text-foreground mt-0.5">TECH SOLUTIONS SA nécessite une révision.</p>
                  <p className="text-[10px] text-gray-400 mt-1">Il y a 1 heure</p>
                </div>
              </div>
            </div>
          )}
        </div>
        
        {/* Profile Dropdown */}
        <div className="relative">
          <div 
            onClick={() => {
              setShowProfileMenu(!showProfileMenu);
              setShowNotifications(false);
            }}
            className="flex items-center gap-3 border-l border-border pl-6 cursor-pointer select-none"
          >
            <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-primary">
              <User className="w-4 h-4" />
            </div>
            <div className="hidden md:block text-sm">
              <p className="font-medium text-foreground">Agent BFPME</p>
              <p className="text-xs text-gray-500">Service Juridique</p>
            </div>
          </div>

          {showProfileMenu && (
            <div className="absolute right-0 mt-2 w-48 bg-white border border-border rounded-xl shadow-lg py-2 z-50">
              <Link 
                href="/parametres" 
                onClick={() => setShowProfileMenu(false)}
                className="flex items-center gap-2 px-4 py-2 text-sm text-foreground hover:bg-gray-50 transition-colors"
              >
                <Settings className="w-4 h-4 text-gray-500" />
                Paramètres
              </Link>
              <button 
                onClick={() => {
                  setShowProfileMenu(false);
                  alert("Déconnexion simulée");
                }}
                className="w-full flex items-center gap-2 px-4 py-2 text-sm text-red-600 hover:bg-red-50 text-left transition-colors cursor-pointer"
              >
                <LogOut className="w-4 h-4" />
                Déconnexion
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
