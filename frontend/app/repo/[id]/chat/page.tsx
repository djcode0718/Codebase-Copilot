'use client';
/**
 * app/repo/[id]/chat/page.tsx
 * Chat screen — 60/40 split: message thread | AI Inspector.
 * Creates a new chat session on mount and handles full SSE streaming.
 */
import { useEffect, useRef, useState, useCallback } from 'react';
import { useParams } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Square, ArrowLeft, Loader2, Cpu, Sparkles, Activity, MessageSquare, ShieldCheck, Plus } from 'lucide-react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import MessageBubble from '@/components/chat/MessageBubble';
import AIInspector from '@/components/chat/AIInspector';
import ExportMenu from '@/components/repo/ExportMenu';
import { useChatStream, type StreamedResponse } from '@/hooks/useChatStream';
import { createClient } from '@/lib/supabase/client';
import {
  createQuickAskSession,
  createMainSession,
  getSuggestions,
  listChatSessions,
  getMessages,
  getRepo,
} from '@/lib/api';
import { toast } from 'sonner';
import type { Message, Repo, QueryMode } from '@/lib/types';

const ARCHITECTURE_QUERY_RE = /(architect|architecture|diagram|mermaid|service map|component relationships|data flow|executive summary)/i;

function withMermaidGuardrails(query: string): string {
  if (!ARCHITECTURE_QUERY_RE.test(query)) return query;

  return `${query}\n\nOutput guardrails:\n- Include exactly one Mermaid diagram inside a fenced code block starting with \`\`\`mermaid.\n- Use valid Mermaid syntax only. Prefer \`flowchart TD\` for architecture diagrams.\n- Do NOT mix \`graph/flowchart\` with \`participant\` declarations.\n- Use simple alphanumeric node ids (e.g., FE, API, DB, IDX) and readable labels in brackets.\n- After the diagram, provide a short confidence level with evidence references.`;
}

function buildThreadStats(messages: Message[], suggestions: string[], inspectedIndex: number | null) {
  return [
    { label: 'Messages', value: messages.length },
    { label: 'Suggestions', value: suggestions.length },
    { label: 'Inspector', value: inspectedIndex !== null ? 'Open' : 'Idle' },
  ];
}

function ChatHeaderSection({
  repoId,
  routedMode,
  isDev,
  token,
  streaming,
  onCreateQuickAsk,
  threadStats,
  repo,
  chatId,
}: {
  repoId: string;
  routedMode: QueryMode | null;
  isDev: boolean;
  token: string;
  streaming: boolean;
  onCreateQuickAsk: () => void;
  threadStats: { label: string; value: string | number }[];
  repo: Repo | null;
  chatId: string | null;
}) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-[1.5rem] border border-border bg-card/80 p-5 shadow-lg shadow-black/5 backdrop-blur-sm"
    >
      <div className="flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Link
              href={`/repo/${repoId}`}
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-background/70 px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              <ArrowLeft size={16} />
              Repository overview
            </Link>
            {isDev && (
              <span className="inline-flex items-center gap-1 rounded-full border border-violet-300 bg-violet-50 px-2 py-1 text-[11px] font-medium text-violet-700 dark:border-violet-500/30 dark:bg-violet-500/10 dark:text-violet-300">
                mode: {routedMode ?? 'pending'}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-border bg-background/70">
              <MessageSquare size={16} className="text-brand" />
            </div>
            <div>
              <h1 className="font-heading text-2xl font-bold tracking-tight">Repository Chat</h1>
              <p className="text-sm text-muted-foreground">Grounded answers with inspectable retrieval metadata.</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              className="border-border cursor-pointer"
              onClick={onCreateQuickAsk}
              disabled={!token || streaming}
            >
              <Plus size={13} className="mr-1.5" />
              New chat
            </Button>
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
        {repo && (
          <div className="self-start xl:self-auto">
            <ExportMenu repo={repo} token={token} scope="chat" chatIds={chatId ? [chatId] : []} />
          </div>
        )}
      </div>
    </motion.section>
  );
}

function EmptyThreadState() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="flex flex-col items-center justify-center rounded-[1.5rem] border border-dashed border-border bg-background/70 px-6 py-10 text-center"
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
  );
}

