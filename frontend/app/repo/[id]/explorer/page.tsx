'use client';

/* eslint-disable react/no-unescaped-entities */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  ArrowLeft,
  Check,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  Copy,
  Circle,
  Download,
  FileCode,
  FileText,
  FileSearch,
  Folder,
  FolderOpen,
  History,
  Info,
  Loader2,
  Minus,
  MessageSquare,
  Plus,
  Play,
  Search,
  Shield,
  Sparkles,
  TestTube,
  Wrench,
  X,
} from 'lucide-react';
import { useRepoSessionToken } from '@/hooks/useRepoSessionToken';
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

function isXmlFile(language?: string): boolean {
  return language === 'xml';
}

function isLogLanguage(language?: string): boolean {
  return language === 'log';
}

type ViewerTheme = 'github' | 'vscode' | 'pycharm';

type ViewerMode = 'markdown' | 'structured' | 'log' | 'code' | 'binary' | 'text';

type ViewerThemeStyle = {
  bg: string;
  header: string;
  lineNumber: string;
  border: string;
  text: string;
  lineHover: string;
};

const VIEWER_THEME_STYLES: Record<ViewerTheme, { light: ViewerThemeStyle; dark: ViewerThemeStyle }> = {
  github: {
    light: {
      bg: 'bg-white',
      header: 'bg-[#f6f8fa]',
      lineNumber: 'text-[#57606a] bg-[#f6f8fa]',
      border: 'border-[#d0d7de]',
      text: 'text-[#24292f]',
      lineHover: 'hover:bg-[#f6f8fa]',
    },
    dark: {
      bg: 'bg-[#0d1117]',
      header: 'bg-[#161b22]',
      lineNumber: 'text-[#8b949e] bg-[#161b22]',
      border: 'border-[#30363d]',
      text: 'text-[#c9d1d9]',
      lineHover: 'hover:bg-[#161b22]',
    },
  },
  vscode: {
    light: {
      bg: 'bg-white',
      header: 'bg-[#f3f3f3]',
      lineNumber: 'text-[#6b6b6b] bg-[#f3f3f3]',
      border: 'border-[#d4d4d4]',
      text: 'text-[#1f1f1f]',
      lineHover: 'hover:bg-[#f5f5f5]',
    },
    dark: {
      bg: 'bg-[#1e1e1e]',
      header: 'bg-[#252526]',
      lineNumber: 'text-[#858585] bg-[#252526]',
      border: 'border-[#3c3c3c]',
      text: 'text-[#d4d4d4]',
      lineHover: 'hover:bg-[#2a2d2e]',
    },
  },
  pycharm: {
    light: {
      bg: 'bg-white',
      header: 'bg-[#f7f7f7]',
      lineNumber: 'text-[#7a7a7a] bg-[#f7f7f7]',
      border: 'border-[#d9d9d9]',
      text: 'text-[#1e1e1e]',
      lineHover: 'hover:bg-[#f7f9fb]',
    },
    dark: {
      bg: 'bg-[#2b2b2b]',
      header: 'bg-[#313335]',
      lineNumber: 'text-[#a9b7c6] bg-[#313335]',
      border: 'border-[#3c3f41]',
      text: 'text-[#a9b7c6]',
      lineHover: 'hover:bg-[#323232]',
    },
  },
};

const MARKDOWN_THEME_STYLES: Record<ViewerTheme, { light: { quote: string; codeWrap: string; codeHead: string; table: string }; dark: { quote: string; codeWrap: string; codeHead: string; table: string } }> = {
  github: {
    light: {
      quote: 'border-sky-300 bg-sky-50',
      codeWrap: 'border-[#d0d7de] bg-[#f6f8fa]',
      codeHead: 'bg-[#f6f8fa] text-[#57606a] border-b border-[#d0d7de]',
      table: 'border-[#d0d7de] bg-white',
    },
    dark: {
      quote: 'border-sky-700 bg-sky-950/40 text-[#c9d1d9]',
      codeWrap: 'border-[#30363d] bg-[#161b22]',
      codeHead: 'bg-[#161b22] text-[#8b949e] border-b border-[#30363d]',
      table: 'border-[#30363d] bg-[#0d1117]',
    },
  },
  vscode: {
    light: {
      quote: 'border-blue-300 bg-blue-50',
      codeWrap: 'border-[#d4d4d4] bg-[#f3f3f3]',
      codeHead: 'bg-[#f3f3f3] text-[#6b6b6b] border-b border-[#d4d4d4]',
      table: 'border-[#d4d4d4] bg-white',
    },
    dark: {
      quote: 'border-blue-700 bg-blue-950/30 text-[#d4d4d4]',
      codeWrap: 'border-[#3c3c3c] bg-[#252526]',
      codeHead: 'bg-[#252526] text-[#9da1a6] border-b border-[#3c3c3c]',
      table: 'border-[#3c3c3c] bg-[#1e1e1e]',
    },
  },
  pycharm: {
    light: {
      quote: 'border-violet-300 bg-violet-50',
      codeWrap: 'border-[#d9d9d9] bg-[#f7f7f7]',
      codeHead: 'bg-[#f7f7f7] text-[#7a7a7a] border-b border-[#d9d9d9]',
      table: 'border-[#d9d9d9] bg-white',
    },
    dark: {
      quote: 'border-violet-700 bg-violet-950/30 text-[#a9b7c6]',
      codeWrap: 'border-[#3c3f41] bg-[#313335]',
      codeHead: 'bg-[#313335] text-[#9aa6b2] border-b border-[#3c3f41]',
      table: 'border-[#3c3f41] bg-[#2b2b2b]',
    },
  },
};

const BINARY_EXTENSIONS = new Set([
  'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'ico', 'pdf', 'zip', 'tar', 'gz', 'rar', '7z', 'exe', 'dll', 'so',
  'class', 'pyc', 'db', 'sqlite', 'woff', 'woff2', 'ttf', 'eot', 'mp3', 'wav', 'mp4', 'webm', 'ogg', 'xlsx', 'docx',
  'pptx', 'jar', 'war', 'bin',
]);

function getFileExtension(path: string): string {
  const base = path.split('/').pop() || path;
  if (base.toLowerCase() === 'dockerfile') return 'dockerfile';
  if (base.toLowerCase() === '.gitignore') return 'gitignore';
  if (base.toLowerCase() === '.env') return 'env';
  const idx = base.lastIndexOf('.');
  return idx >= 0 ? base.slice(idx + 1).toLowerCase() : '';
}

