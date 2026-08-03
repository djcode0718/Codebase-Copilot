'use client';
/**
 * components/chat/MermaidBlock.tsx
 * Dynamically renders Mermaid diagram code blocks found in AI responses.
 * Falls back to raw code if rendering fails.
 */
import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { GitBranch, Copy, Check, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface MermaidBlockProps {
  code: string;
}

function normalizeMermaidSource(raw: string): string {
  const lines = raw
    .replace(/```mermaid/gi, '')
    .replace(/```/g, '')
    .split(/\r?\n/)
    .map((line) => line.trimEnd())
    .filter((line) => line.trim().length > 0);

  // Drop noisy version banners some models emit.
  const cleaned = lines.filter((line) => !/^mermaid\s+version\b/i.test(line.trim()));
  if (cleaned.length === 0) return 'flowchart TD\nA[No diagram content] --> B[Please retry]';

  const first = cleaned[0].trim();
  const isGraph = /^(graph|flowchart)\b/i.test(first);
  const hasParticipant = cleaned.some((line) => /^participant\s+/i.test(line.trim()));

  // Common model mistake: `graph LR` + `participant` lines.
  // In graph mode, just drop participant declarations and let edge lines define nodes.
  if (isGraph && hasParticipant) {
    const withoutParticipants = cleaned.filter((line) => !/^participant\s+/i.test(line.trim()));
    return withoutParticipants.join('\n');
  }

  // If the model starts with participant lines and no diagram type, convert to sequence.
  if (!isGraph && hasParticipant) {
    return ['sequenceDiagram', ...cleaned].join('\n');
  }

  return cleaned.join('\n');
}

export default function MermaidBlock({ code }: MermaidBlockProps) {
  const uid = useId().replace(/:/g, '');
  const id = `mermaid-${uid}`;
  const [svg, setSvg] = useState<string>('');
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  const normalizedCode = useMemo(() => normalizeMermaidSource(code), [code]);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const normalized = normalizedCode;

    let cancelled = false;
    async function render() {
      try {
        const mermaid = (await import('mermaid')).default;
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: 'loose',
          suppressErrorRendering: true,
          theme: 'dark',
          themeVariables: {
            primaryColor: '#22c55e',
            primaryTextColor: '#f8fafc',
            primaryBorderColor: '#334155',
            lineColor: '#64748b',
            secondaryColor: '#1e293b',
            tertiaryColor: '#0f172a',
            background: '#0f172a',
            mainBkg: '#1e293b',
            nodeBorder: '#334155',
            clusterBkg: '#1e293b',
            titleColor: '#f8fafc',
            edgeLabelBackground: '#1e293b',
            fontFamily: 'ui-monospace, SFMono-Regular, monospace',
          },
        });

        await mermaid.parse(normalized, { suppressErrors: true });
        const { svg: rendered } = await mermaid.render(id, normalized);
        const safeSvg = rendered.replace(/<script[\s\S]*?<\/script>/gi, '');
        if (!cancelled) {
          setError('');
          setSvg(safeSvg);
        }
      } catch (e) {
        if (!cancelled) {
          setSvg('');
          setError(e instanceof Error ? e.message : 'Render failed');
        }
      }
    }
    render();
    return () => { cancelled = true; };
  }, [id, normalizedCode]);

  async function handleCopy() {
    await navigator.clipboard.writeText(normalizedCode || code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="my-3 rounded-xl border border-border overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-secondary/80 border-b border-border">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <GitBranch size={12} className="text-brand" />
          <span className="font-mono font-medium">Architecture Diagram</span>
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
        >
          {copied ? <Check size={11} className="text-brand" /> : <Copy size={11} />}
          {copied ? 'Copied' : 'Copy source'}
        </button>
      </div>

      {/* Diagram or fallback */}
      {error ? (
        <div className="p-3 space-y-2">
          <div className="flex items-center gap-2 text-xs text-amber-400">
            <AlertTriangle size={11} />
            <span>Diagram rendering failed — showing source</span>
          </div>
          <pre className="text-xs font-mono text-muted-foreground overflow-x-auto p-2 bg-background rounded-lg scrollbar-thin">
            {normalizedCode || code}
          </pre>
        </div>
      ) : !svg ? (
        <div className="h-32 bg-background/50 animate-pulse flex items-center justify-center">
          <span className="text-xs text-muted-foreground">Rendering diagram…</span>
        </div>
      ) : (
        <div
          ref={containerRef}
          className={cn('overflow-auto bg-background/70 p-4 flex justify-center')}
          dangerouslySetInnerHTML={{ __html: svg }}
        />
      )}
    </div>
  );
}
