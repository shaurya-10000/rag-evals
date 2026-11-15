'use client';

import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { formatDistanceToNow } from 'date-fns';
import {
  Check,
  FileText,
  Folder,
  FolderOpen,
  FolderPlus,
  Inbox,
  Loader2,
  Pencil,
  Plus,
  Search,
  Trash2,
  X,
} from 'lucide-react';

export type CollectionInfo = { id: string; name: string; document_count: number; created_at: string };

type DocSummary = {
  id: string;
  title: string;
  collection_id: string | null;
  source_url: string | null;
  preview: string;
  chunk_count: number;
  created_at: string;
  updated_at: string;
};
type DocDetail = DocSummary & { content: string };
type Banner = { type: 'ok' | 'error'; text: string };

type Props = {
  collections: CollectionInfo[];
  onCollectionsChanged: () => void | Promise<void>;
  onAddDocument: () => void;
  initialDocumentId?: string | null;
};

const MIN_CONTENT_CHARS = 10;

async function api<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { cache: 'no-store', ...init });
  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    /* empty body */
  }
  if (!res.ok) {
    const message = (data as { error?: string } | null)?.error;
    throw new Error(message || `Request failed (${res.status})`);
  }
  return data as T;
}

function jsonInit(method: string, body: unknown): RequestInit {
  return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
}

const errMsg = (err: unknown) => (err instanceof Error ? err.message : 'Something went wrong');

const inputCls =
  'w-full bg-neutral-50 dark:bg-neutral-950 border border-neutral-300 dark:border-neutral-800 rounded-xl py-2 px-3 text-xs md:text-sm text-neutral-900 dark:text-neutral-100 focus:outline-none focus:ring-2 focus:ring-accent-500/50 focus:border-accent-500 transition-all';
const ghostBtn =
  'flex items-center gap-1.5 px-2.5 py-1.5 text-[10px] md:text-xs font-medium text-neutral-500 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-neutral-200 bg-neutral-100 hover:bg-neutral-200 dark:bg-neutral-900 dark:hover:bg-neutral-800 rounded-md transition-colors disabled:opacity-50';
const primaryBtn =
  'flex items-center justify-center gap-2 px-4 py-2 rounded-xl text-white text-xs md:text-sm font-medium shadow-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed';

function Modal({ children, onClose, wide }: { children: ReactNode; onClose: () => void; wide?: boolean }) {
  return (
    <div
      className="fixed inset-0 z-[80] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className={`w-full ${wide ? 'max-w-3xl' : 'max-w-md'} max-h-[90dvh] flex flex-col bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl shadow-2xl overflow-hidden`}
      >
        {children}
      </div>
    </div>
  );
}

