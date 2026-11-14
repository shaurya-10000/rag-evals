'use client';

import { useState, useRef, useEffect } from 'react';
import { Send, Loader2, Layers, User, Database, UploadCloud, FileText, Type, Sparkles, MessageSquare, Copy, Check, Plus, ChevronDown, ChevronUp, Pin, Edit2, Trash2, MoreVertical, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { motion, AnimatePresence } from 'framer-motion';
import { UserMenu } from '@/components/user-menu';

type Chunk = { id: string; content: string; metadata: Record<string, unknown> };
type Message = { role: 'user' | 'assistant'; content: string; chunks?: Chunk[]; isStreaming?: boolean };
type ChatSession = { id: string; title: string; messages: Message[]; pinned: boolean; createdAt: number };

export default function Home() {
  const [activeTab, setActiveTab] = useState<'chat' | 'ingest'>('chat');
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const [expandedSources, setExpandedSources] = useState<Record<number, boolean>>({});

  // Chat History State
  const [sidebarOpen, setSidebarOpen] = useState(false);
  
  // Lazy initialize from localStorage
  const [chats, setChats] = useState<ChatSession[]>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('rag-evals-chats');
      if (saved) {
        try { return JSON.parse(saved); } catch { return []; }
      }
    }
    return [];
  });

  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [editingChatId, setEditingChatId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [chatMenuOpenId, setChatMenuOpenId] = useState<string | null>(null);
  const sidebarRef = useRef<HTMLElement>(null);

  // Ingest State
  const [ingestMode, setIngestMode] = useState<'text' | 'file'>('text');
  const [docTitle, setDocTitle] = useState('');
  const [docText, setDocText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isIngesting, setIsIngesting] = useState(false);
  const [ingestStatus, setIngestStatus] = useState('');

  // Save chats
  useEffect(() => {
    if (chats.length > 0 || localStorage.getItem('rag-evals-chats')) {
      localStorage.setItem('rag-evals-chats', JSON.stringify(chats));
    }
  }, [chats]);

  const scrollToBottom = () => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  useEffect(() => { if (activeTab === 'chat') scrollToBottom(); }, [messages, activeTab]);

  // Chat Handlers
  const startNewChat = () => {
    const newId = Date.now().toString();
    const newChat: ChatSession = {
      id: newId,
      title: "New Chat",
      messages: [],
      pinned: false,
      createdAt: Date.now()
    };
    
    setChats(prev => [newChat, ...prev]);
    setActiveChatId(newId);
    setMessages([]);
    setInput('');
    setActiveTab('chat');
    setSidebarOpen(false);
  };

  const selectChat = (id: string) => {
    setActiveChatId(id);
    const chat = chats.find(c => c.id === id);
    if (chat) setMessages(chat.messages);
    setActiveTab('chat');
    setSidebarOpen(false);
  };

  const deleteChat = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setChats(prev => prev.filter(c => c.id !== id));
    if (activeChatId === id) startNewChat();
    setChatMenuOpenId(null);
  };

  const togglePin = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setChats(prev => prev.map(c => c.id === id ? { ...c, pinned: !c.pinned } : c));
    setChatMenuOpenId(null);
  };

  const startRename = (id: string, currentTitle: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingChatId(id);
    setEditTitle(currentTitle);
    setChatMenuOpenId(null);
  };

  const saveRename = (id: string) => {
    if (editTitle.trim()) {
      setChats(prev => prev.map(c => c.id === id ? { ...c, title: editTitle.trim() } : c));
    }
    setEditingChatId(null);
  };

  const handleCopy = (text: string, index: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };
  const toggleSource = (msgIndex: number) => setExpandedSources(prev => ({ ...prev, [msgIndex]: !prev[msgIndex] }));

  // Ingest Handlers
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
      if (!docTitle) setDocTitle(e.target.files[0].name.split('.')[0]);
    }
  };

  const handleIngest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!docTitle.trim() || isIngesting) return;
    setIsIngesting(true);
    setIngestStatus('Ingesting...');
    try {
      let res;
      if (ingestMode === 'text') {
        if (docText.trim().length < 10) throw new Error('Text must be at least 10 characters.');
        res = await fetch('/api/seed', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title: docTitle, text: docText }) });
      } else {
        if (!file) throw new Error('Please select a file.');
        const formData = new FormData();
        formData.append('file', file);
        formData.append('title', docTitle);
        res = await fetch('/api/seed', { method: 'POST', body: formData });
      }
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to ingest');
      setIngestStatus('Successfully added!');
      setDocTitle(''); setDocText(''); setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      setTimeout(() => setIngestStatus(''), 3000);
    } catch {
      setIngestStatus('Error: Failed to ingest');
    } finally { setIsIngesting(false); }
  };

  // Chat Logic
  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    const userMsg: Message = { role: 'user', content: input };
    const currentInput = input;
    
    let currentChatId = activeChatId;
    if (!currentChatId) {
      currentChatId = Date.now().toString();
      const newChat: ChatSession = {
        id: currentChatId,
        title: currentInput.substring(0, 30) + (currentInput.length > 30 ? '...' : ''),
        messages: [],
        pinned: false,
        createdAt: Date.now()
      };
      setChats(prev => [newChat, ...prev]);
      setActiveChatId(currentChatId);
    }

    const newMessages = [...messages, userMsg, { role: 'assistant' as const, content: '', isStreaming: true }];
    setMessages(newMessages);
    setChats(prev => prev.map(c => c.id === currentChatId ? { ...c, messages: newMessages } : c));
    
    // Auto-generate title if this is the first message in the chat
    if (messages.length === 0) {
      fetch('/api/generate-title', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: currentInput }),
      })
      .then(res => res.json())
      .then(data => {
        if (data.title) {
          setChats(prev => prev.map(c => c.id === currentChatId ? { ...c, title: data.title } : c));
        }
      })
      .catch(() => { /* Silently fail, keep the default title */ });
    }
    
    setInput(''); setIsLoading(true);
    try {
      const res = await fetch('/api/query', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query: currentInput, top_k: 3 }) });
      if (!res.body) throw new Error('No response body');
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let done = false;
      let buffer = '';
      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        if (value) {
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n\n');
          buffer = lines.pop() || '';
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const dataStr = line.replace('data: ', '').trim();
              if (!dataStr) continue;
              try {
                const data = JSON.parse(dataStr);
                setMessages((prev) => {
                  const updated = [...prev];
                  const lastMsg = { ...updated[updated.length - 1] };
                  if (data.type === 'sources') lastMsg.chunks = data.sources;
                  else if (data.type === 'token') lastMsg.content = (lastMsg.content || '') + data.text;
                  else if (data.type === 'done') lastMsg.isStreaming = false;
                  updated[updated.length - 1] = lastMsg;
                  setChats(cPrev => cPrev.map(c => c.id === currentChatId ? { ...c, messages: updated } : c));
                  return updated;
                });
              } catch (err) { console.error('Error parsing SSE:', err); }
            }
          }
        }
      }
    } catch {
      setMessages((prev) => {
        const updated = [...prev];
        const lastMsg = { ...updated[updated.length - 1] };
        lastMsg.content = 'Error connecting to backend.';
        lastMsg.isStreaming = false;
        updated[updated.length - 1] = lastMsg;
        setChats(cPrev => cPrev.map(c => c.id === currentChatId ? { ...c, messages: updated } : c));
        return updated;
      });
    } finally { setIsLoading(false); }
  };

  const sortedChats = [...chats].sort((a, b) => (a.pinned === b.pinned ? b.createdAt - a.createdAt : a.pinned ? -1 : 1));

  return (
    <div className="flex h-screen w-full overflow-hidden bg-neutral-50 dark:bg-neutral-950 text-neutral-800 dark:text-neutral-200 font-sans transition-colors duration-300 relative">
      
      {/* BACKDROP FOR MOBILE */}
      <AnimatePresence>
        {sidebarOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setSidebarOpen(false)}
            className="fixed inset-0 z-[60] bg-black/40 backdrop-blur-sm lg:hidden"
          />
        )}
      </AnimatePresence>

      {/* FLOATING SIDEBAR */}
      <AnimatePresence>
        {sidebarOpen && (
          <motion.aside
            ref={sidebarRef}
            initial={{ x: '-100%', opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: '-100%', opacity: 0 }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="fixed inset-y-3 left-3 z-[70] flex w-72 flex-col rounded-[2rem] border border-neutral-200 dark:border-white/[0.08] bg-white dark:bg-[#0a0a0a] shadow-2xl shadow-black/10 dark:shadow-black/80 overflow-hidden"
          >
            <div className="flex items-center justify-between p-4 pb-2">
              <span className="font-semibold text-sm text-neutral-900 dark:text-neutral-100">Chats</span>
              <div className="flex items-center gap-1">
                <button onClick={startNewChat} className="p-1.5 hover:bg-neutral-100 dark:hover:bg-white/[0.06] rounded-lg text-neutral-500 dark:text-neutral-400 transition-colors" title="New Chat">
                  <Plus className="w-4 h-4" />
                </button>
                <button onClick={() => setSidebarOpen(false)} className="p-1.5 hover:bg-neutral-100 dark:hover:bg-white/[0.06] rounded-lg text-neutral-500 dark:text-neutral-400 transition-colors" title="Close Sidebar">
                  <PanelLeftClose className="w-4 h-4" />
                </button>
              </div>
            </div>
            
            
            <div className="flex-1 overflow-y-auto p-2 space-y-1 scrollbar-thin">
              {sortedChats.length === 0 ? (
                <div className="text-xs text-center text-neutral-500 py-4 mt-4">No chats yet.</div>
              ) : (
                sortedChats.map(chat => (
                  <div 
                    key={chat.id}
                    onClick={() => selectChat(chat.id)}
                    className={`group flex items-center justify-between px-3 py-2.5 rounded-xl cursor-pointer transition-colors ${activeChatId === chat.id ? 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300' : 'hover:bg-neutral-100 dark:hover:bg-white/[0.04] text-neutral-700 dark:text-neutral-300'}`}
                  >
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      {chat.pinned && <Pin className="w-3 h-3 text-emerald-500 shrink-0" />}
                      {editingChatId === chat.id ? (
                        <input
                          type="text"
                          value={editTitle}
                          onChange={(e) => setEditTitle(e.target.value)}
                          onBlur={() => saveRename(chat.id)}
                          onKeyDown={(e) => e.key === 'Enter' && saveRename(chat.id)}
                          autoFocus
                          className="w-full bg-transparent outline-none border-b border-emerald-500 text-sm"
                          onClick={(e) => e.stopPropagation()}
                        />
                      ) : (
                        <span className="text-sm truncate">{chat.title}</span>
                      )}
                    </div>
                    {editingChatId !== chat.id && (
                      <div className="relative opacity-0 group-hover:opacity-100 transition-opacity">
                        <button onClick={(e) => { e.stopPropagation(); setChatMenuOpenId(chatMenuOpenId === chat.id ? null : chat.id); }} className="p-1 hover:bg-neutral-200 dark:hover:bg-neutral-700 rounded-md">
                          <MoreVertical className="w-3.5 h-3.5" />
                        </button>
                        {chatMenuOpenId === chat.id && (
                          <div className="absolute right-0 top-full mt-1 w-32 bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 rounded-lg shadow-xl z-50 overflow-hidden py-1">
                            <button onClick={(e) => togglePin(chat.id, e)} className="w-full text-left px-3 py-1.5 text-xs hover:bg-neutral-100 dark:hover:bg-neutral-700 flex items-center gap-2">
                              <Pin className="w-3 h-3" /> {chat.pinned ? 'Unpin' : 'Pin'}
                            </button>
                            <button onClick={(e) => startRename(chat.id, chat.title, e)} className="w-full text-left px-3 py-1.5 text-xs hover:bg-neutral-100 dark:hover:bg-neutral-700 flex items-center gap-2">
                              <Edit2 className="w-3 h-3" /> Rename
                            </button>
                            <button onClick={(e) => deleteChat(chat.id, e)} className="w-full text-left px-3 py-1.5 text-xs text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 flex items-center gap-2">
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

      {/* MAIN CONTENT */}
      <div className="flex flex-col h-full flex-1 overflow-hidden transition-all duration-300">
        <header className="h-16 border-b border-neutral-200 dark:border-neutral-800/50 flex items-center justify-between px-6 bg-white/80 dark:bg-neutral-950/80 backdrop-blur-xl z-20 shrink-0">
          <div className="flex items-center gap-3">
            {!sidebarOpen && (
              <button onClick={() => setSidebarOpen(true)} className="p-2 -ml-2 rounded-lg text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors">
                <PanelLeftOpen className="w-5 h-5" />
              </button>
            )}
            <div className="w-8 h-8 bg-gradient-to-br from-emerald-400 to-emerald-600 rounded-xl flex items-center justify-center shadow-lg shadow-emerald-500/20">
              <Layers className="w-4 h-4 text-white" />
            </div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-neutral-900 to-neutral-600 dark:from-white dark:to-neutral-400 hidden sm:block">
                RAG Evals
              </h1>
              <span className="hidden sm:inline-block px-1.5 py-0.5 rounded-md bg-emerald-50 dark:bg-emerald-500/10 text-[10px] font-mono font-semibold text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/20">
                v0.1.0
              </span>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <nav className="flex items-center p-1.5 bg-neutral-100/80 dark:bg-neutral-900/80 backdrop-blur-md rounded-full border border-neutral-200 dark:border-neutral-800 shadow-inner">
              <button onClick={() => setActiveTab('chat')} className={`flex items-center gap-2 px-6 py-2 text-sm font-medium rounded-full transition-all duration-300 ease-out ${activeTab === 'chat' ? 'bg-white dark:bg-neutral-800 text-neutral-900 dark:text-white shadow-sm ring-1 ring-black/5 dark:ring-white/10' : 'text-neutral-500 dark:text-neutral-400 hover:text-neutral-800 dark:hover:text-neutral-200 hover:bg-neutral-200/50 dark:hover:bg-neutral-800/50'}`}>
                <MessageSquare className="w-4 h-4" /> Chat
              </button>
              <button onClick={() => setActiveTab('ingest')} className={`flex items-center gap-2 px-6 py-2 text-sm font-medium rounded-full transition-all duration-300 ease-out ${activeTab === 'ingest' ? 'bg-white dark:bg-neutral-800 text-neutral-900 dark:text-white shadow-sm ring-1 ring-black/5 dark:ring-white/10' : 'text-neutral-500 dark:text-neutral-400 hover:text-neutral-800 dark:hover:text-neutral-200 hover:bg-neutral-200/50 dark:hover:bg-neutral-800/50'}`}>
                <Database className="w-4 h-4" /> Knowledge Base
              </button>
            </nav>
            <UserMenu />
          </div>
        </header>

        <main className="flex-1 relative overflow-hidden flex flex-col">
          {activeTab === 'chat' && (
            <div className="flex-1 flex flex-col h-full animate-in fade-in duration-300">
              <div className="flex-1 overflow-y-auto w-full">
                <div className="max-w-4xl mx-auto p-4 sm:p-8 min-h-full flex flex-col">
                  {messages.length === 0 ? (
                    <div className="flex flex-col items-center justify-center flex-1 text-center space-y-8 animate-in fade-in zoom-in-95 duration-500">
                      <div className="space-y-3">
                        <div className="w-20 h-20 bg-gradient-to-br from-emerald-500/20 to-emerald-900/10 rounded-3xl flex items-center justify-center border border-emerald-500/20 mx-auto shadow-2xl shadow-emerald-500/10">
                          <Sparkles className="w-10 h-10 text-emerald-500 dark:text-emerald-400" />
                        </div>
                        <h2 className="text-3xl font-bold text-neutral-900 dark:text-neutral-100 tracking-tight">How can I help you today?</h2>
                        <p className="text-neutral-500 text-sm">Ask anything about your ingested documents.</p>
                      </div>
                      
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-2xl">
                        <button onClick={() => setInput("Summarize the key points of my documents.")} className="p-4 bg-white dark:bg-neutral-900/50 hover:bg-neutral-50 dark:hover:bg-neutral-800 border border-neutral-200 dark:border-neutral-800 rounded-xl text-left transition-all group shadow-sm">
                          <p className="text-sm font-medium text-neutral-700 dark:text-neutral-300 group-hover:text-neutral-900 dark:group-hover:text-white">Summarize documents</p>
                          <p className="text-xs text-neutral-500 mt-1">Get a quick TL;DR</p>
                        </button>
                        <button onClick={() => setInput("What are the main policies mentioned?")} className="p-4 bg-white dark:bg-neutral-900/50 hover:bg-neutral-50 dark:hover:bg-neutral-800 border border-neutral-200 dark:border-neutral-800 rounded-xl text-left transition-all group shadow-sm">
                          <p className="text-sm font-medium text-neutral-700 dark:text-neutral-300 group-hover:text-neutral-900 dark:group-hover:text-white">Find specific policies</p>
                          <p className="text-xs text-neutral-500 mt-1">Extract rules and guidelines</p>
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-6">
                      {messages.map((msg, i) => {
                        const isUser = msg.role === 'user';
                        const isThinking = !isUser && msg.content === '' && msg.isStreaming;
                        const isExpanded = expandedSources[i];
                        return (
                          <div key={i} className={`flex gap-4 ${isUser ? 'justify-end' : 'justify-start'} animate-in fade-in slide-in-from-bottom-2 duration-300`}>
                            {!isUser && (
                              <div className="w-8 h-8 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center shrink-0 mt-0.5">
                                <Layers className="w-4 h-4 text-emerald-500 dark:text-emerald-400" />
                              </div>
                            )}
                            <div className={`max-w-[90%] ${isUser ? 'bg-emerald-600 text-white rounded-2xl rounded-tr-sm px-5 py-3 shadow-md' : 'bg-transparent text-neutral-800 dark:text-neutral-200'}`}>
                              {!isUser ? (
                                <div className="group relative">
                                  {!msg.isStreaming && msg.content && (
                                    <div className="absolute -right-10 top-0 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col gap-2">
                                      <button onClick={() => handleCopy(msg.content, i)} className="p-1.5 text-neutral-500 hover:text-emerald-500 bg-white dark:bg-neutral-900 rounded-md border border-neutral-200 dark:border-neutral-800 transition-colors shadow-sm" title="Copy to clipboard">
                                        {copiedIndex === i ? <Check className="w-4 h-4 text-emerald-500" /> : <Copy className="w-4 h-4" />}
                                      </button>
                                    </div>
                                  )}
                                  <div className="prose dark:prose-invert prose-sm max-w-none prose-p:leading-relaxed prose-pre:bg-neutral-100 dark:prose-pre:bg-neutral-950 prose-pre:border prose-pre:border-neutral-200 dark:prose-pre:border-neutral-800 prose-table:w-full prose-table:border-collapse">
                                    {isThinking ? (
                                      <div className="flex items-center gap-2 h-6 text-sm text-emerald-500 dark:text-emerald-400 font-medium">
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                        <span className="animate-pulse">Searching knowledge base...</span>
                                      </div>
                                    ) : (
                                      <>
                                        <ReactMarkdown 
                                          remarkPlugins={[remarkGfm]}
                                          components={{
                                            table: ({...props}) => (
                                              <div className="overflow-x-auto my-6 rounded-lg border border-neutral-200 dark:border-neutral-800">
                                                <table className="min-w-full divide-y divide-neutral-200 dark:divide-neutral-800" {...props} />
                                              </div>
                                            ),
                                            thead: ({...props}) => <thead className="bg-neutral-100 dark:bg-neutral-900/50" {...props} />,
                                            th: ({...props}) => <th className="px-4 py-3 text-left text-xs font-semibold text-neutral-900 dark:text-neutral-100 uppercase tracking-wider" {...props} />,
                                            td: ({...props}) => <td className="px-4 py-3 text-sm text-neutral-700 dark:text-neutral-300 border-t border-neutral-200 dark:border-neutral-800" {...props} />,
                                            a: ({...props}) => <a className="text-emerald-600 dark:text-emerald-400 hover:underline font-medium" target="_blank" rel="noopener noreferrer" {...props} />
                                          }}
                                        >
                                          {msg.content}
                                        </ReactMarkdown>
                                        {msg.isStreaming && <span className="inline-block w-1.5 h-4 ml-1 bg-emerald-500 dark:bg-emerald-400 animate-pulse align-middle" />}
                                      </>
                                    )}
                                  </div>
                                  {msg.chunks && msg.chunks.length > 0 && (
                                    <div className="mt-4 border border-neutral-200 dark:border-neutral-800 rounded-xl overflow-hidden bg-neutral-100 dark:bg-neutral-900/30">
                                      <button onClick={() => toggleSource(i)} className="w-full flex items-center justify-between px-4 py-2.5 bg-neutral-50 dark:bg-neutral-900/50 hover:bg-neutral-100 dark:hover:bg-neutral-800/50 transition-colors text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">
                                        <span className="flex items-center gap-2"><Database className="w-3.5 h-3.5 text-emerald-500" />{msg.chunks.length} Sources Retrieved</span>
                                        {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                                      </button>
                                      {isExpanded && (
                                        <div className="p-3 space-y-2 border-t border-neutral-200 dark:border-neutral-800/50 bg-white dark:bg-neutral-950/50">
                                          {msg.chunks.map((chunk, j) => (
                                            <div key={j} className="text-xs bg-neutral-50 dark:bg-neutral-900 p-3 rounded-lg border border-neutral-200 dark:border-neutral-800 text-neutral-600 dark:text-neutral-400">
                                              <span className="inline-block px-1.5 py-0.5 bg-neutral-200 dark:bg-neutral-800 text-emerald-600 dark:text-emerald-400 rounded text-[10px] font-bold mb-2">Chunk {j + 1}</span>
                                              <p className="whitespace-pre-wrap">{chunk.content}</p>
                                            </div>
                                          ))}
                                        </div>
                                      )}
                                    </div>
                                  )}
                                </div>
                              ) : (
                                <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                              )}
                            </div>
                            {isUser && (<div className="w-8 h-8 rounded-full bg-neutral-200 dark:bg-neutral-800 flex items-center justify-center shrink-0 mt-0.5"><User className="w-5 h-5 text-neutral-600 dark:text-neutral-400" /></div>)}
                          </div>
                        );
                      })}
                    </div>
                  )}
                  <div ref={messagesEndRef} className="h-4" />
                </div>
              </div>
              <footer className="p-4 border-t border-neutral-200 dark:border-neutral-800/50 bg-white dark:bg-neutral-950 shrink-0">
                <div className="w-full max-w-4xl mx-auto">
                  <form onSubmit={sendMessage} className="relative flex items-end gap-2 bg-white dark:bg-neutral-900 border border-neutral-300 dark:border-neutral-700 rounded-2xl p-2 focus-within:ring-2 focus-within:ring-emerald-500/50 focus-within:border-emerald-500 transition-all shadow-sm">
                    <textarea 
                      value={input} 
                      onChange={(e) => setInput(e.target.value)} 
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault();
                          sendMessage(e);
                        }
                      }}
                      placeholder="Message RAG Evals..." 
                      rows={1}
                      className="w-full max-h-32 bg-transparent text-sm text-neutral-900 dark:text-neutral-100 placeholder-neutral-500 px-3 py-2.5 resize-none focus:outline-none" 
                      style={{ minHeight: '44px' }}
                    />
                    <button type="submit" disabled={isLoading || !input.trim()} className="p-2.5 mb-0.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl transition-all disabled:opacity-50 disabled:bg-neutral-200 dark:disabled:bg-neutral-800 disabled:text-neutral-500 shrink-0 shadow-sm"><Send className="w-4 h-4" /></button>
                  </form>
                  <p className="text-center text-[10px] text-neutral-500 mt-2">RAG Evals can make mistakes. Consider verifying important information.</p>
                </div>
              </footer>
            </div>
          )}
          {activeTab === 'ingest' && (
            <div className="flex-1 overflow-y-auto p-8 animate-in fade-in duration-300">
              <div className="max-w-2xl mx-auto space-y-8">
                <div>
                  <h2 className="text-2xl font-bold text-neutral-900 dark:text-neutral-100">Knowledge Base</h2>
                  <p className="text-sm text-neutral-500 mt-1">Upload documents or paste text to expand the AI&apos;s knowledge.</p>
                </div>
                <div className="bg-white dark:bg-neutral-900/50 border border-neutral-200 dark:border-neutral-800 rounded-2xl p-6 shadow-sm">
                  <div className="flex items-center p-1.5 bg-neutral-100 dark:bg-neutral-950/80 rounded-full border border-neutral-200 dark:border-neutral-800 mb-6 shadow-inner">
                    <button onClick={() => setIngestMode('text')} className={`flex-1 flex items-center justify-center gap-2 py-2.5 text-sm font-medium rounded-full transition-all duration-300 ease-out ${ingestMode === 'text' ? 'bg-white dark:bg-neutral-800 text-neutral-900 dark:text-white shadow-sm ring-1 ring-black/5 dark:ring-white/10' : 'text-neutral-500 dark:text-neutral-400 hover:text-neutral-800 dark:hover:text-neutral-200 hover:bg-neutral-200/50 dark:hover:bg-neutral-800/50'}`}><Type className="w-4 h-4" /> Paste Text</button>
                    <button onClick={() => setIngestMode('file')} className={`flex-1 flex items-center justify-center gap-2 py-2.5 text-sm font-medium rounded-full transition-all duration-300 ease-out ${ingestMode === 'file' ? 'bg-white dark:bg-neutral-800 text-neutral-900 dark:text-white shadow-sm ring-1 ring-black/5 dark:ring-white/10' : 'text-neutral-500 dark:text-neutral-400 hover:text-neutral-800 dark:hover:text-neutral-200 hover:bg-neutral-200/50 dark:hover:bg-neutral-800/50'}`}><UploadCloud className="w-4 h-4" /> Upload Files</button>
                  </div>
                  <form onSubmit={handleIngest} className="flex flex-col gap-5">
                    <div>
                      <label className="block text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider mb-2">Document Title</label>
                      <input type="text" value={docTitle} onChange={(e) => setDocTitle(e.target.value)} placeholder="e.g., Company Handbook" className="w-full bg-neutral-50 dark:bg-neutral-950 border border-neutral-300 dark:border-neutral-800 rounded-xl py-3 px-4 text-sm text-neutral-900 dark:text-neutral-100 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500 transition-all" />
                    </div>
                    {ingestMode === 'text' ? (
                      <div>
                        <div className="flex justify-between items-end mb-2">
                          <label className="block text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Text Content</label>
                          <span className={`text-[10px] font-mono ${docText.length > 0 && docText.length < 10 ? 'text-red-500' : 'text-neutral-500'}`}>{docText.length}/10 chars</span>
                        </div>
                        <textarea value={docText} onChange={(e) => setDocText(e.target.value)} placeholder="Paste your text here..." className="w-full h-48 bg-neutral-50 dark:bg-neutral-950 border border-neutral-300 dark:border-neutral-800 rounded-xl py-3 px-4 text-sm text-neutral-900 dark:text-neutral-100 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500 resize-none transition-all" />
                      </div>
                    ) : (
                      <div>
                        <label className="block text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider mb-2">Upload File</label>
                        <div className="h-48 border-2 border-dashed border-neutral-300 dark:border-neutral-800 hover:border-emerald-500/50 rounded-xl flex flex-col items-center justify-center p-6 cursor-pointer bg-neutral-50 dark:bg-neutral-950/50 transition-all group" onClick={() => fileInputRef.current?.click()}>
                          <input type="file" ref={fileInputRef} onChange={handleFileChange} accept=".pdf,.txt,.md,.png,.jpg,.jpeg,.webp" className="hidden" />
                          {file ? (
                            <div className="text-center">
                              <div className="w-12 h-12 bg-emerald-500/10 rounded-full flex items-center justify-center mx-auto mb-3"><FileText className="w-6 h-6 text-emerald-500 dark:text-emerald-400" /></div>
                              <p className="text-sm font-medium text-neutral-900 dark:text-neutral-200">{file.name}</p>
                              <p className="text-xs text-neutral-500 mt-1">{(file.size / 1024).toFixed(1)} KB</p>
                            </div>
                          ) : (
                            <div className="text-center text-neutral-500 group-hover:text-neutral-700 dark:group-hover:text-neutral-400 transition-colors">
                              <UploadCloud className="w-10 h-10 mx-auto mb-3 opacity-50 group-hover:opacity-100 transition-opacity" />
                              <p className="text-sm font-medium">Click to select a file</p>
                              <p className="text-xs mt-1 opacity-70">PDF, TXT, MD, PNG, JPG</p>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                    <button type="submit" disabled={isIngesting || !docTitle.trim() || (ingestMode === 'text' ? docText.trim().length < 10 : !file)} className="flex items-center justify-center gap-2 w-full bg-emerald-600 hover:bg-emerald-500 text-white py-3 rounded-xl font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-emerald-900/20 mt-2">
                      {isIngesting ? <Loader2 className="w-5 h-5 animate-spin" /> : <Sparkles className="w-5 h-5" />}
                      {isIngesting ? 'Ingesting...' : 'Ingest Document'}
                    </button>
                    {ingestStatus && (<div className={`p-3 rounded-lg text-xs text-center font-medium ${ingestStatus.includes('Error') ? 'bg-red-500/10 text-red-500 dark:text-red-400 border border-red-500/20' : 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20'}`}>{ingestStatus}</div>)}
                  </form>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}







