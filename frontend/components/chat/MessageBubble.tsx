'use client';
/**
 * components/chat/MessageBubble.tsx
 * Renders a single chat message — user or assistant.
 * Assistant messages show markdown, Mermaid diagrams, structured intelligence
 * response sections, inline grounding summary, and expandable inspector data.
 */
import { motion } from 'framer-motion';
import { Copy, Check, Cpu, ChevronDown, ChevronRight, Brain, Shield, Layers, Code2, AlertTriangle, Lightbulb, BarChart2, RefreshCcw, Pencil, ThumbsUp, ThumbsDown, GitBranch } from 'lucide-react';
import { useState, lazy, Suspense, useRef, useCallback } from 'react';
import { cn } from '@/lib/utils';
import type { Message, QueryMode, RetrievedFile } from '@/lib/types';

const MermaidBlock = lazy(() => import('@/components/chat/MermaidBlock'));

const MODE_LABELS: Record<QueryMode, string> = {
  code_lookup: 'CODE LOOKUP',
  architectural: 'ARCHITECTURAL',
};
const MODE_COLORS: Record<QueryMode, string> = {
  code_lookup: 'text-brand',
  architectural: 'text-amber-400',
};

// ── Intelligence Section Definitions ─────────────────────────────────────────

interface IntelSection {
  key: string;
  label: string;
  icon: React.ElementType;
  color: string;
}

const INTEL_SECTIONS: IntelSection[] = [
  { key: 'Answer:',               label: 'Answer',                icon: Brain,         color: 'text-brand' },
  { key: 'Architecture View:',    label: 'Architecture View',     icon: Layers,        color: 'text-blue-400' },
  { key: 'Engineering View:',     label: 'Engineering View',      icon: Code2,         color: 'text-violet-400' },
  { key: 'Business View:',        label: 'Business View',         icon: BarChart2,     color: 'text-amber-400' },
  { key: 'Evidence:',             label: 'Evidence',              icon: Lightbulb,     color: 'text-cyan-400' },
  { key: 'Risks:',                label: 'Risks',                 icon: AlertTriangle, color: 'text-red-400' },
  { key: 'Recommendations:',      label: 'Recommendations',       icon: Shield,        color: 'text-green-400' },
  { key: 'Confidence:',           label: 'Confidence',            icon: BarChart2,     color: 'text-muted-foreground' },
];

function parseIntelligenceSections(content: string): { plain: string; sections: { def: IntelSection; content: string }[] } | null {
  // Detect if content has intelligence structured sections
  const hasIntelSections = INTEL_SECTIONS.some((s) =>
    content.includes(`**${s.key}`) || content.includes(`\n${s.key}`) || content.includes(`\n**${s.key}`)
  );
  if (!hasIntelSections) return null;

  const sections: { def: IntelSection; content: string }[] = [];
  const remaining = content;

  for (const def of INTEL_SECTIONS) {
    const patterns = [`**${def.key}**`, `**${def.key}`, `${def.key}`];
    let found = false;
    for (const pattern of patterns) {
      const idx = remaining.indexOf(pattern);
      if (idx !== -1) {
        // Find next section start
        let nextIdx = remaining.length;
        for (const other of INTEL_SECTIONS) {
          if (other.key === def.key) continue;
          for (const op of [`**${other.key}**`, `**${other.key}`, `${other.key}`]) {
            const ni = remaining.indexOf(op, idx + pattern.length);
            if (ni !== -1 && ni < nextIdx) nextIdx = ni;
          }
        }
        const sectionContent = remaining.slice(idx + pattern.length, nextIdx).trim();
        if (sectionContent) {
          sections.push({ def, content: sectionContent });
        }
        found = true;
        break;
      }
    }
    if (found) {
      // remove the processed section from remaining to avoid re-matching
    }
  }

  if (sections.length === 0) return null;
  // plain is content before first section
  const firstSection = INTEL_SECTIONS[0];
  const plainPatterns = [`**${firstSection.key}**`, `**${firstSection.key}`, `${firstSection.key}`];
  let plainEnd = content.length;
  for (const p of plainPatterns) {
    const idx = content.indexOf(p);
    if (idx !== -1 && idx < plainEnd) plainEnd = idx;
  }

  return { plain: content.slice(0, plainEnd).trim(), sections };
}

// ── Section Accordion ─────────────────────────────────────────────────────────

