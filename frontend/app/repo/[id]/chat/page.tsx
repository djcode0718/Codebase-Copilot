'use client';
/**
 * app/repo/[id]/chat/page.tsx
 * Chat screen — 60/40 split: message thread | AI Inspector.
 * Creates a new chat session on mount and handles full SSE streaming.
 */
import { useEffect, useRef, useState, useCallback, useMemo, lazy, Suspense } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Square, ArrowLeft, Loader2, Cpu, Sparkles, Activity, MessageSquare, ShieldCheck, Plus, Wrench, Search, Pin, PinOff, Trash2, Archive, Pencil, Check, X, Download, ChevronDown, GitBranch } from 'lucide-react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import MessageBubble from '@/components/chat/MessageBubble';
import AIInspector from '@/components/chat/AIInspector';
import ExportMenu from '@/components/repo/ExportMenu';
const RelationshipGraphViewer = lazy(() => import('@/components/chat/RelationshipGraphViewer'));
import { useChatStream, type StreamedResponse } from '@/hooks/useChatStream';
import { useGraphCache } from '@/hooks/useGraphCache';
import { createClient } from '@/lib/supabase/client';
import {
  createQuickAskSession,
  createMainSession,
  getSuggestions,
  listChatSessions,
  getMessages,
  getRepo,
  updateChatSession,
  deleteChat,
  deleteAllChats,
  deleteSelectedChats,
  exportRepositoryMemory,
  getRelationshipGraphKeys,
} from '@/lib/api';
import { toast } from 'sonner';
import type { Chat, Message, Repo, QueryMode, GraphAvailability } from '@/lib/types';

const ARCHITECTURE_QUERY_RE = /(architect|architecture|diagram|mermaid|service map|component relationships|data flow|executive summary)/i;

function withMermaidGuardrails(query: string): string {
  if (!ARCHITECTURE_QUERY_RE.test(query)) return query;

  return `${query}\n\nOutput guardrails:\n- Include exactly one Mermaid diagram inside a fenced code block starting with \`\`\`mermaid.\n- Use valid Mermaid syntax only. Prefer \`flowchart TD\` for architecture diagrams.\n- Do NOT mix \`graph/flowchart\` with \`participant\` declarations.\n- Use simple alphanumeric node ids (e.g., FE, API, DB, IDX) and readable labels in brackets.\n- After the diagram, provide a short confidence level with evidence references.`;
}

function buildThreadStats(messages: Message[], suggestions: string[], inspectedIndex: number | null) {
  void inspectedIndex;
  return [
    { label: 'Messages', value: messages.length },
    { label: 'Suggestions', value: suggestions.length },
  ];
}

function PrioritizedHeaderChips({
  repoId,
  threadStats,
}: {
  repoId: string;
  threadStats: { label: string; value: string | number }[];
}) {
  const messagesStat = threadStats.find((stat) => stat.label === 'Messages');
  const suggestionsStat = threadStats.find((stat) => stat.label === 'Suggestions');
  const shouldShowStat = (stat?: { value: string | number }) => {
    if (!stat) return false;
    const numericValue = typeof stat.value === 'number' ? stat.value : Number(stat.value);
    if (Number.isFinite(numericValue)) return numericValue > 0;
    return Boolean(stat.value);
  };

  return (
    <div className="flex min-w-0 items-center gap-1.5 overflow-x-auto pr-1 scrollbar-thin">
      <Link
        href={`/repo/${repoId}`}
        className="inline-flex h-7 shrink-0 items-center gap-1.5 rounded-full border border-border bg-background/70 px-2.5 text-[11px] text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft size={12} />
        Repository overview
      </Link>

      {shouldShowStat(messagesStat) && (
        <span className="inline-flex h-7 shrink-0 items-center gap-1 rounded-full border border-border bg-background/70 px-2.5 text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
          {messagesStat.label}
          <span className="font-heading text-[11px] normal-case tracking-normal text-foreground">{messagesStat.value}</span>
        </span>
      )}

      {shouldShowStat(suggestionsStat) && (
        <span className="inline-flex h-7 shrink-0 items-center gap-1 rounded-full border border-border bg-background/70 px-2.5 text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
          {suggestionsStat.label}
          <span className="font-heading text-[11px] normal-case tracking-normal text-foreground">{suggestionsStat.value}</span>
        </span>
      )}
    </div>
  );
}

function buildInspectorPayload(
  inspectedIndex: number | null,
  pendingMetadata: Omit<StreamedResponse, 'content'> | null,
  inspectorData: StreamedResponse | null,
) {
  if (inspectedIndex !== null) return inspectorData;
  if (!pendingMetadata) return null;
  return {
    queryMode: pendingMetadata.queryMode,
    retrievedFiles: pendingMetadata.retrievedFiles,
    latencyRetrievalMs: pendingMetadata.latencyRetrievalMs,
    latencyLlmMs: pendingMetadata.latencyLlmMs,
    latencyTotalMs: pendingMetadata.latencyTotalMs,
  };
}

function collectReviewTargets(messages: Message[]): string[] {
  const orderedPaths: string[] = [];
  const seen = new Set<string>();
  for (const msg of messages) {
    if (msg.role !== 'assistant' || !msg.retrieved_files?.length) continue;
    for (const file of msg.retrieved_files) {
      const path = (file.path || '').trim();
      if (!path || seen.has(path)) continue;
      seen.add(path);
      orderedPaths.push(path);
      if (orderedPaths.length >= 8) return orderedPaths;
    }
  }
  return orderedPaths;
}

type ConversationFilter = 'all' | 'pinned' | 'archived' | 'today' | 'week' | 'month';
type ConversationSort = 'newest' | 'oldest' | 'active' | 'alpha' | 'pinned';

function conversationTimestamp(chat: Chat): string {
  return chat.last_message_at || chat.updated_at || chat.created_at || '';
}