export function DocumentsTab({
  collections,
  onCollectionsChanged,
  onAddDocument,
  initialDocumentId = null,
}: Props) {
  const [filter, setFilter] = useState<string>('all'); // 'all' | 'unfiled' | collection id
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [reloadTick, setReloadTick] = useState(0);
  const [result, setResult] = useState<{ key: string; docs: DocSummary[]; error: string | null }>({
    key: '',
    docs: [],
    error: null,
  });
  const [banner, setBanner] = useState<Banner | null>(null);
  const bannerTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Collection UI
  const [newOpen, setNewOpen] = useState(false);
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);
  const [renamingCol, setRenamingCol] = useState(false);
  const [colName, setColName] = useState('');
  const [confirmCol, setConfirmCol] = useState(false);
  const [colBusy, setColBusy] = useState(false);

  // Document UI
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const renameCancelled = useRef(false);
  const [moveMenuId, setMoveMenuId] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [confirmDoc, setConfirmDoc] = useState<DocSummary | null>(null);

  // Editor modal
  const [editorDoc, setEditorDoc] = useState<DocSummary | null>(null);
  const [editorOriginal, setEditorOriginal] = useState<DocDetail | null>(null);
  const [editorTitle, setEditorTitle] = useState('');
  const [editorContent, setEditorContent] = useState('');
  const [editorError, setEditorError] = useState<string | null>(null);
  const [editorSaving, setEditorSaving] = useState(false);
  const editorReq = useRef<string | null>(null);

  const queryKey = `${filter}|${debouncedSearch}|${reloadTick}`;
  const loading = result.key !== queryKey;
  const docs = result.docs;
  const activeCollection = collections.find((c) => c.id === filter) ?? null;
  const nameById = new Map(collections.map((c) => [c.id, c.name]));
  const heading =
    filter === 'all' ? 'All documents' : filter === 'unfiled' ? 'Unfiled' : (activeCollection?.name ?? 'Collection');

  const reload = () => setReloadTick((t) => t + 1);

  const flash = (type: Banner['type'], text: string) => {
    setBanner({ type, text });
    if (bannerTimer.current) clearTimeout(bannerTimer.current);
    bannerTimer.current = setTimeout(() => setBanner(null), 4000);
  };

  useEffect(
    () => () => {
      if (bannerTimer.current) clearTimeout(bannerTimer.current);
    },
    []
  );

  // Debounce the search box
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  // Load documents whenever the filter, search or reload counter changes
  useEffect(() => {
    let cancelled = false;
    const params = new URLSearchParams();
    if (filter === 'unfiled') params.set('unfiled', 'true');
    else if (filter !== 'all') params.set('collection_id', filter);
    if (debouncedSearch.trim()) params.set('q', debouncedSearch.trim());
    const qs = params.toString();

    api<DocSummary[]>(`/api/documents${qs ? `?${qs}` : ''}`)
      .then((list) => {
        if (!cancelled) setResult({ key: queryKey, docs: list, error: null });
      })
      .catch((err) => {
        if (!cancelled) setResult({ key: queryKey, docs: [], error: errMsg(err) });
      });
    return () => {
      cancelled = true;
    };
  }, [filter, debouncedSearch, queryKey]);

  // Close the move menu when clicking elsewhere
  useEffect(() => {
    if (!moveMenuId) return;
    const onPointer = (e: PointerEvent) => {
      if (!(e.target as HTMLElement).closest('[data-move-menu]')) setMoveMenuId(null);
    };
    document.addEventListener('pointerdown', onPointer);
    return () => document.removeEventListener('pointerdown', onPointer);
  }, [moveMenuId]);

  // Escape closes any open modal
  const modalOpen = editorDoc !== null || confirmDoc !== null || confirmCol;
  useEffect(() => {
    if (!modalOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || editorSaving) return;
      editorReq.current = null;
      setEditorDoc(null);
      setEditorOriginal(null);
      setConfirmDoc(null);
      setConfirmCol(false);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [modalOpen, editorSaving]);

  // ---------------------------------------------------------- collections
  const handleCreateCollection = async (e: FormEvent) => {
    e.preventDefault();
    const name = newName.trim();
    if (!name || creating) return;
    setCreating(true);
    try {
      const col = await api<CollectionInfo>('/api/collections', jsonInit('POST', { name }));
      setNewName('');
      setNewOpen(false);
      setFilter(col.id);
      await onCollectionsChanged();
    } catch (err) {
      flash('error', errMsg(err));
    } finally {
      setCreating(false);
    }
  };

  const handleRenameCollection = async (e: FormEvent) => {
    e.preventDefault();
    if (!activeCollection) return;
    const name = colName.trim();
    if (!name || name === activeCollection.name) {
      setRenamingCol(false);
      return;
    }
    setColBusy(true);
    try {
      await api(`/api/collections/${activeCollection.id}`, jsonInit('PATCH', { name }));
      setRenamingCol(false);
      await onCollectionsChanged();
    } catch (err) {
      flash('error', errMsg(err));
    } finally {
      setColBusy(false);
    }
  };

  const handleDeleteCollection = async (deleteDocuments: boolean) => {
    if (!activeCollection) return;
    setColBusy(true);
    try {
      await api(
        `/api/collections/${activeCollection.id}${deleteDocuments ? '?delete_documents=true' : ''}`,
        { method: 'DELETE' }
      );
      flash('ok', deleteDocuments ? 'Collection and its documents deleted.' : 'Collection deleted. Documents are now unfiled.');
      setConfirmCol(false);
      setFilter('all');
      reload();
      await onCollectionsChanged();
    } catch (err) {
      flash('error', errMsg(err));
    } finally {
      setColBusy(false);
    }
  };

  // ------------------------------------------------------------ documents
  const startRename = (doc: DocSummary) => {
    renameCancelled.current = false;
    setRenamingId(doc.id);
    setRenameValue(doc.title);
    setMoveMenuId(null);
  };

  const commitRename = async (doc: DocSummary) => {
    if (renameCancelled.current) {
      renameCancelled.current = false;
      setRenamingId(null);
      return;
    }
    const title = renameValue.trim();
    setRenamingId(null);
    if (!title || title === doc.title) return;
    setBusyId(doc.id);
    try {
      await api(`/api/documents/${doc.id}`, jsonInit('PATCH', { title }));
      reload();
    } catch (err) {
      flash('error', errMsg(err));
    } finally {
      setBusyId(null);
    }
  };

  const handleMove = async (doc: DocSummary, collectionId: string | null) => {
    setMoveMenuId(null);
    if (doc.collection_id === collectionId) return;
    setBusyId(doc.id);
    try {
      await api(`/api/documents/${doc.id}/collection`, jsonInit('PUT', { collection_id: collectionId }));
      flash('ok', collectionId ? `Moved to ${nameById.get(collectionId) ?? 'collection'}.` : 'Moved to Unfiled.');
      reload();
      await onCollectionsChanged();
    } catch (err) {
      flash('error', errMsg(err));
    } finally {
      setBusyId(null);
    }
  };

  const handleDeleteDoc = async () => {
    if (!confirmDoc) return;
    const doc = confirmDoc;
    setBusyId(doc.id);
    try {
      await api(`/api/documents/${doc.id}`, { method: 'DELETE' });
      setConfirmDoc(null);
      flash('ok', `Deleted "${doc.title}".`);
      reload();
      await onCollectionsChanged();
    } catch (err) {
      setConfirmDoc(null);
      flash('error', errMsg(err));
    } finally {
      setBusyId(null);
    }
  };

  // --------------------------------------------------------------- editor
  const openEditor = (doc: DocSummary) => {
    setMoveMenuId(null);
    editorReq.current = doc.id;
    setEditorDoc(doc);
    setEditorOriginal(null);
    setEditorError(null);
    setEditorTitle(doc.title);
    setEditorContent('');
    api<DocDetail>(`/api/documents/${doc.id}`)
      .then((detail) => {
        if (editorReq.current !== doc.id) return;
        setEditorOriginal(detail);
        setEditorTitle(detail.title);
        setEditorContent(detail.content);
      })
      .catch((err) => {
        if (editorReq.current !== doc.id) return;
        setEditorError(errMsg(err));
      });
  };

  const closeEditor = () => {
    if (editorSaving) return;
    editorReq.current = null;
    setEditorDoc(null);
    setEditorOriginal(null);
    setEditorError(null);
  };

  const editorLoading = editorDoc !== null && editorOriginal === null && editorError === null;
  const dirtyTitle = !!editorOriginal && editorTitle.trim() !== editorOriginal.title;
  const dirtyContent = !!editorOriginal && editorContent !== editorOriginal.content;
  const contentTooShort = editorContent.trim().length < MIN_CONTENT_CHARS;
  const canSave =
    !!editorOriginal &&
    !editorSaving &&
    (dirtyTitle || dirtyContent) &&
    editorTitle.trim().length > 0 &&
    (!dirtyContent || !contentTooShort);

  const saveEditor = async () => {
    if (!editorDoc || !canSave) return;
    const payload: { title?: string; content?: string } = {};
    if (dirtyTitle) payload.title = editorTitle.trim();
    if (dirtyContent) payload.content = editorContent;
    setEditorSaving(true);
    setEditorError(null);
    try {
      await api<DocDetail>(`/api/documents/${editorDoc.id}`, jsonInit('PATCH', payload));
      editorReq.current = null;
      setEditorDoc(null);
      setEditorOriginal(null);
      flash('ok', dirtyContent ? 'Saved. The document was re-indexed.' : 'Saved.');
      reload();
    } catch (err) {
      setEditorError(errMsg(err));
    } finally {
      setEditorSaving(false);
    }
  };

  // --------------------------------------------------------------- render
  // Deep link: open the editor for a document chosen elsewhere (e.g. a citation).
  useEffect(() => {
    if (!initialDocumentId) return;
    let cancelled = false;
    api<DocDetail>(`/api/documents/${initialDocumentId}`)
      .then((detail) => {
        if (!cancelled) openEditor(detail);
      })
      .catch(() => {
        if (!cancelled) flash('error', 'That document no longer exists.');
      });
    return () => {
      cancelled = true;
    };
  }, [initialDocumentId]);

  const chipCls = (active: boolean) =>
    `flex items-center gap-2 shrink-0 px-3 py-2 rounded-xl text-xs md:text-sm font-medium transition-colors text-left ${
      active
        ? 'bg-accent-50 dark:bg-accent-500/10 text-accent-700 dark:text-accent-300'
        : 'text-neutral-600 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800/60'
    }`;

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-8 animate-in fade-in duration-300">
      <div className="max-w-5xl mx-auto">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-xl md:text-2xl font-bold text-neutral-900 dark:text-neutral-100">Documents</h2>
            <p className="text-xs md:text-sm text-neutral-500 mt-1">
              Browse, rename, edit and organise everything in your knowledge base.
            </p>
          </div>
          <button onClick={onAddDocument} className={primaryBtn} style={{ backgroundColor: 'var(--accent-600)' }}>
            <Plus className="w-4 h-4" /> Add document
          </button>
        </div>

        {banner && (
          <div
            className={`mt-4 p-2 md:p-3 rounded-lg text-[10px] md:text-xs text-center font-medium ${
              banner.type === 'error'
                ? 'bg-red-500/10 text-red-500 border border-red-500/20'
                : 'bg-accent-500/10 text-accent-600 border border-accent-500/20'
            }`}
          >
            {banner.text}
          </div>
        )}

        <div className="flex flex-col md:flex-row gap-4 md:gap-6 mt-5">
          {/* ---------------- sidebar ---------------- */}
          <aside className="md:w-60 shrink-0">
            <div className="flex md:flex-col gap-1 overflow-x-auto md:overflow-visible pb-1">
              <button onClick={() => setFilter('all')} className={chipCls(filter === 'all')}>
                <FileText className="w-4 h-4 shrink-0" /> <span className="flex-1">All documents</span>
              </button>
              <button onClick={() => setFilter('unfiled')} className={chipCls(filter === 'unfiled')}>
                <Inbox className="w-4 h-4 shrink-0" /> <span className="flex-1">Unfiled</span>
              </button>
              {collections.map((c) => (
                <button key={c.id} onClick={() => setFilter(c.id)} className={chipCls(filter === c.id)}>
                  {filter === c.id ? <FolderOpen className="w-4 h-4 shrink-0" /> : <Folder className="w-4 h-4 shrink-0" />}
                  <span className="flex-1 truncate max-w-[10rem] md:max-w-none">{c.name}</span>
                  <span className="text-[10px] text-neutral-500">{c.document_count}</span>
                </button>
              ))}
              {!newOpen && (
                <button
                  onClick={() => setNewOpen(true)}
                  className="flex items-center gap-2 shrink-0 px-3 py-2 rounded-xl text-xs md:text-sm font-medium text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-800/60 transition-colors"
                >
                  <FolderPlus className="w-4 h-4 shrink-0" /> New collection
                </button>
              )}
            </div>
            {newOpen && (
              <form onSubmit={handleCreateCollection} className="mt-2 flex items-center gap-1.5">
                <input
                  autoFocus
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Escape') {
                      setNewOpen(false);
                      setNewName('');
                    }
                  }}
                  maxLength={100}
                  placeholder="Collection name"
                  className={inputCls}
                />
                <button
                  type="submit"
                  disabled={creating || !newName.trim()}
                  className="p-2 rounded-lg text-white disabled:opacity-50"
                  style={{ backgroundColor: 'var(--accent-600)' }}
                  title="Create"
                >
                  {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setNewOpen(false);
                    setNewName('');
                  }}
                  className="p-2 rounded-lg text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800"
                  title="Cancel"
                >
                  <X className="w-4 h-4" />
                </button>
              </form>
            )}
          </aside>

          {/* ---------------- main list ---------------- */}
          <section className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
              {renamingCol && activeCollection ? (
                <form onSubmit={handleRenameCollection} className="flex items-center gap-1.5 flex-1 min-w-[12rem]">
                  <input
                    autoFocus
                    value={colName}
                    onChange={(e) => setColName(e.target.value)}
                    onKeyDown={(e) => e.key === 'Escape' && setRenamingCol(false)}
                    maxLength={100}
                    className={inputCls}
                  />
                  <button
                    type="submit"
                    disabled={colBusy || !colName.trim()}
                    className="p-2 rounded-lg text-white disabled:opacity-50"
                    style={{ backgroundColor: 'var(--accent-600)' }}
                    title="Save name"
                  >
                    {colBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                  </button>
                  <button
                    type="button"
                    onClick={() => setRenamingCol(false)}
                    className="p-2 rounded-lg text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800"
                    title="Cancel"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </form>
              ) : (
                <div className="flex items-center gap-2 min-w-0">
                  <h3 className="text-sm md:text-base font-semibold text-neutral-900 dark:text-neutral-100 truncate">{heading}</h3>
                  {loading && <Loader2 className="w-3.5 h-3.5 animate-spin text-accent-500 shrink-0" />}
                </div>
              )}
              {activeCollection && !renamingCol && (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      setColName(activeCollection.name);
                      setRenamingCol(true);
                    }}
                    className={ghostBtn}
                  >
                    <Pencil className="w-3.5 h-3.5" /> Rename
                  </button>
                  <button onClick={() => setConfirmCol(true)} className={`${ghostBtn} hover:!text-red-500`}>
                    <Trash2 className="w-3.5 h-3.5" /> Delete
                  </button>
                </div>
              )}
            </div>

            <div className="relative mb-4">
              <Search className="w-4 h-4 text-neutral-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by title..."
                className={`${inputCls} pl-9`}
              />
            </div>

            {result.error && !loading && (
              <div className="p-3 rounded-lg text-xs text-center font-medium bg-red-500/10 text-red-500 border border-red-500/20">
                {result.error}
              </div>
            )}

            {!loading && !result.error && docs.length === 0 && (
              <div className="text-center py-12 border-2 border-dashed border-neutral-300 dark:border-neutral-800 rounded-2xl">
                <FileText className="w-8 h-8 mx-auto mb-2 text-neutral-400" />
                <p className="text-sm font-medium text-neutral-700 dark:text-neutral-300">
                  {debouncedSearch.trim() ? 'No documents match your search.' : 'No documents here yet.'}
                </p>
                {!debouncedSearch.trim() && (
                  <button onClick={onAddDocument} className="mt-2 text-xs text-accent-600 hover:underline">
                    Add your first document
                  </button>
                )}
              </div>
            )}

            <div className={`space-y-3 transition-opacity ${loading ? 'opacity-60' : 'opacity-100'}`}>
              {docs.map((doc) => (
                <div
                  key={doc.id}
                  className="bg-white dark:bg-neutral-900/50 border border-neutral-200 dark:border-neutral-800 rounded-2xl p-3 md:p-4 shadow-sm"
                >
                  <div className="flex items-start gap-3">
                    <div className="w-9 h-9 rounded-xl bg-accent-500/10 border border-accent-500/20 flex items-center justify-center shrink-0">
                      <FileText className="w-4 h-4 text-accent-500" />
                    </div>
                    <div className="flex-1 min-w-0">
                      {renamingId === doc.id ? (
                        <input
                          autoFocus
                          value={renameValue}
                          onChange={(e) => setRenameValue(e.target.value)}
                          onBlur={() => commitRename(doc)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') e.currentTarget.blur();
                            if (e.key === 'Escape') {
                              renameCancelled.current = true;
                              e.currentTarget.blur();
                            }
                          }}
                          maxLength={255}
                          className="w-full bg-transparent outline-none border-b border-accent-500 text-sm font-semibold text-neutral-900 dark:text-white"
                        />
                      ) : (
                        <h4 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100 truncate">{doc.title}</h4>
                      )}
                      {doc.preview && (
                        <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1 line-clamp-2">{doc.preview}</p>
                      )}
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-2 text-[10px] md:text-xs text-neutral-500">
                        <span>{doc.chunk_count} chunks</span>
                        <span>Updated {formatDistanceToNow(new Date(doc.updated_at), { addSuffix: true })}</span>
                        {doc.collection_id && nameById.get(doc.collection_id) && filter !== doc.collection_id && (
                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-neutral-200 dark:bg-neutral-800 text-accent-600 font-semibold">
                            <Folder className="w-3 h-3" /> {nameById.get(doc.collection_id)}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2 mt-3 pl-12">
                    <button onClick={() => openEditor(doc)} disabled={busyId === doc.id} className={ghostBtn}>
                      <Pencil className="w-3.5 h-3.5" /> Edit
                    </button>
                    <button onClick={() => startRename(doc)} disabled={busyId === doc.id} className={ghostBtn}>
                      Rename
                    </button>
                    <div className="relative" data-move-menu>
                      <button
                        onClick={() => setMoveMenuId(moveMenuId === doc.id ? null : doc.id)}
                        disabled={busyId === doc.id}
                        className={ghostBtn}
                      >
                        <Folder className="w-3.5 h-3.5" /> Move
                      </button>
                      {moveMenuId === doc.id && (
                        <div className="absolute left-0 top-full mt-1 w-52 max-h-60 overflow-y-auto bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 rounded-lg shadow-xl z-30 py-1">
                          <button
                            onClick={() => handleMove(doc, null)}
                            className="w-full text-left px-3 py-1.5 text-xs hover:bg-neutral-100 dark:hover:bg-neutral-700 flex items-center gap-2"
                          >
                            <Inbox className="w-3 h-3" /> <span className="flex-1">Unfiled</span>
                            {doc.collection_id === null && <Check className="w-3 h-3 text-accent-500" />}
                          </button>
                          {collections.map((c) => (
                            <button
                              key={c.id}
                              onClick={() => handleMove(doc, c.id)}
                              className="w-full text-left px-3 py-1.5 text-xs hover:bg-neutral-100 dark:hover:bg-neutral-700 flex items-center gap-2"
                            >
                              <Folder className="w-3 h-3 shrink-0" /> <span className="flex-1 truncate">{c.name}</span>
                              {doc.collection_id === c.id && <Check className="w-3 h-3 text-accent-500" />}
                            </button>
                          ))}
                          {collections.length === 0 && (
                            <p className="px-3 py-1.5 text-[10px] text-neutral-500">Create a collection first.</p>
                          )}
                        </div>
                      )}
                    </div>
                    <button
                      onClick={() => setConfirmDoc(doc)}
                      disabled={busyId === doc.id}
                      className={`${ghostBtn} hover:!text-red-500`}
                    >
                      <Trash2 className="w-3.5 h-3.5" /> Delete
                    </button>
                    {busyId === doc.id && <Loader2 className="w-3.5 h-3.5 animate-spin text-accent-500" />}
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>

      {/* ---------------- edit modal ---------------- */}
      {editorDoc && (
        <Modal wide onClose={closeEditor}>
          <div className="flex items-center justify-between px-5 py-4 border-b border-neutral-200 dark:border-neutral-800">
            <h3 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">Edit document</h3>
            <button onClick={closeEditor} disabled={editorSaving} className="p-1 rounded-md text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800">
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-5 space-y-4">
            {editorLoading ? (
              <div className="flex items-center justify-center gap-2 py-16 text-sm text-neutral-500">
                <Loader2 className="w-4 h-4 animate-spin" /> Loading document...
              </div>
            ) : (
              <>
                <div>
                  <label className="block text-[10px] md:text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider mb-1.5">
                    Title
                  </label>
                  <input
                    value={editorTitle}
                    onChange={(e) => setEditorTitle(e.target.value)}
                    maxLength={255}
                    disabled={!editorOriginal || editorSaving}
                    className={inputCls}
                  />
                </div>
                <div>
                  <div className="flex justify-between items-end mb-1.5">
                    <label className="block text-[10px] md:text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">
                      Content
                    </label>
                    <span
                      className={`text-[10px] font-mono ${dirtyContent && contentTooShort ? 'text-red-500' : 'text-neutral-500'}`}
                    >
                      {editorContent.length.toLocaleString()} chars
                    </span>
                  </div>
                  <textarea
                    value={editorContent}
                    onChange={(e) => setEditorContent(e.target.value)}
                    disabled={!editorOriginal || editorSaving}
                    className={`${inputCls} h-[45vh] resize-none font-mono text-xs leading-relaxed`}
                  />
                  {dirtyContent && (
                    <p className="text-[10px] md:text-xs text-neutral-500 mt-1.5">
                      Saving changed text re-chunks and re-embeds this document, which can take a few seconds.
                    </p>
                  )}
                </div>
              </>
            )}
            {editorError && (
              <div className="p-2 md:p-3 rounded-lg text-[10px] md:text-xs text-center font-medium bg-red-500/10 text-red-500 border border-red-500/20">
                {editorError}
              </div>
            )}
          </div>
          <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-neutral-200 dark:border-neutral-800">
            <button onClick={closeEditor} disabled={editorSaving} className={ghostBtn}>
              Cancel
            </button>
            <button onClick={saveEditor} disabled={!canSave} className={primaryBtn} style={{ backgroundColor: 'var(--accent-600)' }}>
              {editorSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
              {editorSaving ? (dirtyContent ? 'Re-indexing...' : 'Saving...') : 'Save changes'}
            </button>
          </div>
        </Modal>
      )}

      {/* ---------------- delete document modal ---------------- */}
      {confirmDoc && (
        <Modal onClose={() => setConfirmDoc(null)}>
          <div className="p-5 space-y-2">
            <h3 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">Delete document?</h3>
            <p className="text-xs text-neutral-500">
              &quot;{confirmDoc.title}&quot; and its {confirmDoc.chunk_count} chunks will be permanently removed.
            </p>
          </div>
          <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-neutral-200 dark:border-neutral-800">
            <button onClick={() => setConfirmDoc(null)} className={ghostBtn}>
              Cancel
            </button>
            <button onClick={handleDeleteDoc} className={`${primaryBtn} bg-red-600 hover:bg-red-700`}>
              <Trash2 className="w-4 h-4" /> Delete
            </button>
          </div>
        </Modal>
      )}

      {/* ---------------- delete collection modal ---------------- */}
      {confirmCol && activeCollection && (
        <Modal onClose={() => !colBusy && setConfirmCol(false)}>
          <div className="p-5 space-y-2">
            <h3 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
              Delete &quot;{activeCollection.name}&quot;?
            </h3>
            <p className="text-xs text-neutral-500">
              This collection holds {activeCollection.document_count} document
              {activeCollection.document_count === 1 ? '' : 's'}. You can keep them (they become unfiled) or delete them too.
            </p>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2 px-5 py-4 border-t border-neutral-200 dark:border-neutral-800">
            <button onClick={() => setConfirmCol(false)} disabled={colBusy} className={ghostBtn}>
              Cancel
            </button>
            <button onClick={() => handleDeleteCollection(false)} disabled={colBusy} className={ghostBtn}>
              Keep documents
            </button>
            <button
              onClick={() => handleDeleteCollection(true)}
              disabled={colBusy}
              className={`${primaryBtn} bg-red-600 hover:bg-red-700`}
            >
              {colBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
              Delete everything
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}