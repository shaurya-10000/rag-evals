'use client';

import { useRef, useState, type FormEvent } from 'react';
import { Link2, Loader2, Sparkles, Type, UploadCloud } from 'lucide-react';
import type { CollectionInfo } from '@/components/documents-tab';
import { useIngestJobs } from '@/hooks/use-ingest-jobs';
import { createIngestJob } from '@/lib/ingest-api';
import { FileDropzone } from './file-dropzone';
import { JobList } from './job-list';
import { fieldCls, labelCls, modeBtn } from './styles';

type Props = {
  active: boolean;
  collections: CollectionInfo[];
  onIngested: () => void | Promise<void>;
  onOpenDocument: (documentId: string) => void;
};

type Mode = 'text' | 'file' | 'url';
type Status = { kind: 'ok' | 'error'; text: string };

const MIN_TEXT_CHARS = 10;

function isHttpUrl(value: string): boolean {
  try {
    const url = new URL(value.trim());
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch {
    return false;
  }
}

export function IngestTab({ active, collections, onIngested, onOpenDocument }: Props) {
  const [mode, setMode] = useState<Mode>('text');
  const [title, setTitle] = useState('');
  const [text, setText] = useState('');
  const [url, setUrl] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [selectedCollectionId, setSelectedCollectionId] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [status, setStatus] = useState<Status | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { jobs, track, dismiss } = useIngestJobs(onIngested);

  // A collection that was deleted elsewhere silently falls back to "No collection".
  const collectionId = collections.some((c) => c.id === selectedCollectionId) ? selectedCollectionId : '';

  const handlePick = (picked: File) => {
    setFile(picked);
    if (!title) setTitle(picked.name.split('.')[0]);
  };

  const hasTitle = title.trim() !== '';
  const canSubmit =
    !isSubmitting &&
    (mode === 'text'
      ? hasTitle && text.trim().length >= MIN_TEXT_CHARS
      : mode === 'file'
        ? hasTitle && file !== null
        : isHttpUrl(url));

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setIsSubmitting(true);
    setStatus(null);
    try {
      const job = await createIngestJob(
        mode === 'text'
          ? { kind: 'text', title, text, collectionId }
          : mode === 'file'
            ? { kind: 'file', title, file: file as File, collectionId }
            : { kind: 'url', title, url: url.trim(), collectionId }
      );
      track(job);
      setStatus({ kind: 'ok', text: 'Import started. You can keep using the app while it finishes.' });
      setTitle('');
      setText('');
      setUrl('');
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      window.setTimeout(() => setStatus(null), 4000);
    } catch (err) {
      setStatus({ kind: 'error', text: err instanceof Error ? err.message : 'Failed to start the import' });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div hidden={!active} className="flex-1 overflow-y-auto p-4 md:p-8 animate-in fade-in duration-300">
      <div className="max-w-2xl mx-auto space-y-6 md:space-y-8">
        <div>
          <h2 className="text-xl md:text-2xl font-bold text-neutral-900 dark:text-neutral-100">Knowledge Base</h2>
          <p className="text-xs md:text-sm text-neutral-500 mt-1">
            Upload documents, import a web page or paste text to expand the AI&apos;s knowledge.
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
            <button type="button" onClick={() => setMode('url')} className={modeBtn(mode === 'url')}>
              <Link2 className="w-3.5 h-3.5 md:w-4 md:h-4" /> From URL
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

            {mode === 'url' && (
              <div>
                <label className={labelCls}>Web address</label>
                <input
                  type="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://example.com/article"
                  className={fieldCls}
                />
                <p className="text-[10px] md:text-xs text-neutral-500 mt-1.5">
                  Web pages, PDFs and text files work. Pages that need a login or JavaScript can&apos;t be read.
                </p>
              </div>
            )}

            <div>
              <label className={labelCls}>{mode === 'url' ? 'Document Title (optional)' : 'Document Title'}</label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder={mode === 'url' ? 'Leave blank to use the page title' : 'e.g., Company Handbook'}
                className={fieldCls}
              />
            </div>

            {mode === 'text' && (
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
            )}

            {mode === 'file' && (
              <div>
                <label className={labelCls}>Upload File</label>
                <FileDropzone file={file} inputRef={fileInputRef} onPick={handlePick} />
              </div>
            )}

            <button
              type="submit"
              disabled={!canSubmit}
              className="flex items-center justify-center gap-2 w-full text-white py-2 md:py-3 rounded-xl font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg mt-2 text-xs md:text-sm"
              style={{ backgroundColor: 'var(--accent-600)' }}
            >
              {isSubmitting ? <Loader2 className="w-4 h-4 md:w-5 md:h-5 animate-spin" /> : <Sparkles className="w-4 h-4 md:w-5 md:h-5" />}
              {isSubmitting ? 'Starting...' : 'Ingest Document'}
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

        <JobList jobs={jobs} onDismiss={dismiss} onOpenDocument={onOpenDocument} />
      </div>
    </div>
  );
}
