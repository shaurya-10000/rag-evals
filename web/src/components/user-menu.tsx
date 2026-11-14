'use client';

import { useEffect, useRef, useState } from 'react';
import { LogOut, User as UserIcon, Settings, Sun, Moon, Monitor, ChevronDown } from 'lucide-react';
import { useTheme } from 'next-themes';

export function UserMenu() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const { theme, setTheme } = useTheme();
  const isClient = typeof window !== 'undefined';

  useEffect(() => {
    if (!open) return;
    const onPointer = (e: PointerEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('pointerdown', onPointer);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('pointerdown', onPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const handleLogout = async () => {
    await fetch('/api/auth/logout', { method: 'POST' });
    window.location.href = '/sign-in';
  };

  if (!isClient) return <div className="w-9 h-9" />;

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(v => !v)}
        aria-label="User menu"
        className="flex items-center gap-2 p-1 pr-2 rounded-full bg-neutral-100 dark:bg-neutral-900 hover:bg-neutral-200 dark:hover:bg-neutral-800 transition-colors border border-neutral-200 dark:border-neutral-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-500"
      >
        <div className="w-7 h-7 rounded-full bg-emerald-500/20 flex items-center justify-center border border-emerald-500/30">
          <UserIcon className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
        </div>
        <ChevronDown className={`w-3.5 h-3.5 text-neutral-500 transition-transform duration-200 ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-64 bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-xl shadow-2xl overflow-hidden z-50 animate-in fade-in slide-in-from-top-2 duration-150">
          {/* User Info Header */}
          <div className="px-4 py-3 border-b border-neutral-200 dark:border-neutral-800/50 bg-neutral-50 dark:bg-neutral-950/30">
            <p className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">Account</p>
            <p className="text-xs text-neutral-500 mt-0.5 truncate">Signed in</p>
          </div>

          {/* Theme Settings */}
          <div className="p-2 border-b border-neutral-200 dark:border-neutral-800/50">
            <p className="px-2 pb-2 text-[10px] font-semibold text-neutral-500 uppercase tracking-wider">Theme</p>
            <div className="grid grid-cols-3 gap-1">
              <button
                onClick={() => setTheme('light')}
                className={`flex flex-col items-center gap-1.5 py-2 rounded-lg text-xs transition-colors
                  ${theme === 'light' ? 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400 font-medium' : 'text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800/50'}`}
              >
                <Sun className="w-3.5 h-3.5" /> Light
              </button>
              <button
                onClick={() => setTheme('dark')}
                className={`flex flex-col items-center gap-1.5 py-2 rounded-lg text-xs transition-colors
                  ${theme === 'dark' ? 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400 font-medium' : 'text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800/50'}`}
              >
                <Moon className="w-3.5 h-3.5" /> Dark
              </button>
              <button
                onClick={() => setTheme('system')}
                className={`flex flex-col items-center gap-1.5 py-2 rounded-lg text-xs transition-colors
                  ${theme === 'system' ? 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400 font-medium' : 'text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800/50'}`}
              >
                <Monitor className="w-3.5 h-3.5" /> System
              </button>
            </div>
          </div>

          {/* Menu Items */}
          <div className="p-1">
            <button className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-neutral-600 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800/50 rounded-md transition-colors text-left">
              <Settings className="w-4 h-4" /> Preferences
            </button>
            <button
              onClick={handleLogout}
              className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 rounded-md transition-colors text-left"
            >
              <LogOut className="w-4 h-4" /> Sign Out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}