function IntelSectionBlock({ def, content, graphKeys, onOpenGraph }: {
  def: IntelSection;
  content: string;
  graphKeys?: Set<string>;
  onOpenGraph?: (s: string) => void;
}) {
  const [expanded, setExpanded] = useState(true);
  return (
    <div className="rounded-xl border border-border/60 overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-2 bg-secondary/60 hover:bg-secondary/80 transition-colors cursor-pointer text-left"
      >
        <def.icon size={12} className={def.color} />
        <span className={cn('text-xs font-semibold tracking-wide uppercase', def.color)}>{def.label}</span>
        <span className="ml-auto text-muted-foreground">
          {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        </span>
      </button>
      {expanded && (
        <div className="px-3 py-2.5 bg-background/50 text-foreground">
          <SimpleMarkdown content={content} graphKeys={graphKeys} onOpenGraph={onOpenGraph} />
        </div>
      )}
    </div>
  );
}


interface MessageBubbleProps {
  message: Message;
  onInspect?: () => void;
  isInspected?: boolean;
  index: number;
  onTryAgain?: () => void;
  onEdit?: () => void;
  actionsDisabled?: boolean;
  /** Cached set of graph-eligible symbol keys (from useGraphCache) */
  graphKeys?: Set<string>;
  /** Called when user clicks "See graph" on an inline code tag */
  onOpenGraph?: (symbol: string) => void;
  onSuggestion?: (query: string, displayText?: string, isCtaFollowup?: boolean) => void;
  previousUserQuery?: string;
  onOpenEvidence?: (file: RetrievedFile) => void;
}

function evidenceAnchorLabel(file: RetrievedFile): string {
  const fileName = file.path.split('/').pop() || file.path;
  if (file.line_start && file.line_end && file.line_end !== file.line_start) {
    return `${fileName}:L${file.line_start}-L${file.line_end}`;
  }
  if (file.line_start) {
    return `${fileName}:L${file.line_start}`;
  }
  return fileName;
}

const INTELLIGENCE_PROMPTS: Record<string, string> = {
  architecture_map: 'Generate a comprehensive repository executive summary. Include: architecture style (monolith/microservices/etc), tech stack, service map, component relationships, data flow, and a Mermaid diagram of the architecture. Provide confidence level. Use exactly one valid Mermaid `flowchart TD` fenced block and do not mix graph syntax with participant declarations.',
  security_review: 'Conduct a best-practices security code review. Evaluate defensive programming patterns, input validation, secure credential storage, API robust design, and dependency management. For any areas of concern, suggest remediation: Severity (Critical/High/Medium/Low), Potential Impact, Potential Risk, and Recommendations for hardening code with file references.',
  business_flows: 'Discover all business capabilities and workflows in this repository. For each workflow provide: Purpose, Entry Point, Services Involved, Data Sources, Events, Dependencies, Exit Point, and Business Value. Generate a workflow summary for each capability found.',
  code_quality: 'Evaluate code quality across this repository. Assess: Maintainability, Readability, Scalability, Modularity, Performance, Reliability. Detect: Dead Code, Duplicate Logic, Large Functions, Anti-Patterns, Excessive Complexity. Generate a Quality Score (0-100) and an actionable remediation plan.',
  impact_analysis: 'Perform a comprehensive impact analysis. Identify the most critical components where changes would have the highest blast radius. For each critical area, list: Affected Files, Affected APIs, Affected Services, Affected Tests, Risk Level (Low/Medium/High/Critical), and reasoning.',
  test_intelligence: 'Analyze test coverage intelligence. Identify: Coverage Gaps, Untested Critical Logic, Missing Edge Cases, High Risk Untested Areas. Suggest specific missing unit tests, integration tests, and performance test scenarios with example test names and what they should verify.',
  onboarding_guide: 'Generate a comprehensive developer onboarding plan for a new Full Stack Engineer. Provide: 30-Minute Quick Understanding, 1-Day Deep Dive Plan, 1-Week Competency Plan, 30-Day Mastery Plan. Identify Critical Modules, Learning Path, Core Systems, and High Value areas to focus on.',
  api_documentation: 'Generate comprehensive API documentation for all endpoints in this repository. For each endpoint provide: Path, Method, Purpose, Request Schema, Response Schema, Authentication, Error Codes, Example Usage, and Business Context. Format as structured documentation.',
  dependency_graph: 'Analyze all module and service dependencies. Generate a dependency map showing: External Libraries, Internal Module Coupling, Circular Dependencies, High-Fan-Out Modules, Critical Path Dependencies. Create a Mermaid dependency graph. Identify risky or outdated dependencies.',
  engineering_report: 'Generate an Engineering Manager Report. Include: Executive Summary, Repository Health Assessment, Technical Debt Report, Risk Assessment, Ownership Insights, Dependency Risks, Productivity Hotspots, Refactoring Opportunities. Provide both Technical View and Business View.',
  tech_debt_scan: 'Identify all technical debt in this repository. Categorize by: Type (Design Debt, Code Debt, Test Debt, Documentation Debt, Infrastructure Debt), Severity (Critical/High/Medium/Low), Estimated Effort to Fix, Business Impact. Generate a prioritized remediation roadmap.',
  digital_twin: 'Build a Repository Digital Twin model that combines Repository Chat, Architecture Intelligence, Knowledge Graph reasoning, Business Flow Discovery, Code Validation, Live Visualization, and Conversation Export. Map all: Services, Modules, APIs, Databases, External Integrations, and Event Flows. Include one valid Mermaid `flowchart TD` diagram with confidence level and evidence references.',
};

const INTELLIGENCE_LABELS: Record<string, string> = {
  architecture_map: 'Run Architecture Map',
  security_review: 'Run Security Review',
  business_flows: 'Run Business Flows',
  code_quality: 'Run Code Quality',
  impact_analysis: 'Run Impact Analysis',
  test_intelligence: 'Run Test Intelligence',
  onboarding_guide: 'Run Onboarding Guide',
  api_documentation: 'Run API Documentation',
  dependency_graph: 'Run Dependency Graph',
  engineering_report: 'Run Engineering Report',
  tech_debt_scan: 'Run Tech Debt Scan',
  digital_twin: 'Run Digital Twin',
};

type SuggestedActionPayload = { suggested_action: string; message: string };

function parseSuggestedActionPayload(content: string, isUser: boolean): SuggestedActionPayload | null {
  if (isUser || !content.trim().startsWith('{')) return null;
  try {
    const parsed = JSON.parse(content.trim());
    if (parsed && typeof parsed === 'object' && typeof parsed.suggested_action === 'string') {
      return parsed as SuggestedActionPayload;
    }
  } catch {
    // Ignore non-JSON content.
  }
  return null;
}

function buildSuggestedActionPrompt(
  suggestedAction: SuggestedActionPayload,
  previousUserQuery?: string,
): { composedPrompt: string; shortLabel: string } {
  const actionKey = suggestedAction.suggested_action;
  const actionLabel = INTELLIGENCE_LABELS[actionKey] || 'Analysis';
  const existingInstructions = INTELLIGENCE_PROMPTS[actionKey] || suggestedAction.message;
  const shortLabel = INTELLIGENCE_LABELS[actionKey] || 'Run Action';

  if (!previousUserQuery) {
    return { composedPrompt: existingInstructions, shortLabel };
  }

  return {
    composedPrompt:
      `The user specifically asked: '${previousUserQuery}' As part of this ${actionLabel} analysis, ` +
      'first explicitly identify which SINGLE file or component is the most relevant to their question, ' +
      `with your reasoning, then provide: ${existingInstructions}`,
    shortLabel,
  };
}

async function copyTextSafely(text: string): Promise<boolean> {
  try {
    if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
    if (typeof document !== 'undefined') {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.setAttribute('readonly', 'true');
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      return true;
    }
  } catch {
    return false;
  }
  return false;
}

function AssistantContent({
  message,
  intelParsed,
  suggestedAction,
  graphKeys,
  onOpenGraph,
  onSuggestion,
  previousUserQuery,
  actionsDisabled,
  onOpenEvidence,
  onInspect,
  isInspected,
}: {
  message: Message;
  intelParsed: { plain: string; sections: { def: IntelSection; content: string }[] } | null;
  suggestedAction: SuggestedActionPayload | null;
  graphKeys?: Set<string>;
  onOpenGraph?: (symbol: string) => void;
  onSuggestion?: (query: string, displayText?: string, isCtaFollowup?: boolean) => void;
  previousUserQuery?: string;
  actionsDisabled: boolean;
  onOpenEvidence?: (file: RetrievedFile) => void;
  onInspect?: () => void;
  isInspected?: boolean;
}) {
  return (
    <div className="space-y-2 rounded-2xl border border-border bg-card/70 p-4 shadow-sm shadow-black/5">
      {intelParsed ? (
        <div className="space-y-2">
          {intelParsed.plain && (
            <div className="text-foreground">
              <SimpleMarkdown content={intelParsed.plain} graphKeys={graphKeys} onOpenGraph={onOpenGraph} />
            </div>
          )}
          {intelParsed.sections.map((s) => (
            <IntelSectionBlock key={s.def.key} def={s.def} content={s.content} graphKeys={graphKeys} onOpenGraph={onOpenGraph} />
          ))}
        </div>
      ) : suggestedAction ? (
        <div className="text-foreground">
          <SimpleMarkdown content={suggestedAction.message} graphKeys={graphKeys} onOpenGraph={onOpenGraph} />
          {onSuggestion && (
            <div className="mt-3">
              <button
                type="button"
                onClick={() => {
                  const { composedPrompt, shortLabel } = buildSuggestedActionPrompt(suggestedAction, previousUserQuery);
                  onSuggestion(composedPrompt, shortLabel, true);
                }}
                disabled={actionsDisabled}
                className="inline-flex h-8 items-center gap-1.5 rounded-md border border-brand/30 bg-background/50 px-3 text-xs font-semibold text-brand transition-all cursor-pointer hover:bg-brand/5 hover:border-brand/50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <GitBranch size={13} />
                {INTELLIGENCE_LABELS[suggestedAction.suggested_action] || 'Run Action'}
              </button>
            </div>
          )}
        </div>
      ) : (
        <div className="text-foreground">
          <SimpleMarkdown content={message.content} graphKeys={graphKeys} onOpenGraph={onOpenGraph} />
        </div>
      )}

      {(message.query_mode || message.retrieved_files?.length || message.latency_ms) && (
        <div className="flex items-center gap-3 text-xs text-muted-foreground flex-wrap pt-1 border-t border-border/60">
          {message.query_mode && (
            <span className={cn('font-mono font-semibold tracking-wide', MODE_COLORS[message.query_mode])}>
              {MODE_LABELS[message.query_mode]}
            </span>
          )}
          {message.retrieved_files && message.retrieved_files.length > 0 && (
            <div className="inline-flex flex-wrap items-center gap-1.5">
              <span>{message.retrieved_files.length} chunks</span>
              {message.retrieved_files.slice(0, 3).map((file, idx) => (
                <button
                  key={`${file.path}-${idx}`}
                  type="button"
                  className="rounded-full border border-border/80 bg-background px-2 py-0.5 text-[11px] hover:border-brand/30 hover:text-brand"
                  onClick={() => onOpenEvidence?.(file)}
                  disabled={!onOpenEvidence}
                  title={file.path}
                >
                  {evidenceAnchorLabel(file)}
                </button>
              ))}
            </div>
          )}
          {message.latency_ms && <span>{message.latency_ms}ms</span>}
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
  );
}

// ── Inline code tag with optional hover "See graph" popover ───────────────

function InlineCodeTag({
  text,
  graphKeys,
  onOpenGraph,
}: {
  text: string;
  graphKeys?: Set<string>;
  onOpenGraph?: (symbol: string) => void;
}) {
  const [popoverVisible, setPopoverVisible] = useState(false);
  const hideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const isGraphEligible = !!graphKeys && graphKeys.size > 0 && graphKeys.has(text);

  const showPopover = useCallback(() => {
    if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
    if (isGraphEligible) setPopoverVisible(true);
  }, [isGraphEligible]);

  const scheduleHide = useCallback(() => {
    hideTimerRef.current = setTimeout(() => setPopoverVisible(false), 150);
  }, []);

  const cancelHide = useCallback(() => {
    if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
  }, []);

  return (
    <span className="relative inline-block">
      <code
        className="font-code text-brand text-xs bg-background border border-border px-1.5 py-0.5 rounded"
        style={isGraphEligible ? { cursor: 'pointer' } : undefined}
        onMouseEnter={showPopover}
        onMouseLeave={scheduleHide}
      >
        {text}
      </code>
      {isGraphEligible && popoverVisible && (
        <span
          className="absolute bottom-full left-1/2 z-30 mb-1.5 -translate-x-1/2 rounded-xl border border-border bg-card shadow-lg px-2 py-1.5 flex items-center gap-1.5 whitespace-nowrap"
          onMouseEnter={cancelHide}
          onMouseLeave={scheduleHide}
          style={{ boxShadow: '0 4px 16px color-mix(in oklab, var(--background) 30%, transparent)' }}
        >
          <button
            type="button"
            onClick={() => {
              setPopoverVisible(false);
              onOpenGraph?.(text);
            }}
            className="flex items-center gap-1 rounded-lg bg-brand/10 border border-brand/20 px-2 py-0.5 text-[10px] font-medium text-brand transition-colors hover:bg-brand/20 cursor-pointer"
          >
            <GitBranch size={10} />
            See graph
          </button>
        </span>
      )}
    </span>
  );
}

function SimpleMarkdown({ content, graphKeys, onOpenGraph }: { content: string; graphKeys?: Set<string>; onOpenGraph?: (s: string) => void }) {
  const lines = content.split('\n');
  const elements: React.ReactNode[] = [];
  let i = 0;

  function parseTableRow(row: string): string[] {
    const normalized = row.trim().replace(/^\|/, '').replace(/\|$/, '');
    return normalized.split('|').map((c) => c.trim());
  }

  function isTableDivider(row: string): boolean {
    const normalized = row.trim().replace(/^\|/, '').replace(/\|$/, '');
    const cells = normalized.split('|').map((c) => c.trim());
    return cells.length > 0 && cells.every((c) => /^:?-{3,}:?$/.test(c));
  }

  while (i < lines.length) {
    const line = lines[i];

    // Mermaid fenced code block
    if (line.startsWith('```mermaid')) {
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith('```')) {
        codeLines.push(lines[i]);
        i++;
      }
      const mermaidCode = codeLines.join('\n');
      elements.push(
        <Suspense key={`mermaid-${i}`} fallback={<div className="h-24 bg-muted/40 rounded-xl animate-pulse flex items-center justify-center text-xs text-muted-foreground">Loading diagram…</div>}>
          <MermaidBlock code={mermaidCode} />
        </Suspense>
      );
      i++;
      continue;
    }

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

    const nextLine = i + 1 < lines.length ? lines[i + 1] : '';
    const isTableHeader = line.includes('|') && isTableDivider(nextLine);

    if (isTableHeader) {
      const headers = parseTableRow(line);
      i += 2; // Skip header + divider
      const rows: string[][] = [];
      while (i < lines.length && lines[i].includes('|') && lines[i].trim() !== '') {
        rows.push(parseTableRow(lines[i]));
        i++;
      }

      elements.push(
        <div key={`tbl-${i}`} className="my-3 overflow-x-auto rounded-xl border border-border/70 bg-background/50">
          <table className="min-w-full border-collapse text-sm">
            <thead>
              <tr className="bg-secondary/50 text-left">
                {headers.map((h, idx) => (
                  <th key={idx} className="border-b border-border/70 px-3 py-2 font-semibold text-foreground whitespace-nowrap">
                    {renderInline(h, graphKeys, onOpenGraph)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, ridx) => (
                <tr key={ridx} className="odd:bg-background even:bg-background/70">
                  {headers.map((_, cidx) => (
                    <td key={cidx} className="border-b border-border/50 px-3 py-2 align-top">
                      {renderInline(row[cidx] || '', graphKeys, onOpenGraph)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      continue;
    }

    const headingMatch = line.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      const level = headingMatch[1].length;
      const text = headingMatch[2].trim();
      const cls = level <= 2 ? 'font-heading font-semibold text-base mt-4 mb-1.5' : 'font-heading font-semibold text-sm mt-4 mb-1';
      elements.push(<p key={i} className={cls}>{renderInline(text, graphKeys, onOpenGraph)}</p>);
    } else if (/^\s*---+\s*$/.test(line) || /^\s*\*\*\*+\s*$/.test(line)) {
      elements.push(<hr key={i} className="my-3 border-border/70" />);
    } else if (/^\s*([-*])\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*([-*])\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*([-*])\s+/, '').trim());
        i++;
      }
      elements.push(
        <ul key={`ul-${i}`} className="ml-5 list-disc space-y-1 text-sm leading-relaxed">
          {items.map((item, idx) => (
            <li key={idx}>{renderInline(item, graphKeys, onOpenGraph)}</li>
          ))}
        </ul>
      );
      continue;
    } else if (/^\s*\d+\.\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*\d+\.\s+/, '').trim());
        i++;
      }
      elements.push(
        <ol key={`ol-${i}`} className="ml-5 list-decimal space-y-1 text-sm leading-relaxed">
          {items.map((item, idx) => (
            <li key={idx}>{renderInline(item, graphKeys, onOpenGraph)}</li>
          ))}
        </ol>
      );
      continue;
    } else if (line.trim() === '') {
      elements.push(<div key={i} className="h-2" />);
    } else {
      elements.push(
        <p key={i} className="text-sm leading-relaxed">
          {renderInline(line, graphKeys, onOpenGraph)}
        </p>
      );
    }
    i++;
  }

  return <div className="prose-dark space-y-0.5">{elements}</div>;
}

function renderInline(text: string, graphKeys?: Set<string>, onOpenGraph?: (s: string) => void): React.ReactNode {
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith('`') && part.endsWith('`')) {
      const inner = part.slice(1, -1);
      return <InlineCodeTag key={i} text={inner} graphKeys={graphKeys} onOpenGraph={onOpenGraph} />;
    }
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="font-semibold text-foreground">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
      return <em key={i} className="italic text-foreground">{part.slice(1, -1)}</em>;
    }
    return part;
  });
}