function detectLanguage(language: string | undefined, path: string): string {
  if (language && language.trim()) return language.toLowerCase();
  const ext = getFileExtension(path);
  const map: Record<string, string> = {
    md: 'markdown',
    py: 'python',
    sh: 'shell',
    js: 'javascript',
    ts: 'typescript',
    jsx: 'jsx',
    tsx: 'tsx',
    java: 'java',
    cs: 'cs',
    cpp: 'cpp',
    c: 'c',
    json: 'json',
    yaml: 'yaml',
    yml: 'yml',
    xml: 'xml',
    html: 'html',
    css: 'css',
    sql: 'sql',
    txt: 'text',
    log: 'log',
    dockerfile: 'dockerfile',
    env: 'env',
    gitignore: 'gitignore',
  };
  return map[ext] || 'text';
}

function isBinaryFile(path: string, content: string): boolean {
  const ext = getFileExtension(path);
  if (BINARY_EXTENSIONS.has(ext)) return true;

  const sample = content.slice(0, 2048);
  if (sample.includes('\u0000')) return true;
  let control = 0;
  for (let i = 0; i < sample.length; i++) {
    const code = sample.charCodeAt(i);
    if (code < 9 || (code > 13 && code < 32)) control++;
  }
  return sample.length > 0 && control / sample.length > 0.1;
}

function detectViewerMode(path: string, language: string, content: string): ViewerMode {
  if (isBinaryFile(path, content)) return 'binary';
  const ext = getFileExtension(path);
  if (isMarkdownFile(language) || ext === 'md') return 'markdown';
  if (isJsonFile(language) || isYamlFile(language) || isXmlFile(language) || ['json', 'yaml', 'yml', 'xml'].includes(ext)) {
    return 'structured';
  }
  if (isLogLanguage(language) || ext === 'log') return 'log';
  if (['txt', 'env', 'gitignore'].includes(ext) || language === 'text') return 'text';
  return 'code';
}

function humanFileSize(size: number): string {
  if (size < 1024) return `${size} B`;
  const units = ['KB', 'MB', 'GB'];
  let value = size / 1024;
  let idx = 0;
  while (value >= 1024 && idx < units.length - 1) {
    value /= 1024;
    idx++;
  }
  return `${value.toFixed(value >= 100 ? 0 : value >= 10 ? 1 : 2)} ${units[idx]}`;
}

