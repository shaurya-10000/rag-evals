'use client';

import { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Edit2, MoreVertical, PanelLeftClose, Pin, Plus, Trash2 } from 'lucide-react';
import type { Conversation } from '@/lib/chat-types';

type Props = {
  open: boolean;
  conversations: Conversation[];
  activeId: string | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
  onNew: () => void;
  onSelect: (id: string) => void;
  onRename: (id: string, title: string) => void;
  onTogglePin: (id: string) => void;
  onDelete: (id: string) => void;
};

const iconBtn =
  'p-1.5 hover:bg-neutral-100 dark:hover:bg-white/[0.06] rounded-lg transition-colors text-neutral-600 dark:text-neutral-400';
const menuItem = 'w-full text-left px-3 py-1.5 text-xs hover:bg-neutral-100 dark:hover:bg-neutral-700 flex items-center gap-2';

export function ChatSidebar({
  open,
  conversations,
  activeId,
  loading,
  error,
  onClose,
  onNew,
  onSelect,
  onRename,
  onTogglePin,
  onDelete,
}: Props) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);

  // Stable sort: pinned first, server order (most recent activity) otherwise.
  const sorted = [...conversations].sort((a, b) => Number(b.pinned) - Number(a.pinned));

  const saveRename = (id: string) => {
    if (editTitle.trim()) onRename(id, editTitle.trim());
    setEditingId(null);
  };

  const confirmDelete = (id: string) => {
    setMenuOpenId(null);
    if (window.confirm('Delete this chat permanently? This cannot be undone.')) onDelete(id);
  };

  return (
    <>
      <AnimatePresence>
        {open && (
          <motion.div
            key="sidebar-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-[60] bg-black/40 backdrop-blur-sm md:hidden"
          />
        )}
      </AnimatePresence>

      <AnimatePresence>
        {open && (
          <motion.aside
            key="sidebar"
            initial={{ x: '-100%', opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: '-100%', opacity: 0 }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="fixed inset-y-3 left-3 z-[70] flex w-72 flex-col rounded-[2rem] border border-neutral-200 dark:border-white/[0.08] bg-white dark:bg-[#0a0a0a] shadow-2xl overflow-hidden"
          >
            <div className="flex items-center justify-between p-4 pb-2">
              <span className="font-semibold text-sm text-neutral-900 dark:text-neutral-100">Chats</span>
              <div className="flex items-center gap-1">
                <button onClick={onNew} className={iconBtn} title="New Chat">
                  <Plus className="w-4 h-4" />
                </button>
                <button onClick={onClose} className={iconBtn} title="Close Sidebar">
                  <PanelLeftClose className="w-4 h-4" />
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-2 space-y-1 scrollbar-thin">
              {error && <div className="mx-1 mb-2 p-2 rounded-lg text-[10px] text-center bg-red-500/10 text-red-500 border border-red-500/20">{error}</div>}
              {loading ? (
                <div className="text-xs text-center text-neutral-500 py-4 mt-4">Loading chats...</div>
              ) : sorted.length === 0 ? (
                <div className="text-xs text-center text-neutral-500 py-4 mt-4">No chats yet.</div>
              ) : (
                sorted.map((chat) => (
                  <div
                    key={chat.id}
                    onClick={() => onSelect(chat.id)}
                    className={`group flex items-center justify-between px-3 py-2.5 rounded-xl cursor-pointer transition-colors ${
                      activeId === chat.id
                        ? 'bg-accent-50 dark:bg-accent-500/10 text-accent-700 dark:text-accent-300'
                        : 'hover:bg-neutral-100 dark:hover:bg-white/[0.04] text-neutral-700 dark:text-neutral-200'
                    }`}
                  >
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      {chat.pinned && <Pin className="w-3 h-3 text-accent-500 shrink-0" />}
                      {editingId === chat.id ? (
                        <input
                          type="text"
                          value={editTitle}
                          onChange={(e) => setEditTitle(e.target.value)}
                          onBlur={() => saveRename(chat.id)}
                          onKeyDown={(e) => e.key === 'Enter' && saveRename(chat.id)}
                          autoFocus
                          maxLength={255}
                          className="w-full bg-transparent outline-none border-b border-accent-500 text-sm text-black dark:text-white"
                          onClick={(e) => e.stopPropagation()}
                        />
                      ) : (
                        <span className="text-sm truncate">{chat.title}</span>
                      )}
                    </div>
                    {editingId !== chat.id && (
                      <div className="relative opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setMenuOpenId(menuOpenId === chat.id ? null : chat.id);
                          }}
                          className="p-1 hover:bg-neutral-200 dark:hover:bg-neutral-700 rounded-md"
                        >
                          <MoreVertical className="w-3.5 h-3.5" />
                        </button>
                        {menuOpenId === chat.id && (
                          <div className="absolute right-0 top-full mt-1 w-32 bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 rounded-lg shadow-xl z-50 overflow-hidden py-1">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setMenuOpenId(null);
                                onTogglePin(chat.id);
                              }}
                              className={menuItem}
                            >
                              <Pin className="w-3 h-3" /> {chat.pinned ? 'Unpin' : 'Pin'}
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setMenuOpenId(null);
                                setEditingId(chat.id);
                                setEditTitle(chat.title);
                              }}
                              className={menuItem}
                            >
                              <Edit2 className="w-3 h-3" /> Rename
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                confirmDelete(chat.id);
                              }}
                              className={`${menuItem} text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10`}
                            >
                              <Trash2 className="w-3 h-3" /> Delete
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </motion.aside>
        )}
      </AnimatePresence>
    </>
  );
}