function ChatMessageList({
  showEmptyState,
  messages,
  inspectedIndex,
  onInspect,
  streaming,
  streamedText,
  error,
  suggestions,
  onSuggestion,
  sessionReady,
  messagesEndRef,
}: {
  showEmptyState: boolean;
  messages: Message[];
  inspectedIndex: number | null;
  onInspect: (index: number, msg: Message) => void;
  streaming: boolean;
  streamedText: string;
  error: string | null;
  suggestions: string[];
  onSuggestion: (q: string) => void;
  sessionReady: boolean;
  messagesEndRef: { current: HTMLDivElement | null };
}) {
  return (
    <div className="flex-1 overflow-y-auto scrollbar-thin px-5 py-5 space-y-5">
      <AnimatePresence>{showEmptyState && <EmptyThreadState />}</AnimatePresence>

      {messages.map((msg, i) => (
        <MessageBubble
          key={msg.id}
          message={msg}
          index={i}
          isInspected={inspectedIndex === i}
          onInspect={msg.role === 'assistant' ? () => onInspect(i, msg) : undefined}
        />
      ))}

      {streaming && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex gap-3">
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
          <div className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Suggested questions</div>
          <div className="flex flex-wrap gap-2">
            {suggestions.map((q, i) => (
              <button
                key={i}
                onClick={() => onSuggestion(q)}
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
  );
}

function ChatComposer({
  repoId,
  isDev,
  routedMode,
  input,
  streaming,
  sessionReady,
  textareaRef,
  onInputChange,
  onKeyDown,
  onSubmit,
  onCancel,
}: {
  repoId: string;
  isDev: boolean;
  routedMode: QueryMode | null;
  input: string;
  streaming: boolean;
  sessionReady: boolean;
  textareaRef: { current: HTMLTextAreaElement | null };
  onInputChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  onSubmit: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="border-t border-border px-5 py-4">
      <div className="mb-2 flex items-center justify-between gap-2">
        <Link
          href={`/repo/${repoId}`}
          className="inline-flex items-center gap-1.5 rounded-full border border-border bg-background/70 px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft size={12} />
          Back to repository
        </Link>
        {isDev && (
          <span className="inline-flex items-center gap-1 rounded-full border border-violet-300 bg-violet-50 px-2 py-1 text-[10px] font-medium text-violet-700 dark:border-violet-500/30 dark:bg-violet-500/10 dark:text-violet-300">
            routed: {routedMode ?? 'pending'}
          </span>
        )}
      </div>
      <div className="flex items-end gap-2 rounded-[1.25rem] border border-border bg-background/70 p-3 shadow-sm shadow-black/5">
        <Textarea
          ref={textareaRef}
          value={input}
          onChange={onInputChange}
          onKeyDown={onKeyDown}
          placeholder={sessionReady ? 'Ask anything about this codebase… (Enter to send)' : 'Initialising session…'}
          disabled={!sessionReady || streaming}
          rows={1}
          className="min-h-[52px] max-h-[180px] flex-1 resize-none border-0 bg-transparent p-0 text-sm shadow-none outline-none focus-visible:ring-0"
          aria-label="Chat input"
        />
        <Button
          onClick={streaming ? onCancel : onSubmit}
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
  );
}

function ChatWorkspace({
  repoId,
  sessionReady,
  showEmptyState,
  messages,
  inspectedIndex,
  streaming,
  streamedText,
  error,
  suggestions,
  isDev,
  routedMode,
  input,
  textareaRef,
  pendingMetadata,
  inspectorData,
  messagesEndRef,
  onInspect,
  onSuggestion,
  onInputChange,
  onKeyDown,
  onSubmit,
  onCancel,
}: {
  repoId: string;
  sessionReady: boolean;
  showEmptyState: boolean;
  messages: Message[];
  inspectedIndex: number | null;
  streaming: boolean;
  streamedText: string;
  error: string | null;
  suggestions: string[];
  isDev: boolean;
  routedMode: QueryMode | null;
  input: string;
  textareaRef: { current: HTMLTextAreaElement | null };
  pendingMetadata: Omit<StreamedResponse, 'content'> | null;
  inspectorData: StreamedResponse | null;
  messagesEndRef: { current: HTMLDivElement | null };
  onInspect: (index: number, msg: Message) => void;
  onSuggestion: (q: string) => void;
  onInputChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  onSubmit: () => void;
  onCancel: () => void;
}) {
  const inspectorPayload = inspectedIndex !== null
    ? inspectorData
    : pendingMetadata
    ? {
        queryMode: pendingMetadata.queryMode,
        retrievedFiles: pendingMetadata.retrievedFiles,
        latencyRetrievalMs: pendingMetadata.latencyRetrievalMs,
        latencyLlmMs: pendingMetadata.latencyLlmMs,
        latencyTotalMs: pendingMetadata.latencyTotalMs,
      }
    : null;

  return (
    <div className="grid min-h-[62vh] grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_22rem] xl:items-start">
      <div className="overflow-hidden rounded-[1.5rem] border border-border bg-card/80 shadow-lg shadow-black/5 backdrop-blur-sm xl:h-[calc(100vh-10rem)] xl:flex xl:flex-col">
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
          <ChatMessageList
            showEmptyState={showEmptyState}
            messages={messages}
            inspectedIndex={inspectedIndex}
            onInspect={onInspect}
            streaming={streaming}
            streamedText={streamedText}
            error={error}
            suggestions={suggestions}
            onSuggestion={onSuggestion}
            sessionReady={sessionReady}
            messagesEndRef={messagesEndRef}
          />

          <ChatComposer
            repoId={repoId}
            isDev={isDev}
            routedMode={routedMode}
            input={input}
            streaming={streaming}
            sessionReady={sessionReady}
            textareaRef={textareaRef}
            onInputChange={onInputChange}
            onKeyDown={onKeyDown}
            onSubmit={onSubmit}
            onCancel={onCancel}
          />
        </div>
      </div>

      <div className="min-h-[32rem] overflow-hidden rounded-[1.5rem] border border-border bg-card/80 shadow-lg shadow-black/5 backdrop-blur-sm xl:sticky xl:top-6 xl:h-[calc(100vh-10rem)]">
        <AIInspector data={inspectorPayload} streaming={streaming} />
      </div>
    </div>
  );
}

function useChatBootstrapEffect({
  repoId,
  loadSession,
  refreshSessions,
  setToken,
  setRepo,
  setSuggestions,
  setInput,
  pendingAutoPromptRef,
  setAutoPromptTick,
}: {
  repoId: string;
  loadSession: (t: string, targetChatId: string) => Promise<number>;
  refreshSessions: (t: string) => Promise<void>;
  setToken: (value: string) => void;
  setRepo: (repo: Repo | null) => void;
  setSuggestions: (value: string[]) => void;
  setInput: (value: string) => void;
  pendingAutoPromptRef: { current: string | null };
  setAutoPromptTick: React.Dispatch<React.SetStateAction<number>>;
}) {
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
        await createMainSession(t, repoId);

        const existingSessions = await listChatSessions(t, repoId, { includeArchived: true, includeDeleted: false, limit: 100 });
        const preferred = existingSessions.find((s) => (s.session_type || 'quick_ask') !== 'main') ?? existingSessions[0];
        if (preferred?.id) {
          activeChatId = preferred.id;
        } else {
          const quickAsk = await createQuickAskSession(t, repoId);
          activeChatId = quickAsk.chat_id;
        }

        await refreshSessions(t);
        const historyCount = await loadSession(t, activeChatId);

        const saved = localStorage.getItem(`chat_suggestions_${activeChatId}`);
        if (saved) {
          try {
            setSuggestions(JSON.parse(saved));
            hasSavedSuggestions = true;
          } catch {
            // Ignore invalid local cache.
          }
        }
        hasHistory = historyCount > 0;
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Failed to initialize chat');
      }

      try {
        const loadedRepo = await getRepo(t, repoId);
        setRepo(loadedRepo);
      } catch {
        // Non-critical for chat initialization.
      }

      const preloadKey = `codebase:preload-prompt:${repoId}`;
      const preloadPrompt = sessionStorage.getItem(preloadKey);
      if (preloadPrompt) {
        sessionStorage.removeItem(preloadKey);
        setInput(preloadPrompt);
        pendingAutoPromptRef.current = preloadPrompt;
        setAutoPromptTick((v) => v + 1);
      }

      if (!hasHistory && !hasSavedSuggestions) {
        try {
          const defaults = await getSuggestions(t, repoId);
          setSuggestions(defaults.questions?.slice(0, 4) ?? []);
        } catch {
          // Suggestions are optional.
        }
      }
    }

    void init();
  }, [
    repoId,
    loadSession,
    refreshSessions,
    pendingAutoPromptRef,
    setAutoPromptTick,
    setInput,
    setRepo,
    setSuggestions,
    setToken,
  ]);
}

