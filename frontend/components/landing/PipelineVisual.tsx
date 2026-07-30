'use client';
import { motion } from 'framer-motion';

export function PipelineVisual() {
  return (
    <div className="relative w-full max-w-4xl mx-auto h-64 border border-border rounded-xl bg-card overflow-hidden flex items-center justify-center">
      {/* Animated path */}
      <svg className="absolute inset-0 w-full h-full" xmlns="http://www.w3.org/2000/svg">
        <motion.path
          d="M 100 128 L 300 128 L 500 128 L 700 128"
          stroke="#22C55E"
          strokeWidth="2"
          strokeDasharray="8 8"
          fill="transparent"
          initial={{ pathLength: 0, opacity: 0 }}
          animate={{ pathLength: 1, opacity: 1 }}
          transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
        />
      </svg>
      <div className="z-10 flex w-full justify-between px-16">
        <div className="bg-background border border-border p-4 rounded-lg flex flex-col items-center">
          <span className="font-heading font-semibold">1. Index</span>
          <span className="text-xs text-muted-foreground mt-1">GitHub Repo</span>
        </div>
        <div className="bg-background border border-border p-4 rounded-lg flex flex-col items-center">
          <span className="font-heading font-semibold">2. Embed</span>
          <span className="text-xs text-muted-foreground mt-1">Chunk & Store</span>
        </div>
        <div className="bg-background border border-border p-4 rounded-lg flex flex-col items-center">
          <span className="font-heading font-semibold">3. Chat</span>
          <span className="text-xs text-muted-foreground mt-1">RAG Pipeline</span>
        </div>
      </div>
    </div>
  );
}