function maybeRepairMojibake(text: string): string {
  // Common mojibake markers when UTF-8 bytes are decoded as Latin-1/CP1252.
  const suspicious = /[ÃÂâ€™â€œâ€â€“â€”]/;
  if (!suspicious.test(text)) return text;

  try {
    const bytes = Uint8Array.from(text, (ch) => ch.charCodeAt(0) & 0xff);
    const repaired = new TextDecoder('utf-8').decode(bytes);

    const mojibakeScore = (value: string) => {
      const m = value.match(/[ÃÂâ€™â€œâ€â€“â€”]/g);
      return m ? m.length : 0;
    };

    return mojibakeScore(repaired) < mojibakeScore(text) ? repaired : text;
  } catch {
    return text;
  }
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
    { regex: /\b(def|class|import|from|return|if|elif|else|for|while|try|except|finally|with|as|yield|async|await|raise|pass|break|continue|lambda|and|or|not|in|is|None|True|False|self|global|nonlocal|assert|del)\b/g, cls: 'text-violet-700' },
    { regex: /\b(int|str|float|bool|list|dict|tuple|set|bytes|type|object|Exception)\b/g, cls: 'text-cyan-700' },
    { regex: /("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g, cls: 'text-emerald-700' },
    { regex: /\b(\d+\.?\d*)\b/g, cls: 'text-amber-700' },
    { regex: /(@\w+)/g, cls: 'text-yellow-700' },
    { regex: /\b(def)\s+(\w+)/g, cls: 'text-blue-700', group: 2 },
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
    { regex: /\b(import|export|from|const|let|var|function|return|if|else|for|while|class|interface|type|enum|extends|implements|new|this|super|async|await|try|catch|finally|throw|typeof|instanceof|void|null|undefined|true|false|default|switch|case|break|continue|yield|of|in|as|is)\b/g, cls: 'text-violet-700' },
    { regex: /\b(string|number|boolean|any|never|unknown|object|Array|Promise|Record|Partial|Required|Omit|Pick)\b/g, cls: 'text-cyan-700' },
    { regex: /(`[^`]*`|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g, cls: 'text-emerald-700' },
    { regex: /\b(\d+\.?\d*)\b/g, cls: 'text-amber-700' },
    { regex: /(\{|\}|\(|\)|\[|\])/g, cls: 'text-zinc-700' },
    { regex: /(=>|\.\.\.)/g, cls: 'text-pink-700' },
  ]);
  parts.push(...tokens);

  if (commentPart) {
    parts.push(<span key="comment" className="text-zinc-500 italic">{commentPart}</span>);
  }
  return parts;
}

function highlightJSON(line: string): React.ReactNode[] {
  const tokens = tokenize(line, [
    { regex: /("(?:[^"\\]|\\.)*")\s*:/g, cls: 'text-sky-700', group: 1 },
    { regex: /:\s*("(?:[^"\\]|\\.)*")/g, cls: 'text-emerald-700', group: 1 },
    { regex: /\b(true|false|null)\b/g, cls: 'text-violet-700' },
    { regex: /\b(-?\d+\.?\d*(?:[eE][+-]?\d+)?)\b/g, cls: 'text-amber-700' },
    { regex: /(\{|\}|\[|\])/g, cls: 'text-zinc-700' },
  ]);
  return tokens;
}

function highlightShell(line: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  if (line.trimStart().startsWith('#')) {
    return [<span key="0" className="text-zinc-500 italic">{line}</span>];
  }
  const tokens = tokenize(line, [
    { regex: /\b(if|then|else|elif|fi|for|do|done|while|until|case|esac|function|return|exit|export|source|alias|unset|local|readonly|shift|set)\b/g, cls: 'text-violet-700' },
    { regex: /(\$\{?\w+\}?|\$\(\w+\))/g, cls: 'text-cyan-700' },
    { regex: /("(?:[^"\\]|\\.)*"|'[^']*')/g, cls: 'text-emerald-700' },
    { regex: /(\||\||&&|>>|>|<|;)/g, cls: 'text-pink-700' },
  ]);
  parts.push(...tokens);
  return parts;
}

function highlightYaml(line: string): React.ReactNode[] {
  if (line.trimStart().startsWith('#')) {
    return [<span key="0" className="text-zinc-500 italic">{line}</span>];
  }
  const tokens = tokenize(line, [
    { regex: /^(\s*[\w.-]+)(:)/gm, cls: 'text-sky-700', group: 1 },
    { regex: /\b(true|false|null|yes|no)\b/gi, cls: 'text-violet-700' },
    { regex: /("(?:[^"\\]|\\.)*"|'[^']*')/g, cls: 'text-emerald-700' },
    { regex: /\b(\d+\.?\d*)\b/g, cls: 'text-amber-700' },
  ]);
  return tokens;
}

function highlightMarkdown(line: string): React.ReactNode[] {
  // Headings
  if (/^#{1,6}\s/.test(line)) {
    return [<span key="0" className="text-sky-700 font-bold">{line}</span>];
  }
  // Blockquote
  if (/^\s*>/.test(line)) {
    return [<span key="0" className="text-zinc-700 italic border-l-2 border-zinc-400 pl-2">{line}</span>];
  }
  // List items
  if (/^\s*[-*+]\s/.test(line) || /^\s*\d+\.\s/.test(line)) {
    return [<span key="0" className="text-foreground/90">{line}</span>];
  }
  // Code fences
  if (/^```/.test(line)) {
    return [<span key="0" className="text-emerald-700">{line}</span>];
  }
  // Bold/italic inline
  const tokens = tokenize(line, [
    { regex: /(\*\*[^*]+\*\*|__[^_]+__)/g, cls: 'text-foreground font-bold' },
    { regex: /(\*[^*]+\*|_[^_]+_)/g, cls: 'text-foreground italic' },
    { regex: /(`[^`]+`)/g, cls: 'text-emerald-700 bg-emerald-100 rounded px-0.5' },
    { regex: /(\[([^\]]+)\]\([^)]+\))/g, cls: 'text-blue-700 underline' },
  ]);
  return tokens;
}

function highlightCSS(line: string): React.ReactNode[] {
  const tokens = tokenize(line, [
    { regex: /(\/\*[\s\S]*?\*\/)/g, cls: 'text-zinc-500 italic' },
    { regex: /([.#][\w-]+)/g, cls: 'text-sky-700' },
    { regex: /([\w-]+)\s*:/g, cls: 'text-violet-700', group: 1 },
    { regex: /:\s*([^;{]+)/g, cls: 'text-emerald-700', group: 1 },
    { regex: /\b(\d+\.?\d*(px|rem|em|%|vh|vw|s|ms)?)\b/g, cls: 'text-amber-700' },
  ]);
  return tokens;
}

function highlightHTML(line: string): React.ReactNode[] {
  const tokens = tokenize(line, [
    { regex: /(<!--[\s\S]*?-->)/g, cls: 'text-zinc-500 italic' },
    { regex: /(<\/?[\w-]+)/g, cls: 'text-pink-700' },
    { regex: /(\s)([\w-]+)(=)/g, cls: 'text-sky-700', group: 2 },
    { regex: /("(?:[^"\\]|\\.)*"|'[^']*')/g, cls: 'text-emerald-700' },
    { regex: /(>|<|\/>)/g, cls: 'text-pink-700' },
  ]);
  return tokens;
}

function highlightSQL(line: string): React.ReactNode[] {
  if (line.trimStart().startsWith('--')) {
    return [<span key="0" className="text-zinc-500 italic">{line}</span>];
  }
  const tokens = tokenize(line, [
    { regex: /\b(SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|ON|AND|OR|NOT|INSERT|INTO|VALUES|UPDATE|SET|DELETE|CREATE|TABLE|ALTER|DROP|INDEX|GROUP|BY|ORDER|HAVING|LIMIT|OFFSET|AS|DISTINCT|UNION|ALL|EXISTS|IN|BETWEEN|LIKE|IS|NULL|CASE|WHEN|THEN|ELSE|END|BEGIN|COMMIT|ROLLBACK)\b/gi, cls: 'text-violet-700 uppercase' },
    { regex: /\b(INT|VARCHAR|TEXT|BOOLEAN|DATE|TIMESTAMP|SERIAL|BIGINT|FLOAT|DECIMAL|UUID)\b/gi, cls: 'text-cyan-700' },
    { regex: /('(?:[^'\\]|\\.)*')/g, cls: 'text-emerald-700' },
    { regex: /\b(\d+\.?\d*)\b/g, cls: 'text-amber-700' },
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

function parseSimpleYaml(content: string): { ok: boolean; value?: unknown; error?: string } {
  try {
    const lines = content.split('\n');
    const root: Record<string, unknown> = {};
    const stack: Array<{ indent: number; obj: Record<string, unknown> }> = [{ indent: -1, obj: root }];

    for (const raw of lines) {
      if (!raw.trim() || raw.trim().startsWith('#')) continue;
      const indent = raw.length - raw.trimStart().length;
      const line = raw.trim();
      const sep = line.indexOf(':');
      if (sep < 0) continue;
      const key = line.slice(0, sep).trim();
      const valRaw = line.slice(sep + 1).trim();

      while (stack.length > 1 && indent <= stack[stack.length - 1].indent) {
        stack.pop();
      }
      const parent = stack[stack.length - 1].obj;

      if (!valRaw) {
        parent[key] = {};
        stack.push({ indent, obj: parent[key] as Record<string, unknown> });
      } else if (valRaw === 'true' || valRaw === 'false') {
        parent[key] = valRaw === 'true';
      } else if (valRaw === 'null') {
        parent[key] = null;
      } else if (!Number.isNaN(Number(valRaw)) && valRaw !== '') {
        parent[key] = Number(valRaw);
      } else {
        parent[key] = valRaw.replace(/^['\"]|['\"]$/g, '');
      }
    }

    return { ok: true, value: root };
  } catch (error) {
    return { ok: false, error: String(error) };
  }
}

function parseXmlToObject(content: string): { ok: boolean; value?: unknown; error?: string } {
  try {
    const parser = new DOMParser();
    const xmlDoc = parser.parseFromString(content, 'application/xml');
    const parseError = xmlDoc.querySelector('parsererror');
    if (parseError) {
      return { ok: false, error: parseError.textContent || 'Invalid XML' };
    }

    const toObject = (node: Element): unknown => {
      const children = Array.from(node.children);
      const attrs = Array.from(node.attributes);
      const text = node.childNodes.length === 1 && node.childNodes[0].nodeType === Node.TEXT_NODE
        ? node.textContent?.trim() || ''
        : '';

      if (!children.length && !attrs.length) return text;

      const obj: Record<string, unknown> = {};
      if (attrs.length) {
        obj['@attributes'] = Object.fromEntries(attrs.map((a) => [a.name, a.value]));
      }
      for (const child of children) {
        const childValue = toObject(child);
        if (obj[child.tagName] === undefined) {
          obj[child.tagName] = childValue;
        } else if (Array.isArray(obj[child.tagName])) {
          (obj[child.tagName] as unknown[]).push(childValue);
        } else {
          obj[child.tagName] = [obj[child.tagName], childValue];
        }
      }
      if (text) obj['#text'] = text;
      return obj;
    };

    return { ok: true, value: { [xmlDoc.documentElement.tagName]: toObject(xmlDoc.documentElement) } };
  } catch (error) {
    return { ok: false, error: String(error) };
  }
}

function StructuredNode({ label, value, depth = 0 }: { label?: string; value: unknown; depth?: number }) {
  const [open, setOpen] = useState(depth < 2);
  const isObject = value !== null && typeof value === 'object';
  const isArray = Array.isArray(value);

  if (!isObject) {
    const shown = typeof value === 'string' ? `"${value}"` : String(value);
    const cls = value === null
      ? 'text-violet-700'
      : typeof value === 'number'
      ? 'text-amber-700'
      : typeof value === 'boolean'
      ? 'text-blue-700'
      : 'text-emerald-700';

    return (
      <div className="font-mono text-xs leading-5" style={{ paddingLeft: `${depth * 16}px` }}>
        {label && <span className="text-sky-700">"{label}"</span>}
        {label && <span className="text-muted-foreground">: </span>}
        <span className={cls}>{shown}</span>
      </div>
    );
  }

  const entries = isArray ? (value as unknown[]) : Object.entries(value as Record<string, unknown>);

  return (
    <div className="font-mono text-xs leading-5" style={{ paddingLeft: `${depth * 16}px` }}>
      <button
        type="button"
        className="flex items-center gap-1 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand rounded"
        onClick={() => setOpen((prev) => !prev)}
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        {label && <span className="text-sky-700">"{label}"</span>}
        {label && <span>: </span>}
        <span>{isArray ? `[${entries.length}]` : `{${entries.length}}`}</span>
      </button>

      {open && (
        <div className="border-l border-border ml-1.5 pl-1.5">
          {isArray
            ? (entries as unknown[]).map((v, i) => <StructuredNode key={i} label={String(i)} value={v} depth={0} />)
            : (entries as [string, unknown][]).map(([k, v]) => <StructuredNode key={k} label={k} value={v} depth={0} />)}
        </div>
      )}
    </div>
  );
}

function AdvancedStructuredViewer({ content, language, theme, isDarkMode }: { content: string; language: string; theme: ViewerTheme; isDarkMode: boolean }) {
  const style = VIEWER_THEME_STYLES[theme][isDarkMode ? 'dark' : 'light'];
  const parsed = useMemo(() => {
    if (language === 'json') {
      try {
        return { ok: true, value: JSON.parse(content) };
      } catch (error) {
        return { ok: false, error: String(error) };
      }
    }
    if (language === 'xml') return parseXmlToObject(content);
    return parseSimpleYaml(content);
  }, [content, language]);

  return (
    <div className={cn('flex-1 overflow-auto px-5 py-4', style.bg)}>
      <div className="mb-3 flex items-center gap-2 text-xs">
        {parsed.ok ? (
          <span className="inline-flex items-center gap-1 rounded border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-emerald-700">
            <Check size={12} /> Valid {language.toUpperCase()}
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 rounded border border-red-200 bg-red-50 px-2 py-0.5 text-red-700">
            <Info size={12} /> Invalid {language.toUpperCase()}
          </span>
        )}
      </div>

      {parsed.ok ? (
        <StructuredNode value={parsed.value} />
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-red-700">{parsed.error}</p>
          <pre className="overflow-auto rounded border border-red-200 bg-red-50 p-3 font-mono text-xs text-red-700">{content}</pre>
        </div>
      )}
    </div>
  );
}

function AdvancedLogViewer({ content, theme, isDarkMode }: { content: string; theme: ViewerTheme; isDarkMode: boolean }) {
  const style = VIEWER_THEME_STYLES[theme][isDarkMode ? 'dark' : 'light'];
  const [filter, setFilter] = useState<'all' | 'error' | 'warn' | 'info'>('all');
  const [query, setQuery] = useState('');
  const lines = useMemo(
    () => content.split('\n').map((text, index) => {
      const upper = text.toUpperCase();
      const level = upper.includes('ERROR') || upper.includes('CRITICAL') || upper.includes('FAIL')
        ? 'error'
        : upper.includes('WARN')
        ? 'warn'
        : upper.includes('INFO')
        ? 'info'
        : 'normal';
      return { index, text, level };
    }),
    [content],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return lines.filter((line) => {
      const matchesFilter = filter === 'all' ? true : line.level === filter;
      const matchesQuery = !q || line.text.toLowerCase().includes(q);
      return matchesFilter && matchesQuery;
    });
  }, [lines, filter, query]);

  return (
    <div className={cn('flex-1 overflow-hidden', style.bg)}>
      <div className={cn('sticky top-0 z-10 flex items-center justify-between gap-3 border-b px-4 py-2', style.header, style.border)}>
        <div className="flex items-center gap-1">
          {(['all', 'error', 'warn', 'info'] as const).map((k) => (
            <Button key={k} size="sm" variant="outline" onClick={() => setFilter(k)} className={cn('h-7 text-xs', filter === k && 'bg-accent')}>
              {k}
            </Button>
          ))}
        </div>
        <div className="relative w-52">
          <Search size={12} className="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search logs" className="h-7 pl-6 pr-7 text-xs" />
          {query && (
            <button
              onClick={() => setQuery('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors p-0.5 rounded hover:bg-muted"
              aria-label="Clear search"
            >
              <X size={14} />
            </button>
          )}
        </div>
      </div>
      <div className="h-full overflow-auto px-4 py-3 font-mono text-xs leading-5">
        {filtered.map((line) => (
          <div
            key={`${line.index}-${line.text.length}`}
            className={cn(
              'flex gap-3 border-b border-border/50 py-0.5',
              line.level === 'error' && (isDarkMode ? 'bg-red-950/30 text-red-300' : 'bg-red-50 text-red-700'),
              line.level === 'warn' && (isDarkMode ? 'bg-amber-950/30 text-amber-300' : 'bg-amber-50 text-amber-700'),
              line.level === 'info' && (isDarkMode ? 'bg-blue-950/30 text-blue-300' : 'bg-blue-50 text-blue-700'),
            )}
          >
            <span className="w-12 select-none text-right text-muted-foreground">{line.index + 1}</span>
            <span className="whitespace-pre-wrap break-all">{line.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function renderInlineMarkdown(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  let pos = 0;
  const regex = /(\*\*([^*]+)\*\*|`([^`]+)`|\[([^\]]+)\]\(([^)]+)\)|\*([^*]+)\*)/g;
  let m: RegExpExecArray | null;
  while ((m = regex.exec(text)) !== null) {
    if (m.index > pos) parts.push(text.slice(pos, m.index));
    if (m[2]) parts.push(<strong key={`b-${m.index}`} className="font-semibold">{m[2]}</strong>);
    else if (m[3]) parts.push(<code key={`c-${m.index}`} className="rounded bg-muted px-1 py-0.5 font-mono text-[0.9em]">{m[3]}</code>);
    else if (m[4] && m[5]) parts.push(<a key={`l-${m.index}`} className="text-blue-700 underline dark:text-blue-300" href={m[5]} target="_blank" rel="noreferrer">{m[4]}</a>);
    else if (m[6]) parts.push(<em key={`i-${m.index}`} className="italic">{m[6]}</em>);
    pos = m.index + m[0].length;
  }
  if (pos < text.length) parts.push(text.slice(pos));
  return parts;
}

function AdvancedMarkdownViewer({ content, theme, isDarkMode }: { content: string; theme: ViewerTheme; isDarkMode: boolean }) {
  const lines = useMemo(() => content.split('\n'), [content]);
  const style = VIEWER_THEME_STYLES[theme][isDarkMode ? 'dark' : 'light'];
  const markdownStyle = MARKDOWN_THEME_STYLES[theme][isDarkMode ? 'dark' : 'light'];

  const blocks = useMemo(() => {
    const out: React.ReactNode[] = [];
    let idx = 0;

    while (idx < lines.length) {
      const line = lines[idx];

      if (/^\s*<\/?script\b/i.test(line)) {
        out.push(
          <pre key={`script-${idx}`} className="rounded border border-amber-200 bg-amber-50 px-2 py-1 font-mono text-xs text-amber-800">
            {line}
          </pre>
        );
        idx++;
        continue;
      }

      if (/^\s*</.test(line) && !/^\s*```/.test(line) && !/^\s*<\/?script\b/i.test(line)) {
        const htmlLines: string[] = [line];
        idx++;
        while (idx < lines.length && /^\s*</.test(lines[idx]) && !/^\s*<\/?script\b/i.test(lines[idx])) {
          htmlLines.push(lines[idx]);
          idx++;
        }
        const safeHtml = htmlLines.join('\n').replace(/<script[\s\S]*?<\/script>/gi, '');
        out.push(
          <div
            key={`html-${idx}`}
            className={cn('my-2', isDarkMode && 'text-[#c9d1d9]')}
            dangerouslySetInnerHTML={{ __html: safeHtml }}
          />
        );
        continue;
      }

      if (/^\s*```/.test(line)) {
        const language = line.trim().slice(3).trim() || 'text';
        const codeLines: string[] = [];
        idx++;
        while (idx < lines.length && !/^\s*```/.test(lines[idx])) {
          codeLines.push(lines[idx]);
          idx++;
        }
        if (idx < lines.length) idx++;

        out.push(
          <div key={`code-${idx}`} className={cn('my-4 overflow-hidden rounded border', markdownStyle.codeWrap)}>
            <div className={cn('px-3 py-1.5 font-mono text-xs', markdownStyle.codeHead)}>{language}</div>
            <pre className={cn('overflow-auto px-3 py-2 font-mono text-xs leading-6', style.text)}>
              {codeLines.map((codeLine, i) => (
                <div key={i}>{highlightLine(codeLine, language)}</div>
              ))}
            </pre>
          </div>
        );
        continue;
      }

      if (/^\|.*\|$/.test(line)) {
        if (/^\|\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?$/.test(line)) {
          idx++;
          continue;
        }
        const cells = line.split('|').slice(1, -1).map((v) => v.trim());
        out.push(
          <div key={`table-${idx}`} className={cn('my-1 grid gap-2 rounded border px-2 py-1', markdownStyle.table)} style={{ gridTemplateColumns: `repeat(${cells.length || 1}, minmax(0, 1fr))` }}>
            {cells.map((cell, cellIdx) => <span key={cellIdx} className="text-xs font-medium">{cell}</span>)}
          </div>
        );
        idx++;
        continue;
      }

      if (/^#{1,6}\s/.test(line)) {
        const level = line.match(/^#+/)?.[0].length || 1;
        const text = line.replace(/^#+\s+/, '');
        const cls = level === 1 ? 'text-4xl font-bold my-5' : level === 2 ? 'text-3xl font-bold my-4' : 'text-2xl font-semibold my-3';
        out.push(<div key={`h-${idx}`} className={cls}>{renderInlineMarkdown(text)}</div>);
        idx++;
        continue;
      }

      if (/^\s*>/.test(line)) {
        out.push(
          <blockquote key={`q-${idx}`} className={cn('border-l-4 px-3 py-1.5 italic', markdownStyle.quote)}>
            {renderInlineMarkdown(line.replace(/^\s*>\s*/, ''))}
          </blockquote>
        );
        idx++;
        continue;
      }

      if (/^\s*[-*+]\s/.test(line) || /^\s*\d+\.\s/.test(line)) {
        out.push(<div key={`li-${idx}`} className="font-medium text-foreground">{renderInlineMarkdown(line)}</div>);
        idx++;
        continue;
      }

      if (!line.trim()) {
        out.push(<div key={`sp-${idx}`} className="h-4" />);
        idx++;
        continue;
      }

      out.push(<p key={`txt-${idx}`} className="leading-7 text-foreground/90">{renderInlineMarkdown(line)}</p>);
      idx++;
    }

    return out;
  }, [lines, markdownStyle, isDarkMode, style.text]);

  return (
    <div className={cn('flex-1 overflow-auto px-8 py-6', style.bg)}>
      <article className={cn('prose prose-sm max-w-4xl', isDarkMode ? 'prose-invert text-[#e5e7eb]' : 'text-[#1f2937]')}>
        {blocks}
      </article>
    </div>
  );
}

type AdvancedCodeViewerProps = {
  content: string;
  language: string;
  theme: ViewerTheme;
  isDarkMode: boolean;
  matchLines: number[];
  activeMatchLine: number | null;
  wordWrap: boolean;
  showLineNumbers: boolean;
  fontSize: number;
};

function AdvancedCodeViewer({
  content,
  language,
  theme,
  isDarkMode,
  matchLines,
  activeMatchLine,
  wordWrap,
  showLineNumbers,
  fontSize,
}: AdvancedCodeViewerProps) {
  const lines = useMemo(() => content.split('\n'), [content]);
  const style = VIEWER_THEME_STYLES[theme][isDarkMode ? 'dark' : 'light'];
  const viewerRef = useRef<HTMLDivElement | null>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const lineHeight = Math.round(fontSize * 1.7);

  const matching = useMemo(() => new Set<number>(matchLines), [matchLines]);

  useEffect(() => {
    const el = viewerRef.current;
    if (!el) return;
    const onScroll = () => setScrollTop(el.scrollTop);
    el.addEventListener('scroll', onScroll, { passive: true });
    return () => el.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    if (activeMatchLine === null) return;
    const el = viewerRef.current;
    if (!el) return;

    // Scroll to position the matched line at the top of the viewport
    // Add a small buffer (40px) below the top for readability
    const bufferTop = 60;
    const targetTop = Math.max(0, activeMatchLine * lineHeight - bufferTop);

    el.scrollTo({ top: targetTop, behavior: 'smooth' });
  }, [activeMatchLine, lineHeight]);

  const viewportHeight = 700;
  const start = Math.max(0, Math.floor(scrollTop / lineHeight) - 40);
  const end = Math.min(lines.length, start + Math.ceil(viewportHeight / lineHeight) + 80);
  const visible = lines.slice(start, end);

  return (
    <div ref={viewerRef} className={cn('flex-1 overflow-auto scrollbar-thin scrollbar-thumb-rounded scrollbar-track-bg', style.bg)}>
      <div style={{ height: `${lines.length * lineHeight}px`, position: 'relative' }}>
        <div style={{ position: 'absolute', top: `${start * lineHeight}px`, left: 0, right: 0 }}>
          {visible.map((line, i) => {
            const lineNo = start + i;
            const highlighted = highlightLine(line, language);
            return (
              <div
                key={lineNo}
                className={cn(
                  'flex items-start',
                  style.lineHover,
                  matching.has(lineNo) && (isDarkMode ? 'bg-amber-500/15' : 'bg-amber-100'),
                  activeMatchLine === lineNo && (isDarkMode ? 'ring-2 ring-amber-300/80 bg-amber-500/25 border-l-2 border-l-amber-300' : 'ring-2 ring-amber-500 bg-amber-200 border-l-2 border-l-amber-600')
                )}
                style={{ minHeight: `${lineHeight}px` }}
              >
                {showLineNumbers && (
                  <div className={cn('sticky left-0 z-10 w-14 border-r px-2 py-1 text-right font-mono text-[11px] select-none', style.lineNumber, style.border)}>
                    {lineNo + 1}
                  </div>
                )}
                <pre
                  className={cn('flex-1 px-3 py-1 font-mono', style.text)}
                  style={{
                    fontSize: `${fontSize}px`,
                    lineHeight: `${lineHeight}px`,
                    whiteSpace: wordWrap ? 'pre-wrap' : 'pre',
                    overflowWrap: wordWrap ? 'anywhere' : 'normal',
                    margin: 0,
                  }}
                >
                  {highlighted}
                </pre>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function BinaryViewer({ path, size, onDownload }: { path: string; size: number; onDownload: () => void }) {
  return (
    <div className="flex flex-1 items-center justify-center bg-white p-6">
      <div className="w-full max-w-md rounded-xl border border-border bg-card p-6 text-center">
        <Shield size={26} className="mx-auto mb-3 text-amber-600" />
        <p className="text-lg font-semibold">Binary file preview is disabled</p>
        <p className="mt-2 text-sm text-muted-foreground">Use download to inspect this file safely in a native tool.</p>
        <p className="mt-3 rounded bg-muted px-3 py-2 text-left font-mono text-xs">
          {path}
          <br />
          {humanFileSize(size)}
        </p>
        <Button className="mt-4" onClick={onDownload}>Download file</Button>
      </div>
    </div>
  );
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
    case 'markdown': case 'md': return 'bg-slate-100 text-slate-700 border-slate-300';
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
  showPath,
  onToggle,
  onClick,
}: {
  node: ExplorerTreeNode;
  depth: number;
  isOpen: boolean;
  isActive: boolean;
  isLoading: boolean;
  showPath?: boolean;
  onToggle: () => void;
  onClick: () => void;
}) {
  const isFolder = node.type === 'folder';
  return (
    <button
      type="button"
      className={cn(
        'group flex w-full gap-1.5 rounded-lg px-2 py-1.5 text-left text-[13px] transition-colors hover:bg-accent/60',
        showPath ? 'items-start py-2' : 'items-center',
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
      <span className="min-w-0 flex-1">
        <span className="block truncate">{node.name}</span>
        {showPath && (
          <span className="block truncate text-[10px] leading-4 text-muted-foreground" title={node.path}>
            {node.path}
          </span>
        )}
      </span>
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
  const token = useRepoSessionToken();

  // Tree state
  const [treeByPath, setTreeByPath] = useState<Record<string, ExplorerTreeNode[]>>({});
  const [openFolders, setOpenFolders] = useState<Set<string>>(new Set(['']));
  const [loadingPath, setLoadingPath] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [searchIndexNodes, setSearchIndexNodes] = useState<ExplorerTreeNode[]>([]);
  const [searchIndexBuilt, setSearchIndexBuilt] = useState(false);
  const [isRepoSearchIndexing, setIsRepoSearchIndexing] = useState(false);

  // File viewer state
  const [activeFile, setActiveFile] = useState<ExplorerFileDetails | null>(null);
  const [activeFilePath, setActiveFilePath] = useState<string>('');
  const viewerTheme: ViewerTheme = 'github';
  const [viewerSearch, setViewerSearch] = useState('');
  const [searchMatchIndex, setSearchMatchIndex] = useState(0);
  const wordWrap = false;
  const [showLineNumbers, setShowLineNumbers] = useState(true);
  const [fontSize, setFontSize] = useState(12);
  const [copied, setCopied] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(false);

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

  async function buildRepoSearchIndex() {
    if (!token || isRepoSearchIndexing || searchIndexBuilt) return;
    setIsRepoSearchIndexing(true);
    try {
      const indexedTree: Record<string, ExplorerTreeNode[]> = { ...treeByPath };
      const queue: string[] = [''];
      const visited = new Set<string>();

      while (queue.length > 0) {
        const currentPath = queue.shift() || '';
        if (visited.has(currentPath)) continue;
        visited.add(currentPath);

        let nodes = indexedTree[currentPath];
        if (!nodes) {
          const payload = await getExplorerTree(token, repoId, { path: currentPath, limit: 500 });
          nodes = payload.nodes;
          indexedTree[currentPath] = nodes;
        }

        for (const node of nodes) {
          if (node.type === 'folder' && node.has_children && !visited.has(node.path)) {
            queue.push(node.path);
          }
        }
      }

      const allNodes = Object.values(indexedTree).flat();
      const dedup = new Map<string, ExplorerTreeNode>();
      for (const node of allNodes) {
        dedup.set(node.path, node);
      }

      setTreeByPath((prev) => ({ ...prev, ...indexedTree }));
      setSearchIndexNodes(Array.from(dedup.values()));
      setSearchIndexBuilt(true);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to build search index');
    } finally {
      setIsRepoSearchIndexing(false);
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
    setSearchMatchIndex(0);
    setRibbonReview(null);
    setRibbonFix(null);
    setRibbonTests(null);
    setRibbonHistory('');
    try {
      const details = await getExplorerFile(token, repoId, path);
      setActiveFile({
        ...details,
        content: maybeRepairMojibake(details.content),
      });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to open file');
      setActiveFile(null);
    }
  }

  const allTreeNodes = useMemo(() => Object.values(treeByPath).flat(), [treeByPath]);
  const activeNode = useMemo(() => allTreeNodes.find((n) => n.path === activeFilePath), [allTreeNodes, activeFilePath]);
  const activeLanguage = useMemo(() => {
    if (!activeFile) return 'text';
    return detectLanguage(activeFile.language, activeFile.path);
  }, [activeFile]);
  const viewerMode = useMemo(() => {
    if (!activeFile) return 'text' as ViewerMode;
    return detectViewerMode(activeFile.path, activeLanguage, activeFile.content);
  }, [activeFile, activeLanguage]);

  const searchMatchLines = useMemo(() => {
    if (!activeFile || !viewerSearch.trim()) return [] as number[];
    const q = viewerSearch.toLowerCase();
    return activeFile.content.split('\n').reduce<number[]>((acc, line, idx) => {
      if (line.toLowerCase().includes(q)) acc.push(idx);
      return acc;
    }, []);
  }, [activeFile, viewerSearch]);

  const activeMatchLine = searchMatchLines.length > 0
    ? searchMatchLines[Math.min(searchMatchIndex, searchMatchLines.length - 1)]
    : null;

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'f') {
        event.preventDefault();
        const searchInput = document.getElementById('file-viewer-search') as HTMLInputElement | null;
        searchInput?.focus();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  useEffect(() => {
    const updateDarkMode = () => {
      const root = document.documentElement;
      const darkByClass = root.classList.contains('dark');
      const themeAttr = root.getAttribute('data-theme') || '';
      const darkByAttr = themeAttr.toLowerCase().includes('dark');
      setIsDarkMode(darkByClass || darkByAttr);
    };

    updateDarkMode();
    const observer = new MutationObserver(updateDarkMode);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class', 'data-theme'],
    });
    return () => observer.disconnect();
  }, []);

  async function handleCopyContent() {
    if (!activeFile) return;
    const textToCopy = maybeRepairMojibake(activeFile.content);
    try {
      if (navigator.clipboard?.writeText && window.isSecureContext) {
        await navigator.clipboard.writeText(textToCopy);
      } else {
        const textarea = document.createElement('textarea');
        textarea.value = textToCopy;
        textarea.setAttribute('readonly', 'true');
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
      }
      setCopied(true);
      toast.success('Copied file content');
      window.setTimeout(() => setCopied(false), 1200);
    } catch {
      toast.error('Failed to copy');
    }
  }

  function handleDownload() {
    if (!activeFile) return;
    const blob = new Blob([maybeRepairMojibake(activeFile.content)], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = activeFile.path.split('/').pop() || 'file.txt';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
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

      const testsToRun = discovered.tests.slice(0, 12);
      const normalizedActivePath = activeFilePath.replace(/\\/g, '/');
      const isSelectedTestFile = /(^|\/)tests?\//.test(normalizedActivePath) && /(^|\/)test_[^/]+\.py$/i.test(normalizedActivePath);
      if (isSelectedTestFile && !testsToRun.includes(normalizedActivePath)) {
        testsToRun.unshift(normalizedActivePath);
      }

      if (testsToRun.length === 0) {
        setRibbonTests({
          status: 'skipped',
          tests: [],
          passed: 0,
          failed: 0,
          duration_seconds: 0,
          coverage: null,
          output: 'No impacted tests discovered for this file.',
        });
        toast.message('No tests found for selected file');
        return;
      }

      const run = await runExplorerTests(token, repoId, testsToRun, 55);
      setRibbonTests(run);
      if (run.status === 'failed' && run.passed === 0 && run.failed === 0) {
        toast.error('Test run failed before execution. Open History/output for details.');
      } else {
        toast.success(`${run.status.toUpperCase()}: ${run.passed} passed, ${run.failed} failed`);
      }
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
      setActiveFile({
        ...refreshed,
        content: maybeRepairMojibake(refreshed.content),
      });
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
  const searchableNodes = useMemo(() => {
    const base = searchIndexBuilt ? searchIndexNodes : Object.values(treeByPath).flat();
    const dedup = new Map<string, ExplorerTreeNode>();
    for (const node of base) {
      dedup.set(node.path, node);
    }
    return Array.from(dedup.values());
  }, [searchIndexBuilt, searchIndexNodes, treeByPath]);

  const filteredRoots = useMemo(() => {
    const roots = treeByPath[''] || [];
    if (!search.trim()) return roots;
    const q = search.toLowerCase();
    return searchableNodes
      .filter((n) => n.name.toLowerCase().includes(q) || n.path.toLowerCase().includes(q))
      .sort((a, b) => {
        if (a.type !== b.type) return a.type === 'folder' ? -1 : 1;
        return a.path.localeCompare(b.path);
      })
      .slice(0, 800);
  }, [treeByPath, search, searchableNodes]);

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
            showPath={Boolean(search.trim())}
            onToggle={() => toggleFolder(node.path)}
            onClick={() => openFile(node.path)}
          />
          {isFolder && isOpen && children.length > 0 && renderTree(children, depth + 1)}
        </div>
      );
    });
  }

  return (
    <div className={cn('flex h-[calc(100vh-4rem)] overflow-hidden', isDarkMode && 'bg-[#111827] text-[#e5e7eb]')}>
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
            <FileSearch size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
            <Input
              value={search}
              onChange={(e) => {
                const value = e.target.value;
                setSearch(value);
                if (value.trim() && token && !searchIndexBuilt && !isRepoSearchIndexing) {
                  void buildRepoSearchIndex();
                }
              }}
              placeholder="Search files..."
              className="h-8 pl-8 pr-7 text-xs"
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors p-0.5 rounded hover:bg-muted"
                aria-label="Clear search"
              >
                <X size={14} />
              </button>
            )}
          </div>
        </div>

        {/* Tree */}
        <div className="flex-1 overflow-y-auto overflow-x-hidden py-1 scrollbar-thin scrollbar-thumb-rounded scrollbar-track-bg">
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
          {search.trim()
            ? filteredRoots.map((node) => (
              <TreeNodeItem
                key={`search-${node.path}`}
                node={node}
                depth={0}
                isOpen={openFolders.has(node.path)}
                isActive={activeFilePath === node.path}
                isLoading={loadingPath === node.path}
                showPath
                onToggle={() => toggleFolder(node.path)}
                onClick={() => openFile(node.path)}
              />
            ))
            : renderTree(filteredRoots, 0)}
        </div>
      </aside>

      {/* ─── Main Content: File Viewer ──────────────────────────────────────── */}
      <main className={cn('flex-1 flex flex-col overflow-hidden', isDarkMode ? 'bg-[#111827]' : 'bg-white')}>
        {activeFile ? (
          <>
            {/* File Header Bar */}
            <div className="border-b border-border bg-card/70 px-5 py-3 flex items-center justify-between gap-4 flex-shrink-0">
              <div className="min-w-0">
                <div className="flex items-center gap-2.5">
                  <span className={cn(
                    'inline-flex items-center rounded-md px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider border',
                    langBadgeClass(activeLanguage),
                  )}>
                    {activeLanguage}
                  </span>
                  <p className="text-sm font-semibold truncate text-foreground">{activeFile.path}</p>
                </div>
                <p className="mt-1.5 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                  <span>{activeFile.line_count} lines</span>
                  <span className="text-border">•</span>
                  <span>{activeFile.functions.length} functions</span>
                  <span className="text-border">•</span>
                  <span>{activeFile.classes.length} classes</span>
                  <span className="text-border">•</span>
                  <span>{activeFile.imports.length} imports</span>
                  <span className="text-border">•</span>
                  <span>{humanFileSize(activeFile.size)}</span>
                  <span className="text-border">•</span>
                  <span>.{getFileExtension(activeFile.path) || 'txt'}</span>
                  <span className="text-border">•</span>
                  <span>{activeNode?.modified_at ? new Date(activeNode.modified_at).toLocaleString() : 'Modified: unknown'}</span>
                  <span className="text-border">•</span>
                  <span>UTF-8</span>
                  <span className="text-border">•</span>
                  <span>detected: {activeLanguage}</span>
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

            <div className={cn('sticky top-0 z-20 border-b border-border px-4 py-2 flex flex-wrap items-center gap-2', isDarkMode ? 'bg-[#1f2937]' : 'bg-white')}>
              <div className="relative min-w-[220px] flex-1 max-w-[360px]">
                <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
                <Input
                  id="file-viewer-search"
                  value={viewerSearch}
                  onChange={(e) => {
                    setViewerSearch(e.target.value);
                    setSearchMatchIndex(0);
                  }}
                  onKeyDown={(e) => {
                    if (e.key !== 'Enter') return;
                    e.preventDefault();
                    if (searchMatchLines.length === 0) return;
                    if (e.shiftKey) {
                      setSearchMatchIndex((idx) => (idx - 1 + searchMatchLines.length) % searchMatchLines.length);
                    } else {
                      setSearchMatchIndex((idx) => (idx + 1) % searchMatchLines.length);
                    }
                  }}
                  placeholder="Search in file (Ctrl+F)"
                  className="h-8 pl-6 pr-7 text-xs"
                  aria-label="Search within file"
                />
                {viewerSearch && (
                  <button
                    onClick={() => {
                      setViewerSearch('');
                      setSearchMatchIndex(0);
                      document.getElementById('file-viewer-search')?.focus();
                    }}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors p-0.5 rounded hover:bg-muted"
                    aria-label="Clear search"
                  >
                    <X size={14} />
                  </button>
                )}
              </div>

              <Button
                size="sm"
                variant="outline"
                className="h-8 w-8 p-0"
                aria-label="Previous match"
                onClick={() => setSearchMatchIndex((idx) => (searchMatchLines.length === 0 ? 0 : (idx - 1 + searchMatchLines.length) % searchMatchLines.length))}
                disabled={searchMatchLines.length === 0}
              >
                <ChevronUp size={12} />
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="h-8 w-8 p-0"
                aria-label="Next match"
                onClick={() => setSearchMatchIndex((idx) => (searchMatchLines.length === 0 ? 0 : (idx + 1) % searchMatchLines.length))}
                disabled={searchMatchLines.length === 0}
              >
                <ChevronDown size={12} />
              </Button>
              <span className="w-[82px] text-center text-xs text-muted-foreground">
                {searchMatchLines.length === 0 ? '0 / 0' : `${Math.min(searchMatchIndex + 1, searchMatchLines.length)} / ${searchMatchLines.length}`}
              </span>
              <span className="hidden text-[11px] text-muted-foreground lg:inline">Enter: next, Shift+Enter: prev</span>

              <Button size="sm" variant="outline" className="h-8 text-xs" onClick={() => void handleCopyContent()} aria-label="Copy file content">
                {copied ? <Check size={12} className="mr-1" /> : <Copy size={12} className="mr-1" />} {copied ? 'Copied' : 'Copy'}
              </Button>
              <Button size="sm" variant="outline" className="h-8 text-xs" onClick={handleDownload} aria-label="Download file">
                <Download size={12} className="mr-1" /> Download
              </Button>
              <Button size="sm" variant="outline" className="h-8 text-xs" onClick={() => setShowLineNumbers((prev) => !prev)} aria-label="Toggle line numbers">
                <FileText size={12} className="mr-1" /> {showLineNumbers ? 'Lines On' : 'Lines Off'}
              </Button>
              <Button size="sm" variant="outline" className="h-8 w-8 p-0" onClick={() => setFontSize((s) => Math.max(10, s - 1))} aria-label="Zoom out">
                <Minus size={12} />
              </Button>
              <span className="text-xs tabular-nums text-muted-foreground w-10 text-center">{fontSize}px</span>
              <Button size="sm" variant="outline" className="h-8 w-8 p-0" onClick={() => setFontSize((s) => Math.min(20, s + 1))} aria-label="Zoom in">
                <Plus size={12} />
              </Button>
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
            {viewerMode === 'binary' ? (
              <BinaryViewer path={activeFile.path} size={activeFile.size} onDownload={handleDownload} />
            ) : viewerMode === 'markdown' ? (
              <AdvancedMarkdownViewer content={activeFile.content} theme={viewerTheme} isDarkMode={isDarkMode} />
            ) : viewerMode === 'structured' ? (
              <AdvancedStructuredViewer content={activeFile.content} language={activeLanguage} theme={viewerTheme} isDarkMode={isDarkMode} />
            ) : viewerMode === 'log' ? (
              <AdvancedLogViewer content={activeFile.content} theme={viewerTheme} isDarkMode={isDarkMode} />
            ) : (
              <AdvancedCodeViewer
                content={activeFile.content}
                language={activeLanguage}
                theme={viewerTheme}
                isDarkMode={isDarkMode}
                matchLines={searchMatchLines}
                activeMatchLine={activeMatchLine}
                wordWrap={wordWrap}
                showLineNumbers={showLineNumbers}
                fontSize={fontSize}
              />
            )}
          </>
        ) : (
          /* Empty state */
          <div className="flex-1 flex items-center justify-center bg-white">
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
