'use client';

import { useState } from 'react';
import { Send, Loader2, Bot, User } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

type Chunk = { id: string; content: string; metadata: Record<string, unknown> };
type Message = { role: 'user' | 'assistant'; content: string; chunks?: Chunk[] };

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const seedDatabase = async () => {
    setIsLoading(true);
    try {
      await fetch('/api/seed', { method: 'POST' });
      alert('Resume ingested into database!');
    } catch {
      alert('Failed to seed');
    } finally {
      setIsLoading(false);
    }
  };

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMsg: Message = { role: 'user', content: input };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    try {
      const res = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userMsg.content, top_k: 3 }),
      });
      const data = await res.json();

      const botMsg: Message = {
        role: 'assistant',
        content: data.answer || data.error || 'No response',
        chunks: data.results,
      };
      setMessages((prev) => [...prev, botMsg]);
    } catch {
      setMessages((prev) => [...prev, { role: 'assistant', content: 'Error connecting to backend.' }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-neutral-950 text-neutral-200">
      <header className="p-4 border-b border-neutral-800 text-center">
        <h1 className="text-xl font-bold flex items-center justify-center gap-2">
          <button onClick={seedDatabase} className="absolute left-4 text-sm bg-neutral-800 hover:bg-neutral-700 px-3 py-1 rounded-md transition-colors" type="button">
            Seed Resume
          </button>
          <Bot className="w-6 h-6 text-emerald-400" />
          RAG Evals Chat
        </h1>
      </header>

      <main className="flex-1 overflow-y-auto p-4 space-y-6 max-w-3xl mx-auto w-full">
        {messages.length === 0 && (
          <div className="text-center text-neutral-500 mt-20">
            <p>Ask a question about the documents in the database.</p>
          </div>
        )}
        
        {messages.map((msg, i) => {
          const isUser = msg.role === 'user';
          const rowClass = isUser ? 'flex gap-3 justify-end' : 'flex gap-3 justify-start';
          const bubbleClass = isUser 
            ? 'max-w-[80%] rounded-2xl p-4 bg-emerald-600 text-white' 
            : 'max-w-[80%] rounded-2xl p-4 bg-neutral-900 border border-neutral-800';

          return (
            <div key={i} className={rowClass}>
              {!isUser && <Bot className="w-6 h-6 text-emerald-400 shrink-0 mt-1" />}
              
              <div className={bubbleClass}>
                {!isUser ? (
                  <div className="prose prose-invert prose-sm"><ReactMarkdown>
                    {msg.content}
                  </ReactMarkdown></div>
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
        
        {isLoading && (
          <div className="flex gap-3">
            <Bot className="w-6 h-6 text-emerald-400 shrink-0 mt-1" />
            <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-4">
              <Loader2 className="w-5 h-5 animate-spin text-neutral-400" />
            </div>
          </div>
        )}
      </main>

      <footer className="p-4 border-t border-neutral-800 max-w-3xl mx-auto w-full">
        <form onSubmit={sendMessage} className="relative">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question..."
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
    </div>
  );
}


