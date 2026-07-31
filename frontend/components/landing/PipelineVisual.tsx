'use client';
import { motion } from 'framer-motion';

export function PipelineVisual() {
  return (
    <div className="relative mx-auto flex h-72 w-full max-w-5xl items-center justify-center overflow-hidden rounded-[1.75rem] border border-border bg-card/80 shadow-xl shadow-black/10">
      {/* Animated path */}
      <svg className="absolute inset-0 h-full w-full" xmlns="http://www.w3.org/2000/svg">
        <motion.path
          d="M 110 144 L 330 144 L 550 144 L 770 144"
          stroke="#22C55E"
          strokeWidth="2"
          strokeDasharray="8 8"
          fill="transparent"
          initial={{ pathLength: 0, opacity: 0 }}
          animate={{ pathLength: 1, opacity: 1 }}
          transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
        />
      </svg>
      <div className="z-10 flex w-full justify-between px-8 sm:px-16">
        <div className="flex flex-col items-center rounded-2xl border border-border bg-background/90 p-4 shadow-sm shadow-black/5">
          <span className="font-heading font-semibold">1. Index</span>
          <span className="text-xs text-muted-foreground mt-1">GitHub Repo</span>
        </div>
        <div className="flex flex-col items-center rounded-2xl border border-border bg-background/90 p-4 shadow-sm shadow-black/5">
          <span className="font-heading font-semibold">2. Embed</span>
          <span className="text-xs text-muted-foreground mt-1">Chunk & Store</span>
        </div>
        <div className="flex flex-col items-center rounded-2xl border border-border bg-background/90 p-4 shadow-sm shadow-black/5">
          <span className="font-heading font-semibold">3. Chat</span>
          <span className="text-xs text-muted-foreground mt-1">RAG Pipeline</span>
        </div>
      </div>
    </div>
  );
}
