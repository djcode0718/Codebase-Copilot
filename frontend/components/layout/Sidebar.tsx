'use client';
/**
 * components/layout/Sidebar.tsx
 * Persistent workspace navigation: collapsible shell, quick actions, recent repos, user controls.
 */
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useRef, useMemo, useState, useSyncExternalStore } from 'react';
import {
  Archive,
  ChevronDown,
  ChevronUp,
  Clock3,
  GitBranch,
  Home,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  MoreHorizontal,
  PanelLeftClose,
  PanelLeftOpen,
  Pencil,
  Pin,
  PinOff,
  Plus,
  Search,
  Settings,
  Sparkles,
  Terminal,
  Trash2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { createClient } from '@/lib/supabase/client';
import { toast } from 'sonner';
import { listChatSessions, updateChatSession, deleteChat } from '@/lib/api';
import type { Chat, Repo } from '@/lib/types';

const STORAGE_KEY = 'codebase-copilot.sidebar.collapsed';

interface SidebarProps {
  repos?: Repo[];
  userEmail?: string;
  mobileOpen?: boolean;
  onMobileClose?: () => void;
}

function openCommandPalette() {
  window.dispatchEvent(new Event('codebase:open-command-palette'));
}

// ── Chat context menu ─────────────────────────────────────────────────────────

interface ChatMenuState {
  chat: Chat;
  repoId: string;
  x: number;
  y: number;
}

function ChatContextMenu({
  state,
  onClose,
  onAction,
}: {
  state: ChatMenuState;
  onClose: () => void;
  onAction: (action: 'open' | 'pin' | 'archive' | 'rename' | 'delete', chat: Chat, repoId: string) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const { chat, repoId, x, y } = state;

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    }
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [onClose]);

  // Clamp to viewport
  const left = Math.min(x, (typeof window !== 'undefined' ? window.innerWidth : 400) - 180);
  const top = Math.min(y, (typeof window !== 'undefined' ? window.innerHeight : 600) - 200);

  const items = [
    { key: 'open' as const, icon: MessageSquare, label: 'Open' },
    { key: 'pin' as const, icon: chat.is_pinned ? PinOff : Pin, label: chat.is_pinned ? 'Unpin' : 'Pin' },
    { key: 'archive' as const, icon: Archive, label: chat.is_archived ? 'Unarchive' : 'Archive' },
    { key: 'rename' as const, icon: Pencil, label: 'Rename' },
    { key: 'delete' as const, icon: Trash2, label: 'Delete', danger: true },
  ] as const;

  return (
    <div
      ref={ref}
      style={{ position: 'fixed', left, top, zIndex: 9999 }}
      className="min-w-[168px] rounded-2xl border border-sidebar-border bg-sidebar shadow-xl shadow-black/20 py-1 text-sm"
      onClick={(e) => e.stopPropagation()}
    >
      <div className="px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-sidebar-foreground/50 truncate border-b border-sidebar-border/60 mb-1">
        {chat.title || 'Untitled chat'}
      </div>
      {items.map(({ key, icon: Icon, label, danger }) => (
        <button
          key={key}
          type="button"
          className={cn(
            'flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm transition-colors hover:bg-sidebar-accent',
            (danger as boolean) ? 'text-destructive hover:text-destructive' : 'text-sidebar-foreground/80 hover:text-sidebar-foreground'
          )}
          onClick={() => { onAction(key, chat, repoId); onClose(); }}
        >
          <Icon size={13} className="flex-shrink-0" />
          {label}
        </button>
      ))}
    </div>
  );
}

// ── Main sidebar ──────────────────────────────────────────────────────────────

