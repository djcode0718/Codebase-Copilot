'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { ShieldCheck, Sparkles, Lock, Building2, Briefcase, MessageSquareText, ShieldAlert, Radar, Network, Bot, SearchCode, GitBranch, Globe, Activity, Fingerprint, LayoutDashboard, Database, Server, Boxes, Cpu, CheckCircle2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

export type OAuthProvider = 'github' | 'google' | 'azure';

const SHOWCASE_ITEMS = [
  {
    title: 'Repository Chat',
    description: 'Query implementation details with grounded repository context and linked evidence.',
    icon: MessageSquareText,
  },
  {
    title: 'AI Engineering Review',
    description: 'Generate actionable findings and remediation guidance across architecture and quality.',
    icon: Sparkles,
  },
  {
    title: 'Architecture Analysis',
    description: 'Understand service boundaries, dependency chains, and design trade-offs quickly.',
    icon: Network,
  },
  {
    title: 'Security Intelligence',
    description: 'Highlight vulnerabilities, risky patterns, and auth-sensitive paths before release.',
    icon: ShieldAlert,
  },
  {
    title: 'Digital Twin Generation',
    description: 'Maintain a living model of repository behavior, ownership, and architectural health.',
    icon: Bot,
  },
  {
    title: 'Repository Health',
    description: 'Track quality and maintainability indicators with confidence-focused scoring.',
    icon: Radar,
  },
  {
    title: 'Evaluation Dashboard',
    description: 'Measure faithfulness, retrieval quality, and response reliability over time.',
    icon: LayoutDashboard,
  },
  {
    title: 'Code Intelligence',
    description: 'Navigate files, symbols, and architectural touchpoints with engineering precision.',
    icon: SearchCode,
  },
];

const MATURITY_METRICS = [
  { label: 'Repository Health', value: '92%', icon: Activity },
  { label: 'Security Grade', value: 'A', icon: Fingerprint },
  { label: 'Architecture Score', value: '95', icon: Network },
  { label: 'AI Coverage', value: '89%', icon: Cpu },
  { label: 'Repositories Indexed', value: '1,248', icon: Database },
  { label: 'Reviews Generated', value: '18,400', icon: Sparkles },
  { label: 'Fixes Suggested', value: '73,000', icon: Server },
  { label: 'Enterprise Workspaces', value: '320', icon: Building2 },
];

const PRIMARY_METRIC_LABELS = new Set([
  'Repository Health',
  'Security Grade',
  'Architecture Score',
  'AI Coverage',
]);

const SUPPORTED_TECH = [
  'GitHub',
  'Azure',
  'AWS',
  'Docker',
  'Kubernetes',
  'Python',
  'Java',
  'Go',
  'Rust',
  'C#',
  'React',
  'Next.js',
  'Node.js',
  'FastAPI',
  'Spring',
  'PostgreSQL',
  'Redis',
  'OpenAI',
  'Claude',
  'Gemini',
  'LangChain',
  'MCP',
  'Ollama',
  'TypeScript',
  'JavaScript',
  'C++',
  'Kotlin',
];

const TRUST_SIGNALS = [
  'Secure Authentication',
  'OAuth 2.0 Protected',
  'Enterprise Ready',
  'Multi-Repository Intelligence',
  'AI Engineering Reviews',
  'Architecture Intelligence',
  'Repository Evaluation',
  'Privacy First',
];

function ProviderIcon({ provider }: { provider: OAuthProvider }) {
  if (provider === 'github') return <GitBranch size={16} aria-hidden="true" />;
  if (provider === 'google') return <Globe size={16} aria-hidden="true" />;
  return <Briefcase size={16} aria-hidden="true" />;
}

export function OAuthButtons({
  loadingProvider,
  onOAuth,
}: {
  loadingProvider: OAuthProvider | null;
  onOAuth: (provider: OAuthProvider) => Promise<void>;
}) {
  const providers: { key: OAuthProvider; label: string; emphasis?: boolean }[] = [
    { key: 'github', label: 'Continue with GitHub', emphasis: true },
    { key: 'google', label: 'Continue with Google' },
    { key: 'azure', label: 'Continue with Microsoft' },
  ];

  return (
    <div className="space-y-2" aria-label="Sign in with OAuth providers">
      {providers.map((provider) => (
        <Button
          key={provider.key}
          type="button"
          variant={provider.emphasis ? 'default' : 'outline'}
          onClick={() => void onOAuth(provider.key)}
          disabled={Boolean(loadingProvider)}
          className={cn(
            'w-full h-11 justify-center gap-2.5 cursor-pointer rounded-xl transition-all duration-200 focus-visible:ring-2 focus-visible:ring-brand/60 focus-visible:ring-offset-2 focus-visible:ring-offset-background',
            provider.emphasis
              ? 'bg-foreground text-background hover:bg-foreground/90 hover:-translate-y-[1px]'
              : 'border-border hover:border-brand/50 hover:bg-accent hover:-translate-y-[1px]'
          )}
        >
          <ProviderIcon provider={provider.key} />
          {loadingProvider === provider.key ? 'Redirecting...' : provider.label}
        </Button>
      ))}
      <p className="text-xs text-muted-foreground">
        Use the same email across providers to keep one workspace profile.
      </p>
    </div>
  );
}

