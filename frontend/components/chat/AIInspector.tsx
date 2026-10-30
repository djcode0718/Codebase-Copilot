'use client';
/**
 * components/chat/AIInspector.tsx
 * Right-rail panel showing query mode, retriever path, retrieved chunks,
 * and latency breakdown per assistant message.
 * All data sourced from the real metadata SSE event — no decoration.
 */
import { motion, AnimatePresence } from 'framer-motion';
import { FileCode2, ChevronDown, ChevronRight, Zap, Database, Clock } from 'lucide-react';
import { useState } from 'react';
import { cn } from '@/lib/utils';
import type { RetrievedFile, QueryMode } from '@/lib/types';

interface InspectorData {
  queryMode: QueryMode | null;
  retrievedFiles: RetrievedFile[];
  latencyRetrievalMs: number | null;
  latencyLlmMs: number | null;
  latencyTotalMs: number | null;
}

interface AIInspectorProps {
  data: InspectorData | null;
  streaming?: boolean;
  onOpenEvidence?: (file: RetrievedFile) => void;
}

const MODE_CONFIG = {
  code_lookup: {
    label: 'CODE LOOKUP',
    description: 'BM25 + Dense → RRF fusion',
    className: 'text-brand bg-brand/10 border-brand/20',
  },
  architectural: {
    label: 'ARCHITECTURAL',
    description: 'Dense retrieval (extended top-k)',
    className: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
  },
  relationship: {
    label: 'RELATIONSHIP',
    description: 'AST call & reference graph',
    className: 'text-purple-400 bg-purple-500/10 border-purple-500/20',
  },
};

function ScoreBar({ score }: { score: number }) {
  return (
    <div className="h-1.5 w-10 flex-shrink-0 overflow-hidden rounded-full bg-secondary">
      <div
        className="h-full bg-brand rounded-full"
        style={{ width: `${Math.min(score * 100 * 2, 100)}%` }} // score is 0-1, scale to 100%
      />
    </div>
  );
}

function FileChunk({ file, index, onOpenEvidence }: { file: RetrievedFile; index: number; onOpenEvidence?: (file: RetrievedFile) => void }) {
  const fileName = file.path.split('/').pop() ?? file.path;
  const dirPath = file.path.includes('/') ? file.path.split('/').slice(0, -1).join('/') : '';
  const lineLabel = file.line_start && file.line_end && file.line_end !== file.line_start
    ? `L${file.line_start}-L${file.line_end}`
    : file.line_start
    ? `L${file.line_start}`
    : null;

  return (
    <motion.div
      initial={{ opacity: 0, x: 8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.04, duration: 0.2 }}
      className="flex items-center gap-1.5 border-b border-border/60 py-1.5 last:border-0"
    >
      <span className="w-4 flex-shrink-0 font-mono text-[11px] text-muted-foreground">
        {index + 1}
      </span>
      <FileCode2 size={11} className="text-muted-foreground flex-shrink-0" />
      <button
        type="button"
        className="flex-1 min-w-0 text-left"
        onClick={() => onOpenEvidence?.(file)}
        disabled={!onOpenEvidence}
        title={file.path}
      >
        <p className="truncate text-[11px] font-medium text-foreground">{fileName}</p>
        <p className="truncate text-[11px] text-muted-foreground">
          {dirPath}{lineLabel ? `${dirPath ? ' • ' : ''}${lineLabel}` : ''}
        </p>
      </button>
      <div className="flex items-center gap-1.5 flex-shrink-0">
        <ScoreBar score={file.score} />
        <span className="w-10 text-right font-mono text-[11px] text-muted-foreground">
          {file.score.toFixed(3)}
        </span>
      </div>
    </motion.div>
  );
}

