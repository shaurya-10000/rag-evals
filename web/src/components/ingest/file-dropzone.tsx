'use client';

import { useState, type ChangeEvent, type RefObject } from 'react';
import { FileText, UploadCloud } from 'lucide-react';
import { WEB_UPLOAD_LIMIT_BYTES, WEB_UPLOAD_LIMIT_MB } from '@/lib/limits';

const ACCEPT = '.pdf,.docx,.pptx,.csv,.txt,.md,.markdown,.png,.jpg,.jpeg,.webp';

type Props = {
  file: File | null;
  inputRef: RefObject<HTMLInputElement | null>;
  onPick: (file: File) => void;
};

export function FileDropzone({ file, inputRef, onPick }: Props) {
  const [tooBig, setTooBig] = useState<string | null>(null);

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    const picked = e.target.files?.[0];
    if (!picked) return;
    if (picked.size > WEB_UPLOAD_LIMIT_BYTES) {
      const mb = (picked.size / (1024 * 1024)).toFixed(1);
      setTooBig(`${picked.name} is ${mb} MB. Files can be up to ${WEB_UPLOAD_LIMIT_MB} MB here. Split it, or paste the text instead.`);
      e.target.value = '';
      return;
    }
    setTooBig(null);
    onPick(picked);
  };

  return (
    <>
      <div
        className="h-32 md:h-48 border-2 border-dashed border-neutral-300 dark:border-neutral-800 hover:border-accent-500/50 rounded-xl flex flex-col items-center justify-center p-4 md:p-6 cursor-pointer bg-neutral-50 dark:bg-neutral-950/50 transition-all group"
        onClick={() => inputRef.current?.click()}
      >
        <input type="file" ref={inputRef} onChange={handleChange} accept={ACCEPT} className="hidden" />
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
            <p className="text-[10px] md:text-xs mt-1 opacity-70">
              PDF, DOCX, PPTX, CSV, TXT, MD, PNG, JPG, up to {WEB_UPLOAD_LIMIT_MB} MB
            </p>
          </div>
        )}
      </div>
      {tooBig && (
        <p role="alert" className="mt-2 text-[10px] md:text-xs text-red-500">
          {tooBig}
        </p>
      )}
    </>
  );
}
