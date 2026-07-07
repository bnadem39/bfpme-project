'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Home, FileText, FolderOpen, Settings, LogOut } from 'lucide-react';

export default function Sidebar() {
  const pathname = usePathname();

  const getLinkClass = (path: string) => {
    const baseClass = "flex items-center gap-3 px-3 py-2 rounded-md transition-colors font-medium";
    const isActive = pathname === path;
    return isActive 
      ? `${baseClass} bg-primary text-white` 
      : `${baseClass} text-foreground hover:bg-gray-100`;
  };

  return (
    <div className="w-64 h-screen bg-surface border-r border-border flex flex-col fixed left-0 top-0 z-20">
      <div className="h-16 flex items-center px-6 border-b border-border">
        <h1 className="text-xl font-bold text-primary">BFPME Extractor</h1>
      </div>
      
      <nav className="flex-1 p-4 space-y-2 overflow-y-auto">
        <Link href="/" className={getLinkClass('/')}>
          <Home className="w-5 h-5" />
          <span>Tableau de bord</span>
        </Link>
        
        <Link href="/extractions" className={getLinkClass('/extractions')}>
          <FileText className="w-5 h-5" />
          <span>Extractions</span>
        </Link>

        <Link href="/dossiers" className={getLinkClass('/dossiers')}>
          <FolderOpen className="w-5 h-5" />
          <span>Dossiers</span>
        </Link>
      </nav>
      
      <div className="p-4 border-t border-border space-y-2">
        <Link href="/parametres" className={getLinkClass('/parametres')}>
          <Settings className="w-5 h-5" />
          <span>Paramètres</span>
        </Link>
        <button 
          onClick={() => alert("Simulation de déconnexion")}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-red-600 hover:bg-red-50 transition-colors cursor-pointer"
        >
          <LogOut className="w-5 h-5" />
          <span className="font-medium">Déconnexion</span>
        </button>
      </div>
    </div>
  );
}