export default function MessageBubble({ message, onInspect, isInspected, index, onTryAgain, onEdit, actionsDisabled = false, graphKeys, onOpenGraph, onSuggestion, previousUserQuery, onOpenEvidence }: MessageBubbleProps) {
  const [copied, setCopied] = useState(false);
  const [reaction, setReaction] = useState<'up' | 'down' | null>(null);
  const isUser = message.role === 'user';

  const intelParsed = !isUser ? parseIntelligenceSections(message.content) : null;
  const suggestedAction = parseSuggestedActionPayload(message.content, isUser);

  async function handleCopy() {
    try {
      const copiedOk = await copyTextSafely(message.content);
      if (!copiedOk) throw new Error('Clipboard copy failed');
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
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
          <AssistantContent
            message={message}
            intelParsed={intelParsed}
            suggestedAction={suggestedAction}
            graphKeys={graphKeys}
            onOpenGraph={onOpenGraph}
            onSuggestion={onSuggestion}
            previousUserQuery={previousUserQuery}
            actionsDisabled={actionsDisabled}
            onOpenEvidence={onOpenEvidence}
            onInspect={onInspect}
            isInspected={isInspected}
          />
        )}

        {/* Actions */}
        <div className={cn('flex items-center gap-1 text-xs text-muted-foreground', isUser ? 'justify-end' : 'justify-start')}>
          {isUser && (
            <button
              type="button"
              onClick={handleCopy}
              disabled={actionsDisabled}
              className="inline-flex h-8 w-8 items-center justify-center rounded-md transition-colors cursor-pointer hover:bg-secondary hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
              title={copied ? 'Copied' : 'Copy question'}
            >
              {copied ? <Check size={16} className="text-brand" /> : <Copy size={16} />}
            </button>
          )}

          {isUser && onEdit && (
            <button
              type="button"
              onClick={onEdit}
              disabled={actionsDisabled}
              className="inline-flex h-8 w-8 items-center justify-center rounded-md transition-colors cursor-pointer hover:bg-secondary hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
              title="Edit question"
            >
              <Pencil size={16} />
            </button>
          )}

          {!isUser && (
            <button
              type="button"
              onClick={handleCopy}
              disabled={actionsDisabled}
              className="inline-flex h-8 w-8 items-center justify-center rounded-md transition-colors cursor-pointer hover:bg-secondary hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
              title={copied ? 'Copied' : 'Copy answer'}
            >
              {copied ? <Check size={16} className="text-brand" /> : <Copy size={16} />}
            </button>
          )}

          {!isUser && (
            <>
              <button
                type="button"
                onClick={() => setReaction((prev) => (prev === 'up' ? null : 'up'))}
                disabled={actionsDisabled}
                className="inline-flex h-8 w-8 items-center justify-center rounded-md transition-colors cursor-pointer hover:bg-secondary hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
                title="Like"
              >
                <ThumbsUp size={16} className={reaction === 'up' ? 'text-brand' : undefined} />
              </button>
              <button
                type="button"
                onClick={() => setReaction((prev) => (prev === 'down' ? null : 'down'))}
                disabled={actionsDisabled}
                className="inline-flex h-8 w-8 items-center justify-center rounded-md transition-colors cursor-pointer hover:bg-secondary hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
                title="Dislike"
              >
                <ThumbsDown size={16} className={reaction === 'down' ? 'text-destructive' : undefined} />
              </button>
            </>
          )}

          {!isUser && onTryAgain && (
            <button
              type="button"
              onClick={onTryAgain}
              disabled={actionsDisabled}
              className="inline-flex h-8 w-8 items-center justify-center rounded-md transition-colors cursor-pointer hover:bg-secondary hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
              title="Try again"
            >
              <RefreshCcw size={16} />
            </button>
          )}
        </div>
      </div>
    </motion.div>
  );
}
