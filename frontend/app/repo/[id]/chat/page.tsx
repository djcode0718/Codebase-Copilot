'use client';
/**
 * app/repo/[id]/chat/page.tsx
 * Chat screen — 60/40 split: message thread | AI Inspector.
 * Creates a new chat session on mount and handles full SSE streaming.
 */
import { useEffect, useRef, useState, useCallback } from 'react';
import { useParams } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Square, ArrowLeft, Loader2, Cpu } from 'lucide-react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import MessageBubble from '@/components/chat/MessageBubble';
import AIInspector from '@/components/chat/AIInspector';
import { useChatStream, type StreamedResponse } from '@/hooks/useChatStream';
import { createClient } from '@/lib/supabase/client';
import { createChatSession, getSuggestions, listChats, getMessages } from '@/lib/api';
import { toast } from 'sonner';
import type { Message } from '@/lib/types';

export default function ChatPage() {
  const { id: repoId } = useParams<{ id: string }>();
  const [token, setToken] = useState('');
  const [chatId, setChatId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [inspectedIndex, setInspectedIndex] = useState<number | null>(null);
  const [inspectorData, setInspectorData] = useState<StreamedResponse | null>(null);
  const [sessionReady, setSessionReady] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const { streaming, streamedText, pendingMetadata, error, sendMessage, cancelStream } =
    useChatStream();

  // Bootstrap: get token → create session → load suggestions
  useEffect(() => {
    async function init() {
      const { data } = await createClient().auth.getSession();
      const t = data.session?.access_token ?? '';
      setToken(t);
      if (!t) return;
      try {
        // Try to load existing chat
        const chats = await listChats(t, repoId);
        if (chats.length > 0) {
          const activeChat = chats[0];
          setChatId(activeChat.id);
          const history = await getMessages(t, activeChat.id);
          setMessages(history);
          setSessionReady(true);
        } else {
          // No chats exist, create new
          const session = await createChatSession(t, repoId);
          setChatId(session.chat_id);
          setSessionReady(true);
        }
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Failed to initialize chat');
      }
      try {
        const s = await getSuggestions(t, repoId);
        setSuggestions(s.questions?.slice(0, 4) ?? []);
      } catch { /* suggestions are optional */ }
    }
    init();
  }, [repoId]);

  // Scroll to bottom on new message or streaming
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamedText]);

  // Auto-resize textarea
  function handleInputChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setInput(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 180)}px`;
  }

  const handleSend = useCallback(async (query: string) => {
    if (!chatId || !token || !query.trim() || streaming) return;

    const userMsg: Message = {
      id: `u-${Date.now()}`,
      chat_id: chatId,
      role: 'user',
      content: query.trim(),
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';

    const result = await sendMessage(chatId, query.trim(), token);
    if (result) {
      const assistantMsg: Message = {
        id: `a-${Date.now()}`,
        chat_id: chatId,
        role: 'assistant',
        content: result.content,
        query_mode: result.queryMode ?? undefined,
        retrieved_files: result.retrievedFiles,
        latency_ms: result.latencyTotalMs ?? undefined,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
      // Auto-open inspector for the new message
      const newIdx = messages.length + 1; // user + assistant
      setInspectedIndex(newIdx);
      setInspectorData(result);
      if (result.suggestions && result.suggestions.length > 0) {
        setSuggestions(result.suggestions);
      }
    }
  }, [chatId, token, streaming, sendMessage, messages.length]);

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend(input);
    }
  }

  function handleInspect(index: number, msg: Message) {
    setInspectedIndex(index);
    setInspectorData({
      content: msg.content,
      queryMode: msg.query_mode ?? null,
      retrievedFiles: msg.retrieved_files ?? [],
      latencyRetrievalMs: null,
      latencyLlmMs: null,
      latencyTotalMs: msg.latency_ms ?? null,
    });
  }

  const showEmptyState = messages.length === 0 && !streaming;

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-3 px-6 py-4 border-b border-border flex-shrink-0">
        <Link
          href={`/repo/${repoId}`}
          className="text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
        >
          <ArrowLeft size={16} />
        </Link>
        <div className="flex items-center gap-2">
          <Cpu size={15} className="text-brand" />
          <span className="font-heading font-semibold text-sm">Chat</span>
        </div>
        {!sessionReady && (
          <Loader2 size={13} className="text-muted-foreground animate-spin ml-1" />
        )}
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Message thread — 60% */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto scrollbar-thin px-6 py-6 space-y-6">
            {/* Empty state with suggestions */}
            <AnimatePresence>
              {showEmptyState && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="flex flex-col items-center justify-center py-16 text-center"
                >
                  <div className="w-12 h-12 bg-brand/10 border border-brand/20 rounded-2xl flex items-center justify-center mb-4">
                    <Cpu size={20} className="text-brand" />
                  </div>
                  <h2 className="font-heading font-semibold text-base mb-1">
                    Ask anything about this codebase
                  </h2>
                  <p className="text-muted-foreground text-sm mb-8 max-w-sm">
                    Questions are grounded in real code. Every answer shows which files were retrieved.
                  </p>

                </motion.div>
              )}
            </AnimatePresence>

            {/* Messages */}
            {messages.map((msg, i) => (
              <MessageBubble
                key={msg.id}
                message={msg}
                index={i}
                isInspected={inspectedIndex === i}
                onInspect={msg.role === 'assistant' ? () => handleInspect(i, msg) : undefined}
              />
            ))}

            {/* Streaming message */}
            {streaming && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex gap-3"
              >
                <div className="w-7 h-7 rounded-full bg-brand/10 border border-brand/20 flex items-center justify-center flex-shrink-0 mt-1">
                  <Cpu size={13} className="text-brand" />
                </div>
                <div className="max-w-[75%]">
                  <div className="text-foreground text-sm leading-relaxed">
                    {streamedText}
                    {streamedText && (
                      <span className="streaming-caret" aria-hidden="true" />
                    )}
                    {!streamedText && (
                      <div className="flex items-center gap-1 text-muted-foreground">
                        <Loader2 size={12} className="animate-spin" />
                        <span className="text-xs">Retrieving…</span>
                      </div>
                    )}
                  </div>
                </div>
              </motion.div>
            )}

            {error && (
              <p className="text-xs text-destructive">⚠ {error}</p>
            )}

            {/* Suggestions (Persistent at bottom) */}
            {suggestions.length > 0 && (
              <div className="pt-4 pb-2">
                <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                  Suggested Questions
                </div>
                <div className="flex flex-wrap gap-2">
                  {suggestions.map((q, i) => (
                    <button
                      key={i}
                      onClick={() => handleSend(q)}
                      disabled={!sessionReady || streaming}
                      className="text-left px-3 py-2 bg-card border border-border rounded-lg text-xs text-muted-foreground hover:border-brand/30 hover:text-foreground hover:bg-brand/5 transition-all duration-150 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input area */}
          <div className="px-6 py-4 border-t border-border flex-shrink-0">
            <div className="flex gap-2 items-end">
              <Textarea
                ref={textareaRef}
                value={input}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                placeholder={sessionReady ? 'Ask anything about this codebase… (Enter to send)' : 'Initialising session…'}
                disabled={!sessionReady || streaming}
                rows={1}
                className="flex-1 resize-none bg-card border-border focus-visible:ring-brand min-h-[44px] max-h-[180px] overflow-y-auto scrollbar-thin text-sm"
                aria-label="Chat input"
              />
              <Button
                onClick={streaming ? cancelStream : () => handleSend(input)}
                disabled={(!input.trim() && !streaming) || !sessionReady}
                className={
                  streaming
                    ? 'bg-secondary hover:bg-secondary/80 text-foreground cursor-pointer h-11 w-11 p-0'
                    : 'bg-brand hover:bg-green-400 text-green-950 cursor-pointer h-11 w-11 p-0'
                }
                aria-label={streaming ? 'Stop generation' : 'Send message'}
              >
                {streaming ? <Square size={14} /> : <Send size={14} />}
              </Button>
            </div>
          </div>
        </div>

        {/* AI Inspector — 40% */}
        <div className="w-80 flex-shrink-0 border-l border-border hidden lg:flex flex-col overflow-hidden">
          <AIInspector
            data={inspectedIndex !== null ? inspectorData : pendingMetadata
              ? {
                  queryMode: pendingMetadata.queryMode,
                  retrievedFiles: pendingMetadata.retrievedFiles,
                  latencyRetrievalMs: pendingMetadata.latencyRetrievalMs,
                  latencyLlmMs: pendingMetadata.latencyLlmMs,
                  latencyTotalMs: pendingMetadata.latencyTotalMs,
                }
              : null}
            streaming={streaming}
          />
        </div>
      </div>
    </div>
  );
}
