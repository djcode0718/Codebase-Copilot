'use client';
/**
 * components/repo/ExportMenu.tsx
 * Export repository conversation memory through backend export API.
 */
import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Download, FileText, FileJson, FileCode2, ChevronDown, FileArchive } from 'lucide-react';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import { exportRepositoryMemory } from '@/lib/api';
import type { Repo } from '@/lib/types';

interface ExportMenuProps {
  repo: Repo;
  token?: string;
  scope?: 'repo' | 'chat';
  chatIds?: string[];
}

function decodeBase64ToBytes(base64: string): Uint8Array {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

function downloadFile(content: string, filename: string, mimeType: string, encoding?: string) {
  const blob = encoding === 'base64'
    ? new Blob([decodeBase64ToBytes(content) as unknown as BlobPart], { type: mimeType })
    : new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.style.display = 'none';
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    URL.revokeObjectURL(url);
    a.remove();
  }, 1000);
}

const EXPORT_OPTIONS = [
  { id: 'md', icon: FileText, label: 'Memory Export (.md)', desc: 'Conversation + summaries' },
  { id: 'txt', icon: FileCode2, label: 'Memory Export (.txt)', desc: 'Plain text export' },
  { id: 'json', icon: FileJson, label: 'Memory Export (.json)', desc: 'Structured export payload' },
  { id: 'pdf', icon: FileArchive, label: 'Memory Export (.pdf)', desc: 'Downloadable PDF payload' },
  { id: 'docx', icon: FileArchive, label: 'Memory Export (.docx)', desc: 'Downloadable DOCX payload' },
] as const;

export default function ExportMenu({ repo, token, scope = 'repo', chatIds = [] }: ExportMenuProps) {
  const [open, setOpen] = useState(false);
  const [menuPosition, setMenuPosition] = useState<{ top: number; left: number; width: number } | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open || !ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    const width = 208;
    const left = Math.max(8, Math.min(rect.right - width, window.innerWidth - width - 8));
    setMenuPosition({
      top: rect.bottom + 8,
      left,
      width,
    });
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function handleViewportChange() {
      if (!ref.current) return;
      const rect = ref.current.getBoundingClientRect();
      const width = 208;
      const left = Math.max(8, Math.min(rect.right - width, window.innerWidth - width - 8));
      setMenuPosition({ top: rect.bottom + 8, left, width });
    }
    window.addEventListener('resize', handleViewportChange);
    window.addEventListener('scroll', handleViewportChange, true);
    return () => {
      window.removeEventListener('resize', handleViewportChange);
      window.removeEventListener('scroll', handleViewportChange, true);
    };
  }, [open]);

  useEffect(() => {
    function handler(e: MouseEvent) {
      const target = e.target as Node;
      const clickedTrigger = ref.current?.contains(target);
      const clickedMenu = menuRef.current?.contains(target);
      if (!clickedTrigger && !clickedMenu) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  async function handleExport(id: typeof EXPORT_OPTIONS[number]['id']) {
    setOpen(false);
    if (!token) {
      toast.error('Sign in to export repository memory.');
      return;
    }

    try {
      const selectedChatIds = scope === 'chat' ? chatIds.filter(Boolean) : undefined;
      const payload = await exportRepositoryMemory(token, repo.id, id, selectedChatIds);
      const encoding = typeof payload.meta?.encoding === 'string' ? payload.meta.encoding : undefined;
      downloadFile(payload.content, payload.filename, payload.content_type, encoding);
      toast.success(scope === 'chat' ? 'Chat history exported' : 'Repository memory exported');
    } catch (error) {
      console.error(error);
      toast.error('Export failed');
    }
  }

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 rounded-xl border border-border bg-card/80 px-3 py-2 text-xs text-muted-foreground hover:text-foreground hover:border-border/80 transition-colors cursor-pointer"
      >
        <Download size={13} />
        {scope === 'chat' ? 'Export chat' : 'Export'}
        <ChevronDown size={11} className={cn('transition-transform', open && 'rotate-180')} />
      </button>

      {open && typeof document !== 'undefined' && menuPosition && createPortal(
        <div
          ref={menuRef}
          className="fixed z-[9999] rounded-2xl border border-border bg-card shadow-lg shadow-black/20 overflow-hidden"
          style={{ top: menuPosition.top, left: menuPosition.left, width: menuPosition.width }}
        >
          {EXPORT_OPTIONS.map((opt) => (
            <button
              key={opt.id}
              onClick={() => {
                void handleExport(opt.id);
              }}
              className="flex w-full items-start gap-3 px-3 py-2.5 text-left text-sm hover:bg-accent transition-colors cursor-pointer"
            >
              <opt.icon size={13} className="text-brand mt-0.5 flex-shrink-0" />
              <div>
                <p className="font-medium text-xs">{opt.label}</p>
                <p className="text-[11px] text-muted-foreground">{opt.desc}</p>
              </div>
            </button>
          ))}
        </div>,
        document.body
      )}
    </div>
  );
}