function useChatInteractionHandlers({
  chatId,
  token,
  streaming,
  sendMessage,
  messages,
  streamedText,
  pendingMetadata,
  suggestions,
  setMessages,
  setSuggestions,
  setInput,
  setInspectedIndex,
  setInspectorData,
  sessionReady,
  pendingAutoPromptRef,
  autoPromptTick,
  messagesEndRef,
  textareaRef,
}: {
  chatId: string | null;
  token: string;
  streaming: boolean;
  sendMessage: (chatId: string, query: string, token: string) => Promise<StreamedResponse | null>;
  messages: Message[];
  streamedText: string;
  pendingMetadata: Omit<StreamedResponse, 'content'> | null;
  suggestions: string[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  setSuggestions: React.Dispatch<React.SetStateAction<string[]>>;
  setInput: React.Dispatch<React.SetStateAction<string>>;
  setInspectedIndex: React.Dispatch<React.SetStateAction<number | null>>;
  setInspectorData: React.Dispatch<React.SetStateAction<StreamedResponse | null>>;
  sessionReady: boolean;
  pendingAutoPromptRef: { current: string | null };
  autoPromptTick: number;
  messagesEndRef: { current: HTMLDivElement | null };
  textareaRef: { current: HTMLTextAreaElement | null };
}) {
  useEffect(() => {
    if (chatId && suggestions.length > 0) {
      try {
        localStorage.setItem(`chat_suggestions_${chatId}`, JSON.stringify(suggestions));
      } catch (e) {
        console.error(e);
      }
    }
  }, [chatId, suggestions]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamedText, messagesEndRef]);

  const {
    handleInputChange,
    handleSend,
    handleKeyDown,
    handleInspect,
  } = useMessageMutationHandlers({
    chatId,
    token,
    streaming,
    sendMessage,
    messages,
    setMessages,
    setSuggestions,
    setInput,
    setInspectedIndex,
    setInspectorData,
    sessionReady,
    pendingAutoPromptRef,
    autoPromptTick,
    textareaRef,
  });

  const lastAssistantMode = [...messages].reverse().find((m) => m.role === 'assistant' && m.query_mode)?.query_mode ?? null;
  const routedMode: QueryMode | null = pendingMetadata?.queryMode ?? lastAssistantMode;
  const showEmptyState = messages.length === 0 && !streaming;

  return {
    routedMode,
    showEmptyState,
    handleInputChange,
    handleSend,
    handleKeyDown,
    handleInspect,
  };
}

