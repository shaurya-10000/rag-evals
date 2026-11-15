'use client';

import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { LogOut, User as UserIcon, Sun, Moon, Monitor, ChevronDown, Volume2 } from 'lucide-react';
import { useTheme } from 'next-themes';

// Helper to safely read localStorage without triggering hydration errors
const subscribe = () => () => {};
const getSnapshot = (key: string, fallback: string) => {
  if (typeof window === 'undefined') return fallback;
  return localStorage.getItem(key) || fallback;
};

export function UserMenu() {
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const { theme, setTheme } = useTheme();

  // Use useSyncExternalStore to safely read from localStorage without cascading renders
  const accent = useSyncExternalStore(
    subscribe,
    () => getSnapshot('rag-evals-accent', 'emerald'),
    () => 'emerald'
  );
  
  const savedVoice = useSyncExternalStore(
    subscribe,
    () => getSnapshot('rag-evals-voice', ''),
    () => ''
  );

  const [voices, setVoices] = useState<{name: string, label: string}[]>([]);

  // Use a ref to prevent the "setState in effect" warning
  const isMountedRef = useRef(false);

  useEffect(() => {
    // Apply accent on load
    document.documentElement.setAttribute('data-theme', accent);
    if (!isMountedRef.current) {
      isMountedRef.current = true;
      setMounted(true);
    }
  }, [accent]);

  useEffect(() => {
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      const loadVoices = () => {
        const allVoices = window.speechSynthesis.getVoices();
        const englishVoices = allVoices.filter(v => v.lang.startsWith('en'));
        
        const usFemale = englishVoices.find(v => v.name.includes('Zira') || (v.name.includes('Female') && v.lang.includes('US')));
        const usMale = englishVoices.find(v => v.name.includes('David') || (v.name.includes('Male') && v.lang.includes('US')));
        const ukFemale = englishVoices.find(v => v.name.includes('Hazel') || v.name.includes('Sonia') || (v.name.includes('Female') && v.lang.includes('GB')));
        const ukMale = englishVoices.find(v => v.name.includes('George') || (v.name.includes('Male') && v.lang.includes('GB')));

        const voiceMap = [
          { voice: usFemale, label: "American English (Female)" },
          { voice: usMale, label: "American English (Male)" },
          { voice: ukFemale, label: "British English (Female)" },
          { voice: ukMale, label: "British English (Male)" }
        ];

        const uniqueVoices = voiceMap
          .filter(item => item.voice !== undefined)
          .filter((item, index, self) => 
            index === self.findIndex((t) => t.voice?.name === item.voice?.name)
          )
          .map(item => ({ name: item.voice!.name, label: item.label }));

        setVoices(uniqueVoices);
      };
      window.speechSynthesis.onvoiceschanged = loadVoices;
      loadVoices();
    }
  }, []);

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

  const handleAccentChange = (color: string) => {
    localStorage.setItem('rag-evals-accent', color);
    document.documentElement.setAttribute('data-theme', color);
    window.dispatchEvent(new Event('storage')); // Force re-render
  };

  const handleVoiceChange = (voiceName: string) => {
    localStorage.setItem('rag-evals-voice', voiceName);
    window.dispatchEvent(new Event('storage')); // Force re-render
  };

  if (!mounted) {
    return (
      <div className="w-9 h-9 rounded-full bg-neutral-100 dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800" />
    );
  }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(v => !v)}
        aria-label="User menu"
        className="flex items-center gap-2 p-1 pr-2 rounded-full bg-neutral-100 dark:bg-neutral-900 hover:bg-neutral-200 dark:hover:bg-neutral-800 transition-colors border border-neutral-200 dark:border-neutral-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500"
      >
        <div className="w-7 h-7 rounded-full bg-accent-500/20 flex items-center justify-center border border-accent-500/30">
          <UserIcon className="w-3.5 h-3.5 text-accent-600" />
        </div>
        <ChevronDown className={`w-3.5 h-3.5 text-neutral-500 transition-transform duration-200 ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-72 bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-xl shadow-2xl overflow-hidden z-50 animate-in fade-in slide-in-from-top-2 duration-150">
          
          {/* User Info Header */}
          <div className="px-4 py-3 border-b border-neutral-200 dark:border-neutral-800/50 bg-neutral-50 dark:bg-neutral-950/30">
            <p className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">Account Settings</p>
          </div>

          {/* Theme Settings */}
          <div className="p-3 border-b border-neutral-200 dark:border-neutral-800/50">
            <p className="px-1 pb-2 text-[10px] font-semibold text-neutral-500 uppercase tracking-wider">Appearance</p>
            <div className="grid grid-cols-3 gap-1">
              <button onClick={() => setTheme('light')} className={`flex flex-col items-center gap-1.5 py-2 rounded-lg text-xs transition-colors ${theme === 'light' ? 'bg-accent-50 text-accent-600 font-medium' : 'text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800/50'}`}>
                <Sun className="w-3.5 h-3.5" /> Light
              </button>
              <button onClick={() => setTheme('dark')} className={`flex flex-col items-center gap-1.5 py-2 rounded-lg text-xs transition-colors ${theme === 'dark' ? 'bg-accent-50 text-accent-600 font-medium' : 'text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800/50'}`}>
                <Moon className="w-3.5 h-3.5" /> Dark
              </button>
              <button onClick={() => setTheme('system')} className={`flex flex-col items-center gap-1.5 py-2 rounded-lg text-xs transition-colors ${theme === 'system' ? 'bg-accent-50 text-accent-600 font-medium' : 'text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800/50'}`}>
                <Monitor className="w-3.5 h-3.5" /> System
              </button>
            </div>
          </div>

          {/* Color Palettes */}
          <div className="p-3 border-b border-neutral-200 dark:border-neutral-800/50">
            <p className="px-1 pb-2 text-[10px] font-semibold text-neutral-500 uppercase tracking-wider">Accent Color</p>
            <div className="flex gap-2">
              <button onClick={() => handleAccentChange('emerald')} className={`w-6 h-6 rounded-full bg-[#10b981] ring-offset-2 ring-offset-white dark:ring-offset-neutral-900 transition-all ${accent === 'emerald' ? 'ring-2 ring-neutral-400' : ''}`} />
              <button onClick={() => handleAccentChange('blue')} className={`w-6 h-6 rounded-full bg-[#3b82f6] ring-offset-2 ring-offset-white dark:ring-offset-neutral-900 transition-all ${accent === 'blue' ? 'ring-2 ring-neutral-400' : ''}`} />
              <button onClick={() => handleAccentChange('purple')} className={`w-6 h-6 rounded-full bg-[#a855f7] ring-offset-2 ring-offset-white dark:ring-offset-neutral-900 transition-all ${accent === 'purple' ? 'ring-2 ring-neutral-400' : ''}`} />
              <button onClick={() => handleAccentChange('orange')} className={`w-6 h-6 rounded-full bg-[#f97316] ring-offset-2 ring-offset-white dark:ring-offset-neutral-900 transition-all ${accent === 'orange' ? 'ring-2 ring-neutral-400' : ''}`} />
              <button onClick={() => handleAccentChange('rose')} className={`w-6 h-6 rounded-full bg-[#f43f5e] ring-offset-2 ring-offset-white dark:ring-offset-neutral-900 transition-all ${accent === 'rose' ? 'ring-2 ring-neutral-400' : ''}`} />
            </div>
          </div>

          {/* TTS Voice Settings */}
          <div className="p-3 border-b border-neutral-200 dark:border-neutral-800/50">
            <div className="flex items-center gap-1.5 px-1 pb-2 text-[10px] font-semibold text-neutral-500 uppercase tracking-wider">
              <Volume2 className="w-3 h-3" /> Voice Accent
            </div>
            <select
              value={savedVoice}
              onChange={(e) => handleVoiceChange(e.target.value)}
              className="w-full bg-neutral-50 dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 rounded-lg py-2 px-3 text-xs text-neutral-900 dark:text-neutral-100 focus:outline-none focus:ring-2 focus:ring-accent-500/50"
            >
              {voices.length === 0 && <option value="">Loading voices...</option>}
              {voices.map((voice) => (
                <option key={voice.name} value={voice.name}>
                  {voice.label}
                </option>
              ))}
            </select>
          </div>

          {/* Menu Items */}
          <div className="p-1">
            <button onClick={handleLogout} className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 rounded-md transition-colors text-left">
              <LogOut className="w-4 h-4" /> Sign Out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
