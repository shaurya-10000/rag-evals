'use client';

import { useState, useRef, useEffect } from 'react';
import { Send, Loader2, Bot, User, Database, UploadCloud, FileText, Type } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

type Chunk = { id: string; content: string; metadata: Record<string, unknown> };
type Message = { role: 'user' | 'assistant'; content: string; chunks?: Chunk[]; isStreaming?: boolean };

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

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
    scrollToBottom();
  }, [messages]);

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
    <div className="flex h-screen bg-neutral-950 text-neutral-200">
      
      {/* LEFT SIDEBAR */}
      <aside className="w-1/3 min-w-[350px] border-r border-neutral-800 flex flex-col bg-neutral-900/50">
        <div className="p-4 border-b border-neutral-800 flex items-center gap-2">
          <Database className="w-5 h-5 text-emerald-400" />
          <h2 className="font-bold text-lg">Knowledge Base</h2>
        </div>
        
        <div className="p-4 flex flex-col gap-4 flex-1">
          <div className="flex p-1 bg-neutral-950 rounded-lg border border-neutral-800">
            <button
              onClick={() => setIngestMode('text')}
              className={`flex-1 flex items-center justify-center gap-2 py-1.5 text-sm font-medium rounded-md transition-colors ${ingestMode === 'text' ? 'bg-neutral-800 text-white' : 'text-neutral-400 hover:text-neutral-200'}`}
            >
              <Type className="w-4 h-4" /> Text
            </button>
            <button
              onClick={() => setIngestMode('file')}
              className={`flex-1 flex items-center justify-center gap-2 py-1.5 text-sm font-medium rounded-md transition-colors ${ingestMode === 'file' ? 'bg-neutral-800 text-white' : 'text-neutral-400 hover:text-neutral-200'}`}
            >
              <UploadCloud className="w-4 h-4" /> Files
            </button>
          </div>

          <form onSubmit={handleIngest} className="flex flex-col gap-4 flex-1">
            <div>
              <label className="block text-xs font-semibold text-neutral-400 uppercase mb-1">Document Title</label>
              <input
                type="text"
                value={docTitle}
                onChange={(e) => setDocTitle(e.target.value)}
                placeholder="e.g., Company Handbook"
                className="w-full bg-neutral-950 border border-neutral-800 rounded-md py-2 px-3 text-sm focus:outline-none focus:border-emerald-500"
              />
            </div>

            {ingestMode === 'text' ? (
              <div className="flex-1 flex flex-col">
                <div className="flex justify-between items-end mb-1">
                  <label className="block text-xs font-semibold text-neutral-400 uppercase">Text Content</label>
                  <span className={`text-[10px] ${docText.length > 0 && docText.length < 10 ? 'text-red-400' : 'text-neutral-500'}`}>
                    {docText.length}/10 chars
                  </span>
                </div>
                <textarea
                  value={docText}
                  onChange={(e) => setDocText(e.target.value)}
                  placeholder="Paste your text here (min 10 chars)..."
                  className="w-full flex-1 bg-neutral-950 border border-neutral-800 rounded-md py-2 px-3 text-sm focus:outline-none focus:border-emerald-500 resize-none"
                />
              </div>
            ) : (
              <div className="flex-1 flex flex-col">
                <label className="block text-xs font-semibold text-neutral-400 uppercase mb-1">Upload File (.pdf, .txt, .md, .png, .jpg)</label>
                <div 
                  className="flex-1 border-2 border-dashed border-neutral-800 hover:border-emerald-500/50 rounded-md flex flex-col items-center justify-center p-6 cursor-pointer bg-neutral-950 transition-colors relative"
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
                      <FileText className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
                      <p className="text-sm font-medium text-neutral-200">{file.name}</p>
                      <p className="text-xs text-neutral-500">{(file.size / 1024).toFixed(1)} KB</p>
                    </div>
                  ) : (
                    <div className="text-center text-neutral-500">
                      <UploadCloud className="w-8 h-8 mx-auto mb-2 opacity-50" />
                      <p className="text-sm">Click to select a file</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            <button
              type="submit"
              disabled={isIngesting || !docTitle.trim() || (ingestMode === 'text' ? docText.trim().length < 10 : !file)}
              className="flex items-center justify-center gap-2 w-full bg-emerald-600 hover:bg-emerald-500 text-white py-2 rounded-md transition-colors disabled:opacity-50"
            >
              {isIngesting ? <Loader2 className="w-4 h-4 animate-spin" /> : (ingestMode === 'text' ? <Database className="w-4 h-4" /> : <UploadCloud className="w-4 h-4" />)}
              {isIngesting ? 'Ingesting...' : 'Ingest'}
            </button>
            
            {ingestStatus && (
              <p className={`text-xs text-center ${ingestStatus.includes('Error') ? 'text-red-400' : 'text-emerald-400'}`}>
                {ingestStatus}
              </p>
            )}
          </form>
        </div>
      </aside>

      {/* RIGHT SIDE: Chat */}
      <main className="flex-1 flex flex-col">
        <header className="p-4 border-b border-neutral-800 text-center">
          <h1 className="text-xl font-bold flex items-center justify-center gap-2">
            <Bot className="w-6 h-6 text-emerald-400" />
            RAG Evals Chat
          </h1>
        </header>

        <div className="flex-1 overflow-y-auto p-4 space-y-6 max-w-4xl mx-auto w-full">
          {messages.length === 0 && (
            <div className="text-center text-neutral-500 mt-20">
              <p>Ask a question about the documents in your knowledge base.</p>
            </div>
          )}
          
          {messages.map((msg, i) => {
            const isUser = msg.role === 'user';
            const rowClass = isUser ? 'flex gap-3 justify-end' : 'flex gap-3 justify-start';
            const bubbleClass = isUser 
              ? 'max-w-[80%] rounded-2xl p-4 bg-emerald-600 text-white' 
              : 'max-w-[80%] rounded-2xl p-4 bg-neutral-900 border border-neutral-800';

            // Show thinking dots if it's an assistant message with no content yet
            const isThinking = !isUser && msg.content === '' && msg.isStreaming;

            return (
              <div key={i} className={rowClass}>
                {!isUser && <Bot className="w-6 h-6 text-emerald-400 shrink-0 mt-1" />}
                
                <div className={bubbleClass}>
                  {!isUser ? (
                    <div className="prose prose-invert prose-sm">
                      {isThinking ? (
                        <div className="flex items-center gap-1 h-6">
                          <span className="w-2 h-2 bg-emerald-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                          <span className="w-2 h-2 bg-emerald-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                          <span className="w-2 h-2 bg-emerald-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                        </div>
                      ) : (
                        <>
                          <ReactMarkdown>{msg.content}</ReactMarkdown>
                          {msg.isStreaming && <span className="inline-block w-2 h-4 ml-1 bg-emerald-400 animate-pulse" />}
                        </>
                      )}
                    </div>
                  ) : (
                    <p>{msg.content}</p>
                  )}
                  
                  {msg.chunks && msg.chunks.length > 0 && (
                    <div className="mt-4 space-y-2">
                      <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">Sources</p>
                      {msg.chunks.map((chunk, j) => (
                        <div key={j} className="text-xs bg-neutral-950 p-2 rounded border border-neutral-800 text-neutral-400">
                          <span className="text-emerald-500 font-bold mr-1">[{j + 1}]</span>
                          {chunk.content}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                
                {isUser && <User className="w-6 h-6 text-neutral-400 shrink-0 mt-1" />}
              </div>
            );
          })}
          <div ref={messagesEndRef} />
        </div>

        <footer className="p-4 border-t border-neutral-800 max-w-4xl mx-auto w-full">
          <form onSubmit={sendMessage} className="relative">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a question about your documents..."
              className="w-full bg-neutral-900 border border-neutral-800 rounded-full py-3 px-6 pr-12 text-sm focus:outline-none focus:border-emerald-500 transition-colors"
            />
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-full transition-colors disabled:opacity-50"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </footer>
      </main>
    </div>
  );
}