export default function Sidebar({
  repos = [],
  userEmail,
  mobileOpen = false,
  onMobileClose,
}: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const supabase = useMemo(() => createClient(), []);

  const [expandedRepoId, setExpandedRepoId] = useState<string | null>(null);
  const [repoChats, setRepoChats] = useState<Record<string, Chat[]>>({});
  const [loadingChatRepoId, setLoadingChatRepoId] = useState<string | null>(null);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [contextMenu, setContextMenu] = useState<ChatMenuState | null>(null);
  const [renamingChatId, setRenamingChatId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');

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
    () => {
      try {
        return window.localStorage.getItem(STORAGE_KEY) === '1';
      } catch {
        return false;
      }
    },
    () => false
  );
  const collapsed = isHydrated ? collapsedStored : false;

  function setCollapsed(nextValue: boolean) {
    try {
      window.localStorage.setItem(STORAGE_KEY, nextValue ? '1' : '0');
    } catch {
      // ignore storage errors
    }

    window.dispatchEvent(new Event('codebase-sidebar-collapsed-change'));
  }

  useEffect(() => {
    if (mobileOpen) {
      document.body.style.overflow = 'hidden';
      return () => {
        document.body.style.overflow = '';
      };
    }

    document.body.style.overflow = '';
    return undefined;
  }, [mobileOpen]);

  function closeMobileIfOpen() {
    onMobileClose?.();
  }

  const sortedRepos = useMemo(
    () => [...repos].sort((a, b) => (b.created_at || '').localeCompare(a.created_at || '')),
    [repos]
  );
  const recentRepos = sortedRepos.slice(0, 5);

  async function handleSignOut() {
    await supabase.auth.signOut();
    closeMobileIfOpen();
    router.push('/auth/sign-in');
    router.refresh();
    toast.success('Signed out');
  }

  async function toggleRepoChatHistory(repo: Repo) {
    if (expandedRepoId === repo.id) {
      setExpandedRepoId(null);
      return;
    }

    setExpandedRepoId(repo.id);
    if (repoChats[repo.id]) return;

    setLoadingChatRepoId(repo.id);
    try {
      const { data } = await supabase.auth.getSession();
      const token = data.session?.access_token ?? '';
      if (!token) return;
      const sessions = await listChatSessions(token, repo.id, { includeArchived: true, includeDeleted: false, limit: 8 });
      setRepoChats((prev) => ({ ...prev, [repo.id]: sessions }));
    } catch {
      setRepoChats((prev) => ({ ...prev, [repo.id]: [] }));
    } finally {
      setLoadingChatRepoId(null);
    }
  }

  /** Navigate to a specific chat session, dispatching event if page already open. */
  function openChatSession(repoId: string, chatId: string) {
    try { sessionStorage.setItem(`codebase:open-chat-session:${repoId}`, chatId); } catch {}
    window.dispatchEvent(new CustomEvent('codebase:switch-chat-session', { detail: { repoId, chatId } }));
    router.push(`/repo/${repoId}/chat`);
    closeMobileIfOpen();
  }

  async function handleContextAction(
    action: 'open' | 'pin' | 'archive' | 'rename' | 'delete',
    chat: Chat,
    repoId: string
  ) {
    if (action === 'open') { openChatSession(repoId, chat.id); return; }
    if (action === 'rename') {
      setRenamingChatId(chat.id);
      setRenameValue(chat.title || '');
      return;
    }
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token ?? '';
    if (!token) return;
    try {
      if (action === 'pin') {
        await updateChatSession(token, chat.id, { is_pinned: !chat.is_pinned });
        toast.success(chat.is_pinned ? 'Unpinned' : 'Pinned');
      } else if (action === 'archive') {
        await updateChatSession(token, chat.id, { is_archived: !chat.is_archived });
        toast.success(chat.is_archived ? 'Unarchived' : 'Archived');
      } else if (action === 'delete') {
        if (!window.confirm('Delete this conversation?')) return;
        await deleteChat(token, chat.id);
        toast.success('Conversation deleted');
      }
      // Refresh chat list for this repo
      const sessions = await listChatSessions(token, repoId, { includeArchived: true, includeDeleted: false, limit: 8 });
      setRepoChats((prev) => ({ ...prev, [repoId]: sessions }));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Action failed');
    }
  }

  async function commitRename(repoId: string) {
    const title = renameValue.trim();
    if (!title || !renamingChatId) { setRenamingChatId(null); return; }
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token ?? '';
    if (!token) return;
    try {
      await updateChatSession(token, renamingChatId, { title });
      const sessions = await listChatSessions(token, repoId, { includeArchived: true, includeDeleted: false, limit: 8 });
      setRepoChats((prev) => ({ ...prev, [repoId]: sessions }));
      toast.success('Renamed');
    } catch {
      toast.error('Failed to rename');
    } finally {
      setRenamingChatId(null);
    }
  }

  return (
    <>
      <div
        className={cn(
          'fixed inset-0 z-40 bg-black/35 backdrop-blur-[1px] transition-opacity md:hidden',
          mobileOpen ? 'opacity-100' : 'pointer-events-none opacity-0'
        )}
        onClick={closeMobileIfOpen}
        aria-hidden="true"
      />

      {contextMenu && (
        <ChatContextMenu
          state={contextMenu}
          onClose={() => setContextMenu(null)}
          onAction={handleContextAction}
        />
      )}

      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 flex h-screen flex-col border-r border-sidebar-border bg-sidebar/95 text-sidebar-foreground shadow-[0_0_0_1px_rgba(255,255,255,0.02),0_24px_80px_rgba(15,23,42,0.16)] backdrop-blur-xl transition-all duration-200 md:sticky md:top-0 md:z-auto md:self-start md:translate-x-0',
          mobileOpen ? 'translate-x-0' : '-translate-x-full',
          collapsed ? 'w-20 max-w-20 md:w-20' : 'w-[18.5rem] max-w-[88vw] md:w-72'
        )}
      >
        {/* Brand + collapse */}
        <div className={cn('flex items-center gap-2 border-b border-sidebar-border p-4', collapsed ? 'flex-col justify-center gap-3 px-2 py-3' : 'justify-between')}>
          <Link
            href="/dashboard"
            onClick={closeMobileIfOpen}
            className={cn('flex items-center gap-2 group', collapsed && 'justify-center')}
            title="Codebase Copilot"
          >
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
          <button
            type="button"
            onClick={() => setCollapsed(!collapsed)}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-sidebar-border bg-sidebar-accent/60 text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent transition-colors"
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? <PanelLeftOpen size={15} /> : <PanelLeftClose size={15} />}
          </button>
        </div>

        {/* Quick actions — Search only */}
        <div className="border-b border-sidebar-border p-3 space-y-2">
          {!collapsed && (
            <div className="flex items-center gap-2 px-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-sidebar-foreground/55">
              <Sparkles size={12} />
              Quick actions
            </div>
          )}
          <div className={cn('grid gap-2', collapsed && 'place-items-center')}>
            <button
              type="button"
              onClick={() => { openCommandPalette(); closeMobileIfOpen(); }}
              className={cn(
                'flex items-center gap-2 rounded-2xl border border-sidebar-border bg-sidebar-accent/50 px-3 py-2.5 text-sm text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-sidebar-foreground transition-colors',
                collapsed && 'h-11 w-11 justify-center px-0'
              )}
              title="Search workspace (⌘K)"
            >
              <Search size={15} className="shrink-0" />
              {!collapsed && <span className="truncate">Search workspace</span>}
            </button>
          </div>
        </div>

        {/* Main nav — Home only */}
        <nav className="p-2 space-y-0.5 border-b border-sidebar-border">
          {[{ href: '/', icon: Home, label: 'Home' }].map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={closeMobileIfOpen}
                className={cn(
                  'flex items-center gap-2.5 rounded-2xl px-3 py-2.5 text-sm font-medium transition-all duration-150',
                  collapsed && 'justify-center px-0',
                  active
                    ? 'bg-brand/10 text-brand border border-brand/20 shadow-sm shadow-brand/5'
                    : 'text-sidebar-foreground/72 hover:bg-sidebar-accent hover:text-sidebar-foreground'
                )}
                title={item.label}
              >
                <item.icon size={16} className={active ? 'text-brand' : ''} />
                {!collapsed && <span>{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        {/* Recent repositories */}
        <div className="flex-1 overflow-y-auto p-2 scrollbar-thin">
          {!collapsed && (
            <div className="flex items-center justify-between px-2.5 py-1.5 mb-1">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Recent</span>
            </div>
          )}
          {recentRepos.length === 0 ? (
            <div className={cn('rounded-xl border border-dashed border-sidebar-border/80 bg-sidebar-accent/20 p-3', collapsed && 'text-center')}>
              {!collapsed ? (
                <>
                  <p className="text-sm font-medium text-sidebar-foreground">No repositories yet</p>
                  <p className="mt-1 text-xs text-sidebar-foreground/60">Index a repository to populate the workspace.</p>
                </>
              ) : (
                <Clock3 size={15} className="mx-auto text-sidebar-foreground/55" />
              )}
            </div>
          ) : (
            <div className="space-y-3">
              {!collapsed && (
                <div className="px-2.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-sidebar-foreground/55">Repositories</div>
              )}
              <div className="space-y-1">
                {recentRepos.map((repo) => {
                  const isActive = pathname.startsWith(`/repo/${repo.id}`);
                  const href = repo.status === 'ready' ? `/repo/${repo.id}` : `/repo/${repo.id}/indexing`;
                  const historyExpanded = expandedRepoId === repo.id;
                  const chats = repoChats[repo.id] ?? [];
                  return (
                    <div key={repo.id}>
                      <Link
                        href={href}
                        onClick={closeMobileIfOpen}
                        className={cn(
                          'flex items-center gap-2 rounded-2xl px-3 py-2.5 text-sm transition-all duration-150 group',
                          collapsed && 'justify-center px-0',
                          isActive
                            ? 'bg-sidebar-accent text-foreground border border-sidebar-border'
                            : 'text-sidebar-foreground/72 hover:bg-sidebar-accent hover:text-foreground'
                        )}
                        title={repo.name}
                      >
                        <GitBranch size={14} className="flex-shrink-0" />
                        {!collapsed && (
                          <div className="min-w-0 flex-1">
                            <div className="truncate text-sm font-medium">{repo.name}</div>
                            <div className="truncate text-[11px] text-sidebar-foreground/55">{repo.index_name}</div>
                          </div>
                        )}
                      </Link>

                      {!collapsed && repo.status === 'ready' && (
                        <div className="ml-5 mt-1 space-y-1 border-l border-sidebar-border/70 pl-2">
                          <button
                            type="button"
                            onClick={() => void toggleRepoChatHistory(repo)}
                            className="flex w-full items-center gap-1.5 rounded-xl px-2 py-1.5 text-left text-xs text-sidebar-foreground/65 transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground"
                            aria-expanded={historyExpanded}
                          >
                            <ChevronDown size={12} className={cn('transition-transform', !historyExpanded && '-rotate-90')} />
                            <MessageSquare size={12} />
                            <span className="truncate">Chat History</span>
                          </button>

                          {historyExpanded && (
                            <div className="space-y-0.5 pb-1">
                              {loadingChatRepoId === repo.id ? (
                                <div className="px-2 py-1 text-[11px] text-sidebar-foreground/50">Loading…</div>
                              ) : chats.length === 0 ? (
                                <div className="px-2 py-1 text-[11px] text-sidebar-foreground/50">No conversations yet</div>
                              ) : (
                                chats.slice(0, 6).map((chat) => {
                                  const isRenaming = renamingChatId === chat.id;
                                  return (
                                    <div
                                      key={chat.id}
                                      className="group flex items-center gap-1 rounded-xl hover:bg-sidebar-accent transition-colors"
                                      onContextMenu={(e) => {
                                        e.preventDefault();
                                        setContextMenu({ chat, repoId: repo.id, x: e.clientX, y: e.clientY });
                                      }}
                                    >
                                      {isRenaming ? (
                                        <div className="flex flex-1 items-center gap-1 px-2 py-1">
                                          <input
                                            autoFocus
                                            value={renameValue}
                                            onChange={(e) => setRenameValue(e.target.value)}
                                            onKeyDown={(e) => {
                                              if (e.key === 'Enter') void commitRename(repo.id);
                                              if (e.key === 'Escape') setRenamingChatId(null);
                                            }}
                                            onBlur={() => void commitRename(repo.id)}
                                            className="flex-1 min-w-0 rounded border border-sidebar-border bg-sidebar px-1.5 py-0.5 text-xs outline-none focus:border-brand"
                                          />
                                        </div>
                                      ) : (
                                        <>
                                          <button
                                            type="button"
                                            onClick={() => openChatSession(repo.id, chat.id)}
                                            className="flex-1 min-w-0 truncate px-2 py-1.5 text-left text-xs text-sidebar-foreground/65 hover:text-sidebar-foreground"
                                            title={chat.title || 'Untitled chat'}
                                          >
                                            {chat.is_pinned ? '★ ' : ''}{chat.title || 'Untitled chat'}
                                          </button>
                                          <button
                                            type="button"
                                            title="More options"
                                            className="mr-1 hidden group-hover:flex h-5 w-5 items-center justify-center rounded text-sidebar-foreground/40 hover:text-sidebar-foreground hover:bg-sidebar-border/50 transition-colors"
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              setContextMenu({ chat, repoId: repo.id, x: e.clientX, y: e.clientY });
                                            }}
                                          >
                                            <MoreHorizontal size={11} />
                                          </button>
                                        </>
                                      )}
                                    </div>
                                  );
                                })
                              )}
                              <button
                                type="button"
                                onClick={() => {
                                  try { sessionStorage.setItem(`codebase:new-chat:${repo.id}`, '1'); } catch {}
                                  router.push(`/repo/${repo.id}/chat`);
                                  closeMobileIfOpen();
                                }}
                                className="flex w-full items-center gap-1.5 rounded-xl px-2 py-1.5 text-xs font-medium text-brand transition-colors hover:bg-brand/10"
                              >
                                <Plus size={11} />
                                New Chat
                              </button>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* User section with expandable menu */}
        <div className="border-t border-sidebar-border p-3">
          <button
            type="button"
            onClick={() => setUserMenuOpen((v) => !v)}
            className={cn(
              'flex w-full items-center gap-2 rounded-2xl bg-sidebar-accent/35 px-3 py-2.5 transition-colors hover:bg-sidebar-accent/60',
              collapsed && 'justify-center px-0'
            )}
          >
            <div className="w-8 h-8 rounded-full bg-brand/10 flex items-center justify-center flex-shrink-0 border border-sidebar-border">
              <span className="text-xs font-semibold">{userEmail?.[0]?.toUpperCase() ?? 'G'}</span>
            </div>
            {!collapsed && (
              <>
                <div className="min-w-0 flex-1 text-left">
                  <span className="block text-xs font-medium truncate">{userEmail ?? 'Guest'}</span>
                  <span className="block text-[11px] text-sidebar-foreground/55 truncate">Workspace member</span>
                </div>
                {userMenuOpen ? <ChevronUp size={13} className="text-sidebar-foreground/50 flex-shrink-0" /> : <ChevronDown size={13} className="text-sidebar-foreground/50 flex-shrink-0" />}
              </>
            )}
          </button>

          {userMenuOpen && !collapsed && (
            <div className="mt-1.5 space-y-0.5 rounded-2xl border border-sidebar-border bg-sidebar-accent/20 p-1.5">
              {[
                { icon: LayoutDashboard, label: 'Dashboard',       onClick: () => { router.push('/dashboard'); closeMobileIfOpen(); setUserMenuOpen(false); }, danger: false },
                { icon: Plus,            label: 'Index repository', onClick: () => { router.push('/dashboard'); closeMobileIfOpen(); setUserMenuOpen(false); }, danger: false },
                { icon: Settings,        label: 'Settings',         onClick: () => { router.push('/settings');  closeMobileIfOpen(); setUserMenuOpen(false); }, danger: false },
                { icon: LogOut,          label: 'Sign out',         onClick: handleSignOut,                                                                    danger: true  },
              ].map(({ icon: Icon, label, onClick, danger }) => (
                <button
                  key={label}
                  type="button"
                  onClick={onClick}
                  className={cn(
                    'flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-sm transition-colors hover:bg-sidebar-accent',
                    danger ? 'text-destructive hover:text-destructive' : 'text-sidebar-foreground/80 hover:text-sidebar-foreground'
                  )}
                >
                  <Icon size={14} className="flex-shrink-0" />
                  {label}
                </button>
              ))}
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
