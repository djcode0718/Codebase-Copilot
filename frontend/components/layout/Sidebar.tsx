'use client';
/**
 * components/layout/Sidebar.tsx
 * Persistent workspace navigation — user controls + Home moved to Topbar.
 */
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useRef, useMemo, useState, useSyncExternalStore, type Dispatch, type SetStateAction } from 'react';
import {
  Archive,
  Clock3,
  Download,
  GitBranch,
  MessageSquare,
  MoreHorizontal,
  PanelLeftClose,
  PanelLeftOpen,
  Pencil,
  Pin,
  PinOff,
  Plus,
  Search,
  Sparkles,
  Terminal,
  Trash2,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { getRepoWorkspaceHref, isRepoWorkspaceReady } from '@/lib/repo-routing';
import { createClient } from '@/lib/supabase/client';
import { toast } from 'sonner';
import { ApiRequestError, listChatSessions, updateChatSession, deleteChat, deleteAllChats, exportRepositoryMemory } from '@/lib/api';
import type { Chat, Repo } from '@/lib/types';

const STORAGE_KEY = 'codebase-copilot.sidebar.collapsed';
const ACTIVE_REPO_STORAGE_KEY = 'codebase-copilot.sidebar.active-repo-id';
const HISTORY_VISIBILITY_STORAGE_KEY = 'codebase-copilot.sidebar.history-visibility.v1';
const SIDEBAR_CHAT_VISIBLE_ROWS = 6;

function extractRepoIdFromPath(pathname: string): string | null {
  const match = pathname.match(/^\/repo\/([^/]+)/);
  return match?.[1] ?? null;
}

function readStoredRecord(key: string): Record<string, boolean> {
  if (typeof window === 'undefined') return {};
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, boolean>;
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

function promoteRepoToTop(sortedRepos: Repo[], activeRepoId: string | null): Repo[] {
  if (!activeRepoId) return sortedRepos;
  const idx = sortedRepos.findIndex((repo) => repo.id === activeRepoId);
  if (idx <= 0) return sortedRepos;
  const next = [...sortedRepos];
  const [activeRepo] = next.splice(idx, 1);
  next.unshift(activeRepo);
  return next;
}

function chatSortTimestamp(chat: Chat): number {
  const value = chat.last_message_at || chat.updated_at || chat.created_at || '';
  const ts = value ? new Date(value).getTime() : 0;
  return Number.isFinite(ts) ? ts : 0;
}

function sortChatsByLatest(chats: Chat[]): Chat[] {
  return [...chats].sort((a, b) => chatSortTimestamp(b) - chatSortTimestamp(a));
}

function isExpiredAuthError(err: unknown): boolean {
  if (err instanceof ApiRequestError) {
    return err.status === 401 && /token expired|sign in again/i.test(err.detail || err.message);
  }
  if (err instanceof Error) {
    return /token expired|sign in again/i.test(err.message);
  }
  return false;
}

interface SidebarProps {
  repos?: Repo[];
  userEmail?: string;
  userId?: string;
  mobileOpen?: boolean;
  onMobileClose?: () => void;
}

function openCommandPalette() {
  window.dispatchEvent(new Event('codebase:open-command-palette'));
}

function downloadTextFile(filename: string, content: string, contentType: string) {
  const blob = new Blob([content], { type: contentType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}

async function runChatContextAction(args: {
  action: 'open' | 'pin' | 'archive' | 'rename' | 'delete' | 'download';
  chat: Chat;
  repoId: string;
  token: string;
  fetchChats: (repoId: string) => Promise<Chat[] | undefined>;
  setRepoChats: Dispatch<SetStateAction<Record<string, Chat[]>>>;
}) {
  const { action, chat, repoId, token, fetchChats, setRepoChats } = args;

  if (action === 'pin') {
    await updateChatSession(token, chat.id, { is_pinned: !chat.is_pinned });
    toast.success(chat.is_pinned ? 'Unpinned' : 'Pinned');
    await fetchChats(repoId);
    return;
  }

  if (action === 'archive') {
    await updateChatSession(token, chat.id, { is_archived: !chat.is_archived });
    toast.success(chat.is_archived ? 'Unarchived' : 'Archived');
    await fetchChats(repoId);
    return;
  }

  if (action === 'delete') {
    await deleteChat(token, chat.id);
    setRepoChats((prev) => ({
      ...prev,
      [repoId]: (prev[repoId] ?? []).filter((c) => c.id !== chat.id),
    }));
    toast.success('Conversation deleted');
    return;
  }

  if (action === 'download') {
    const payload = await exportRepositoryMemory(token, repoId, 'md', [chat.id]);
    downloadTextFile(payload.filename, payload.content, payload.content_type || 'text/markdown');
    toast.success('Exported');
  }
}

// ── Chat context menu ─────────────────────────────────────────────────────────

interface ChatMenuState { chat: Chat; repoId: string; x: number; y: number; }

function ChatContextMenu({
  state, onClose, onAction,
}: {
  state: ChatMenuState;
  onClose: () => void;
  onAction: (action: 'open' | 'pin' | 'archive' | 'rename' | 'delete' | 'download', chat: Chat, repoId: string) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const { chat, repoId, x, y } = state;
  const [menuPosition, setMenuPosition] = useState({ left: x, top: y });

  useEffect(() => {
    function updateMenuPosition() {
      if (typeof window === 'undefined') return;
      const viewportPadding = 8;
      const menuEl = ref.current;
      const menuWidth = menuEl?.offsetWidth ?? 200;
      const menuHeight = menuEl?.offsetHeight ?? 280;

      const maxLeft = Math.max(viewportPadding, window.innerWidth - menuWidth - viewportPadding);
      const maxTop = Math.max(viewportPadding, window.innerHeight - menuHeight - viewportPadding);

      const nextLeft = Math.min(Math.max(x, viewportPadding), maxLeft);
      let nextTop = y;

      // Prefer showing below the anchor, but flip above if bottom would clip.
      if (y + menuHeight > window.innerHeight - viewportPadding) {
        nextTop = y - menuHeight;
      }
      nextTop = Math.min(Math.max(nextTop, viewportPadding), maxTop);

      setMenuPosition({ left: nextLeft, top: nextTop });
    }

    updateMenuPosition();
    window.addEventListener('resize', updateMenuPosition);
    window.addEventListener('scroll', updateMenuPosition, true);
    return () => {
      window.removeEventListener('resize', updateMenuPosition);
      window.removeEventListener('scroll', updateMenuPosition, true);
    };
  }, [x, y]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    }
    function handleKeyDown(e: KeyboardEvent) { if (e.key === 'Escape') onClose(); }
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [onClose]);

  const items = [
    { key: 'open'     as const, icon: MessageSquare,                label: 'Open', danger: false },
    { key: 'rename'   as const, icon: Pencil,                       label: 'Rename', danger: false },
    { key: 'pin'      as const, icon: chat.is_pinned ? PinOff : Pin, label: chat.is_pinned ? 'Unpin' : 'Pin', danger: false },
    { key: 'archive'  as const, icon: Archive,                      label: chat.is_archived ? 'Unarchive' : 'Archive', danger: false },
    { key: 'download' as const, icon: Download,                     label: 'Export', danger: false },
    { key: 'delete'   as const, icon: Trash2,                       label: 'Delete', danger: true },
  ] as const;

  return (
    <div
      ref={ref}
      style={{ position: 'fixed', left: menuPosition.left, top: menuPosition.top, zIndex: 9999 }}
      className="min-w-[168px] rounded-2xl border border-sidebar-border bg-sidebar shadow-xl shadow-black/20 py-1 text-sm"
      onClick={(e) => e.stopPropagation()}
    >
      <div className="px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-sidebar-foreground/50 truncate border-b border-sidebar-border/60 mb-1">
        {chat.title || 'Untitled chat'}
      </div>
      {items.map(({ key, icon: Icon, label, danger }) => (
        <button key={key} type="button"
          className={cn(
            'flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm transition-colors hover:bg-sidebar-accent',
            (danger as boolean | undefined) ? 'text-destructive hover:text-destructive' : 'text-sidebar-foreground/80 hover:text-sidebar-foreground'
          )}
          onClick={() => { onClose(); void onAction(key, chat, repoId); }}
        >
          <Icon size={13} className="flex-shrink-0" />
          {label}
        </button>
      ))}
    </div>
  );
}

interface RepoConversationsProps {
  repo: Repo;
  allChats: Chat[];
  visibleChats: Chat[];
  loadingChatRepoId: string | null;
  isSearchOpen: boolean;
  query: string;
  renamingChatId: string | null;
  renameValue: string;
  isRepoHistoryVisible: (repoId: string) => boolean;
  toggleRepoHistory: (repoId: string) => void;
  setSearchOpen: Dispatch<SetStateAction<Record<string, boolean>>>;
  setSearchQuery: Dispatch<SetStateAction<Record<string, string>>>;
  setContextMenu: Dispatch<SetStateAction<ChatMenuState | null>>;
  setRenameValue: Dispatch<SetStateAction<string>>;
  setRenamingChatId: Dispatch<SetStateAction<string | null>>;
  commitRename: (repoId: string) => Promise<void>;
  openChatSession: (repoId: string, chatId: string) => void;
  handleNewChat: (repoId: string) => void;
  handleDeleteAllChats: (repoId: string) => Promise<void>;
}

function RepoConversationsSection(props: RepoConversationsProps) {
  const {
    repo,
    allChats,
    visibleChats,
    loadingChatRepoId,
    isSearchOpen,
    query,
    renamingChatId,
    renameValue,
    isRepoHistoryVisible,
    toggleRepoHistory,
    setSearchOpen,
    setSearchQuery,
    setContextMenu,
    setRenameValue,
    setRenamingChatId,
    commitRename,
    openChatSession,
    handleNewChat,
    handleDeleteAllChats,
  } = props;

  return (
    <div className="ml-5 mt-0.5 space-y-0.5 border-l border-sidebar-border/70 pl-2">
      <div className="mb-0.5 flex items-center justify-between px-2">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-sidebar-foreground/45">Conversations</span>
        <button
          type="button"
          onClick={() => toggleRepoHistory(repo.id)}
          className="text-[10px] text-sidebar-foreground/55 underline underline-offset-2 hover:text-sidebar-foreground"
        >
          {isRepoHistoryVisible(repo.id) ? 'Hide' : 'Show'}
        </button>
      </div>

      {isRepoHistoryVisible(repo.id) && (
        <>
          {isSearchOpen ? (
            <div className="flex items-center gap-1 rounded-xl border border-sidebar-border bg-sidebar px-2 py-1.5 mb-1">
              <Search size={11} className="shrink-0 text-sidebar-foreground/45" />
              <input
                autoFocus
                value={query}
                onChange={(e) => setSearchQuery(prev => ({ ...prev, [repo.id]: e.target.value }))}
                placeholder="Search conversations…"
                className="flex-1 min-w-0 bg-transparent text-xs outline-none placeholder:text-sidebar-foreground/40 text-sidebar-foreground"
              />
              <button type="button"
                onClick={() => { setSearchOpen(p => ({ ...p, [repo.id]: false })); setSearchQuery(p => ({ ...p, [repo.id]: '' })); }}
                className="text-sidebar-foreground/40 hover:text-sidebar-foreground"
              ><X size={11} /></button>
            </div>
          ) : (
            <button type="button"
              onClick={() => setSearchOpen(p => ({ ...p, [repo.id]: true }))}
              className="flex w-full items-center gap-1.5 rounded-xl px-2 py-1.5 text-left text-xs text-sidebar-foreground/60 transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground"
            >
              <Search size={11} /> <span className="truncate">Search conversations</span>
            </button>
          )}

          <div className="flex items-center gap-1 pt-0.5">
            <button type="button"
              onClick={() => handleNewChat(repo.id)}
              className="flex flex-1 items-center gap-1.5 rounded-xl px-2 py-1.5 text-xs font-medium text-brand transition-colors hover:bg-brand/10"
            >
              <Plus size={11} /> New Chat
            </button>
            {allChats.length > 0 && (
              <button type="button" title="Delete all conversations"
                onClick={() => void handleDeleteAllChats(repo.id)}
                className="flex h-6 w-6 items-center justify-center rounded-lg text-destructive/40 hover:text-destructive hover:bg-destructive/10 transition-colors"
              >
                <Trash2 size={11} />
              </button>
            )}
          </div>

          <div
            className={cn(
              'space-y-0.5 pb-1',
              visibleChats.length > SIDEBAR_CHAT_VISIBLE_ROWS && 'max-h-48 overflow-y-auto pr-1 scrollbar-thin'
            )}
          >
            {loadingChatRepoId === repo.id ? (
              <div className="px-2 py-1 text-[11px] text-sidebar-foreground/50">Loading…</div>
            ) : visibleChats.length === 0 ? (
              <div className="px-2 py-1 text-[11px] text-sidebar-foreground/50">
                {query ? 'No matches' : 'No conversations yet'}
              </div>
            ) : (
              visibleChats.map((chat) => {
                const isRenaming = renamingChatId === chat.id;
                return (
                  <div key={chat.id}
                    className="group flex items-center gap-1 rounded-xl hover:bg-sidebar-accent transition-colors"
                    onContextMenu={(e) => { e.preventDefault(); setContextMenu({ chat, repoId: repo.id, x: e.clientX, y: e.clientY }); }}
                  >
                    {isRenaming ? (
                      <div className="flex flex-1 items-center gap-1 px-2 py-1">
                        <input autoFocus value={renameValue}
                          onChange={(e) => setRenameValue(e.target.value)}
                          onKeyDown={(e) => { if (e.key === 'Enter') void commitRename(repo.id); if (e.key === 'Escape') setRenamingChatId(null); }}
                          onBlur={() => void commitRename(repo.id)}
                          className="flex-1 min-w-0 rounded border border-sidebar-border bg-sidebar px-1.5 py-0.5 text-xs outline-none focus:border-brand"
                        />
                      </div>
                    ) : (
                      <>
                        <button type="button" onClick={() => openChatSession(repo.id, chat.id)}
                          className="flex-1 min-w-0 truncate px-2 py-1.5 text-left text-xs text-sidebar-foreground/65 hover:text-sidebar-foreground"
                          title={chat.title || 'Untitled chat'}
                        >
                          {chat.is_pinned ? '★ ' : ''}{chat.title || 'Untitled chat'}
                        </button>
                        <button
                          type="button"
                          title="More options"
                          className="mr-1 hidden group-hover:flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-md text-sidebar-foreground/50 hover:text-sidebar-foreground hover:bg-sidebar-border/60 transition-colors"
                          onClick={(e) => {
                            e.stopPropagation();
                            e.preventDefault();
                            const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
                            setContextMenu({ chat, repoId: repo.id, x: rect.left, y: rect.bottom + 4 });
                          }}
                        >
                          <MoreHorizontal size={13} />
                        </button>
                      </>
                    )}
                  </div>
                );
              })
            )}

          </div>
        </>
      )}
    </div>
  );
}

interface RepositoryListSectionProps {
  collapsed: boolean;
  pathname: string;
  recentRepos: Repo[];
  repoChats: Record<string, Chat[]>;
  loadingChatRepoId: string | null;
  searchOpen: Record<string, boolean>;
  searchQuery: Record<string, string>;
  renamingChatId: string | null;
  renameValue: string;
  isRepoHistoryVisible: (repoId: string) => boolean;
  toggleRepoHistory: (repoId: string) => void;
  setSearchOpen: Dispatch<SetStateAction<Record<string, boolean>>>;
  setSearchQuery: Dispatch<SetStateAction<Record<string, string>>>;
  setContextMenu: Dispatch<SetStateAction<ChatMenuState | null>>;
  setRenameValue: Dispatch<SetStateAction<string>>;
  setRenamingChatId: Dispatch<SetStateAction<string | null>>;
  setActiveRepoPreference: (repoId: string, source: 'repo-link' | 'new-chat' | 'open-chat') => void;
  closeMobileIfOpen: () => void;
  commitRename: (repoId: string) => Promise<void>;
  openChatSession: (repoId: string, chatId: string) => void;
  handleNewChat: (repoId: string) => void;
  handleDeleteAllChats: (repoId: string) => Promise<void>;
}

function RepositoryListSection(props: RepositoryListSectionProps) {
  const {
    collapsed,
    pathname,
    recentRepos,
    repoChats,
    loadingChatRepoId,
    searchOpen,
    searchQuery,
    renamingChatId,
    renameValue,
    isRepoHistoryVisible,
    toggleRepoHistory,
    setSearchOpen,
    setSearchQuery,
    setContextMenu,
    setRenameValue,
    setRenamingChatId,
    setActiveRepoPreference,
    closeMobileIfOpen,
    commitRename,
    openChatSession,
    handleNewChat,
    handleDeleteAllChats,
  } = props;

  if (recentRepos.length === 0) {
    return (
      <div className={cn('rounded-xl border border-dashed border-sidebar-border/80 bg-sidebar-accent/20 p-3', collapsed && 'text-center')}>
        {!collapsed ? (
          <><p className="text-sm font-medium text-sidebar-foreground">No repositories yet</p>
          <p className="mt-1 text-xs text-sidebar-foreground/60">Index a repository to populate the workspace.</p></>
        ) : <Clock3 size={15} className="mx-auto text-sidebar-foreground/55" />}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {!collapsed && <div className="px-2.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-sidebar-foreground/55">Repositories</div>}
      <div className="space-y-1">
        {recentRepos.map((repo) => {
          const isActive = pathname.startsWith(`/repo/${repo.id}`);
          const href = getRepoWorkspaceHref(repo);
          const isWorkspaceReady = isRepoWorkspaceReady(repo);
          const allChats = repoChats[repo.id] ?? [];
          const query = (searchQuery[repo.id] ?? '').trim().toLowerCase();
          const visibleChats = query
            ? allChats.filter(c => (c.title || '').toLowerCase().includes(query) || (c.last_message_preview || '').toLowerCase().includes(query))
            : allChats;
          const isSearchOpen = searchOpen[repo.id] ?? false;

          return (
            <div key={repo.id}>
              <Link href={href} onClick={() => { setActiveRepoPreference(repo.id, 'repo-link'); closeMobileIfOpen(); }}
                className={cn(
                  'flex items-center gap-2 rounded-2xl px-3 py-2.5 text-sm transition-all duration-150 group',
                  collapsed && 'justify-center px-0',
                  isActive ? 'bg-sidebar-accent text-foreground border border-sidebar-border' : 'text-sidebar-foreground/72 hover:bg-sidebar-accent hover:text-foreground'
                )} title={repo.name}
              >
                <GitBranch size={14} className="flex-shrink-0" />
                {!collapsed && (
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">{repo.name}</div>
                    <div className="truncate text-[11px] text-sidebar-foreground/55">{repo.index_name}</div>
                  </div>
                )}
              </Link>

              {!collapsed && isWorkspaceReady && (
                <RepoConversationsSection
                  repo={repo}
                  allChats={allChats}
                  visibleChats={visibleChats}
                  loadingChatRepoId={loadingChatRepoId}
                  isSearchOpen={isSearchOpen}
                  query={query}
                  renamingChatId={renamingChatId}
                  renameValue={renameValue}
                  isRepoHistoryVisible={isRepoHistoryVisible}
                  toggleRepoHistory={toggleRepoHistory}
                  setSearchOpen={setSearchOpen}
                  setSearchQuery={setSearchQuery}
                  setContextMenu={setContextMenu}
                  setRenameValue={setRenameValue}
                  setRenamingChatId={setRenamingChatId}
                  commitRename={commitRename}
                  openChatSession={openChatSession}
                  handleNewChat={handleNewChat}
                  handleDeleteAllChats={handleDeleteAllChats}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Main sidebar ──────────────────────────────────────────────────────────────

export default function Sidebar({ repos = [], userEmail, userId, mobileOpen = false, onMobileClose }: SidebarProps) {
  const pathname = usePathname();
  const router   = useRouter();
  const supabase = useMemo(() => createClient(), []);
  const userIdRef = useRef(userId);

  const [repoChats,        setRepoChats]        = useState<Record<string, Chat[]>>({});
  const [loadingChatRepoId, setLoadingChatRepoId] = useState<string | null>(null);
  const [contextMenu,      setContextMenu]      = useState<ChatMenuState | null>(null);
  const [renamingChatId,   setRenamingChatId]   = useState<string | null>(null);
  const [renameValue,      setRenameValue]      = useState('');
  const [authToken,        setAuthToken]        = useState('');
  const authExpiredNotifiedRef = useRef(false);
  // Per-repo inline search
  const [searchOpen,   setSearchOpen]   = useState<Record<string, boolean>>({});
  const [searchQuery,  setSearchQuery]  = useState<Record<string, string>>({});
  const [historyVisibleByRepo, setHistoryVisibleByRepo] = useState<Record<string, boolean>>(() => {
    return readStoredRecord(HISTORY_VISIBILITY_STORAGE_KEY);
  });
  const [lastUsedRepoId, setLastUsedRepoId] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null;
    try {
      return window.localStorage.getItem(ACTIVE_REPO_STORAGE_KEY);
    } catch {
      return null;
    }
  });

  // Track latest userId ref and reset cached chats whenever user identity changes
  useEffect(() => {
    userIdRef.current = userId;
    setRepoChats({});
    setLoadingChatRepoId(null);
    setSearchQuery({});
    setSearchOpen({});
  }, [userId]);

  function logSidebarOperation(operation: string, details: Record<string, unknown> = {}) {
    console.info('[Sidebar]', operation, details);
  }

  const activeRepoIdFromPath = useMemo(() => extractRepoIdFromPath(pathname), [pathname]);
  const activeRepoId = activeRepoIdFromPath ?? lastUsedRepoId;

  // Keep auth token fresh — avoids async session fetch inside action handlers
  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setAuthToken(data.session?.access_token ?? '');
    });
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      setAuthToken(session?.access_token ?? '');
      if (event === 'SIGNED_OUT' || !session) {
        setRepoChats({});
        setLoadingChatRepoId(null);
        setLastUsedRepoId(null);
      }
    });
    return () => subscription.unsubscribe();
  }, [supabase]);

  const isHydrated = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false
  );
  const collapsedStored = useSyncExternalStore(
    (onStoreChange) => {
      window.addEventListener('storage', onStoreChange);
      window.addEventListener('codebase-sidebar-collapsed-change', onStoreChange);
      return () => {
        window.removeEventListener('storage', onStoreChange);
        window.removeEventListener('codebase-sidebar-collapsed-change', onStoreChange);
      };
    },
    () => { try { return window.localStorage.getItem(STORAGE_KEY) === '1'; } catch { return false; } },
    () => false
  );
  const collapsed = isHydrated ? collapsedStored : false;

  useEffect(() => {
    if (!activeRepoIdFromPath) return;
    try { window.localStorage.setItem(ACTIVE_REPO_STORAGE_KEY, activeRepoIdFromPath); } catch {}
    logSidebarOperation('active-repo-path-updated', { repoId: activeRepoIdFromPath });
  }, [activeRepoIdFromPath]);

  function setCollapsed(nextValue: boolean) {
    try { window.localStorage.setItem(STORAGE_KEY, nextValue ? '1' : '0'); } catch {}
    window.dispatchEvent(new Event('codebase-sidebar-collapsed-change'));
  }

  useEffect(() => {
    if (mobileOpen) {
      document.body.style.overflow = 'hidden';
      return () => { document.body.style.overflow = ''; };
    }
    document.body.style.overflow = '';
    return undefined;
  }, [mobileOpen]);

  function closeMobileIfOpen() { onMobileClose?.(); }

  function setActiveRepoPreference(repoId: string, source: 'repo-link' | 'new-chat' | 'open-chat') {
    setLastUsedRepoId(repoId);
    try { window.localStorage.setItem(ACTIVE_REPO_STORAGE_KEY, repoId); } catch {}
    logSidebarOperation('active-repo-updated', { repoId, source });
  }

  function isRepoHistoryVisible(repoId: string) {
    return historyVisibleByRepo[repoId] ?? true;
  }

  function toggleRepoHistory(repoId: string) {
    setHistoryVisibleByRepo((prev) => {
      const next = !(prev[repoId] ?? true);
      const updated = { ...prev, [repoId]: next };
      try { window.localStorage.setItem(HISTORY_VISIBILITY_STORAGE_KEY, JSON.stringify(updated)); } catch {}
      logSidebarOperation('repo-history-visibility-changed', { repoId, visible: next });
      return updated;
    });
  }

  const sortedRepos = useMemo(
    () => [...repos].sort((a, b) => (b.created_at || '').localeCompare(a.created_at || '')),
    [repos]
  );
  const prioritizedRepos = useMemo(() => {
    return promoteRepoToTop(sortedRepos, activeRepoId);
  }, [activeRepoId, sortedRepos]);
  const recentRepos = prioritizedRepos.slice(0, 5);

  async function fetchChats(
    repoId: string,
    token?: string,
    options?: { originatingUserId?: string; isCancelled?: () => boolean }
  ) {
    const t = token ?? authToken;
    const requestUserId = options?.originatingUserId ?? userIdRef.current;
    if (!t || !requestUserId) return;
    try {
      const sessions = await listChatSessions(t, repoId, { includeArchived: true, includeDeleted: false, limit: 20 });
      // Discard stale responses if cancelled or user changed before request completed
      if (options?.isCancelled?.() || userIdRef.current !== requestUserId) {
        return;
      }
      authExpiredNotifiedRef.current = false;
      setRepoChats((prev) => ({ ...prev, [repoId]: sortChatsByLatest(sessions) }));
      return sessions;
    } catch (err) {
      if (options?.isCancelled?.() || userIdRef.current !== requestUserId) {
        return;
      }
      if (isExpiredAuthError(err)) {
        if (!authExpiredNotifiedRef.current) {
          authExpiredNotifiedRef.current = true;
          toast.error('Your session has expired. Please sign in again.');
        }
        setRepoChats((prev) => ({ ...prev, [repoId]: [] }));
        return [];
      }
      throw err;
    }
  }

  useEffect(() => {
    function handleChatSessionCreated(e: Event) {
      const detail = (e as CustomEvent<{ repoId: string; session: Chat }>).detail;
      if (!detail?.repoId || !detail?.session) return;

      setRepoChats((prev) => {
        const existing = prev[detail.repoId] ?? [];
        const withoutDup = existing.filter((chat) => chat.id !== detail.session.id);
        return {
          ...prev,
          [detail.repoId]: sortChatsByLatest([detail.session, ...withoutDup]),
        };
      });

      void fetchChats(detail.repoId).catch(() => undefined);
    }

    function handleChatSessionsUpdated(e: Event) {
      const detail = (e as CustomEvent<{ repoId: string; sessions: Chat[] }>).detail;
      if (!detail?.repoId || !Array.isArray(detail.sessions)) return;
      setRepoChats((prev) => ({
        ...prev,
        [detail.repoId]: sortChatsByLatest(detail.sessions),
      }));
    }

    window.addEventListener('codebase:chat-session-created', handleChatSessionCreated as EventListener);
    window.addEventListener('codebase:chat-sessions-updated', handleChatSessionsUpdated as EventListener);
    return () => {
      window.removeEventListener('codebase:chat-session-created', handleChatSessionCreated as EventListener);
      window.removeEventListener('codebase:chat-sessions-updated', handleChatSessionsUpdated as EventListener);
    };
    // We intentionally rely on latest closure values for fetchChats/auth token.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authToken]);

  // Auto-load chats for all ready repos with cancellation and account isolation guards
  useEffect(() => {
    let cancelled = false;

    async function loadChats() {
      const { data } = await supabase.auth.getSession();
      const token = data.session?.access_token ?? '';
      const requestUserId = data.session?.user?.id;
      if (!token || !requestUserId || !userId || requestUserId !== userId) return;

      for (const repo of recentRepos) {
        if (cancelled || userIdRef.current !== requestUserId) break;
        if (repo.status !== 'ready' || repoChats[repo.id]) continue;
        try {
          setLoadingChatRepoId(repo.id);
          await fetchChats(repo.id, token, {
            originatingUserId: requestUserId,
            isCancelled: () => cancelled,
          });
          if (cancelled || userIdRef.current !== requestUserId) break;

          // Guard against account switches while async requests are in flight
          const { data: verifyData } = await supabase.auth.getSession();
          if (verifyData.session?.user?.id !== requestUserId) break;
        } catch {
          if (!cancelled && userIdRef.current === requestUserId) {
            setRepoChats((prev) => ({ ...prev, [repo.id]: [] }));
          }
        } finally {
          if (!cancelled && userIdRef.current === requestUserId) {
            setLoadingChatRepoId(null);
          }
        }
      }
    }

    if (recentRepos.length > 0 && userId) void loadChats();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recentRepos.map(r => r.id).join(','), userId]);

  function openChatSession(repoId: string, chatId: string) {
    setActiveRepoPreference(repoId, 'open-chat');
    try { sessionStorage.setItem(`codebase:open-chat-session:${repoId}`, chatId); } catch {}
    window.dispatchEvent(new CustomEvent('codebase:switch-chat-session', { detail: { repoId, chatId } }));
    router.push(`/repo/${repoId}/chat`);
    closeMobileIfOpen();
  }

  /** Create a new chat — works whether or not we're already on the chat page */
  function handleNewChat(repoId: string) {
    setActiveRepoPreference(repoId, 'new-chat');
    try { sessionStorage.setItem(`codebase:new-chat:${repoId}`, '1'); } catch {}
    window.dispatchEvent(new CustomEvent('codebase:new-chat', { detail: { repoId } }));
    router.push(`/repo/${repoId}/chat`);
    closeMobileIfOpen();
  }

  async function handleContextAction(
    action: 'open' | 'pin' | 'archive' | 'rename' | 'delete' | 'download',
    chat: Chat,
    repoId: string
  ) {
    if (action === 'open')   { openChatSession(repoId, chat.id); return; }
    if (action === 'rename') { setRenamingChatId(chat.id); setRenameValue(chat.title || ''); return; }

    const token = authToken;
    if (!token) { toast.error('Not authenticated'); return; }

    try {
      await runChatContextAction({
        action,
        chat,
        repoId,
        token,
        fetchChats,
        setRepoChats,
      });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Action failed');
    }
  }

  async function handleDeleteAllChats(repoId: string) {
    const token = authToken;
    if (!token) { toast.error('Not authenticated'); return; }
    try {
      await deleteAllChats(token, repoId);
      setRepoChats((prev) => ({ ...prev, [repoId]: [] }));
      toast.success('All conversations deleted');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete all conversations');
    }
  }

  async function commitRename(repoId: string) {
    const title = renameValue.trim();
    if (!title || !renamingChatId) { setRenamingChatId(null); return; }
    const token = authToken;
    if (!token) return;
    try {
      await updateChatSession(token, renamingChatId, { title });
      await fetchChats(repoId);
      toast.success('Renamed');
    } catch { toast.error('Failed to rename'); }
    finally { setRenamingChatId(null); }
  }

  return (
    <>
      <div
        className={cn('fixed inset-0 z-40 bg-black/35 backdrop-blur-[1px] transition-opacity md:hidden', mobileOpen ? 'opacity-100' : 'pointer-events-none opacity-0')}
        onClick={closeMobileIfOpen} aria-hidden="true"
      />

      {contextMenu && (
        <ChatContextMenu state={contextMenu} onClose={() => setContextMenu(null)} onAction={handleContextAction} />
      )}

      <aside className={cn(
        'fixed inset-y-0 left-0 z-50 flex h-screen flex-col border-r border-sidebar-border bg-sidebar/95 text-sidebar-foreground shadow-[0_0_0_1px_rgba(255,255,255,0.02),0_24px_80px_rgba(15,23,42,0.16)] backdrop-blur-xl transition-all duration-200 md:sticky md:top-0 md:z-auto md:self-start md:translate-x-0',
        mobileOpen ? 'translate-x-0' : '-translate-x-full',
        collapsed ? 'w-20 max-w-20 md:w-20' : 'w-[18.5rem] max-w-[88vw] md:w-72'
      )}>
        {/* Brand + collapse */}
        <div className={cn('flex items-center gap-2 border-b border-sidebar-border p-4', collapsed ? 'flex-col justify-center gap-3 px-2 py-3' : 'justify-between')}>
          <Link href="/dashboard" onClick={closeMobileIfOpen} className={cn('flex items-center gap-2 group', collapsed && 'justify-center')} title="Codebase Copilot">
            <div className="w-10 h-10 rounded-2xl bg-brand/15 border border-brand/20 flex items-center justify-center flex-shrink-0 shadow-lg shadow-brand/10">
              <Terminal size={15} className="text-brand" />
            </div>
            {!collapsed && (
              <div className="min-w-0">
                <span className="block font-heading font-semibold text-sm tracking-tight truncate">Codebase Copilot</span>
                <span className="block text-[11px] text-sidebar-foreground/60 truncate">Enterprise workspace</span>
              </div>
            )}
          </Link>
          <button type="button" onClick={() => setCollapsed(!collapsed)}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-sidebar-border bg-sidebar-accent/60 text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent transition-colors"
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? <PanelLeftOpen size={15} /> : <PanelLeftClose size={15} />}
          </button>
        </div>

        {/* Quick actions */}
        <div className="border-b border-sidebar-border p-3 space-y-2">
          {!collapsed && (
            <div className="flex items-center gap-2 px-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-sidebar-foreground/55">
              <Sparkles size={12} /> Quick actions
            </div>
          )}
          <div className={cn('grid gap-2', collapsed && 'place-items-center')}>
            <button type="button" onClick={() => { openCommandPalette(); closeMobileIfOpen(); }}
              className={cn('flex items-center gap-2 rounded-2xl border border-sidebar-border bg-sidebar-accent/50 px-3 py-2.5 text-sm text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-sidebar-foreground transition-colors', collapsed && 'h-11 w-11 justify-center px-0')}
              title="Search workspace (⌘K)"
            >
              <Search size={15} className="shrink-0" />
              {!collapsed && <span className="truncate">Search workspace</span>}
            </button>
          </div>
        </div>

        {/* Repositories + chats */}
        <div className="flex-1 overflow-y-auto p-2 scrollbar-thin">
          {!collapsed && (
            <div className="flex items-center justify-between px-2.5 py-1.5 mb-1">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Recent</span>
            </div>
          )}
          <RepositoryListSection
            collapsed={collapsed}
            pathname={pathname}
            recentRepos={recentRepos}
            repoChats={repoChats}
            loadingChatRepoId={loadingChatRepoId}
            searchOpen={searchOpen}
            searchQuery={searchQuery}
            renamingChatId={renamingChatId}
            renameValue={renameValue}
            isRepoHistoryVisible={isRepoHistoryVisible}
            toggleRepoHistory={toggleRepoHistory}
            setSearchOpen={setSearchOpen}
            setSearchQuery={setSearchQuery}
            setContextMenu={setContextMenu}
            setRenameValue={setRenameValue}
            setRenamingChatId={setRenamingChatId}
            setActiveRepoPreference={setActiveRepoPreference}
            closeMobileIfOpen={closeMobileIfOpen}
            commitRename={commitRename}
            openChatSession={openChatSession}
            handleNewChat={handleNewChat}
            handleDeleteAllChats={handleDeleteAllChats}
          />
        </div>

        {/* Repository Explorer - Only on /repo/[id]/review page */}
        {pathname.includes('/review') && (
          <div className="flex-1 overflow-y-auto border-t border-sidebar-border mt-3 pt-3">
            <div className="px-2.5 py-1.5 mb-2">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-sidebar-foreground/60">Repository Files</h3>
            </div>
            <div className="space-y-1 px-1">
              <p className="px-2.5 text-[10px] text-sidebar-foreground/50 italic">Open files from the explorer panel on the right. Files will appear here when selected.</p>
            </div>
          </div>
        )}

        {/* Chat History - Only on non-review pages */}
        {!pathname.includes('/review') && (
          <div className="border-t border-sidebar-border mt-3 pt-3">
            <div className="flex items-center justify-between px-2.5 py-1.5">
              <span className="text-xs font-semibold text-sidebar-foreground/60 uppercase tracking-wider">Chat History</span>
            </div>
            <div className="mt-2 space-y-1 max-h-[200px] overflow-auto text-[11px] text-sidebar-foreground/60">
              <p className="px-2">Chat sessions will appear here</p>
            </div>
          </div>
        )}
        {/* User section moved to Topbar */}
      </aside>
    </>
  );
}
