'use client';
/**
 * components/repo/RepoCard.tsx
 * Repository card for the dashboard grid.
 */
import Link from 'next/link';
import { motion } from 'framer-motion';
import { GitBranch, FileCode2, Layers, Clock, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import type { Repo } from '@/lib/types';

const STATUS_CONFIG = {
  ready: {
    label: 'Ready',
    className: 'bg-brand/10 text-brand border-brand/20',
    dot: 'bg-brand',
  },
  indexing: {
    label: 'Indexing…',
    className: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    dot: 'bg-amber-400 animate-pulse',
  },
  failed: {
    label: 'Failed',
    className: 'bg-destructive/10 text-destructive border-destructive/20',
    dot: 'bg-destructive',
  },
};

interface RepoCardProps {
  repo: Repo;
  onDelete?: (id: string) => void;
  index?: number;
}

export default function RepoCard({ repo, onDelete, index = 0 }: RepoCardProps) {
  const status = STATUS_CONFIG[repo.status] ?? STATUS_CONFIG.indexing;
  const href =
    repo.status === 'ready'
      ? `/repo/${repo.id}`
      : `/repo/${repo.id}/indexing`;

  const formattedDate = new Date(repo.created_at).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
    >
      <div className="group relative overflow-hidden rounded-[1.5rem] border border-border bg-card/80 shadow-sm shadow-black/5 transition-all duration-200 hover:-translate-y-0.5 hover:border-brand/30 hover:shadow-lg hover:shadow-black/10">
        {/* Top accent line for ready repos */}
        {repo.status === 'ready' && (
          <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-brand/0 via-brand to-brand/0 opacity-80 transition-opacity duration-300" />
        )}

        <Link href={href} className="block p-5">
          <div className="flex items-start justify-between gap-2 mb-4">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-10 h-10 rounded-2xl border border-border bg-background/80 flex items-center justify-center flex-shrink-0">
                <GitBranch size={15} className="text-muted-foreground" />
              </div>
              <div className="min-w-0">
                <h3 className="font-heading font-semibold text-sm truncate">
                  {repo.name}
                </h3>
                <p className="text-xs text-muted-foreground truncate mt-0.5">
                  {repo.index_name}
                </p>
              </div>
            </div>

            {/* Status badge */}
            <div
              className={cn(
                'flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-medium flex-shrink-0',
                status.className
              )}
            >
              <span className={cn('w-1.5 h-1.5 rounded-full', status.dot)} />
              {status.label}
            </div>
          </div>

          {/* Stats */}
          {repo.status === 'ready' && (
            <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
              {repo.file_count !== undefined && (
                <div className="flex items-center gap-1">
                  <FileCode2 size={11} />
                  <span>{repo.file_count} files</span>
                </div>
              )}
              {repo.node_count !== undefined && (
                <div className="flex items-center gap-1">
                  <Layers size={11} />
                  <span>{repo.node_count} chunks</span>
                </div>
              )}
              {repo.llm_provider && (
                <Badge
                  variant="outline"
                  className="text-xs border-border py-0 px-1.5 h-4 font-mono"
                >
                  {repo.llm_provider}
                </Badge>
              )}
            </div>
          )}

          {repo.status === 'indexing' && (
            <div className="h-1.5 bg-secondary rounded-full overflow-hidden mt-3">
              <div className="h-full bg-amber-400 rounded-full animate-pulse w-1/3" />
            </div>
          )}

          {/* Footer */}
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground mt-4 pt-4 border-t border-border/80">
            <Clock size={11} />
            <span>{formattedDate}</span>
          </div>
        </Link>

        {/* Delete button */}
        {onDelete && (
          <button
            onClick={(e) => {
              e.preventDefault();
              onDelete(repo.id);
            }}
            className="absolute top-3 right-3 p-1.5 rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10 opacity-0 group-hover:opacity-100 transition-all duration-150 cursor-pointer"
            aria-label={`Delete ${repo.name}`}
          >
            <Trash2 size={13} />
          </button>
        )}
      </div>
    </motion.div>
  );
}
