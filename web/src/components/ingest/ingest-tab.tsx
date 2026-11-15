'use client';

import { useRef, useState, type ChangeEvent, type FormEvent } from 'react';
import { FileText, Loader2, Sparkles, Type, UploadCloud } from 'lucide-react';
import type { CollectionInfo } from '@/components/documents-tab';

type Props = {
  active: boolean;
  collections: CollectionInfo[];
  onIngested: () => void | Promise<void>;
};

type Mode = 'text' | 'file';
type Status = { kind: 'ok' | 'error'; text: string };

const MIN_TEXT_CHARS = 10;

const fieldCls =
  'w-full bg-neutral-50 dark:bg-neutral-950 border border-neutral-300 dark:border-neutral-800 rounded-xl py-2 md:py-3 px-3 md:px-4 text-xs md:text-sm text-neutral-900 dark:text-neutral-100 focus:outline-none focus:ring-2 focus:ring-accent-500/50 focus:border-accent-500 transition-all';
const labelCls =
  'block text-[10px] md:text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider mb-1.5 md:mb-2';
const modeBtn = (selected: boolean) =>
  `flex-1 flex items-center justify-center gap-1.5 md:gap-2 py-1.5 md:py-2.5 text-xs md:text-sm font-medium rounded-full transition-all duration-300 ease-out ${
    selected
      ? 'bg-white dark:bg-neutral-800 text-neutral-900 dark:text-white shadow-sm ring-1 ring-black/5 dark:ring-white/10'
      : 'text-neutral-500 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-200 hover:bg-neutral-200/50 dark:hover:bg-neutral-800/50'
  }`;

