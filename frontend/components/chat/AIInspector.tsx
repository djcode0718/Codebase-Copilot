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
};

function ScoreBar({ score }: { score: number }) {
  return (
    <div className="w-12 h-1 bg-secondary rounded-full overflow-hidden flex-shrink-0">
      <div
        className="h-full bg-brand rounded-full"
        style={{ width: `${Math.min(score * 100 * 2, 100)}%` }} // score is 0-1, scale to 100%
      />
    </div>
  );
}

function FileChunk({ file, index }: { file: RetrievedFile; index: number }) {
  const fileName = file.path.split('/').pop() ?? file.path;
  const dirPath = file.path.includes('/') ? file.path.split('/').slice(0, -1).join('/') : '';

  return (
    <motion.div
      initial={{ opacity: 0, x: 8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.04, duration: 0.2 }}
      className="flex items-center gap-2 py-1.5 border-b border-border/50 last:border-0"
    >
      <span className="text-xs text-muted-foreground font-mono w-4 flex-shrink-0">
        {index + 1}
      </span>
      <FileCode2 size={11} className="text-muted-foreground flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium text-foreground truncate">{fileName}</p>
        {dirPath && (
          <p className="text-xs text-muted-foreground truncate">{dirPath}</p>
        )}
      </div>
      <div className="flex items-center gap-1.5 flex-shrink-0">
        <ScoreBar score={file.score} />
        <span className="text-xs font-mono text-muted-foreground w-10 text-right">
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
      <div className="grid grid-cols-3 gap-1 text-xs text-muted-foreground">
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-sm bg-blue-400 flex-shrink-0" />
          <span>Retrieval</span>
          <span className="font-mono ml-auto">{ret}ms</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-sm bg-violet-400 flex-shrink-0" />
          <span>Other</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-sm bg-amber-400 flex-shrink-0" />
          <span>LLM</span>
          <span className="font-mono ml-auto">{l}ms</span>
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

export default function AIInspector({ data, streaming }: AIInspectorProps) {
  const [chunksOpen, setChunksOpen] = useState(true);
  const modeConfig = data?.queryMode ? MODE_CONFIG[data.queryMode] : null;

  return (
    <div className="h-full flex flex-col overflow-y-auto scrollbar-thin">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border flex-shrink-0">
        <div className="flex items-center gap-2">
          <Zap size={13} className="text-brand" />
          <span className="text-xs font-semibold text-foreground uppercase tracking-wider">
            AI Inspector
          </span>
        </div>
      </div>

      {/* Empty state */}
      {!data && !streaming && (
        <div className="flex-1 flex items-center justify-center p-6 text-center">
          <div>
            <Database size={24} className="text-muted-foreground mx-auto mb-2" />
            <p className="text-xs text-muted-foreground">
              Send a message to see retrieval details
            </p>
          </div>
        </div>
      )}

      {/* Streaming state */}
      {streaming && !data && (
        <div className="p-4 space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-4 bg-secondary rounded animate-pulse" />
          ))}
        </div>
      )}

      <AnimatePresence mode="wait">
        {data && (
          <motion.div
            key={data.queryMode}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex-1 space-y-4 p-4"
          >
            {/* Query mode */}
            {modeConfig && (
              <div>
                <p className="text-xs text-muted-foreground mb-1.5">Query Mode</p>
                <div className={cn(
                  'inline-flex items-center gap-1.5 px-2 py-1 rounded border text-xs font-mono font-semibold',
                  modeConfig.className
                )}>
                  {modeConfig.label}
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  {modeConfig.description}
                </p>
              </div>
            )}

            {/* Retrieved chunks */}
            {data.retrievedFiles.length > 0 && (
              <div>
                <button
                  onClick={() => setChunksOpen(!chunksOpen)}
                  className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors cursor-pointer mb-2 w-full"
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
                      <div className="bg-background border border-border rounded-lg p-3">
                        {data.retrievedFiles.map((f, i) => (
                          <FileChunk key={`${f.path}-${i}`} file={f} index={i} />
                        ))}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            )}

            {/* Latency breakdown */}
            {data.latencyTotalMs !== null && (
              <div>
                <p className="text-xs text-muted-foreground mb-2">Latency breakdown</p>
                <div className="bg-background border border-border rounded-lg p-3">
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