function useReducedMotionPreference() {
  const [reducedMotion, setReducedMotion] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  });

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');

    const listener = (event: MediaQueryListEvent) => setReducedMotion(event.matches);
    mediaQuery.addEventListener('change', listener);
    return () => mediaQuery.removeEventListener('change', listener);
  }, []);

  return reducedMotion;
}

export function AuthExperienceShell({
  heading,
  subtitle,
  authCard,
  footer,
  showBrand = true,
}: {
  heading: string;
  subtitle: string;
  authCard: React.ReactNode;
  footer: React.ReactNode;
  showBrand?: boolean;
}) {
  const reducedMotion = useReducedMotionPreference();
  const [showcaseIndex, setShowcaseIndex] = useState(0);
  const activeShowcase = SHOWCASE_ITEMS[showcaseIndex];

  useEffect(() => {
    if (reducedMotion) return;
    const timer = window.setInterval(() => {
      setShowcaseIndex((current) => (current + 1) % SHOWCASE_ITEMS.length);
    }, 5000);
    return () => window.clearInterval(timer);
  }, [reducedMotion]);

  const ecosystemItems = useMemo(
    () => SUPPORTED_TECH.map((tech, index) => ({ tech, delay: `${(index % 8) * 0.4}s` })),
    []
  );
  const primaryMetrics = MATURITY_METRICS.filter((metric) => PRIMARY_METRIC_LABELS.has(metric.label));
  const secondaryMetrics = MATURITY_METRICS.filter((metric) => !PRIMARY_METRIC_LABELS.has(metric.label));

  return (
    <div className="min-h-[100dvh] overflow-x-hidden overflow-y-auto bg-background p-3 sm:p-4">
      <div className="absolute inset-0 bg-[linear-gradient(rgba(51,65,85,0.11)_1px,transparent_1px),linear-gradient(90deg,rgba(51,65,85,0.11)_1px,transparent_1px)] bg-[size:48px_48px] pointer-events-none" />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(34,197,94,0.15),transparent_36%),radial-gradient(circle_at_82%_18%,rgba(59,130,246,0.14),transparent_28%)]" />
      <div className="relative mx-auto grid h-full w-full max-w-[1280px] gap-4 lg:grid-cols-[minmax(420px,0.9fr)_minmax(540px,1.1fr)] xl:gap-6">
        <section className="surface-glass rounded-3xl border border-border/90 bg-card/92 p-5 pb-7 shadow-[0_20px_48px_rgba(15,23,42,0.13)] sm:p-6 sm:pb-8 lg:max-h-[calc(100dvh-2rem)] lg:overflow-y-auto scrollbar-none">
          {showBrand ? (
            <Link href="/" className="inline-flex items-center gap-2" aria-label="Codebase Copilot home">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand text-green-950">
                <span className="font-code text-sm font-bold">CC</span>
              </div>
              <span className="font-heading text-lg font-semibold tracking-tight">Codebase Copilot</span>
            </Link>
          ) : null}
          <div className={cn(showBrand ? 'mt-6 space-y-2' : 'space-y-2')}>
            <p className="inline-flex items-center gap-2 rounded-full border border-brand/30 bg-brand/10 px-3 py-1 text-xs text-brand">
              <Sparkles size={12} aria-hidden="true" /> AI Engineering Workspace
            </p>
            <h1 className="font-heading text-3xl font-bold tracking-tight sm:text-[2rem]">{heading}</h1>
            <p className="text-sm text-muted-foreground">{subtitle}</p>
          </div>
          <div className="mt-5 rounded-2xl border border-border/85 bg-background/58 p-4 shadow-inner shadow-black/5 sm:p-5">{authCard}</div>
          <div className="mt-5">{footer}</div>
        </section>

        <section className="surface-glass rounded-3xl border border-border/90 bg-card/74 p-5 pb-7 backdrop-blur-sm sm:p-6 sm:pb-8 lg:max-h-[calc(100dvh-2rem)] lg:overflow-y-auto scrollbar-none">
          <h2 className="font-heading text-[2rem] font-semibold tracking-tight leading-[1.1] sm:text-[2.25rem] xl:text-[2.35rem]">
            AI Operating System for Repository Engineering
          </h2>
          <p className="mt-1.5 text-sm text-muted-foreground sm:text-[0.94rem]">
            Understand, review, secure, and improve repositories with enterprise AI across architecture, code quality, and delivery workflows.
          </p>

          <div className="mt-4 rounded-2xl border border-border/80 bg-background/58 p-3.5 shadow-inner shadow-black/5">
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Interactive showcase</p>
              <div className="flex items-center gap-1.5" aria-hidden="true">
                {SHOWCASE_ITEMS.map((_, idx) => (
                  <span
                    key={idx}
                    className={cn(
                      'h-1.5 rounded-full transition-all duration-300',
                      idx === showcaseIndex ? 'w-6 bg-brand' : 'w-2 bg-border'
                    )}
                  />
                ))}
              </div>
            </div>
            <div
              className="mt-2.5 rounded-xl border border-border bg-card/88 p-3.5 transition-all duration-300"
              aria-live="polite"
            >
              <div className="flex items-start gap-3">
                <div className="mt-0.5 flex h-9 w-9 items-center justify-center rounded-xl border border-brand/25 bg-brand/10 text-brand">
                  <activeShowcase.icon size={17} aria-hidden="true" />
                </div>
                <div className="space-y-1">
                  <p className="text-sm font-semibold">{activeShowcase.title}</p>
                  <p className="text-sm text-muted-foreground">{activeShowcase.description}</p>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
            {primaryMetrics.map((metric) => (
              <div key={metric.label} className="auth-elevate rounded-xl border border-border bg-background/70 px-3 py-2 transition-all duration-200">
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <metric.icon size={12} className="text-brand" aria-hidden="true" />
                  <span>{metric.label}</span>
                </div>
                <p className="mt-1 font-heading text-lg font-semibold tracking-tight">{metric.value}</p>
              </div>
            ))}
          </div>

          <div className="mt-2.5 grid gap-1.5 sm:grid-cols-2 xl:grid-cols-4">
            {secondaryMetrics.map((metric) => (
              <div key={metric.label} className="rounded-lg border border-border/80 bg-background/65 px-2.5 py-1.5 text-xs text-muted-foreground">
                <div className="flex items-center gap-1.5">
                  <metric.icon size={11} className="text-brand" aria-hidden="true" />
                  <span className="truncate">{metric.label}</span>
                </div>
                <p className="mt-0.5 text-sm font-semibold text-foreground">{metric.value}</p>
              </div>
            ))}
          </div>

          <div className="mt-3 rounded-2xl border border-border bg-background/62 p-3">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              <Boxes size={12} className="text-brand" aria-hidden="true" />
              Technology ecosystem
            </div>
            <div className="mt-2.5 flex flex-wrap gap-2">
              {ecosystemItems.map(({ tech, delay }) => (
                <span
                  key={tech}
                  style={reducedMotion ? undefined : { animationDelay: delay }}
                  className={cn(
                    'auth-tech-chip rounded-full border border-border/95 bg-card px-2.5 py-1 text-[11px] font-medium text-foreground/85 shadow-sm',
                    reducedMotion ? '' : 'auth-tech-float'
                  )}
                >
                  {tech}
                </span>
              ))}
            </div>
          </div>

          <div className="mt-3.5 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
            {TRUST_SIGNALS.map((signal) => (
              <div key={signal} className="auth-elevate flex items-center gap-1.5 rounded-full border border-border/90 bg-card px-2.5 py-1.5 text-[11px] text-foreground/85 shadow-sm transition-all duration-200">
                {signal === 'OAuth 2.0 Protected' ? <Lock size={13} className="text-brand" aria-hidden="true" /> : null}
                {signal === 'Secure Authentication' ? <ShieldCheck size={13} className="text-brand" aria-hidden="true" /> : null}
                {signal === 'Privacy First' ? <Lock size={13} className="text-brand" aria-hidden="true" /> : null}
                {signal === 'Enterprise Ready' ? <Building2 size={13} className="text-brand" aria-hidden="true" /> : null}
                {signal === 'Multi-Repository Intelligence' ? <Database size={13} className="text-brand" aria-hidden="true" /> : null}
                {signal === 'AI Engineering Reviews' ? <Sparkles size={13} className="text-brand" aria-hidden="true" /> : null}
                {signal === 'Architecture Intelligence' ? <Network size={13} className="text-brand" aria-hidden="true" /> : null}
                {signal === 'Repository Evaluation' ? <Radar size={13} className="text-brand" aria-hidden="true" /> : null}
                <span className="truncate">{signal}</span>
                <CheckCircle2 size={11} className="ml-auto shrink-0 text-brand/80" aria-hidden="true" />
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
