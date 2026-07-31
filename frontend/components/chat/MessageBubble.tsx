'use client';
/**
 * components/chat/MessageBubble.tsx
 * Renders a single chat message — user or assistant.
 * Assistant messages show markdown, inline grounding summary, and expandable inspector data.
 */
import { motion } from 'framer-motion';
import { Copy, Check, Cpu } from 'lucide-react';
import { useState } from 'react';
import { cn } from '@/lib/utils';
import type { Message, QueryMode } from '@/lib/types';

const MODE_LABELS: Record<QueryMode, string> = {
  code_lookup: 'CODE LOOKUP',
  architectural: 'ARCHITECTURAL',
};
const MODE_COLORS: Record<QueryMode, string> = {
  code_lookup: 'text-brand',
  architectural: 'text-amber-400',
};

interface MessageBubbleProps {
  message: Message;
  onInspect?: () => void;
  isInspected?: boolean;
  index: number;
}

function SimpleMarkdown({ content }: { content: string }) {
  // Lightweight markdown render — avoids heavy library dependency
  const lines = content.split('\n');
  const elements: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Fenced code block
    if (line.startsWith('```')) {
      const lang = line.slice(3).trim();
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith('```')) {
        codeLines.push(lines[i]);
        i++;
      }
      elements.push(
        <div key={i} className="my-3">
          {lang && (
            <div className="px-3 py-1 bg-secondary border border-border rounded-t-lg text-xs font-mono text-muted-foreground border-b-0">
              {lang}
            </div>
          )}
          <pre className={cn('bg-background border border-border p-3 overflow-x-auto scrollbar-thin text-sm', lang ? 'rounded-b-lg' : 'rounded-lg')}>
            <code className="font-code text-green-300">{codeLines.join('\n')}</code>
          </pre>
        </div>
      );
      i++;
      continue;
    }

    // Headings
    if (line.startsWith('### ')) {
      elements.push(<h3 key={i} className="font-heading font-semibold text-sm mt-4 mb-1">{line.slice(4)}</h3>);
    } else if (line.startsWith('## ')) {
      elements.push(<h2 key={i} className="font-heading font-semibold text-base mt-4 mb-1">{line.slice(3)}</h2>);
    } else if (line.startsWith('# ')) {
      elements.push(<h1 key={i} className="font-heading font-bold text-lg mt-4 mb-1">{line.slice(2)}</h1>);
    // List items
    } else if (line.startsWith('- ') || line.startsWith('* ')) {
      elements.push(
        <li key={i} className="ml-4 text-sm leading-relaxed list-disc">
          {renderInline(line.slice(2))}
        </li>
      );
    // Blank line
    } else if (line.trim() === '') {
      elements.push(<div key={i} className="h-2" />);
    // Regular paragraph
    } else {
      elements.push(
        <p key={i} className="text-sm leading-relaxed">
          {renderInline(line)}
        </p>
      );
    }
    i++;
  }

  return <div className="prose-dark space-y-0.5">{elements}</div>;
}

function renderInline(text: string): React.ReactNode {
  // Bold + inline code
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={i} className="font-code text-brand text-xs bg-background border border-border px-1.5 py-0.5 rounded">{part.slice(1, -1)}</code>;
    }
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="font-semibold text-foreground">{part.slice(2, -2)}</strong>;
    }
    return part;
  });
}

export default function MessageBubble({ message, onInspect, isInspected, index }: MessageBubbleProps) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === 'user';

  async function handleCopy() {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index * 0.05, 0.3), duration: 0.2 }}
      className={cn('group flex gap-3', isUser ? 'flex-row-reverse' : 'flex-row')}
    >
      {/* Avatar */}
      <div className={cn(
        'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-1 text-xs font-medium shadow-sm',
        isUser ? 'bg-secondary text-foreground border border-border' : 'bg-brand/10 border border-brand/20 text-brand'
      )}>
        {isUser ? 'U' : <Cpu size={13} />}
      </div>

      {/* Content */}
      <div className={cn('max-w-[78%] space-y-2', isUser ? 'items-end' : 'items-start')}>
        {isUser ? (
          <div className="rounded-2xl rounded-tr-sm border border-border bg-secondary/90 px-4 py-3 text-sm text-foreground shadow-sm shadow-black/5">
            {message.content}
          </div>
        ) : (
          <div className="space-y-2 rounded-2xl border border-border bg-card/70 p-4 shadow-sm shadow-black/5">
            {/* Markdown content */}
            <div className="text-foreground">
              <SimpleMarkdown content={message.content} />
            </div>

            {/* Grounding summary bar */}
            {(message.query_mode || message.retrieved_files?.length || message.latency_ms) && (
              <div className="flex items-center gap-3 text-xs text-muted-foreground flex-wrap">
                {message.query_mode && (
                  <span className={cn('font-mono font-semibold tracking-wide', MODE_COLORS[message.query_mode])}>
                    {MODE_LABELS[message.query_mode]}
                  </span>
                )}
                {message.retrieved_files && message.retrieved_files.length > 0 && (
                  <span>{message.retrieved_files.length} chunks</span>
                )}
                {message.latency_ms && (
                  <span>{message.latency_ms}ms</span>
                )}
                {onInspect && (
                  <button
                    onClick={onInspect}
                    className={cn(
                      'text-xs underline underline-offset-2 transition-colors cursor-pointer',
                      isInspected ? 'text-brand' : 'text-muted-foreground hover:text-foreground'
                    )}
                  >
                    {isInspected ? 'Inspecting' : 'Inspect'}
                  </button>
                )}
              </div>
            )}

            {!message.query_mode && !message.retrieved_files?.length && !message.latency_ms && onInspect && (
              <div className="text-xs text-muted-foreground">
                Grounded response ready for inspection.
              </div>
            )}
          </div>
        )}

        {/* Actions */}
        {!isUser && (
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 text-xs text-muted-foreground transition-colors cursor-pointer hover:text-foreground"
          >
            {copied ? <Check size={11} className="text-brand" /> : <Copy size={11} />}
            {copied ? 'Copied' : 'Copy'}
          </button>
        )}
      </div>
    </motion.div>
  );
}
