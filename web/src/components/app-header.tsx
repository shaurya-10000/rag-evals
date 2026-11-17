'use client';

import { Database, FileText, Gauge, Layers, MessageSquare, PanelLeftOpen, type LucideIcon } from 'lucide-react';
import { UserMenu } from '@/components/user-menu';

export type AppTab = 'chat' | 'ingest' | 'documents' | 'usage';

const TABS: { id: AppTab; label: string; icon: LucideIcon }[] = [
  { id: 'chat', label: 'Chat', icon: MessageSquare },
  { id: 'ingest', label: 'Knowledge Base', icon: Database },
  { id: 'documents', label: 'Documents', icon: FileText },
  { id: 'usage', label: 'Usage', icon: Gauge },
];

const TAB_BASE = 'flex items-center gap-1.5 md:gap-2 px-3 md:px-6 py-1.5 md:py-2 text-xs md:text-sm font-medium rounded-full';
const TAB_ACTIVE = `${TAB_BASE} bg-white dark:bg-neutral-800 text-neutral-900 dark:text-white shadow-sm`;
const TAB_IDLE = `${TAB_BASE} text-neutral-500 dark:text-neutral-400 hover:text-neutral-900`;

type Props = {
  activeTab: AppTab;
  onTabChange: (tab: AppTab) => void;
  sidebarOpen: boolean;
  onOpenSidebar: () => void;
};

export function AppHeader({ activeTab, onTabChange, sidebarOpen, onOpenSidebar }: Props) {
  return (
    <header className="h-16 border-b border-neutral-200 dark:border-neutral-800/50 flex items-center justify-between px-4 md:px-6 bg-background/80 backdrop-blur-xl z-20 shrink-0">
      <div className="flex items-center gap-2 md:gap-3">
        {!sidebarOpen && (
          <button
            onClick={onOpenSidebar}
            className="p-2 -ml-2 rounded-lg text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
            aria-label="Open chat history"
          >
            <PanelLeftOpen className="w-5 h-5" />
          </button>
        )}
        <div
          className="w-8 h-8 rounded-xl items-center justify-center shadow-lg hidden sm:flex"
          style={{ background: 'linear-gradient(to bottom right, var(--accent-500), var(--accent-600))' }}
        >
          <Layers className="w-4 h-4 text-white" />
        </div>
        <h1 className="text-sm md:text-base font-extrabold tracking-tight text-neutral-900 dark:text-white hidden sm:block">
          RAG Evals
        </h1>
      </div>
      <div className="flex items-center gap-2 md:gap-4">
        <nav className="flex items-center p-1 md:p-1.5 bg-neutral-100 dark:bg-neutral-900/80 backdrop-blur-md rounded-full border border-neutral-200 dark:border-neutral-800 shadow-inner">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button key={id} onClick={() => onTabChange(id)} className={activeTab === id ? TAB_ACTIVE : TAB_IDLE}>
              <Icon className="w-3.5 h-3.5 md:w-4 md:h-4" /> <span className="hidden xs:inline">{label}</span>
            </button>
          ))}
        </nav>
        <UserMenu />
      </div>
    </header>
  );
}
