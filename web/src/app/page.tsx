'use client';

import { useCallback, useEffect, useState } from 'react';
import { AppHeader, type AppTab } from '@/components/app-header';
import { ChatSidebar } from '@/components/chat/chat-sidebar';
import { ChatTab } from '@/components/chat/chat-tab';
import { DocumentsTab, type CollectionInfo } from '@/components/documents-tab';
import { IngestTab } from '@/components/ingest/ingest-tab';
import { useChat } from '@/hooks/use-chat';
import { useConversations } from '@/hooks/use-conversations';

export default function Home() {
  const [activeTab, setActiveTab] = useState<AppTab>('chat');
  const [focusDocumentId, setFocusDocumentId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [collections, setCollections] = useState<CollectionInfo[]>([]);
  const [scopeCollectionId, setScopeCollectionId] = useState('');

  // A scope pointing at a deleted collection quietly falls back to "All documents".
  const activeScope = collections.some((c) => c.id === scopeCollectionId) ? scopeCollectionId : '';

  const conversations = useConversations();
  const chat = useChat({
    scopeCollectionId: activeScope,
    createConversation: conversations.create,
    onFirstMessage: conversations.generateTitle,
  });

  const refreshCollections = useCallback(async () => {
    try {
      const res = await fetch('/api/collections', { cache: 'no-store' });
      if (!res.ok) return;
      setCollections((await res.json()) as CollectionInfo[]);
    } catch {
      /* keep the previous list */
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetch('/api/collections', { cache: 'no-store' })
      .then((res) => (res.ok ? res.json() : null))
      .then((data: CollectionInfo[] | null) => {
        if (!cancelled && data) setCollections(data);
      })
      .catch(() => {
        /* keep the empty list */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const goToTab = (tab: AppTab, documentId: string | null = null) => {
    setFocusDocumentId(documentId);
    setActiveTab(tab);
  };

  const handleNewChat = () => {
    chat.startNewChat();
    goToTab('chat');
    setSidebarOpen(false);
  };

  const handleSelectChat = (id: string) => {
    void chat.selectConversation(id);
    goToTab('chat');
    setSidebarOpen(false);
  };

  const handleDeleteChat = async (id: string) => {
    if (await conversations.remove(id)) chat.discardConversation(id);
  };

  return (
    <div className="flex h-[100dvh] w-full overflow-hidden bg-background text-foreground font-sans transition-colors duration-300 relative">
      <ChatSidebar
        open={sidebarOpen}
        conversations={conversations.conversations}
        activeId={chat.activeId}
        loading={conversations.loading}
        error={conversations.error}
        onClose={() => setSidebarOpen(false)}
        onNew={handleNewChat}
        onSelect={handleSelectChat}
        onRename={(id, title) => void conversations.rename(id, title)}
        onTogglePin={(id) => void conversations.togglePin(id)}
        onDelete={(id) => void handleDeleteChat(id)}
      />

      <div className="flex flex-col h-full flex-1 overflow-hidden transition-all duration-300">
        <AppHeader
          activeTab={activeTab}
          onTabChange={goToTab}
          sidebarOpen={sidebarOpen}
          onOpenSidebar={() => setSidebarOpen(true)}
        />

        <main className="flex-1 relative overflow-hidden flex flex-col">
          <ChatTab
            active={activeTab === 'chat'}
            conversationId={chat.activeId}
            messages={chat.messages}
            historyLoading={chat.historyLoading}
            isStreaming={chat.isStreaming}
            error={chat.error}
            collections={collections}
            scopeCollectionId={activeScope}
            onScopeChange={setScopeCollectionId}
            onSend={(text) => void chat.send(text)}
            onOpenDocument={(documentId) => goToTab('documents', documentId)}
          />
          <IngestTab
            active={activeTab === 'ingest'}
            collections={collections}
            onIngested={refreshCollections}
            onOpenDocument={(documentId) => goToTab('documents', documentId)}
          />
          {activeTab === 'documents' && (
            <DocumentsTab
              collections={collections}
              onCollectionsChanged={refreshCollections}
              onAddDocument={() => goToTab('ingest')}
              initialDocumentId={focusDocumentId}
            />
          )}
        </main>
      </div>
    </div>
  );
}
