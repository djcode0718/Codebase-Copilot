'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  ChevronDown,
  ChevronRight,
  Circle,
  FileCode,
  FileSearch,
  Folder,
  FolderOpen,
  History,
  Loader2,
  MessageSquare,
  Play,
  Shield,
  Sparkles,
  TestTube,
  Wrench,
} from 'lucide-react';
import { createClient } from '@/lib/supabase/client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  addExplorerConversationEntry,
  applyExplorerFix,
  discoverExplorerTests,
  generateExplorerFix,
  getExplorerFile,
  getExplorerHistory,
  getExplorerTree,
  runExplorerFileReview,
  runExplorerTests,
} from '@/lib/api';
import type {
  ExplorerFileDetails,
  ExplorerFixProposal,
  ExplorerReviewResult,
  ExplorerTreeNode,
  ExplorerTestRunResult,
} from '@/lib/types';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

// ─── Format Detection ───────────────────────────────────────────────────────────

function isMarkdownFile(language?: string): boolean {
  return language === 'markdown' || language === 'md';
}

function isJsonFile(language?: string): boolean {
  return language === 'json';
}

function isYamlFile(language?: string): boolean {
  return language === 'yaml' || language === 'yml' || language === 'toml';
}

function isShellFile(language?: string): boolean {
  return language === 'shell' || language === 'bash' || language === 'sh';
}

function isPythonFile(language?: string): boolean {
  return language === 'python' || language === 'py';
}

function isTextFile(language?: string): boolean {
  return language === 'text' || language === 'txt' || !language;
}

function shouldRenderAsMarkdown(language?: string): boolean {
  return isMarkdownFile(language);
}

function shouldRenderAsJson(language?: string): boolean {
  return isJsonFile(language);
}

// ─── Markdown Viewer Component ──────────────────────────────────────────────────