function useMessageMutationHandlers({
  chatId,
  token,
  streaming,
  sendMessage,
  messages,
  setMessages,
  setSuggestions,
  setInput,
  setInspectedIndex,
  setInspectorData,
  sessionReady,
  pendingAutoPromptRef,
  autoPromptTick,
  textareaRef,
}: {
  chatId: string | null;
  token: string;
  streaming: boolean;
  sendMessage: (chatId: string, query: string, token: string) => Promise<StreamedResponse | null>;
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  setSuggestions: React.Dispatch<React.SetStateAction<string[]>>;
  setInput: React.Dispatch<React.SetStateAction<string>>;
  setInspectedIndex: React.Dispatch<React.SetStateAction<number | null>>;
  setInspectorData: React.Dispatch<React.SetStateAction<StreamedResponse | null>>;
  sessionReady: boolean;
  pendingAutoPromptRef: { current: string | null };
  autoPromptTick: number;
  textareaRef: { current: HTMLTextAreaElement | null };
}) {
  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 180)}px`;
  }, [setInput]);

  const handleSend = useCallback(async (query: string) => {
    if (!chatId || !token || !query.trim() || streaming) return;
    const userQuery = query.trim();
    const modelQuery = withMermaidGuardrails(userQuery);
    const userMsg: Message = { id: `u-${Date.now()}`, chat_id: chatId, role: 'user', content: userQuery, created_at: new Date().toISOString() };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    const result = await sendMessage(chatId, modelQuery, token);
    if (!result) return;
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
    setInspectedIndex(messages.length + 1);
    setInspectorData(result);
    if (result.suggestions?.length) setSuggestions(result.suggestions);
  }, [chatId, token, streaming, sendMessage, messages.length, setMessages, setInput, setInspectedIndex, setInspectorData, setSuggestions, textareaRef]);

  useEffect(() => {
    if (!sessionReady || !chatId || streaming) return;
    const prompt = (pendingAutoPromptRef.current || '').trim();
    if (!prompt) return;
    pendingAutoPromptRef.current = null;
    void handleSend(prompt);
  }, [autoPromptTick, chatId, handleSend, sessionReady, streaming, pendingAutoPromptRef]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>, input: string) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void handleSend(input);
    }
  }, [handleSend]);

  const handleInspect = useCallback((index: number, msg: Message) => {
    setInspectedIndex(index);
    setInspectorData({
      content: msg.content,
      queryMode: msg.query_mode ?? null,
      retrievedFiles: msg.retrieved_files ?? [],
      latencyRetrievalMs: null,
      latencyLlmMs: null,
      latencyTotalMs: msg.latency_ms ?? null,
    });
  }, [setInspectedIndex, setInspectorData]);

  return { handleInputChange, handleSend, handleKeyDown, handleInspect };
}

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
  const [repo, setRepo] = useState<Repo | null>(null);
  const pendingAutoPromptRef = useRef<string | null>(null);
  const [autoPromptTick, setAutoPromptTick] = useState(0);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { streaming, streamedText, pendingMetadata, error, sendMessage, cancelStream } =
    useChatStream();

  const loadSession = useCallback(async (t: string, targetChatId: string) => {
    const history = await getMessages(t, targetChatId);
    setChatId(targetChatId);
    setMessages(history);
    setInspectedIndex(null);
    setInspectorData(null);
    setSessionReady(true);
    return history.length;
  }, []);

  const refreshSessions = useCallback(async (t: string) => {
    await listChatSessions(t, repoId, { includeArchived: true, includeDeleted: false, limit: 100 });
  }, [repoId]);
  const handleCreateQuickAsk = useCallback(async () => {
    if (!token) return;
    try {
      const session = await createQuickAskSession(token, repoId);
      await refreshSessions(token);
      await loadSession(token, session.chat_id);
      setSuggestions([]);
      pendingAutoPromptRef.current = null;
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create repository chat');
    }
  }, [token, repoId, refreshSessions, loadSession]);
  useChatBootstrapEffect({
    repoId,
    loadSession,
    refreshSessions,
    setToken,
    setRepo,
    setSuggestions,
    setInput,
    pendingAutoPromptRef,
    setAutoPromptTick,
  });
  const { routedMode, showEmptyState, handleInputChange, handleSend, handleKeyDown, handleInspect } =
    useChatInteractionHandlers({
      chatId,
      token,
      streaming,
      sendMessage,
      messages,
      streamedText,
      pendingMetadata,
      suggestions,
      setMessages,
      setSuggestions,
      setInput,
      setInspectedIndex,
      setInspectorData,
      sessionReady,
      pendingAutoPromptRef,
      autoPromptTick,
      messagesEndRef,
      textareaRef,
    });
  const isDev = process.env.NODE_ENV !== 'production';
  const displayThreadStats = buildThreadStats(messages, suggestions, inspectedIndex);
  return (
    <div className="space-y-6">
      <ChatHeaderSection
        repoId={repoId}
        routedMode={routedMode}
        isDev={isDev}
        token={token}
        streaming={streaming}
        onCreateQuickAsk={handleCreateQuickAsk}
        threadStats={displayThreadStats}
        repo={repo}
        chatId={chatId}
      />

      <ChatWorkspace
        repoId={repoId}
        sessionReady={sessionReady}
        showEmptyState={showEmptyState}
        messages={messages}
        inspectedIndex={inspectedIndex}
        streaming={streaming}
        streamedText={streamedText}
        error={error}
        suggestions={suggestions}
        isDev={isDev}
        routedMode={routedMode}
        input={input}
        textareaRef={textareaRef}
        pendingMetadata={pendingMetadata}
        inspectorData={inspectorData}
        messagesEndRef={messagesEndRef}
        onInspect={handleInspect}
        onSuggestion={handleSend}
        onInputChange={handleInputChange}
        onKeyDown={(e) => handleKeyDown(e, input)}
        onSubmit={() => handleSend(input)}
        onCancel={cancelStream}
      />
    </div>
  );
}
