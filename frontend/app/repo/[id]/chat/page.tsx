'use client';
/**
 * app/repo/[id]/chat/page.tsx
 * Chat screen — 60/40 split: message thread | AI Inspector.
 * Creates a new chat session on mount and handles full SSE streaming.
 */
import { useEffect, useRef, useState, useCallback } from 'react';
import { useParams } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Square, ArrowLeft, Loader2, Cpu, Sparkles, Activity, MessageSquare, ShieldCheck } from 'lucide-react';
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

      let activeChatId = '';
      let hasHistory = false;
      let hasSavedSuggestions = false;

      try {
        // Try to load existing chat
        const chats = await listChats(t, repoId);
        if (chats.length > 0) {
          const activeChat = chats[0];
          activeChatId = activeChat.id;
          setChatId(activeChatId);
          const history = await getMessages(t, activeChatId);
          setMessages(history);
          hasHistory = history.length > 0;
          setSessionReady(true);

          // Try to restore suggestions from localStorage
          const saved = localStorage.getItem(`chat_suggestions_${activeChatId}`);
          if (saved) {
            try {
              setSuggestions(JSON.parse(saved));
              hasSavedSuggestions = true;
            } catch {
              // fallback
            }
          }
        } else {
          // No chats exist, create new
          const session = await createChatSession(t, repoId);
          activeChatId = session.chat_id;
          setChatId(activeChatId);
          setSessionReady(true);
        }
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Failed to initialize chat');
      }

      // Fetch default repo suggestions ONLY if there is no chat history and no saved suggestions in localStorage
      if (!hasHistory && !hasSavedSuggestions) {
        try {
          const s = await getSuggestions(t, repoId);
          setSuggestions(s.questions?.slice(0, 4) ?? []);
        } catch { /* suggestions are optional */ }
      }
    }
    init();
  }, [repoId]);

  // Sync suggestions to localStorage whenever they change
  useEffect(() => {
    if (chatId && suggestions.length > 0) {
      try {
        localStorage.setItem(`chat_suggestions_${chatId}`, JSON.stringify(suggestions));
      } catch (e) {
        console.error(e);
      }
    }
  }, [chatId, suggestions]);

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
  const threadStats = [
    { label: 'Messages', value: messages.length },
    { label: 'Suggestions', value: suggestions.length },
    { label: 'Inspector', value: inspectedIndex !== null ? 'Open' : 'Idle' },
  ];

  return (
    <div className="space-y-6">
      <motion.section
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-[1.5rem] border border-border bg-card/80 p-5 shadow-lg shadow-black/5 backdrop-blur-sm"
      >
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-3">
            <Link
              href={`/repo/${repoId}`}
              className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              <ArrowLeft size={16} />
              Repository overview
            </Link>
            <div className="flex items-center gap-2">
              <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-border bg-background/70">
                <MessageSquare size={16} className="text-brand" />
              </div>
              <div>
                <h1 className="font-heading text-2xl font-bold tracking-tight">Chat</h1>
                <p className="text-sm text-muted-foreground">Grounded answers with inspectable retrieval metadata.</p>
              </div>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3 sm:min-w-[22rem]">
            {threadStats.map((stat) => (
              <div key={stat.label} className="rounded-2xl border border-border bg-background/70 px-3 py-3">
                <div className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">{stat.label}</div>
                <div className="mt-2 font-heading text-lg font-semibold">{stat.value}</div>
              </div>
            ))}
          </div>
        </div>
      </motion.section>

      <div className="grid min-h-[calc(100vh-18rem)] grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="overflow-hidden rounded-[1.5rem] border border-border bg-card/80 shadow-lg shadow-black/5 backdrop-blur-sm">
          <div className="flex items-center justify-between border-b border-border px-5 py-4">
            <div className="flex items-center gap-2 text-sm font-medium">
              <Activity size={15} className="text-brand" />
              Chat thread
            </div>
            {!sessionReady && (
              <div className="inline-flex items-center gap-2 rounded-full border border-border bg-background/70 px-3 py-1 text-xs text-muted-foreground">
                <Loader2 size={12} className="animate-spin" />
                Initialising
              </div>
            )}
          </div>

          <div className="flex h-full min-h-0 flex-col">
            <div className="flex-1 overflow-y-auto scrollbar-thin px-5 py-5 space-y-5">
              <AnimatePresence>
                {showEmptyState && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="flex flex-col items-center justify-center rounded-[1.5rem] border border-dashed border-border bg-background/70 px-6 py-16 text-center"
                  >
                    <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-brand/20 bg-brand/10 text-brand">
                      <Sparkles size={22} />
                    </div>
                    <h2 className="font-heading text-lg font-semibold">Ask anything about this codebase</h2>
                    <p className="mt-2 max-w-md text-sm text-muted-foreground">
                      Questions are grounded in real code. Answers show retrieval mode, matched files, and latency.
                    </p>
                    <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
                      <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground">
                        <ShieldCheck size={11} className="text-brand" />
                        Grounded responses
                      </span>
                      <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground">
                        <Activity size={11} className="text-brand" />
                        Live inspector
                      </span>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {messages.map((msg, i) => (
                <MessageBubble
                  key={msg.id}
                  message={msg}
                  index={i}
                  isInspected={inspectedIndex === i}
                  onInspect={msg.role === 'assistant' ? () => handleInspect(i, msg) : undefined}
                />
              ))}

              {streaming && (
                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex gap-3"
                >
                  <div className="mt-1 flex h-8 w-8 items-center justify-center rounded-full border border-brand/20 bg-brand/10 text-brand">
                    <Cpu size={13} />
                  </div>
                  <div className="max-w-[78%] rounded-2xl border border-border bg-background/70 px-4 py-3 shadow-sm shadow-black/5">
                    <div className="text-sm leading-relaxed text-foreground">
                      {streamedText}
                      {streamedText && <span className="streaming-caret" aria-hidden="true" />}
                      {!streamedText && (
                        <div className="flex items-center gap-2 text-muted-foreground">
                          <Loader2 size={12} className="animate-spin" />
                          <span className="text-xs">Retrieving…</span>
                        </div>
                      )}
                    </div>
                  </div>
                </motion.div>
              )}

              {error && <p className="text-xs text-destructive">⚠ {error}</p>}

              {suggestions.length > 0 && (
                <div className="pt-2 pb-1">
                  <div className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                    Suggested questions
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {suggestions.map((q, i) => (
                      <button
                        key={i}
                        onClick={() => handleSend(q)}
                        disabled={!sessionReady || streaming}
                        className="rounded-full border border-border bg-background/70 px-3 py-2 text-left text-xs text-muted-foreground transition-all duration-150 hover:border-brand/30 hover:bg-brand/5 hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            <div className="border-t border-border px-5 py-4">
              <div className="flex items-end gap-2 rounded-[1.25rem] border border-border bg-background/70 p-3 shadow-sm shadow-black/5">
                <Textarea
                  ref={textareaRef}
                  value={input}
                  onChange={handleInputChange}
                  onKeyDown={handleKeyDown}
                  placeholder={sessionReady ? 'Ask anything about this codebase… (Enter to send)' : 'Initialising session…'}
                  disabled={!sessionReady || streaming}
                  rows={1}
                  className="min-h-[52px] max-h-[180px] flex-1 resize-none border-0 bg-transparent p-0 text-sm shadow-none outline-none focus-visible:ring-0"
                  aria-label="Chat input"
                />
                <Button
                  onClick={streaming ? cancelStream : () => handleSend(input)}
                  disabled={(!input.trim() && !streaming) || !sessionReady}
                  className={
                    streaming
                      ? 'h-11 w-11 cursor-pointer bg-secondary p-0 text-foreground hover:bg-secondary/80'
                      : 'h-11 w-11 cursor-pointer bg-brand p-0 text-green-950 hover:bg-green-400'
                  }
                  aria-label={streaming ? 'Stop generation' : 'Send message'}
                >
                  {streaming ? <Square size={14} /> : <Send size={14} />}
                </Button>
              </div>
            </div>
          </div>
        </div>

        <div className="min-h-[32rem] overflow-hidden rounded-[1.5rem] border border-border bg-card/80 shadow-lg shadow-black/5 backdrop-blur-sm">
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