export function IngestTab({ active, collections, onIngested }: Props) {
  const [mode, setMode] = useState<Mode>('text');
  const [title, setTitle] = useState('');
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [selectedCollectionId, setSelectedCollectionId] = useState('');
  const [isIngesting, setIsIngesting] = useState(false);
  const [status, setStatus] = useState<Status | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // A collection that was deleted elsewhere silently falls back to "No collection".
  const collectionId = collections.some((c) => c.id === selectedCollectionId) ? selectedCollectionId : '';

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const picked = e.target.files?.[0];
    if (!picked) return;
    setFile(picked);
    if (!title) setTitle(picked.name.split('.')[0]);
  };

  const canSubmit = !isIngesting && title.trim() !== '' && (mode === 'text' ? text.trim().length >= MIN_TEXT_CHARS : !!file);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setIsIngesting(true);
    setStatus(null);
    try {
      let res: Response;
      if (mode === 'text') {
        res = await fetch('/api/seed', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title, text, collection_id: collectionId || undefined }),
        });
      } else {
        const formData = new FormData();
        formData.append('file', file as File);
        formData.append('title', title);
        if (collectionId) formData.append('collection_id', collectionId);
        res = await fetch('/api/seed', { method: 'POST', body: formData });
      }
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to ingest');

      setStatus({ kind: 'ok', text: 'Successfully added!' });
      void onIngested();
      setTitle('');
      setText('');
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      window.setTimeout(() => setStatus(null), 3000);
    } catch (err) {
      setStatus({ kind: 'error', text: err instanceof Error ? err.message : 'Failed to ingest' });
    } finally {
      setIsIngesting(false);
    }
  };

  return (
    <div hidden={!active} className="flex-1 overflow-y-auto p-4 md:p-8 animate-in fade-in duration-300">
      <div className="max-w-2xl mx-auto space-y-6 md:space-y-8">
        <div>
          <h2 className="text-xl md:text-2xl font-bold text-neutral-900 dark:text-neutral-100">Knowledge Base</h2>
          <p className="text-xs md:text-sm text-neutral-500 mt-1">
            Upload documents or paste text to expand the AI&apos;s knowledge.
          </p>
        </div>
        <div className="bg-white dark:bg-neutral-900/50 border border-neutral-200 dark:border-neutral-800 rounded-2xl p-4 md:p-6 shadow-sm">
          <div className="flex items-center p-1 md:p-1.5 bg-neutral-100 dark:bg-neutral-950/80 rounded-full border border-neutral-200 dark:border-neutral-800 mb-4 md:mb-6 shadow-inner">
            <button type="button" onClick={() => setMode('text')} className={modeBtn(mode === 'text')}>
              <Type className="w-3.5 h-3.5 md:w-4 md:h-4" /> Paste Text
            </button>
            <button type="button" onClick={() => setMode('file')} className={modeBtn(mode === 'file')}>
              <UploadCloud className="w-3.5 h-3.5 md:w-4 md:h-4" /> Upload Files
            </button>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4 md:gap-5">
            {collections.length > 0 && (
              <div>
                <label className={labelCls}>Collection (optional)</label>
                <select value={collectionId} onChange={(e) => setSelectedCollectionId(e.target.value)} className={fieldCls}>
                  <option value="">No collection</option>
                  {collections.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div>
              <label className={labelCls}>Document Title</label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g., Company Handbook"
                className={fieldCls}
              />
            </div>

            {mode === 'text' ? (
              <div>
                <div className="flex justify-between items-end mb-1.5 md:mb-2">
                  <label className="block text-[10px] md:text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">
                    Text Content
                  </label>
                  <span
                    className={`text-[9px] md:text-[10px] font-mono ${text.length > 0 && text.length < MIN_TEXT_CHARS ? 'text-red-500' : 'text-neutral-500'}`}
                  >
                    {text.length}/{MIN_TEXT_CHARS} chars
                  </span>
                </div>
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Paste your text here..."
                  className={`${fieldCls} h-32 md:h-48 resize-none`}
                />
              </div>
            ) : (
              <div>
                <label className={labelCls}>Upload File</label>
                <div
                  className="h-32 md:h-48 border-2 border-dashed border-neutral-300 dark:border-neutral-800 hover:border-accent-500/50 rounded-xl flex flex-col items-center justify-center p-4 md:p-6 cursor-pointer bg-neutral-50 dark:bg-neutral-950/50 transition-all group"
                  onClick={() => fileInputRef.current?.click()}
                >
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileChange}
                    accept=".pdf,.txt,.md,.png,.jpg,.jpeg,.webp"
                    className="hidden"
                  />
                  {file ? (
                    <div className="text-center">
                      <div className="w-10 h-10 md:w-12 md:h-12 bg-accent-500/10 rounded-full flex items-center justify-center mx-auto mb-2 md:mb-3">
                        <FileText className="w-5 h-5 md:w-6 md:h-6 text-accent-500" />
                      </div>
                      <p className="text-xs md:text-sm font-medium text-neutral-900 dark:text-neutral-200">{file.name}</p>
                      <p className="text-[10px] md:text-xs text-neutral-500 mt-1">{(file.size / 1024).toFixed(1)} KB</p>
                    </div>
                  ) : (
                    <div className="text-center text-neutral-500 group-hover:text-neutral-700 dark:group-hover:text-neutral-400 transition-colors">
                      <UploadCloud className="w-8 h-8 md:w-10 md:h-10 mx-auto mb-2 md:mb-3 opacity-50 group-hover:opacity-100 transition-opacity" />
                      <p className="text-xs md:text-sm font-medium">Click to select a file</p>
                      <p className="text-[10px] md:text-xs mt-1 opacity-70">PDF, TXT, MD, PNG, JPG</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            <button
              type="submit"
              disabled={!canSubmit}
              className="flex items-center justify-center gap-2 w-full text-white py-2 md:py-3 rounded-xl font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg mt-2 text-xs md:text-sm"
              style={{ backgroundColor: 'var(--accent-600)' }}
            >
              {isIngesting ? <Loader2 className="w-4 h-4 md:w-5 md:h-5 animate-spin" /> : <Sparkles className="w-4 h-4 md:w-5 md:h-5" />}
              {isIngesting ? 'Ingesting...' : 'Ingest Document'}
            </button>

            {status && (
              <div
                className={`p-2 md:p-3 rounded-lg text-[10px] md:text-xs text-center font-medium ${
                  status.kind === 'error'
                    ? 'bg-red-500/10 text-red-500 border border-red-500/20'
                    : 'bg-accent-500/10 text-accent-600 border border-accent-500/20'
                }`}
              >
                {status.kind === 'error' ? `Error: ${status.text}` : status.text}
              </div>
            )}
          </form>
        </div>
      </div>
    </div>
  );
}