function LatencyBar({
  retrieval,
  llm,
  total,
}: {
  retrieval: number | null;
  llm: number | null;
  total: number | null;
}) {
  if (!total) return null;
  const ret = retrieval ?? 0;
  const l = llm ?? 0;
  const other = Math.max(0, total - ret - l);
  const retPct = (ret / total) * 100;
  const llmPct = (l / total) * 100;
  const otherPct = Math.max(0, 100 - retPct - llmPct);

  return (
    <div className="space-y-2">
      {/* Stacked bar */}
      <div className="h-2 rounded-full overflow-hidden bg-secondary flex">
        <div
          className="bg-blue-400 h-full"
          style={{ width: `${retPct}%` }}
          title={`Retrieval: ${ret}ms`}
        />
        <div
          className="bg-violet-400 h-full"
          style={{ width: `${otherPct}%` }}
          title="Rerank (in total)"
        />
        <div
          className="bg-amber-400 h-full"
          style={{ width: `${llmPct}%` }}
          title={`LLM: ${l}ms`}
        />
      </div>

      {/* Legend */}
      <div className="grid grid-cols-1 gap-2 text-xs text-muted-foreground sm:grid-cols-2">
        <div className="flex items-center justify-between gap-2 rounded-md bg-background/60 px-2 py-1.5">
          <span className="inline-flex items-center gap-1.5 min-w-0">
            <span className="w-2 h-2 rounded-sm bg-blue-400 flex-shrink-0" />
            <span className="truncate">Retrieval</span>
          </span>
          <span className="font-mono whitespace-nowrap">{ret}ms</span>
        </div>
        <div className="flex items-center justify-between gap-2 rounded-md bg-background/60 px-2 py-1.5">
          <span className="inline-flex items-center gap-1.5 min-w-0">
            <span className="w-2 h-2 rounded-sm bg-violet-400 flex-shrink-0" />
            <span className="truncate">Other</span>
          </span>
          <span className="font-mono whitespace-nowrap">{other}ms</span>
        </div>
        <div className="flex items-center justify-between gap-2 rounded-md bg-background/60 px-2 py-1.5 sm:col-span-2">
          <span className="inline-flex items-center gap-1.5 min-w-0">
            <span className="w-2 h-2 rounded-sm bg-amber-400 flex-shrink-0" />
            <span className="truncate">LLM</span>
          </span>
          <span className="font-mono whitespace-nowrap">{l}ms</span>
        </div>
      </div>

      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground flex items-center gap-1">
          <Clock size={10} />
          Total
        </span>
        <span className="font-mono font-medium text-foreground">{total}ms</span>
      </div>
    </div>
  );
}

export default function AIInspector({ data, streaming, onOpenEvidence }: AIInspectorProps) {
  const [chunksOpen, setChunksOpen] = useState(true);
  const modeConfig = data?.queryMode ? MODE_CONFIG[data.queryMode] : null;

  return (
    <div className="h-full min-h-0 flex flex-col overflow-y-auto scrollbar-thin bg-card/40">
      {/* Header */}
      <div className="px-3 py-3 border-b border-border flex-shrink-0 bg-background/60 backdrop-blur-sm">
        <div className="flex items-center gap-2">
          <Zap size={13} className="text-brand" />
          <span className="text-[11px] font-semibold text-foreground uppercase tracking-[0.12em]">
            AI Inspector
          </span>
        </div>
      </div>

      {/* Empty state */}
      {!data && !streaming && (
        <div className="flex-1 flex items-center justify-center p-4 text-center">
          <div>
            <Database size={22} className="text-muted-foreground mx-auto mb-2" />
            <p className="text-[11px] text-muted-foreground">
              Send a message to see retrieval details
            </p>
          </div>
        </div>
      )}

      {/* Streaming state */}
      {streaming && !data && (
        <div className="p-3 space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-4 rounded bg-secondary animate-pulse" />
          ))}
        </div>
      )}

      <AnimatePresence mode="wait">
        {data && (
          <motion.div
            key={data.queryMode}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex-1 min-h-0 space-y-3 p-3"
          >
            {/* Query mode */}
            {modeConfig && (
              <div className="rounded-2xl border border-border bg-background/70 p-3 shadow-sm shadow-black/5">
                <p className="mb-1.5 text-[11px] text-muted-foreground">Query mode</p>
                <div className={cn(
                  'inline-flex items-center gap-1 px-2 py-1 rounded-full border text-[11px] font-mono font-semibold',
                  modeConfig.className
                )}>
                  {modeConfig.label}
                </div>
                <p className="mt-1.5 text-[11px] text-muted-foreground leading-snug">
                  {modeConfig.description}
                </p>
              </div>
            )}

            {/* Retrieved chunks */}
            {data.retrievedFiles.length > 0 && (
              <div className="rounded-2xl border border-border bg-background/70 p-3 shadow-sm shadow-black/5">
                <button
                  onClick={() => setChunksOpen(!chunksOpen)}
                  className="mb-1.5 flex w-full items-center gap-1 text-[11px] text-muted-foreground transition-colors hover:text-foreground cursor-pointer"
                >
                  {chunksOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                  <span>
                    Retrieved chunks ({data.retrievedFiles.length})
                  </span>
                </button>
                <AnimatePresence>
                  {chunksOpen && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      className="overflow-hidden"
                    >
                      <div className="space-y-0.5 rounded-xl border border-border bg-card/80 p-2.5">
                        {data.retrievedFiles.map((f, i) => (
                          <FileChunk key={`${f.path}-${i}`} file={f} index={i} onOpenEvidence={onOpenEvidence} />
                        ))}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            )}

            {/* Latency breakdown */}
            {data.latencyTotalMs !== null && (
              <div className="rounded-2xl border border-border bg-background/70 p-3 shadow-sm shadow-black/5">
                <p className="mb-1.5 text-[11px] text-muted-foreground">Latency breakdown</p>
                <div className="rounded-xl border border-border bg-card/80 p-2.5">
                  <LatencyBar
                    retrieval={data.latencyRetrievalMs}
                    llm={data.latencyLlmMs}
                    total={data.latencyTotalMs}
                  />
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