function MarkdownViewer({ content }: { content: string }) {
  const lines = content.split('\n');

  const renderMarkdownLine = (line: string, idx: number) => {
    // Headings
    if (/^#{1,6}\s/.test(line)) {
      const level = line.match(/^#+/)?.[0].length || 1;
      const text = line.replace(/^#+\s+/, '');
      const sizeClass =
        level === 1 ? 'text-4xl font-bold mt-8 mb-4' :
        level === 2 ? 'text-3xl font-bold mt-6 mb-3' :
        level === 3 ? 'text-2xl font-bold mt-4 mb-2' :
        'text-lg font-bold mt-3 mb-2';
      return <div key={idx} className={cn(sizeClass, 'text-blue-700 dark:text-sky-400')}>{text}</div>;
    }

    // Blockquotes
    if (/^\s*>/.test(line)) {
      const text = line.replace(/^\s*>\s*/, '');
      return (
        <div key={idx} className="border-l-4 border-blue-300 dark:border-blue-600 pl-4 italic text-gray-600 dark:text-gray-400 bg-blue-50 dark:bg-blue-950/20 py-2 my-2 rounded-r">
          {text}
        </div>
      );
    }

    // Code fences
    if (/^```/.test(line)) {
      return (
        <div key={idx} className="text-emerald-700 dark:text-emerald-400 font-mono text-sm font-semibold bg-gray-100 dark:bg-gray-900 px-3 py-1 my-1 rounded">
          {line}
        </div>
      );
    }

    // Horizontal rules
    if (/^---+$|^\*\*\*+$|^___+$/.test(line)) {
      return <div key={idx} className="border-t border-gray-300 dark:border-gray-700 my-6" />;
    }

    // Unordered lists
    if (/^\s*[-*+]\s/.test(line)) {
      const match = line.match(/^(\s*)[-*+]\s+(.*)$/);
      if (match) {
        const indent = match[1].length / 2;
        return (
          <div key={idx} style={{ marginLeft: `${indent * 1.5}rem` }} className="flex gap-2 text-gray-800 dark:text-gray-200">
            <span className="text-blue-600 dark:text-blue-400 font-bold">•</span>
            <span>{match[2]}</span>
          </div>
        );
      }
    }

    // Numbered lists
    if (/^\s*\d+\.\s/.test(line)) {
      const match = line.match(/^(\s*)(\d+)\.\s+(.*)$/);
      if (match) {
        const indent = match[1].length / 2;
        return (
          <div key={idx} style={{ marginLeft: `${indent * 1.5}rem` }} className="flex gap-2 text-gray-800 dark:text-gray-200">
            <span className="text-blue-600 dark:text-blue-400 font-bold">{match[2]}.</span>
            <span>{match[3]}</span>
          </div>
        );
      }
    }

    // Empty lines
    if (!line.trim()) {
      return <div key={idx} className="h-3" />;
    }

    // Regular paragraph with inline formatting
    const renderInlined = (text: string) => {
      const parts: React.ReactNode[] = [];
      let pos = 0;

      // Match patterns: **bold**, *italic*, `code`, [link](url)
      const patterns = [
        { re: /\*\*([^*]+)\*\*/g, type: 'bold' },
        { re: /\*([^*]+)\*/g, type: 'italic' },
        { re: /`([^`]+)`/g, type: 'code' },
        { re: /\[([^\]]+)\]\(([^)]+)\)/g, type: 'link' },
      ];

      const allMatches: Array<{ start: number; end: number; text: string; type: string; url?: string }> = [];

      for (const { re, type } of patterns) {
        let m: RegExpExecArray | null;
        while ((m = re.exec(text)) !== null) {
          if (type === 'link') {
            allMatches.push({ start: m.index, end: m.index + m[0].length, text: m[1], url: m[2], type });
          } else {
            allMatches.push({ start: m.index, end: m.index + m[0].length, text: m[1], type });
          }
        }
      }

      allMatches.sort((a, b) => a.start - b.start);

      let offset = 0;
      allMatches.forEach((match, i) => {
        if (match.start > offset) {
          parts.push(text.slice(offset, match.start));
        }

        if (match.type === 'bold') {
          parts.push(<strong key={i} className="font-bold text-gray-900 dark:text-gray-100">{match.text}</strong>);
        } else if (match.type === 'italic') {
          parts.push(<em key={i} className="italic text-gray-700 dark:text-gray-300">{match.text}</em>);
        } else if (match.type === 'code') {
          parts.push(
            <code key={i} className="bg-gray-200 dark:bg-gray-800 text-emerald-700 dark:text-emerald-400 px-1.5 py-0.5 rounded font-mono text-sm">
              {match.text}
            </code>
          );
        } else if (match.type === 'link') {
          parts.push(
            <a key={i} href={match.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 dark:text-blue-400 underline hover:text-blue-800 dark:hover:text-blue-300">
              {match.text}
            </a>
          );
        }
        offset = match.end;
      });

      if (offset < text.length) {
        parts.push(text.slice(offset));
      }

      return parts;
    };

    return (
      <div key={idx} className="text-gray-800 dark:text-gray-200 leading-relaxed">
        {renderInlined(line)}
      </div>
    );
  };

  return (
    <div className="flex-1 overflow-auto scrollbar-thin bg-white dark:bg-[#0d1117]">
      <article className="max-w-4xl mx-auto px-8 py-6 prose prose-sm dark:prose-invert">
        <div className="space-y-2 text-gray-700 dark:text-gray-300">
          {lines.map((line, idx) => renderMarkdownLine(line, idx))}
        </div>
      </article>
    </div>
  );
}

// ─── JSON Viewer Component ──────────────────────────────────────────────────────

function JsonViewer({ content }: { content: string }) {
  const [parsed, error] = useMemo(() => {
    try {
      return [JSON.parse(content), null];
    } catch (e) {
      return [null, String(e)];
    }
  }, [content]);

  const renderJson = (obj: any, depth: number = 0): React.ReactNode => {
    if (obj === null) return <span className="text-violet-400">null</span>;
    if (typeof obj === 'boolean') return <span className="text-violet-400">{String(obj)}</span>;
    if (typeof obj === 'number') return <span className="text-amber-300">{obj}</span>;
    if (typeof obj === 'string') return <span className="text-emerald-400">"{obj}"</span>;

    if (Array.isArray(obj)) {
      if (obj.length === 0) return <span className="text-zinc-400">[]</span>;
      return (
        <div className="inline-block">
          <span className="text-zinc-300">[</span>
          <div style={{ marginLeft: `${(depth + 1) * 1.5}rem` }} className="space-y-1">
            {obj.map((item, i) => (
              <div key={i} className="flex gap-2">
                {renderJson(item, depth + 1)}
                {i < obj.length - 1 && <span className="text-zinc-300">,</span>}
              </div>
            ))}
          </div>
          <div style={{ marginLeft: `${depth * 1.5}rem` }} className="inline-block">
            <span className="text-zinc-300">]</span>
          </div>
        </div>
      );
    }

    if (typeof obj === 'object') {
      const keys = Object.keys(obj);
      if (keys.length === 0) return <span className="text-zinc-300">{'{}'}</span>;
      return (
        <div className="inline-block">
          <span className="text-zinc-300">{'{'}</span>
          <div style={{ marginLeft: `${(depth + 1) * 1.5}rem` }} className="space-y-1">
            {keys.map((key, i) => (
              <div key={i} className="flex gap-1">
                <span className="text-sky-400">"{key}"</span>
                <span className="text-zinc-300">:</span>
                <div className="inline-block">{renderJson(obj[key], depth + 1)}</div>
                {i < keys.length - 1 && <span className="text-zinc-300">,</span>}
              </div>
            ))}
          </div>
          <div style={{ marginLeft: `${depth * 1.5}rem` }} className="inline-block">
            <span className="text-zinc-300">{'}'}</span>
          </div>
        </div>
      );
    }

    return <span className="text-zinc-400">{String(obj)}</span>;
  };

  return (
    <div className="flex-1 overflow-auto scrollbar-thin bg-[#0d1117]">
      <div className="p-6 font-mono text-[13px] leading-relaxed text-[#c9d1d9]">
        {error ? (
          <div className="text-red-400 space-y-2">
            <p className="font-bold">JSON Parse Error:</p>
            <p className="text-xs text-red-300">{error}</p>
            <pre className="mt-4 text-[11px] bg-red-500/10 p-3 rounded overflow-auto max-h-40 text-red-200">
              {content}
            </pre>
          </div>
        ) : (
          <div>{renderJson(parsed)}</div>
        )}
      </div>
    </div>
  );
}

// ─── Code Viewer Component ──────────────────────────────────────────────────────

function CodeViewer({
  content,
  highlightedLines
}: {
  content: string
  highlightedLines: React.ReactNode[][]
}) {
  return (
    <div className="flex-1 overflow-auto scrollbar-thin bg-[#0d1117]">
      <div className="flex h-full">
        {/* Line numbers - sticky */}
        <div className="sticky left-0 z-20 bg-[#0d1117] border-r border-[#21262d] select-none px-4 py-4 text-right font-mono text-[11px] text-[#6e7681] leading-[1.7rem] flex-shrink-0 min-w-[4rem]">
          {content.split('\n').map((_, idx) => (
            <div key={idx} className="hover:text-[#8b949e] transition-colors cursor-default">
              {idx + 1}
            </div>
          ))}
        </div>

        {/* Code content */}
        <div className="flex-1 overflow-x-auto">
          <pre className="p-4 font-mono text-[12.5px] leading-[1.7rem] whitespace-pre text-[#c9d1d9] bg-[#0d1117] min-w-full">
            {highlightedLines.map((nodes, idx) => (
              <div key={idx} className="hover:bg-[#161b22] transition-colors">
                {nodes}
              </div>
            ))}
          </pre>
        </div>
      </div>
    </div>
  );
}

// ─── Syntax Highlighting ───────────────────────────────────────────────────────

function highlightLine(line: string, language: string): React.ReactNode[] {
  if (!line) return [<span key="empty">{'\n'}</span>];

  switch (language) {
    case 'python':
      return highlightPython(line);
    case 'typescript':
    case 'tsx':
    case 'javascript':
    case 'jsx':
      return highlightTS(line);
    case 'json':
      return highlightJSON(line);
    case 'shell':
    case 'bash':
    case 'sh':
      return highlightShell(line);
    case 'yaml':
    case 'yml':
    case 'toml':
      return highlightYaml(line);
    case 'markdown':
    case 'md':
      return highlightMarkdown(line);
    case 'css':
    case 'scss':
      return highlightCSS(line);
    case 'html':
    case 'xml':
      return highlightHTML(line);
    case 'sql':
      return highlightSQL(line);
    default:
      return [<span key="0">{line}</span>];
  }
}

function highlightPython(line: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  // Comment
  const commentIdx = findUnquotedHash(line);
  const codePart = commentIdx >= 0 ? line.slice(0, commentIdx) : line;
  const commentPart = commentIdx >= 0 ? line.slice(commentIdx) : '';

  const tokens = tokenize(codePart, [
    { regex: /\b(def|class|import|from|return|if|elif|else|for|while|try|except|finally|with|as|yield|async|await|raise|pass|break|continue|lambda|and|or|not|in|is|None|True|False|self|global|nonlocal|assert|del)\b/g, cls: 'text-violet-400' },
    { regex: /\b(int|str|float|bool|list|dict|tuple|set|bytes|type|object|Exception)\b/g, cls: 'text-cyan-400' },
    { regex: /("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g, cls: 'text-emerald-400' },
    { regex: /\b(\d+\.?\d*)\b/g, cls: 'text-amber-300' },
    { regex: /(@\w+)/g, cls: 'text-yellow-400' },
    { regex: /\b(def)\s+(\w+)/g, cls: 'text-blue-300', group: 2 },
  ]);
  parts.push(...tokens);

  if (commentPart) {
    parts.push(<span key="comment" className="text-zinc-500 italic">{commentPart}</span>);
  }
  return parts;
}

function highlightTS(line: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  const commentMatch = line.match(/^(.*?)(\/\/.*$)/);
  const codePart = commentMatch ? commentMatch[1] : line;
  const commentPart = commentMatch ? commentMatch[2] : '';

  const tokens = tokenize(codePart, [
    { regex: /\b(import|export|from|const|let|var|function|return|if|else|for|while|class|interface|type|enum|extends|implements|new|this|super|async|await|try|catch|finally|throw|typeof|instanceof|void|null|undefined|true|false|default|switch|case|break|continue|yield|of|in|as|is)\b/g, cls: 'text-violet-400' },
    { regex: /\b(string|number|boolean|any|never|unknown|object|Array|Promise|Record|Partial|Required|Omit|Pick)\b/g, cls: 'text-cyan-400' },
    { regex: /(`[^`]*`|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g, cls: 'text-emerald-400' },
    { regex: /\b(\d+\.?\d*)\b/g, cls: 'text-amber-300' },
    { regex: /(\{|\}|\(|\)|\[|\])/g, cls: 'text-zinc-400' },
    { regex: /(=>|\.\.\.)/g, cls: 'text-pink-400' },
  ]);
  parts.push(...tokens);

  if (commentPart) {
    parts.push(<span key="comment" className="text-zinc-500 italic">{commentPart}</span>);
  }
  return parts;
}

function highlightJSON(line: string): React.ReactNode[] {
  const tokens = tokenize(line, [
    { regex: /("(?:[^"\\]|\\.)*")\s*:/g, cls: 'text-sky-400', group: 1 },
    { regex: /:\s*("(?:[^"\\]|\\.)*")/g, cls: 'text-emerald-400', group: 1 },
    { regex: /\b(true|false|null)\b/g, cls: 'text-violet-400' },
    { regex: /\b(-?\d+\.?\d*(?:[eE][+-]?\d+)?)\b/g, cls: 'text-amber-300' },
    { regex: /(\{|\}|\[|\])/g, cls: 'text-zinc-500' },
  ]);
  return tokens;
}

function highlightShell(line: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  if (line.trimStart().startsWith('#')) {
    return [<span key="0" className="text-zinc-500 italic">{line}</span>];
  }
  const tokens = tokenize(line, [
    { regex: /\b(if|then|else|elif|fi|for|do|done|while|until|case|esac|function|return|exit|export|source|alias|unset|local|readonly|shift|set)\b/g, cls: 'text-violet-400' },
    { regex: /(\$\{?\w+\}?|\$\(\w+\))/g, cls: 'text-cyan-400' },
    { regex: /("(?:[^"\\]|\\.)*"|'[^']*')/g, cls: 'text-emerald-400' },
    { regex: /(\||\||&&|>>|>|<|;)/g, cls: 'text-pink-400' },
  ]);
  parts.push(...tokens);
  return parts;
}

function highlightYaml(line: string): React.ReactNode[] {
  if (line.trimStart().startsWith('#')) {
    return [<span key="0" className="text-zinc-500 italic">{line}</span>];
  }
  const tokens = tokenize(line, [
    { regex: /^(\s*[\w.-]+)(:)/gm, cls: 'text-sky-400', group: 1 },
    { regex: /\b(true|false|null|yes|no)\b/gi, cls: 'text-violet-400' },
    { regex: /("(?:[^"\\]|\\.)*"|'[^']*')/g, cls: 'text-emerald-400' },
    { regex: /\b(\d+\.?\d*)\b/g, cls: 'text-amber-300' },
  ]);
  return tokens;
}

function highlightMarkdown(line: string): React.ReactNode[] {
  // Headings
  if (/^#{1,6}\s/.test(line)) {
    return [<span key="0" className="text-sky-400 font-bold">{line}</span>];
  }
  // Blockquote
  if (/^\s*>/.test(line)) {
    return [<span key="0" className="text-zinc-400 italic border-l-2 border-zinc-600 pl-2">{line}</span>];
  }
  // List items
  if (/^\s*[-*+]\s/.test(line) || /^\s*\d+\.\s/.test(line)) {
    return [<span key="0" className="text-foreground/90">{line}</span>];
  }
  // Code fences
  if (/^```/.test(line)) {
    return [<span key="0" className="text-emerald-400">{line}</span>];
  }
  // Bold/italic inline
  const tokens = tokenize(line, [
    { regex: /(\*\*[^*]+\*\*|__[^_]+__)/g, cls: 'text-foreground font-bold' },
    { regex: /(\*[^*]+\*|_[^_]+_)/g, cls: 'text-foreground italic' },
    { regex: /(`[^`]+`)/g, cls: 'text-emerald-400 bg-emerald-400/10 rounded px-0.5' },
    { regex: /(\[([^\]]+)\]\([^)]+\))/g, cls: 'text-blue-400 underline' },
  ]);
  return tokens;
}

function highlightCSS(line: string): React.ReactNode[] {
  const tokens = tokenize(line, [
    { regex: /(\/\*[\s\S]*?\*\/)/g, cls: 'text-zinc-500 italic' },
    { regex: /([.#][\w-]+)/g, cls: 'text-sky-400' },
    { regex: /([\w-]+)\s*:/g, cls: 'text-violet-400', group: 1 },
    { regex: /:\s*([^;{]+)/g, cls: 'text-emerald-400', group: 1 },
    { regex: /\b(\d+\.?\d*(px|rem|em|%|vh|vw|s|ms)?)\b/g, cls: 'text-amber-300' },
  ]);
  return tokens;
}

function highlightHTML(line: string): React.ReactNode[] {
  const tokens = tokenize(line, [
    { regex: /(<!--[\s\S]*?-->)/g, cls: 'text-zinc-500 italic' },
    { regex: /(<\/?[\w-]+)/g, cls: 'text-pink-400' },
    { regex: /(\s)([\w-]+)(=)/g, cls: 'text-sky-400', group: 2 },
    { regex: /("(?:[^"\\]|\\.)*"|'[^']*')/g, cls: 'text-emerald-400' },
    { regex: /(>|<|\/>)/g, cls: 'text-pink-400' },
  ]);
  return tokens;
}

function highlightSQL(line: string): React.ReactNode[] {
  if (line.trimStart().startsWith('--')) {
    return [<span key="0" className="text-zinc-500 italic">{line}</span>];
  }
  const tokens = tokenize(line, [
    { regex: /\b(SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|ON|AND|OR|NOT|INSERT|INTO|VALUES|UPDATE|SET|DELETE|CREATE|TABLE|ALTER|DROP|INDEX|GROUP|BY|ORDER|HAVING|LIMIT|OFFSET|AS|DISTINCT|UNION|ALL|EXISTS|IN|BETWEEN|LIKE|IS|NULL|CASE|WHEN|THEN|ELSE|END|BEGIN|COMMIT|ROLLBACK)\b/gi, cls: 'text-violet-400 uppercase' },
    { regex: /\b(INT|VARCHAR|TEXT|BOOLEAN|DATE|TIMESTAMP|SERIAL|BIGINT|FLOAT|DECIMAL|UUID)\b/gi, cls: 'text-cyan-400' },
    { regex: /('(?:[^'\\]|\\.)*')/g, cls: 'text-emerald-400' },
    { regex: /\b(\d+\.?\d*)\b/g, cls: 'text-amber-300' },
  ]);
  return tokens;
}

/** Simple tokenizer - applies rules in order, returns React nodes */
function tokenize(text: string, rules: { regex: RegExp; cls: string; group?: number }[]): React.ReactNode[] {
  if (!text) return [<span key="empty"></span>];

  interface Match { start: number; end: number; text: string; cls: string }
  const matches: Match[] = [];

  for (const rule of rules) {
    const re = new RegExp(rule.regex.source, rule.regex.flags);
    let m: RegExpExecArray | null;
    while ((m = re.exec(text)) !== null) {
      const group = rule.group ?? 0;
      const matchText = m[group] || m[0];
      const start = group ? text.indexOf(matchText, m.index) : m.index;
      if (start < 0) continue;
      matches.push({ start, end: start + matchText.length, text: matchText, cls: rule.cls });
    }
  }

  // Sort by start, remove overlaps
  matches.sort((a, b) => a.start - b.start);
  const filtered: Match[] = [];
  let lastEnd = 0;
  for (const m of matches) {
    if (m.start >= lastEnd) {
      filtered.push(m);
      lastEnd = m.end;
    }
  }

  const result: React.ReactNode[] = [];
  let pos = 0;
  filtered.forEach((m, i) => {
    if (m.start > pos) {
      result.push(<span key={`t${i}`}>{text.slice(pos, m.start)}</span>);
    }
    result.push(<span key={`m${i}`} className={m.cls}>{m.text}</span>);
    pos = m.end;
  });
  if (pos < text.length) {
    result.push(<span key="rest">{text.slice(pos)}</span>);
  }
  return result;
}

function findUnquotedHash(line: string): number {
  let inString = false;
  let quote = '';
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (inString) {
      if (ch === '\\') { i++; continue; }
      if (ch === quote) inString = false;
    } else {
      if (ch === '"' || ch === "'") { inString = true; quote = ch; }
      else if (ch === '#') return i;
    }
  }
  return -1;
}

// ─── Health dot helper ─────────────────────────────────────────────────────────
function healthColor(health?: string) {
  if (health === 'critical') return 'text-red-400';
  if (health === 'review_suggested') return 'text-amber-400';
  if (health === 'healthy') return 'text-emerald-400';
  return 'text-zinc-500';
}

// ─── Language badge color helper ───────────────────────────────────────────────
function langBadgeClass(lang: string): string {
  switch (lang) {
    case 'python': return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
    case 'typescript': case 'tsx': return 'bg-sky-500/10 text-sky-400 border-sky-500/20';
    case 'javascript': case 'jsx': return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20';
    case 'markdown': case 'md': return 'bg-slate-500/10 text-slate-300 border-slate-500/20';
    case 'json': return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
    case 'shell': case 'bash': case 'sh': return 'bg-green-500/10 text-green-400 border-green-500/20';
    case 'yaml': case 'yml': case 'toml': return 'bg-violet-500/10 text-violet-400 border-violet-500/20';
    case 'css': case 'scss': return 'bg-pink-500/10 text-pink-400 border-pink-500/20';
    case 'html': case 'xml': return 'bg-orange-500/10 text-orange-400 border-orange-500/20';
    case 'sql': return 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20';
    case 'rust': return 'bg-orange-600/10 text-orange-300 border-orange-600/20';
    case 'go': return 'bg-cyan-600/10 text-cyan-300 border-cyan-600/20';
    case 'java': return 'bg-red-500/10 text-red-400 border-red-500/20';
    default: return 'bg-muted text-muted-foreground border-border';
  }
}

// ─── Sidebar Tree Node ─────────────────────────────────────────────────────────
function TreeNodeItem({
  node,
  depth,
  isOpen,
  isActive,
  isLoading,
  onToggle,
  onClick,
}: {
  node: ExplorerTreeNode;
  depth: number;
  isOpen: boolean;
  isActive: boolean;
  isLoading: boolean;
  onToggle: () => void;
  onClick: () => void;
}) {
  const isFolder = node.type === 'folder';
  return (
    <button
      type="button"
      className={cn(
        'group flex w-full items-center gap-1.5 rounded-lg px-2 py-1.5 text-left text-[13px] transition-colors hover:bg-accent/60',
        isActive && 'bg-brand/10 text-brand font-medium',
      )}
      style={{ paddingLeft: `${depth * 14 + 8}px` }}
      onClick={isFolder ? onToggle : onClick}
    >
      {isFolder ? (
        <>
          {isLoading ? (
            <Loader2 size={13} className="animate-spin text-muted-foreground flex-shrink-0" />
          ) : isOpen ? (
            <ChevronDown size={13} className="text-muted-foreground flex-shrink-0" />
          ) : (
            <ChevronRight size={13} className="text-muted-foreground flex-shrink-0" />
          )}
          {isOpen ? (
            <FolderOpen size={14} className="text-amber-400 flex-shrink-0" />
          ) : (
            <Folder size={14} className="text-amber-400/70 flex-shrink-0" />
          )}
        </>
      ) : (
        <>
          <span className="w-[13px] flex-shrink-0" />
          <FileCode size={14} className="text-muted-foreground flex-shrink-0" />
        </>
      )}
      <span className="truncate flex-1">{node.name}</span>
      {!isFolder && (
        <Circle size={6} fill="currentColor" className={cn('flex-shrink-0 opacity-70', healthColor(node.health))} />
      )}
    </button>
  );
}

// ─── Main Page ─────────────────────────────────────────────────────────────────
export default function RepositoryExplorerPage() {
  const { id: repoId } = useParams<{ id: string }>();
  const router = useRouter();
  const [token, setToken] = useState('');

  // Tree state
  const [treeByPath, setTreeByPath] = useState<Record<string, ExplorerTreeNode[]>>({});
  const [openFolders, setOpenFolders] = useState<Set<string>>(new Set(['']));
  const [loadingPath, setLoadingPath] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  // File viewer state
  const [activeFile, setActiveFile] = useState<ExplorerFileDetails | null>(null);
  const [activeFilePath, setActiveFilePath] = useState<string>('');

  // Review actions state
  const [ribbonReview, setRibbonReview] = useState<ExplorerReviewResult | null>(null);
  const [ribbonFix, setRibbonFix] = useState<ExplorerFixProposal | null>(null);
  const [ribbonTests, setRibbonTests] = useState<ExplorerTestRunResult | null>(null);
  const [ribbonHistory, setRibbonHistory] = useState('');
  const [ribbonAction, setRibbonAction] = useState<string | null>(null);
  const [showDiff, setShowDiff] = useState(false);

  // Init
  useEffect(() => {
    async function init() {
      const { data } = await createClient().auth.getSession();
      const t = data.session?.access_token ?? '';
      setToken(t);
    }
    void init();
  }, []);

  // Load root tree on token ready
  useEffect(() => {
    if (!token) return;
    void loadFolder('');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function loadFolder(path: string) {
    if (!token) return;
    if (treeByPath[path]) return;
    setLoadingPath(path);
    try {
      const payload = await getExplorerTree(token, repoId, { path, limit: 500 });
      setTreeByPath((prev) => ({ ...prev, [path]: payload.nodes }));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to load tree');
    } finally {
      setLoadingPath(null);
    }
  }

  function toggleFolder(path: string) {
    const next = new Set(openFolders);
    if (next.has(path)) {
      next.delete(path);
    } else {
      next.add(path);
      void loadFolder(path);
    }
    setOpenFolders(next);
  }

  async function openFile(path: string) {
    setActiveFilePath(path);
    setRibbonReview(null);
    setRibbonFix(null);
    setRibbonTests(null);
    setRibbonHistory('');
    try {
      const details = await getExplorerFile(token, repoId, path);
      setActiveFile(details);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to open file');
      setActiveFile(null);
    }
  }

  // ─── Review actions ──────────────────────────────────────────────────────────
  async function runReview(type: string) {
    if (!token || !activeFilePath) return;
    try {
      setRibbonAction(type);
      const result = await runExplorerFileReview(token, repoId, { path: activeFilePath, review_type: type });
      setRibbonReview(result);
      toast.success(`${type.replace('_', ' ')} complete`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Action failed');
    } finally {
      setRibbonAction(null);
    }
  }

  async function handleGenerateTests() {
    if (!token || !activeFilePath) return;
    try {
      setRibbonAction('generate_tests');
      const discovered = await discoverExplorerTests(token, repoId, [activeFilePath]);
      setRibbonHistory(`Generated tests (${discovered.tests.length}): ${discovered.tests.slice(0, 6).join(', ') || 'none'}`);
      toast.success('Generated test candidates');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Generate tests failed');
    } finally {
      setRibbonAction(null);
    }
  }

  async function handleRunTests() {
    if (!token || !activeFilePath) return;
    try {
      setRibbonAction('run_tests');
      const discovered = await discoverExplorerTests(token, repoId, [activeFilePath]);
      const run = await runExplorerTests(token, repoId, discovered.tests.slice(0, 12), 55);
      setRibbonTests(run);
      toast.success(`${run.status.toUpperCase()}: ${run.passed} passed, ${run.failed} failed`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Run tests failed');
    } finally {
      setRibbonAction(null);
    }
  }

  async function handleGenerateFix() {
    if (!token || !activeFilePath) return;
    const finding = ribbonReview?.findings?.[0]?.finding || 'Improve maintainability and robustness';
    const recommendation = ribbonReview?.findings?.[0]?.recommendation || '';
    try {
      setRibbonAction('generate_fix');
      const fix = await generateExplorerFix(token, repoId, { path: activeFilePath, finding, recommendation });
      setRibbonFix(fix);
      setShowDiff(true);
      toast.success('Fix generated');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Generate fix failed');
    } finally {
      setRibbonAction(null);
    }
  }

  async function handleApplyFix() {
    if (!token || !activeFilePath || !ribbonFix) return;
    if (!window.confirm('Apply this fix?')) return;
    try {
      setRibbonAction('apply_fix');
      await applyExplorerFix(token, repoId, {
        fix_id: ribbonFix.fix_id,
        expected_sha256: activeFile?.sha256,
        run_validation: true,
      });
      const refreshed = await getExplorerFile(token, repoId, activeFilePath);
      setActiveFile(refreshed);
      toast.success('Fix applied');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Apply fix failed');
    } finally {
      setRibbonAction(null);
    }
  }

  async function handleHistory() {
    if (!token || !activeFilePath) return;
    try {
      setRibbonAction('history');
      const history = await getExplorerHistory(token, repoId, activeFilePath);
      setRibbonHistory(
        [
          `Reviews: ${history.reviews.length}`,
          `Fixes: ${history.fixes.length}`,
          `Applied: ${history.applied_fixes.length}`,
          `Tests: ${history.test_runs.length}`,
        ].join(' • ')
      );
      toast.success('History loaded');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'History load failed');
    } finally {
      setRibbonAction(null);
    }
  }

  async function handleAskAi() {
    if (!token || !activeFilePath) return;
    try {
      setRibbonAction('ask_ai');
      await addExplorerConversationEntry(token, repoId, {
        path: activeFilePath,
        role: 'user',
        content: `Open AI conversation for ${activeFilePath}`,
      });
      window.dispatchEvent(new CustomEvent('codebase:new-chat', { detail: { repoId } }));
      toast.success('AI chat context queued');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Ask AI failed');
    } finally {
      setRibbonAction(null);
    }
  }

  // ─── Filtered tree nodes ─────────────────────────────────────────────────────
  const filteredRoots = useMemo(() => {
    const roots = treeByPath[''] || [];
    if (!search.trim()) return roots;
    const q = search.toLowerCase();
    return roots.filter((n) => n.name.toLowerCase().includes(q) || n.path.toLowerCase().includes(q));
  }, [treeByPath, search]);

  // ─── Recursive tree renderer ─────────────────────────────────────────────────
  function renderTree(nodes: ExplorerTreeNode[], depth: number) {
    return nodes.map((node) => {
      const isFolder = node.type === 'folder';
      const isOpen = openFolders.has(node.path);
      const children = treeByPath[node.path] || [];
      const isActive = activeFilePath === node.path;
      const isLoading = loadingPath === node.path;

      return (
        <div key={node.path}>
          <TreeNodeItem
            node={node}
            depth={depth}
            isOpen={isOpen}
            isActive={isActive}
            isLoading={isLoading}
            onToggle={() => toggleFolder(node.path)}
            onClick={() => openFile(node.path)}
          />
          {isFolder && isOpen && children.length > 0 && renderTree(children, depth + 1)}
        </div>
      );
    });
  }

  // ─── Health score ────────────────────────────────────────────────────────────
  const healthScore = useMemo(() => {
    if (!activeFile) return null;
    if (activeFile.health === 'critical') return 42;
    if (activeFile.health === 'review_suggested') return 67;
    if (activeFile.health === 'healthy') return 84;
    return 74;
  }, [activeFile]);

  // ─── Highlighted lines (memoized) ───────────────────────────────────────────
  const highlightedLines = useMemo(() => {
    if (!activeFile) return [];
    const lang = activeFile.language || '';
    return activeFile.content.split('\n').map((line) => highlightLine(line, lang));
  }, [activeFile]);

  return (
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden">
      {/* ─── Sidebar: File Explorer ─────────────────────────────────────────── */}
      <aside className="w-72 flex-shrink-0 border-r border-border bg-card/50 flex flex-col overflow-hidden">
        {/* Sidebar Header */}
        <div className="border-b border-border p-3 space-y-2">
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => router.push(`/repo/${repoId}`)}>
              <ArrowLeft size={14} />
            </Button>
            <div className="flex items-center gap-1.5 min-w-0">
              <Sparkles size={14} className="text-brand flex-shrink-0" />
              <span className="text-sm font-semibold truncate">AI Code Explorer</span>
            </div>
          </div>
          <div className="relative">
            <FileSearch size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search files..."
              className="h-8 pl-8 text-xs"
            />
          </div>
        </div>

        {/* Tree */}
        <div className="flex-1 overflow-y-auto overflow-x-hidden py-1 scrollbar-thin">
          {filteredRoots.length === 0 && !loadingPath && (
            <p className="px-3 py-6 text-center text-xs text-muted-foreground">
              {token ? 'No files found' : 'Loading...'}
            </p>
          )}
          {loadingPath === '' && filteredRoots.length === 0 && (
            <div className="flex items-center justify-center py-8">
              <Loader2 size={18} className="animate-spin text-muted-foreground" />
            </div>
          )}
          {renderTree(filteredRoots, 0)}
        </div>
      </aside>

      {/* ─── Main Content: File Viewer ──────────────────────────────────────── */}
      <main className="flex-1 flex flex-col overflow-hidden bg-background">
        {activeFile ? (
          <>
            {/* File Header Bar */}
            <div className="border-b border-border bg-card/70 px-5 py-3 flex items-center justify-between gap-4 flex-shrink-0">
              <div className="min-w-0">
                <div className="flex items-center gap-2.5">
                  <span className={cn(
                    'inline-flex items-center rounded-md px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider border',
                    langBadgeClass(activeFile.language || ''),
                  )}>
                    {activeFile.language || 'text'}
                  </span>
                  <p className="text-sm font-semibold truncate text-foreground">{activeFile.path}</p>
                </div>
                <p className="text-[11px] text-muted-foreground mt-1.5 flex items-center gap-2">
                  <span>{activeFile.line_count} lines</span>
                  <span className="text-border">•</span>
                  <span>{activeFile.functions.length} functions</span>
                  <span className="text-border">•</span>
                  <span>{activeFile.classes.length} classes</span>
                  <span className="text-border">•</span>
                  <span>{activeFile.imports.length} imports</span>
                </p>
              </div>
              <div className="flex items-center gap-3 flex-shrink-0">
                <span className={cn(
                  'inline-flex items-center gap-1.5 text-xs font-medium px-2 py-1 rounded-full border',
                  activeFile.health === 'critical' && 'text-red-400 border-red-500/20 bg-red-500/5',
                  activeFile.health === 'review_suggested' && 'text-amber-400 border-amber-500/20 bg-amber-500/5',
                  activeFile.health === 'healthy' && 'text-emerald-400 border-emerald-500/20 bg-emerald-500/5',
                  !['critical', 'review_suggested', 'healthy'].includes(activeFile.health || '') && 'text-muted-foreground border-border bg-muted/30',
                )}>
                  <Circle size={5} fill="currentColor" />
                  {activeFile.health || 'unknown'}
                </span>
                {healthScore && (
                  <span className="text-lg font-bold tabular-nums text-foreground">{healthScore}</span>
                )}
              </div>
            </div>

            {/* Action Toolbar */}
            <div className="border-b border-border bg-card/40 px-4 py-2 flex flex-wrap items-center gap-1.5 flex-shrink-0">
              <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => void runReview('explain')}>Explain</Button>
              <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => void runReview('review')}>Review</Button>
              <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => void runReview('find_bugs')}>Find Bugs</Button>
              <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => void runReview('security')}><Shield size={12} className="mr-1" />Security</Button>
              <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => void runReview('architecture')}>Architecture</Button>
              <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => void runReview('performance')}><Play size={12} className="mr-1" />Performance</Button>
              <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => void handleGenerateTests()}><TestTube size={12} className="mr-1" />Tests</Button>
              <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => void handleRunTests()}>Run Tests</Button>
              <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => void handleGenerateFix()}><Wrench size={12} className="mr-1" />Fix</Button>
              <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => void handleApplyFix()} disabled={!ribbonFix}>Apply</Button>
              <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => setShowDiff((p) => !p)}>Diff</Button>
              <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => void handleHistory()}><History size={12} className="mr-1" />History</Button>
              <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => void handleAskAi()}><MessageSquare size={12} className="mr-1" />Ask AI</Button>
              {ribbonAction && (
                <span className="inline-flex items-center gap-1.5 text-xs text-brand ml-2">
                  <Loader2 size={12} className="animate-spin" /> {ribbonAction.replace(/_/g, ' ')}...
                </span>
              )}
            </div>

            {/* Review / Fix Results Panel */}
            {(ribbonReview || ribbonFix || ribbonTests || ribbonHistory) && (
              <div className="border-b border-border bg-brand/5 px-5 py-3 flex-shrink-0 space-y-2 max-h-52 overflow-y-auto">
                {ribbonReview && (
                  <div className="text-sm">
                    <span className="font-medium">Score: {ribbonReview.overall_score}</span>
                    <span className="text-muted-foreground ml-2">{ribbonReview.summary}</span>
                    {ribbonReview.findings.length > 0 && (
                      <div className="mt-1.5 space-y-1">
                        {ribbonReview.findings.slice(0, 5).map((f, i) => (
                          <div key={i} className="text-xs text-muted-foreground flex items-start gap-1.5">
                            <span className={cn(
                              'uppercase font-semibold text-[10px] mt-0.5',
                              f.severity === 'critical' && 'text-red-400',
                              f.severity === 'high' && 'text-amber-400',
                            )}>{f.severity}</span>
                            <span>{f.finding}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
                {ribbonFix && showDiff && (
                  <div className="text-xs">
                    <p className="font-medium text-sm mb-1">Fix Proposal</p>
                    <pre className="max-h-28 overflow-auto rounded bg-black/10 p-2 whitespace-pre-wrap font-mono text-[11px]">{ribbonFix.diff || 'No changes'}</pre>
                  </div>
                )}
                {ribbonTests && (
                  <p className="text-xs text-muted-foreground">
                    Tests: <span className="font-medium">{ribbonTests.status.toUpperCase()}</span> — Passed {ribbonTests.passed} • Failed {ribbonTests.failed} • {ribbonTests.duration_seconds}s
                  </p>
                )}
                {ribbonHistory && (
                  <p className="text-xs text-muted-foreground">{ribbonHistory}</p>
                )}
              </div>
            )}

            {/* Full File Content Viewer - Format-aware rendering */}
            {isMarkdownFile(activeFile.language) ? (
              <MarkdownViewer content={activeFile.content} />
            ) : isJsonFile(activeFile.language) ? (
              <JsonViewer content={activeFile.content} />
            ) : (
              <CodeViewer content={activeFile.content} highlightedLines={highlightedLines} />
            )}
          </>
        ) : (
          /* Empty state */
          <div className="flex-1 flex items-center justify-center bg-background">
            <div className="text-center space-y-4">
              <div className="mx-auto w-20 h-20 rounded-2xl bg-brand/10 border border-brand/20 flex items-center justify-center">
                <FileCode size={32} className="text-brand/50" />
              </div>
              <div>
                <p className="text-base font-medium text-foreground">Select a file to view</p>
                <p className="text-sm text-muted-foreground mt-1">Browse the repository tree on the left</p>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

