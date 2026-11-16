export const fieldCls =
  'w-full bg-neutral-50 dark:bg-neutral-950 border border-neutral-300 dark:border-neutral-800 rounded-xl py-2 md:py-3 px-3 md:px-4 text-xs md:text-sm text-neutral-900 dark:text-neutral-100 focus:outline-none focus:ring-2 focus:ring-accent-500/50 focus:border-accent-500 transition-all';

export const labelCls =
  'block text-[10px] md:text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider mb-1.5 md:mb-2';

export const modeBtn = (selected: boolean) =>
  `flex-1 flex items-center justify-center gap-1.5 md:gap-2 py-1.5 md:py-2.5 text-xs md:text-sm font-medium rounded-full transition-all duration-300 ease-out ${
    selected
      ? 'bg-white dark:bg-neutral-800 text-neutral-900 dark:text-white shadow-sm ring-1 ring-black/5 dark:ring-white/10'
      : 'text-neutral-500 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-200 hover:bg-neutral-200/50 dark:hover:bg-neutral-800/50'
  }`;