function formatConversationDate(value?: string | null): string {
  if (!value) return 'No activity yet';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'No activity yet';
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const dayMs = 24 * 60 * 60 * 1000;
  if (diffMs < dayMs && date.toDateString() === now.toDateString()) return 'Today';
  if (diffMs < 2 * dayMs) return 'Yesterday';
  if (diffMs < 7 * dayMs) return `${Math.floor(diffMs / dayMs)} Days Ago`;
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function conversationMatchesFilter(chat: Chat, filter: ConversationFilter): boolean {
  const date = new Date(conversationTimestamp(chat));
  const now = new Date();
  if (filter === 'pinned') return Boolean(chat.is_pinned);
  if (filter === 'archived') return Boolean(chat.is_archived);
  if (filter === 'all') return true;
  if (Number.isNaN(date.getTime())) return false;
  if (filter === 'today') return date.toDateString() === now.toDateString();
  const diffMs = now.getTime() - date.getTime();
  if (filter === 'week') return diffMs <= 7 * 24 * 60 * 60 * 1000;
  if (filter === 'month') return diffMs <= 31 * 24 * 60 * 60 * 1000;
  return true;
}

function sortConversations(items: Chat[], sort: ConversationSort): Chat[] {
  return [...items].sort((a, b) => {
    if (sort === 'alpha') return (a.title || '').localeCompare(b.title || '');
    if (sort === 'oldest') return conversationTimestamp(a).localeCompare(conversationTimestamp(b));
    if (sort === 'active') return (b.message_count || 0) - (a.message_count || 0);
    if (sort === 'pinned' && Boolean(a.is_pinned) !== Boolean(b.is_pinned)) return a.is_pinned ? -1 : 1;
    if (Boolean(a.is_pinned) !== Boolean(b.is_pinned)) return a.is_pinned ? -1 : 1;
    return conversationTimestamp(b).localeCompare(conversationTimestamp(a));
  });
}

function downloadTextFile(filename: string, content: string, contentType: string) {
  const blob = new Blob([content], { type: contentType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function getSessionBadge(session: Chat): string {
  if (session.is_pinned) return 'pinned';
  if (session.is_favorite) return 'favorite';
  if (session.is_archived) return 'archived';
  return '';
}

function ConversationSessionCard({
  session, active, isEditing, draftTitle, streaming, selectedIds,
  onToggleSelect, onOpen, onDraftChange, onCommitRename, onCancelEdit, onStartEdit,
  onPin, onArchive, onExport, onDelete,
}: {
  session: Chat; active: boolean; isEditing: boolean; draftTitle: string;
  streaming: boolean; selectedIds: Set<string>;
  onToggleSelect: () => void; onOpen: () => void;
  onDraftChange: (v: string) => void; onCommitRename: () => void;
  onCancelEdit: () => void; onStartEdit: () => void;
  onPin: () => void; onArchive: () => void; onExport: () => void; onDelete: () => void;
}) {
  const title = session.title || 'Repository Overview';

  return (
    <div className={active ? 'rounded-2xl border border-brand/30 bg-brand/5 p-3' : 'rounded-2xl border border-border bg-background/60 p-3'}>
      <div className="flex items-start gap-2">
        <input type="checkbox" checked={selectedIds.has(session.id)} onChange={onToggleSelect} className="mt-1" aria-label={`Select ${title}`} />
        <button type="button" onClick={onOpen} disabled={streaming} className="min-w-0 flex-1 text-left disabled:cursor-not-allowed disabled:opacity-60">
          {isEditing ? (
            <input value={draftTitle} onChange={(e) => onDraftChange(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') onCommitRename(); if (e.key === 'Escape') onCancelEdit(); }}
              autoFocus className="w-full rounded-lg border border-border bg-background px-2 py-1 text-sm font-medium outline-none" />
          ) : (
            <div className="truncate text-sm font-semibold text-foreground">{title}</div>
          )}
          <div className="mt-1 line-clamp-2 text-xs text-muted-foreground">{session.last_message_preview || 'Start a repository conversation.'}</div>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
            <span>{formatConversationDate(conversationTimestamp(session))}</span>
            <span>{session.message_count || 0} Messages</span>
            {session.is_archived && <span>Archived</span>}
          </div>
        </button>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        {isEditing ? (
          <>
            <Button variant="outline" size="sm" className="h-7 cursor-pointer border-border px-2" onClick={onCommitRename} title="Save title"><Check size={12} /></Button>
            <Button variant="outline" size="sm" className="h-7 cursor-pointer border-border px-2" onClick={onCancelEdit} title="Cancel rename"><X size={12} /></Button>
          </>
        ) : (
          <Button variant="outline" size="sm" className="h-7 cursor-pointer border-border px-2" onClick={onStartEdit} title="Rename conversation"><Pencil size={12} /></Button>
        )}
        <Button variant="outline" size="sm" className="h-7 cursor-pointer border-border px-2" onClick={onPin} title={session.is_pinned ? 'Unpin conversation' : 'Pin conversation'}>
          {session.is_pinned ? <PinOff size={12} /> : <Pin size={12} />}
        </Button>
        <Button variant="outline" size="sm" className="h-7 cursor-pointer border-border px-2" onClick={onArchive} title={session.is_archived ? 'Unarchive conversation' : 'Archive conversation'}>
          <Archive size={12} />
        </Button>
        <Button variant="outline" size="sm" className="h-7 cursor-pointer border-border px-2" onClick={onExport} title="Export conversation"><Download size={12} /></Button>
        <Button variant="outline" size="sm" className="h-7 cursor-pointer border-border px-2 text-destructive hover:text-destructive" onClick={onDelete} title="Delete conversation"><Trash2 size={12} /></Button>
      </div>
    </div>
  );
}

function ConversationHistoryPanel({
  token,
  repoId,
  sessions,
  currentChatId,
  streaming,
  onNewChat,
  onOpenSession,
  onSessionsChanged,
}: {
  token: string;
  repoId: string;
  sessions: Chat[];
  currentChatId: string | null;
  streaming: boolean;
  onNewChat: () => Promise<void>;
  onOpenSession: (chatId: string) => Promise<void>;
  onSessionsChanged: () => Promise<void>;
}) {
  const [expanded, setExpanded] = useState(true);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<ConversationFilter>('all');
  const [sort, setSort] = useState<ConversationSort>('pinned');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftTitle, setDraftTitle] = useState('');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const visibleSessions = useMemo(() => {
    const q = search.trim().toLowerCase();
    const filtered = sessions.filter((session) => {
      if (!conversationMatchesFilter(session, filter)) return false;
      if (!q) return true;
      return (
        (session.title || '').toLowerCase().includes(q) ||
        (session.last_message_preview || '').toLowerCase().includes(q)
      );
    });
    return sortConversations(filtered, sort);
  }, [filter, search, sessions, sort]);

  async function refreshAfter(action: Promise<unknown>, success: string) {
    try {
      await action;
      await onSessionsChanged();
      toast.success(success);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Conversation action failed');
    }
  }

  async function commitRename(chatId: string) {
    const title = draftTitle.trim();
    if (!title) return;
    setEditingId(null);
    await refreshAfter(updateChatSession(token, chatId, { title }), 'Conversation renamed');
  }

  async function handleDelete(chatId: string) {
    if (!window.confirm('Delete this conversation? It can be restored by administrators from the database because deletion is soft.')) return;
    await refreshAfter(deleteChat(token, chatId), 'Conversation deleted');
  }

  async function handleDeleteSelected() {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    if (!window.confirm(`Delete ${ids.length} selected conversation${ids.length === 1 ? '' : 's'}?`)) return;
    await refreshAfter(deleteSelectedChats(token, repoId, ids), 'Selected conversations deleted');
    setSelectedIds(new Set());
  }

  async function handleDeleteAll() {
    if (!window.confirm('Delete all conversations for this repository? This is a soft delete, but the list will be cleared for this workspace.')) return;
    await refreshAfter(deleteAllChats(token, repoId), 'All repository conversations deleted');
    setSelectedIds(new Set());
  }

  async function handleExport(chatId: string) {
    try {
      const payload = await exportRepositoryMemory(token, repoId, 'md', [chatId]);
      downloadTextFile(payload.filename, payload.content, payload.content_type || 'text/markdown');
      toast.success('Conversation exported');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to export conversation');
    }
  }

  function toggleSelected(chatId: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(chatId)) next.delete(chatId);
      else next.add(chatId);
      return next;
    });
  }

  // --- ConversationHistoryPanel render ---

  return (
    <aside className="overflow-hidden rounded-[1.5rem] border border-border bg-card/80 shadow-lg shadow-black/5 backdrop-blur-sm xl:sticky xl:top-6 xl:max-h-[calc(100vh-10rem)]">
      <div className="border-b border-border p-4">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="flex w-full items-center justify-between gap-2 text-left"
          aria-expanded={expanded}
        >
          <span className="flex items-center gap-2 font-heading text-base font-semibold">
            <MessageSquare size={16} className="text-brand" />
            Chat History
          </span>
          <ChevronDown size={15} className={expanded ? 'transition-transform' : '-rotate-90 transition-transform'} />
        </button>
        <Button
          variant="outline"
          size="sm"
          className="mt-4 w-full cursor-pointer border-border"
          onClick={() => void onNewChat()}
          disabled={!token || streaming}
        >
          <Plus size={13} className="mr-1.5" />
          New Chat
        </Button>
      </div>

      {expanded && (
        <div className="space-y-3 p-4">
          <div className="flex items-center gap-2 rounded-2xl border border-border bg-background/70 px-3 py-2">
            <Search size={14} className="text-muted-foreground" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search conversations"
              className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
              aria-label="Search conversations"
            />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <select value={filter} onChange={(e) => setFilter(e.target.value as ConversationFilter)} className="rounded-xl border border-border bg-background px-2 py-2 text-xs">
              <option value="all">All</option>
              <option value="pinned">Pinned</option>
              <option value="archived">Archived</option>
              <option value="today">Today</option>
              <option value="week">This Week</option>
              <option value="month">This Month</option>
            </select>
            <select value={sort} onChange={(e) => setSort(e.target.value as ConversationSort)} className="rounded-xl border border-border bg-background px-2 py-2 text-xs">
              <option value="pinned">Pinned First</option>
              <option value="newest">Newest</option>
              <option value="oldest">Oldest</option>
              <option value="active">Most Active</option>
              <option value="alpha">Alphabetical</option>
            </select>
          </div>

          {selectedIds.size > 0 && (
            <div className="flex items-center justify-between rounded-2xl border border-border bg-background/70 px-3 py-2 text-xs">
              <span>{selectedIds.size} selected</span>
              <Button variant="outline" size="sm" className="h-7 cursor-pointer border-border px-2" onClick={() => void handleDeleteSelected()}>
                Delete
              </Button>
            </div>
          )}

          {/* Conversation list */}
          <div className="max-h-[48vh] space-y-2 overflow-y-auto pr-1 scrollbar-thin">
            {visibleSessions.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-border bg-background/50 p-4 text-center text-sm text-muted-foreground">
                No conversations found.
              </div>
            ) : (
              visibleSessions.map((session) => (
                <ConversationSessionCard
                  key={session.id}
                  session={session}
                  active={session.id === currentChatId}
                  isEditing={editingId === session.id}
                  draftTitle={draftTitle}
                  streaming={streaming}
                  selectedIds={selectedIds}
                  onToggleSelect={() => toggleSelected(session.id)}
                  onOpen={() => void onOpenSession(session.id)}
                  onDraftChange={setDraftTitle}
                  onCommitRename={() => void commitRename(session.id)}
                  onCancelEdit={() => setEditingId(null)}
                  onStartEdit={() => { setEditingId(session.id); setDraftTitle(session.title || 'Repository Overview'); }}
                  onPin={() => void refreshAfter(updateChatSession(token, session.id, { is_pinned: !session.is_pinned }), session.is_pinned ? 'Conversation unpinned' : 'Conversation pinned')}
                  onArchive={() => void refreshAfter(updateChatSession(token, session.id, { is_archived: !session.is_archived }), session.is_archived ? 'Conversation restored' : 'Conversation archived')}
                  onExport={() => void handleExport(session.id)}
                  onDelete={() => void handleDelete(session.id)}
                />
              ))
            )}
          </div>

          {sessions.length > 0 && (
            <Button variant="outline" size="sm" className="w-full cursor-pointer border-border text-destructive hover:text-destructive" onClick={() => void handleDeleteAll()}>
              Delete All Repository Conversations
            </Button>
          )}
        </div>
      )}
    </aside>
  );
}

function EmptyThreadState() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="flex flex-col items-center justify-center rounded-[1.5rem] border border-dashed border-border bg-background/70 px-6 py-6 text-center"
    >
      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-2xl border border-brand/20 bg-brand/10 text-brand">
        <Sparkles size={18} />
      </div>
      <h2 className="font-heading text-base font-semibold">Ask anything about this codebase</h2>
      <p className="mt-1.5 max-w-md text-xs text-muted-foreground">
        Questions are grounded in real code. Answers show retrieval mode, matched files, and latency.
      </p>
      <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
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
  retryPrompt,
  suggestions,
  onSuggestion,
  onRetry,
  onTryAgainForAnswer,
  onEditQuestion,
  sessionReady,
  messagesEndRef,
  graphKeys,
  onOpenGraph,
}: {
  showEmptyState: boolean;
  messages: Message[];
  inspectedIndex: number | null;
  onInspect: (index: number, msg: Message) => void;
  streaming: boolean;
  streamedText: string;
  error: string | null;
  retryPrompt: string | null;
  suggestions: string[];
  onSuggestion: (q: string) => void;
  onRetry: () => void;
  onTryAgainForAnswer: (index: number, msg: Message) => void;
  onEditQuestion: (msg: Message) => void;
  sessionReady: boolean;
  messagesEndRef: { current: HTMLDivElement | null };
  graphKeys?: Set<string>;
  onOpenGraph?: (symbol: string) => void;
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
          onTryAgain={msg.role === 'assistant' ? () => onTryAgainForAnswer(i, msg) : undefined}
          onEdit={msg.role === 'user' ? () => onEditQuestion(msg) : undefined}
          actionsDisabled={streaming || !sessionReady}
          graphKeys={graphKeys}
          onOpenGraph={onOpenGraph}
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

      {(error || retryPrompt) && (
        <div className="flex items-center gap-2 rounded-xl border border-destructive/25 bg-destructive/5 px-3 py-2 text-xs">
          {error ? <p className="text-destructive">⚠ {error}</p> : <p className="text-muted-foreground">Last answer could not be completed.</p>}
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="h-7 cursor-pointer border-destructive/30 px-2 text-destructive hover:text-destructive"
            onClick={onRetry}
            disabled={streaming || !sessionReady || !retryPrompt}
          >
            Retry answer
          </Button>
        </div>
      )}

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
          autoCorrect="off"
          autoCapitalize="off"
          spellCheck={false}
          className="min-h-[52px] max-h-[180px] flex-1 resize-none border-0 bg-background/80 px-2 py-1.5 text-sm shadow-none outline-none focus-visible:ring-0 [caret-color:var(--foreground)] placeholder:text-muted-foreground/60"
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
  repo,
  token,
  chatId,
  sessionReady,
  showEmptyState,
  messages,
  inspectedIndex,
  streaming,
  streamedText,
  error,
  retryPrompt,
  suggestions,
  isDev,
  routedMode,
  input,
  textareaRef,
  messagesEndRef,
  onInspect,
  onSuggestion,
  onRetry,
  onTryAgainForAnswer,
  onEditQuestion,
  onInputChange,
  onKeyDown,
  onSubmit,
  onCancel,
  sessionLoading,
  onCreateQuickAsk,
  onOpenReview,
  threadStats,
  graphAvailability,
  graphKeys,
  onOpenGraph,
}: {
  repoId: string;
  repo: Repo | null;
  token: string;
  chatId: string | null;
  sessionReady: boolean;
  showEmptyState: boolean;
  messages: Message[];
  inspectedIndex: number | null;
  streaming: boolean;
  streamedText: string;
  error: string | null;
  retryPrompt: string | null;
  suggestions: string[];
  isDev: boolean;
  routedMode: QueryMode | null;
  input: string;
  textareaRef: { current: HTMLTextAreaElement | null };
  messagesEndRef: { current: HTMLDivElement | null };
  onInspect: (index: number, msg: Message) => void;
  onSuggestion: (q: string) => void;
  onRetry: () => void;
  onTryAgainForAnswer: (index: number, msg: Message) => void;
  onEditQuestion: (msg: Message) => void;
  onInputChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  onSubmit: () => void;
  onCancel: () => void;
  sessionLoading?: boolean;
  onCreateQuickAsk: () => void;
  onOpenReview: () => void;
  threadStats: { label: string; value: string | number }[];
  graphAvailability: GraphAvailability;
  graphKeys?: Set<string>;
  onOpenGraph: (symbol?: string) => void;
}) {
  return (
    <div className="overflow-hidden rounded-[1.5rem] border border-border bg-card/80 shadow-lg shadow-black/5 backdrop-blur-sm xl:flex xl:h-[calc(100dvh-8rem)] xl:flex-col">
        <div className="sticky top-0 z-30 flex-shrink-0 border-b border-border bg-card px-4 py-2.5 shadow-sm backdrop-blur-sm">
          <div className="flex flex-col gap-2 xl:flex-row xl:items-center xl:justify-between xl:gap-3">
            <div className="flex min-w-0 items-center gap-1.5">
              <span className="inline-flex h-7 shrink-0 items-center gap-1.5 rounded-full border border-border bg-background/70 px-2.5 py-1">
                <Activity size={13} className="text-brand" />
                <span className="text-sm font-medium text-foreground">Chat thread</span>
              </span>
              <PrioritizedHeaderChips repoId={repoId} threadStats={threadStats} />
            </div>

            <div className="flex shrink-0 items-center gap-1.5">
              {(sessionLoading || !sessionReady) && (
                <div className="inline-flex items-center gap-2 rounded-full border border-border bg-background/70 px-3 py-1 text-xs text-muted-foreground">
                  <Loader2 size={12} className="animate-spin" />
                  {sessionLoading ? 'Loading conversation...' : 'Initialising'}
                </div>
              )}
              <Button
                variant="outline"
                size="sm"
                className="h-7 border-border px-2.5 text-[11px] cursor-pointer"
                onClick={onCreateQuickAsk}
                disabled={!token || streaming}
              >
                <Plus size={12} className="mr-1" />
                New chat
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-7 border-border px-2.5 text-[11px] cursor-pointer"
                onClick={onOpenReview}
                disabled={!token || streaming}
              >
                <Wrench size={12} className="mr-1" />
                Review
              </Button>
              {/* View graph button — always visible regardless of query mode */}
              <Button
                variant="outline"
                size="sm"
                className={cn(
                  'h-7 border-border px-2.5 text-[11px] cursor-pointer',
                  graphAvailability === 'available' && 'border-brand/30 text-brand hover:bg-brand/5',
                )}
                onClick={() => onOpenGraph()}
                disabled={graphAvailability !== 'available'}
                title={
                  graphAvailability === 'loading' ? 'Checking graph availability…' :
                  graphAvailability === 'no_graph' ? 'No graph yet — index the repository first' :
                  graphAvailability === 'error' ? 'Couldn\'t check graph availability — try refreshing' :
                  'View relationship graph'
                }
              >
                {graphAvailability === 'loading' ? (
                  <Loader2 size={12} className="mr-1 animate-spin" />
                ) : (
                  <GitBranch size={12} className="mr-1" />
                )}
                {graphAvailability === 'loading' ? 'Checking…' : 'View graph'}
              </Button>
              {repo && chatId && (
                <ExportMenu repo={repo} token={token} scope="chat" chatIds={[chatId]} />
              )}
            </div>
          </div>
        </div>

        <div className="flex h-full min-h-0 flex-col">
          {sessionLoading ? (
            <div className="flex flex-1 items-center justify-center py-20 text-muted-foreground">
              <div className="flex flex-col items-center gap-3">
                <Loader2 size={22} className="animate-spin text-brand" />
                <span className="text-sm">Loading conversation...</span>
              </div>
            </div>
          ) : (
            <ChatMessageList
              showEmptyState={showEmptyState}
              messages={messages}
              inspectedIndex={inspectedIndex}
              onInspect={onInspect}
              streaming={streaming}
              streamedText={streamedText}
              error={error}
              retryPrompt={retryPrompt}
              suggestions={suggestions}
              onSuggestion={onSuggestion}
              onRetry={onRetry}
              onTryAgainForAnswer={onTryAgainForAnswer}
              onEditQuestion={onEditQuestion}
              sessionReady={sessionReady}
              messagesEndRef={messagesEndRef}
              graphKeys={graphKeys}
              onOpenGraph={(sym) => onOpenGraph(sym)}
            />
          )}

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

        const openSessionKey = `codebase:open-chat-session:${repoId}`;
        const newChatKey = `codebase:new-chat:${repoId}`;
        const requestedChatId = sessionStorage.getItem(openSessionKey);
        const forceNewChat = sessionStorage.getItem(newChatKey) === '1';
        sessionStorage.removeItem(openSessionKey);
        sessionStorage.removeItem(newChatKey);

        const existingSessions = await listChatSessions(t, repoId, { includeArchived: true, includeDeleted: false, limit: 100 });
        const preferred = requestedChatId
          ? existingSessions.find((s) => s.id === requestedChatId) ?? { id: requestedChatId }
          : existingSessions.find((s) => (s.session_type || 'quick_ask') !== 'main') ?? existingSessions[0];
        if (forceNewChat) {
          const quickAsk = await createQuickAskSession(t, repoId);
          activeChatId = quickAsk.chat_id;
        } else if (preferred?.id) {
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
  streamedTextRef,
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
  onAfterMessagePersisted,
  setRetryPrompt,
}: {
  chatId: string | null;
  token: string;
  streaming: boolean;
  sendMessage: (chatId: string, query: string, token: string) => Promise<StreamedResponse | null>;
  messages: Message[];
  streamedText: string;
  streamedTextRef: React.MutableRefObject<string>;
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
  onAfterMessagePersisted: () => Promise<void>;
  setRetryPrompt: React.Dispatch<React.SetStateAction<string | null>>;
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
    streamedTextRef,
    pendingMetadata,
    setMessages,
    setSuggestions,
    setInput,
    setInspectedIndex,
    setInspectorData,
    sessionReady,
    pendingAutoPromptRef,
    autoPromptTick,
    textareaRef,
    onAfterMessagePersisted,
    setRetryPrompt,
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

function buildFallbackAssistantMessage(chatId: string | null, content: string, meta: Omit<StreamedResponse, 'content'> | null): Message {
  return {
    id: `fallback-${Date.now()}`,
    chat_id: chatId ?? '',
    role: 'assistant' as const,
    content,
    query_mode: meta?.queryMode ?? undefined,
    retrieved_files: meta?.retrievedFiles ?? [],
    latency_ms: meta?.latencyTotalMs ?? undefined,
    created_at: new Date().toISOString(),
  };
}

function useMessageMutationHandlers({
  chatId,
  token,
  streaming,
  sendMessage,
  messages,
  streamedTextRef,
  pendingMetadata,
  setMessages,
  setSuggestions,
  setInput,
  setInspectedIndex,
  setInspectorData,
  sessionReady,
  pendingAutoPromptRef,
  autoPromptTick,
  textareaRef,
  onAfterMessagePersisted,
  setRetryPrompt,
}: {
  chatId: string | null;
  token: string;
  streaming: boolean;
  sendMessage: (chatId: string, query: string, token: string) => Promise<StreamedResponse | null>;
  messages: Message[];
  streamedTextRef: React.MutableRefObject<string>;
  pendingMetadata: Omit<StreamedResponse, 'content'> | null;
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  setSuggestions: React.Dispatch<React.SetStateAction<string[]>>;
  setInput: React.Dispatch<React.SetStateAction<string>>;
  setInspectedIndex: React.Dispatch<React.SetStateAction<number | null>>;
  setInspectorData: React.Dispatch<React.SetStateAction<StreamedResponse | null>>;
  sessionReady: boolean;
  pendingAutoPromptRef: { current: string | null };
  autoPromptTick: number;
  textareaRef: { current: HTMLTextAreaElement | null };
  onAfterMessagePersisted: () => Promise<void>;
  setRetryPrompt: React.Dispatch<React.SetStateAction<string | null>>;
}) {

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 180)}px`;
  }, [setInput]);

  function buildInspectorPayloadFromMeta(meta: Omit<StreamedResponse, 'content'> | null, content: string): StreamedResponse {
    return {
      content,
      queryMode: meta?.queryMode ?? null,
      retrievedFiles: meta?.retrievedFiles ?? [],
      latencyRetrievalMs: meta?.latencyRetrievalMs ?? null,
      latencyLlmMs: meta?.latencyLlmMs ?? null,
      latencyTotalMs: meta?.latencyTotalMs ?? null,
    };
  }

  const handleSend = useCallback(async (query: string) => {
    if (!chatId || !token || !query.trim() || streaming) return;
    const initialMessageCount = messages.length;
    const userQuery = query.trim();
    const modelQuery = withMermaidGuardrails(userQuery);
    const userMsg: Message = { id: `u-${Date.now()}`, chat_id: chatId, role: 'user', content: userQuery, created_at: new Date().toISOString() };
    setMessages((prev) => [...prev, userMsg]);
    setRetryPrompt(null);
    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    const result = await sendMessage(chatId, modelQuery, token);
    // Use ref (non-stale) for partial recovery — the state closure captured
    // the empty value from before sendMessage started.
    const latestStreamedText = streamedTextRef.current;
    if (!result || !result.content.trim()) {
      if (latestStreamedText.trim()) {
        const partialAssistantMsg: Message = {
          id: `a-partial-${Date.now()}`,
          chat_id: chatId,
          role: 'assistant',
          content: latestStreamedText,
          query_mode: pendingMetadata?.queryMode ?? undefined,
          retrieved_files: pendingMetadata?.retrievedFiles ?? [],
          latency_ms: pendingMetadata?.latencyTotalMs ?? undefined,
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, partialAssistantMsg]);
        setInspectedIndex(messages.length + 1);
        setInspectorData(buildInspectorPayloadFromMeta(pendingMetadata, latestStreamedText));
        setRetryPrompt(userQuery);
        toast.warning('Recovered partial streamed answer due to stream interruption.');
        return;
      }

      try {
        const expectedMinCount = initialMessageCount + 2;
        for (let attempt = 0; attempt < 4; attempt++) {
          const latestMessages = await getMessages(token, chatId);
          const latestAssistant = latestMessages[latestMessages.length - 1];
          if (latestMessages.length >= expectedMinCount && latestAssistant?.role === 'assistant' && latestAssistant.content?.trim()) {
            setMessages(latestMessages);
            setInspectedIndex(latestMessages.length - 1);
            setInspectorData({
              content: latestAssistant.content,
              queryMode: latestAssistant.query_mode ?? null,
              retrievedFiles: latestAssistant.retrieved_files ?? [],
              latencyRetrievalMs: null,
              latencyLlmMs: null,
              latencyTotalMs: latestAssistant.latency_ms ?? null,
            });
            void onAfterMessagePersisted();
            return;
          }
          await new Promise((resolve) => setTimeout(resolve, 350 * (attempt + 1)));
        }
      } catch {
        // If recovery fails, keep the current error flow below.
      }

      const fallbackAssistantMsg: Message = {
        id: `a-fallback-${Date.now()}`,
        chat_id: chatId,
        role: 'assistant',
        content:
          'I could not stream a full answer just now. Please retry, or ask a narrower repository-specific question (file, function, class, or module).',
        query_mode: pendingMetadata?.queryMode ?? undefined,
        retrieved_files: pendingMetadata?.retrievedFiles ?? [],
        latency_ms: pendingMetadata?.latencyTotalMs ?? undefined,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, fallbackAssistantMsg]);
      setInspectedIndex(messages.length + 1);
      setInspectorData(buildInspectorPayloadFromMeta(pendingMetadata, fallbackAssistantMsg.content));
      setRetryPrompt(userQuery);
      toast.error('Recovered with a safe fallback answer due to empty stream content.');
      void onAfterMessagePersisted();
      return;
    }

    // Build and append the successful assistant message
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
    let insertedAssistantIndex = -1;
    setMessages((prev) => {
      insertedAssistantIndex = prev.length;
      return [...prev, assistantMsg];
    });
    if (insertedAssistantIndex >= 0) {
      setInspectedIndex(insertedAssistantIndex);
    }
    setInspectorData(result);
    setRetryPrompt(null);
    if (result.suggestions?.length) setSuggestions(result.suggestions);
    void onAfterMessagePersisted();
  }, [chatId, token, streaming, sendMessage, messages.length, streamedTextRef, pendingMetadata, setMessages, setInput, setInspectedIndex, setInspectorData, setRetryPrompt, setSuggestions, textareaRef, onAfterMessagePersisted]);

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
  const router = useRouter();
  const [token, setToken] = useState('');
  const [chatId, setChatId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessions, setSessions] = useState<Chat[]>([]);
  const [input, setInput] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [inspectedIndex, setInspectedIndex] = useState<number | null>(null);
  const [inspectorData, setInspectorData] = useState<StreamedResponse | null>(null);
  const [sessionReady, setSessionReady] = useState(false);
  const [sessionLoading, setSessionLoading] = useState(false);
  const [repo, setRepo] = useState<Repo | null>(null);
  const [retryPrompt, setRetryPrompt] = useState<string | null>(null);

  // ── Graph viewer state ────────────────────────────────────────────────────
  const { fetchKeys, getAvailability } = useGraphCache();
  const [graphAvailability, setGraphAvailability] = useState<GraphAvailability>(() => getAvailability(repoId));
  const [graphViewerOpen, setGraphViewerOpen] = useState(false);
  const [graphFocusSymbol, setGraphFocusSymbol] = useState<string | null>(null);
  const [cachedGraphKeys, setCachedGraphKeys] = useState<Set<string> | undefined>(undefined);

  // ── Adjust state during rendering when graphAvailability changes ──────────
  const [prevAvailability, setPrevAvailability] = useState(graphAvailability);
  if (graphAvailability !== prevAvailability) {
    setPrevAvailability(graphAvailability);
    if (graphAvailability !== 'available') {
      setCachedGraphKeys(undefined);
    }
  }

  const pendingAutoPromptRef = useRef<string | null>(null);
  const [autoPromptTick, setAutoPromptTick] = useState(0);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { streaming, streamedText, streamedTextRef, pendingMetadata, error, sendMessage, cancelStream } =
    useChatStream();

  // ── Prefetch graph keys once token + repoId are both available ───────────
  useEffect(() => {
    if (!token || !repoId) return;
    if (graphAvailability !== 'loading') return;
    void fetchKeys(token, repoId).then((status) => {
      setGraphAvailability(status);
    });
  }, [token, repoId, fetchKeys, graphAvailability]);

  // Keep cachedGraphKeys in sync with graphAvailability (async only)
  useEffect(() => {
    if (!token || !repoId || graphAvailability !== 'available') return;
    getRelationshipGraphKeys(token, repoId)
      .then((d) => setCachedGraphKeys(new Set(d.keys)))
      .catch(() => setCachedGraphKeys(undefined));
  }, [graphAvailability, token, repoId]);

  const handleOpenGraph = useCallback((symbol?: string) => {
    setGraphFocusSymbol(symbol ?? null);
    setGraphViewerOpen(true);
  }, []);

  const handleCloseGraph = useCallback(() => {
    setGraphViewerOpen(false);
  }, []);

  const loadSession = useCallback(async (t: string, targetChatId: string) => {
    setSessionReady(false);
    setSessionLoading(true);
    setMessages([]);
    setRetryPrompt(null);
    setInspectedIndex(null);
    setInspectorData(null);
    setChatId(targetChatId);
    try {
      const history = await getMessages(t, targetChatId);
      setMessages(history.filter((msg) => msg.role !== 'system'));
      setSessionReady(true);
      return history.length;
    } catch (e) {
      setSessionReady(true); // restore so user isn't stuck
      throw e;
    } finally {
      setSessionLoading(false);
    }
  }, []);

  const refreshSessions = useCallback(async (t: string) => {
    const latest = await listChatSessions(t, repoId, { includeArchived: true, includeDeleted: false, limit: 100 });
    setSessions(latest);
    window.dispatchEvent(new CustomEvent('codebase:chat-sessions-updated', { detail: { repoId, sessions: latest } }));
  }, [repoId]);
  const handleCreateQuickAsk = useCallback(async () => {
    if (!token) return;
    try {
      const session = await createQuickAskSession(token, repoId);
      const optimisticSession: Chat = {
        id: session.chat_id,
        repo_id: repoId,
        user_id: '',
        title: 'New chat',
        session_type: 'quick_ask',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        message_count: 0,
        is_archived: false,
        is_pinned: false,
      };
      window.dispatchEvent(new CustomEvent('codebase:chat-session-created', { detail: { repoId, session: optimisticSession } }));
      await refreshSessions(token);
      await loadSession(token, session.chat_id);
      setSuggestions([]);
      pendingAutoPromptRef.current = null;
      setRetryPrompt(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create repository chat');
    }
  }, [token, repoId, refreshSessions, loadSession]);
  const handleOpenReview = useCallback(() => {
    const files = collectReviewTargets(messages);
    const payload = {
      files,
      prompt: 'Review these files for correctness, security, performance, and maintainability risks.',
    };
    try {
      sessionStorage.setItem(`codebase:review-prefill:${repoId}`, JSON.stringify(payload));
    } catch {
      // Ignore storage errors and still navigate.
    }
    router.push(`/repo/${repoId}/review`);
  }, [messages, repoId, router]);
  const handleOpenSession = useCallback(async (targetChatId: string) => {
    if (!token || streaming || sessionLoading) return;
    try {
      await loadSession(token, targetChatId);
      const saved = localStorage.getItem(`chat_suggestions_${targetChatId}`);
      setSuggestions(saved ? JSON.parse(saved) : []);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to open conversation');
    }
  }, [loadSession, sessionLoading, streaming, token]);
  const handleSessionsChanged = useCallback(async () => {
    if (!token) return;
    await refreshSessions(token);
  }, [refreshSessions, token]);
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

  // Listen for sidebar chat-session switch events so the page updates without remount.
  useEffect(() => {
    function handleSwitchSession(e: Event) {
      const { repoId: targetRepo, chatId: targetChat } = (e as CustomEvent<{ repoId: string; chatId: string }>).detail;
      if (targetRepo !== repoId || !targetChat) return;
      void handleOpenSession(targetChat);
    }
    window.addEventListener('codebase:switch-chat-session', handleSwitchSession);
    return () => window.removeEventListener('codebase:switch-chat-session', handleSwitchSession);
  }, [repoId, handleOpenSession]);

  // Listen for sidebar "New Chat" event so clicking New Chat works when already on this page.
  useEffect(() => {
    function handleNewChat(e: Event) {
      const { repoId: targetRepo } = (e as CustomEvent<{ repoId: string }>).detail;
      if (targetRepo !== repoId) return;
      void handleCreateQuickAsk();
    }
    window.addEventListener('codebase:new-chat', handleNewChat);
    return () => window.removeEventListener('codebase:new-chat', handleNewChat);
  }, [repoId, handleCreateQuickAsk]);
  const { routedMode, showEmptyState, handleInputChange, handleSend, handleKeyDown, handleInspect } =
    useChatInteractionHandlers({
      chatId,
      token,
      streaming,
      sendMessage,
      messages,
      streamedText,
      streamedTextRef,
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
      onAfterMessagePersisted: handleSessionsChanged,
      setRetryPrompt,
    });

  const findNearestUserPromptForAssistant = useCallback((assistantIndex: number): string | null => {
    for (let i = Math.min(assistantIndex - 1, messages.length - 1); i >= 0; i -= 1) {
      const msg = messages[i];
      if (msg.role !== 'user') continue;
      const query = (msg.content || '').trim();
      if (query) return query;
    }
    return null;
  }, [messages]);

  const handleTryAgainForAnswer = useCallback((assistantIndex: number) => {
    if (streaming || !sessionReady) return;
    const userPrompt = findNearestUserPromptForAssistant(assistantIndex);
    if (!userPrompt) {
      toast.error('Could not locate the original question for this answer.');
      return;
    }
    void handleSend(userPrompt);
  }, [findNearestUserPromptForAssistant, handleSend, sessionReady, streaming]);

  const handleEditQuestion = useCallback((msg: Message) => {
    const next = (msg.content || '').trim();
    if (!next) return;
    setInput(next);
    requestAnimationFrame(() => {
      if (!textareaRef.current) return;
      textareaRef.current.focus();
      textareaRef.current.selectionStart = textareaRef.current.value.length;
      textareaRef.current.selectionEnd = textareaRef.current.value.length;
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    });
  }, []);

  const isDev = process.env.NODE_ENV !== 'production';
  const displayThreadStats = buildThreadStats(messages, suggestions, inspectedIndex);
  const inspectorPayload = buildInspectorPayload(inspectedIndex, pendingMetadata, inspectorData);
  return (
    <>
      <div className="grid grid-cols-1 gap-4 xl:h-[calc(100dvh-8rem)] xl:grid-cols-[minmax(0,1fr)_21rem] xl:items-start xl:overflow-hidden">
        <div className="min-w-0 xl:h-full xl:min-h-0">
          <ChatWorkspace
            repoId={repoId}
            repo={repo}
            token={token}
            chatId={chatId}
            sessionReady={sessionReady && !sessionLoading}
            showEmptyState={showEmptyState && !sessionLoading}
            messages={messages}
            inspectedIndex={inspectedIndex}
            streaming={streaming}
            streamedText={streamedText}
            error={error}
            retryPrompt={retryPrompt}
            suggestions={suggestions}
            isDev={isDev}
            routedMode={routedMode}
            input={input}
            textareaRef={textareaRef}
            messagesEndRef={messagesEndRef}
            onInspect={handleInspect}
            onSuggestion={handleSend}
            onRetry={() => {
              if (!retryPrompt) return;
              void handleSend(retryPrompt);
            }}
            onTryAgainForAnswer={handleTryAgainForAnswer}
            onEditQuestion={handleEditQuestion}
            onInputChange={handleInputChange}
            onKeyDown={(e) => handleKeyDown(e, input)}
            onSubmit={() => handleSend(input)}
            onCancel={cancelStream}
            sessionLoading={sessionLoading}
            onCreateQuickAsk={handleCreateQuickAsk}
            onOpenReview={handleOpenReview}
            threadStats={displayThreadStats}
            graphAvailability={graphAvailability}
            graphKeys={cachedGraphKeys}
            onOpenGraph={handleOpenGraph}
          />
        </div>

        <div className="xl:sticky xl:top-0 xl:flex xl:h-full xl:min-h-0 xl:flex-col xl:overflow-hidden">
          <div className="min-h-[20rem] overflow-hidden rounded-[1.5rem] border border-border bg-card/80 shadow-lg shadow-black/5 backdrop-blur-sm xl:h-full xl:min-h-0 xl:flex-1">
            <AIInspector data={inspectorPayload} streaming={streaming} />
          </div>
        </div>
      </div>

      {/* Relationship graph viewer modal — lazy loaded */}
      {graphViewerOpen && token && (
        <Suspense fallback={null}>
          <RelationshipGraphViewer
            repoId={repoId}
            token={token}
            focusSymbol={graphFocusSymbol}
            onClose={handleCloseGraph}
          />
        </Suspense>
      )}
    </>
  );
}

