'use client';

import { useState, useRef, useEffect } from 'react';
import { Send, Loader2, Bot, User, Database, UploadCloud, FileText, Type, Sparkles, Terminal, MessageSquare, Copy, Check, Plus, ChevronDown, ChevronUp } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

type Chunk = { id: string; content: string; metadata: Record<string, unknown> };
type Message = { role: 'user' | 'assistant'; content: string; chunks?: Chunk[]; isStreaming?: boolean };

export default function Home() {
  const [activeTab, setActiveTab] = useState<'chat' | 'ingest'>('chat');
  
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const [expandedSources, setExpandedSources] = useState<Record<number, boolean>>({});

  // Ingest State
  const [ingestMode, setIngestMode] = useState<'text' | 'file'>('text');
  const [docTitle, setDocTitle] = useState('');
  const [docText, setDocText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isIngesting, setIsIngesting] = useState(false);
  const [ingestStatus, setIngestStatus] = useState('');

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (activeTab === 'chat') {
      scrollToBottom();
    }
  }, [messages, activeTab]);

  const handleCopy = (text: string, index: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const toggleSource = (msgIndex: number) => {
    setExpandedSources(prev => ({ ...prev, [msgIndex]: !prev[msgIndex] }));
  };

  const clearChat = () => {
    setMessages([]);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
      if (!docTitle) {
        setDocTitle(e.target.files[0].name.split('.')[0]);
      }
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
        res = await fetch('/api/seed', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: docTitle, text: docText }),
        });
      } else {
        if (!file) throw new Error('Please select a file.');
        const formData = new FormData();
        formData.append('file', file);
        formData.append('title', docTitle);
        res = await fetch('/api/seed', {
          method: 'POST',
          body: formData,
        });
      }
      
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to ingest');
      
      setIngestStatus('Successfully added!');
      setDocTitle('');
      setDocText('');
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      setTimeout(() => setIngestStatus(''), 3000);
    } catch (err) {
      setIngestStatus(`Error: ${err instanceof Error ? err.message : 'Failed'}`);
    } finally {
      setIsIngesting(false);
    }
  };

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMsg: Message = { role: 'user', content: input };
    const currentInput = input;
    
    setMessages((prev) => [
      ...prev, 
      userMsg, 
      { role: 'assistant', content: '', isStreaming: true }
    ]);
    
    setInput('');
    setIsLoading(true);

    try {
      const res = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: currentInput, top_k: 3 }),
      });

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
                  const newMessages = [...prev];
                  const lastMsg = { ...newMessages[newMessages.length - 1] };
                  
                  if (data.type === 'sources') {
                    lastMsg.chunks = data.sources;
                  } else if (data.type === 'token') {
                    lastMsg.content = (lastMsg.content || '') + data.text;
                  } else if (data.type === 'done') {
                    lastMsg.isStreaming = false;
                  }
                  
                  newMessages[newMessages.length - 1] = lastMsg;
                  return newMessages;
                });
              } catch (err) {
                console.error('Error parsing SSE:', err);
              }
            }
          }
        }
      }
    } catch (err) {
      setMessages((prev) => {
        const newMessages = [...prev];
        const lastMsg = { ...newMessages[newMessages.length - 1] };
        lastMsg.content = 'Error connecting to backend.';
        lastMsg.isStreaming = false;
        newMessages[newMessages.length - 1] = lastMsg;
        return newMessages;
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-neutral-950 text-neutral-200 overflow-hidden font-sans">
      
      {/* GLOBAL HEADER */}
      <header className="h-16 border-b border-neutral-800/50 flex items-center justify-between px-6 bg-neutral-950/80 backdrop-blur-xl z-20 shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-emerald-500/10 rounded-lg flex items-center justify-center border border-emerald-500/20">
            <Bot className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-neutral-100 flex items-center gap-2">
              RAG Evals
              <span className="px-1.5 py-0.5 rounded-md bg-neutral-900 text-[10px] font-mono text-neutral-400 border border-neutral-800">v0.1.0</span>
            </h1>
          </div>
        </div>

        {/* NAVIGATION TABS & ACTIONS */}
        <div className="flex items-center gap-4">
          {activeTab === 'chat' && messages.length > 0 && (
            <button
              onClick={clearChat}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-neutral-400 hover:text-white bg-neutral-900 hover:bg-neutral-800 rounded-lg transition-colors border border-neutral-800"
            >
              <Plus className="w-3.5 h-3.5" /> New Chat
            </button>
          )}

          <nav className="flex items-center gap-1 p-1 bg-neutral-900/50 rounded-lg border border-neutral-800/50">
            <button
              onClick={() => setActiveTab('chat')}
              className={`flex items-center gap-2 px-4 py-1.5 text-sm font-medium rounded-md transition-all ${activeTab === 'chat' ? 'bg-neutral-800 text-white shadow-sm' : 'text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800/50'}`}
            >
              <MessageSquare className="w-4 h-4" /> Chat
            </button>
            <button
              onClick={() => setActiveTab('ingest')}
              className={`flex items-center gap-2 px-4 py-1.5 text-sm font-medium rounded-md transition-all ${activeTab === 'ingest' ? 'bg-neutral-800 text-white shadow-sm' : 'text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800/50'}`}
            >
              <Database className="w-4 h-4" /> Knowledge Base
            </button>
          </nav>
        </div>
      </header>

      {/* MAIN CONTENT AREA */}
      <main className="flex-1 relative overflow-hidden flex flex-col">
        
        {/* CHAT VIEW */}
        {activeTab === 'chat' && (
          <div className="flex-1 flex flex-col h-full animate-in fade-in duration-300">
            {/* Removed max-w-3xl constraint here to allow full width */}
            <div className="flex-1 overflow-y-auto p-4 sm:p-8 w-full">
              {messages.length === 0 && (
                <div className="flex flex-col items-center justify-center h-full text-center space-y-4 opacity-50">
                  <div className="w-16 h-16 bg-neutral-900 rounded-2xl flex items-center justify-center border border-neutral-800">
                    <Terminal className="w-8 h-8 text-neutral-400" />
                  </div>
                  <div>
                    <p className="text-lg font-medium text-neutral-300">Ready to query</p>
                    <p className="text-sm text-neutral-500 mt-1">Ask a question about your knowledge base.</p>
                  </div>
                </div>
              )}
              
              <div className="space-y-6">
                {messages.map((msg, i) => {
                  const isUser = msg.role === 'user';
                  const isThinking = !isUser && msg.content === '' && msg.isStreaming;
                  const isExpanded = expandedSources[i];

                  return (
                    <div key={i} className={`flex gap-4 ${isUser ? 'justify-end' : 'justify-start'} animate-in fade-in slide-in-from-bottom-2 duration-300`}>
                      {!isUser && (
                        <div className="w-8 h-8 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center shrink-0 mt-0.5">
                          <Bot className="w-5 h-5 text-emerald-400" />
                        </div>
                      )}
                      
                      {/* Increased max-w-[85%] to max-w-[90%] for full-screen feel */}
                      <div className={`max-w-[90%] ${
                        isUser 
                          ? 'bg-emerald-600 text-white rounded-2xl rounded-tr-sm px-5 py-3 shadow-md' 
                          : 'bg-transparent text-neutral-200'
                      }`}>
                        {!isUser ? (
                          <div className="group relative">
                            {/* Action Buttons */}
                            {!msg.isStreaming && msg.content && (
                              <div className="absolute -right-10 top-0 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col gap-2">
                                <button
                                  onClick={() => handleCopy(msg.content, i)}
                                  className="p-1.5 text-neutral-500 hover:text-emerald-400 bg-neutral-900 rounded-md border border-neutral-800 transition-colors"
                                  title="Copy to clipboard"
                                >
                                  {copiedIndex === i ? <Check className="w-4 h-4 text-emerald-500" /> : <Copy className="w-4 h-4" />}
                                </button>
                              </div>
                            )}

                            <div className="prose prose-invert prose-sm max-w-none prose-p:leading-relaxed prose-pre:bg-neutral-950 prose-pre:border prose-pre:border-neutral-800">
                              {isThinking ? (
                                <div className="flex items-center gap-1.5 h-6">
                                  <span className="w-2 h-2 bg-emerald-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                                  <span className="w-2 h-2 bg-emerald-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                                  <span className="w-2 h-2 bg-emerald-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                                </div>
                              ) : (
                                <>
                                  <ReactMarkdown>{msg.content}</ReactMarkdown>
                                  {msg.isStreaming && <span className="inline-block w-1.5 h-4 ml-1 bg-emerald-400 animate-pulse align-middle" />}
                                </>
                              )}
                            </div>
                            
                            {/* Sources Accordion */}
                            {msg.chunks && msg.chunks.length > 0 && (
                              <div className="mt-4 border border-neutral-800 rounded-xl overflow-hidden bg-neutral-900/30">
                                <button
                                  onClick={() => toggleSource(i)}
                                  className="w-full flex items-center justify-between px-4 py-2.5 bg-neutral-900/50 hover:bg-neutral-800/50 transition-colors text-xs font-semibold text-neutral-400 uppercase tracking-wider"
                                >
                                  <span className="flex items-center gap-2">
                                    <Database className="w-3.5 h-3.5 text-emerald-500" />
                                    {msg.chunks.length} Sources Retrieved
                                  </span>
                                  {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                                </button>
                                
                                {isExpanded && (
                                  <div className="p-3 space-y-2 border-t border-neutral-800/50 bg-neutral-950/50">
                                    {msg.chunks.map((chunk, j) => (
                                      <div key={j} className="text-xs bg-neutral-900 p-3 rounded-lg border border-neutral-800 text-neutral-400">
                                        <span className="inline-block px-1.5 py-0.5 bg-neutral-800 text-emerald-400 rounded text-[10px] font-bold mb-2">
                                          Chunk {j + 1}
                                        </span>
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
                      
                      {isUser && (
                        <div className="w-8 h-8 rounded-full bg-neutral-800 flex items-center justify-center shrink-0 mt-0.5">
                          <User className="w-5 h-5 text-neutral-400" />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
              <div ref={messagesEndRef} className="h-4" />
            </div>

            <footer className="p-4 border-t border-neutral-800/50 bg-neutral-950/80 backdrop-blur-lg shrink-0">
              <div className="w-full"> {/* Removed max-w-3xl constraint here too */}
                <form onSubmit={sendMessage} className="relative flex items-center">
                  <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Ask a question..."
                    className="w-full bg-neutral-900 border border-neutral-800 rounded-2xl py-4 pl-5 pr-14 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500 transition-all shadow-inner"
                  />
                  <button
                    type="submit"
                    disabled={isLoading || !input.trim()}
                    className="absolute right-2 p-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-md"
                  >
                    <Send className="w-4 h-4" />
                  </button>
                </form>
                <p className="text-center text-[10px] text-neutral-600 mt-2">
                  RAG Evals can make mistakes. Consider verifying important information.
                </p>
              </div>
            </footer>
          </div>
        )}

        {/* INGEST VIEW */}
        {activeTab === 'ingest' && (
          <div className="flex-1 overflow-y-auto p-8 animate-in fade-in duration-300">
            {/* Kept max-w-2xl here so the form doesn't look absurdly stretched out on ultrawide monitors */}
            <div className="max-w-2xl mx-auto space-y-8">
              <div>
                <h2 className="text-2xl font-bold text-neutral-100">Knowledge Base</h2>
                <p className="text-sm text-neutral-400 mt-1">Upload documents or paste text to expand the AI's knowledge.</p>
              </div>

              <div className="bg-neutral-900/50 border border-neutral-800 rounded-2xl p-6 backdrop-blur-sm">
                <div className="flex p-1 bg-neutral-950 rounded-xl border border-neutral-800 mb-6">
                  <button
                    onClick={() => setIngestMode('text')}
                    className={`flex-1 flex items-center justify-center gap-2 py-2 text-sm font-medium rounded-lg transition-all ${ingestMode === 'text' ? 'bg-neutral-800 text-white shadow-sm' : 'text-neutral-400 hover:text-neutral-200'}`}
                  >
                    <Type className="w-4 h-4" /> Paste Text
                  </button>
                  <button
                    onClick={() => setIngestMode('file')}
                    className={`flex-1 flex items-center justify-center gap-2 py-2 text-sm font-medium rounded-lg transition-all ${ingestMode === 'file' ? 'bg-neutral-800 text-white shadow-sm' : 'text-neutral-400 hover:text-neutral-200'}`}
                  >
                    <UploadCloud className="w-4 h-4" /> Upload Files
                  </button>
                </div>

                <form onSubmit={handleIngest} className="flex flex-col gap-5">
                  <div>
                    <label className="block text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-2">Document Title</label>
                    <input
                      type="text"
                      value={docTitle}
                      onChange={(e) => setDocTitle(e.target.value)}
                      placeholder="e.g., Company Handbook"
                      className="w-full bg-neutral-950 border border-neutral-800 rounded-xl py-3 px-4 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500 transition-all"
                    />
                  </div>

                  {ingestMode === 'text' ? (
                    <div>
                      <div className="flex justify-between items-end mb-2">
                        <label className="block text-xs font-semibold text-neutral-400 uppercase tracking-wider">Text Content</label>
                        <span className={`text-[10px] font-mono ${docText.length > 0 && docText.length < 10 ? 'text-red-400' : 'text-neutral-500'}`}>
                          {docText.length}/10 chars
                        </span>
                      </div>
                      <textarea
                        value={docText}
                        onChange={(e) => setDocText(e.target.value)}
                        placeholder="Paste your text here..."
                        className="w-full h-48 bg-neutral-950 border border-neutral-800 rounded-xl py-3 px-4 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500 resize-none transition-all"
                      />
                    </div>
                  ) : (
                    <div>
                      <label className="block text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-2">Upload File</label>
                      <div 
                        className="h-48 border-2 border-dashed border-neutral-800 hover:border-emerald-500/50 rounded-xl flex flex-col items-center justify-center p-6 cursor-pointer bg-neutral-950/50 transition-all group"
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
                            <div className="w-12 h-12 bg-emerald-500/10 rounded-full flex items-center justify-center mx-auto mb-3">
                              <FileText className="w-6 h-6 text-emerald-400" />
                            </div>
                            <p className="text-sm font-medium text-neutral-200">{file.name}</p>
                            <p className="text-xs text-neutral-500 mt-1">{(file.size / 1024).toFixed(1)} KB</p>
                          </div>
                        ) : (
                          <div className="text-center text-neutral-500 group-hover:text-neutral-400 transition-colors">
                            <UploadCloud className="w-10 h-10 mx-auto mb-3 opacity-50 group-hover:opacity-100 transition-opacity" />
                            <p className="text-sm font-medium">Click to select a file</p>
                            <p className="text-xs mt-1 opacity-70">PDF, TXT, MD, PNG, JPG</p>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  <button
                    type="submit"
                    disabled={isIngesting || !docTitle.trim() || (ingestMode === 'text' ? docText.trim().length < 10 : !file)}
                    className="flex items-center justify-center gap-2 w-full bg-emerald-600 hover:bg-emerald-500 text-white py-3 rounded-xl font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-emerald-900/20 mt-2"
                  >
                    {isIngesting ? <Loader2 className="w-5 h-5 animate-spin" /> : <Sparkles className="w-5 h-5" />}
                    {isIngesting ? 'Ingesting...' : 'Ingest Document'}
                  </button>
                  
                  {ingestStatus && (
                    <div className={`p-3 rounded-lg text-xs text-center font-medium ${ingestStatus.includes('Error') ? 'bg-red-500/10 text-red-400 border border-red-500/20' : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'}`}>
                      {ingestStatus}
                    </div>
                  )}
                </form>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
