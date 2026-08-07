'use client';
import { motion } from 'framer-motion';
import {
  Search, Activity, Code2, LineChart, Shield, GitBranch,
  MessageSquare, Zap, Brain, FileCode2, BarChart3, RefreshCw, FileArchive,
} from 'lucide-react';

const features = [
  {
    title: 'Thread-First Workspace',
    description: 'The chat thread stays front-and-center while repository context and AI Inspector live in a compact right rail.',
    icon: MessageSquare,
    accent: 'text-brand border-brand/20 bg-brand/10',
  },
  {
    title: 'Grounded Responses',
    description: 'Every answer is backed by exact chunks retrieved from your codebase. Zero hallucinations, full evidence trail.',
    icon: Search,
    accent: 'text-brand border-brand/20 bg-brand/10',
  },
  {
    title: 'Hybrid RAG Pipeline',
    description: 'Dense + BM25 + RRF retrieval with ColBERT reranking and dual-mode query routing for maximum relevance.',
    icon: Brain,
    accent: 'text-violet-500 border-violet-500/20 bg-violet-500/10',
  },
  {
    title: 'Architecture Discovery',
    description: 'Automatic Mermaid diagram generation. Service maps, data flow charts, and component relationship graphs.',
    icon: GitBranch,
    accent: 'text-blue-500 border-blue-500/20 bg-blue-500/10',
  },
  {
    title: 'Repository Health Score',
    description: 'Continuous 0–100 health scoring across 12 categories: security, code quality, tech debt, test coverage, and more.',
    icon: BarChart3,
    accent: 'text-amber-500 border-amber-500/20 bg-amber-500/10',
  },
  {
    title: 'AI Engineering Review',
    description: 'Per-file, per-commit, and PR diff reviews with severity-ranked findings and auto-generated code fixes.',
    icon: FileCode2,
    accent: 'text-teal-500 border-teal-500/20 bg-teal-500/10',
  },
  {
    title: 'Security Intelligence',
    description: 'Automated vulnerability scanning, auth flow analysis, and actionable remediation recommendations.',
    icon: Shield,
    accent: 'text-red-500 border-red-500/20 bg-red-500/10',
  },
  {
    title: 'Live Indexing',
    description: 'Watch the RAG pipeline parse, embed, and store your code in real-time with SSE progress streaming.',
    icon: Activity,
    accent: 'text-brand border-brand/20 bg-brand/10',
  },
  {
    title: 'AI Inspector',
    description: 'Inspect every response: retrieval mode, matched files, latency breakdown, and confidence scores.',
    icon: Code2,
    accent: 'text-violet-500 border-violet-500/20 bg-violet-500/10',
  },
  {
    title: 'Evaluations & Metrics',
    description: 'Built-in ML metrics radar: hit rate, MRR, faithfulness, relevancy, and latency across all retrieval modes.',
    icon: LineChart,
    accent: 'text-blue-500 border-blue-500/20 bg-blue-500/10',
  },
  {
    title: 'In-Thread Chat Export',
    description: 'Export the active conversation directly from the chat banner to Markdown, JSON, TXT, PDF, or DOCX.',
    icon: FileArchive,
    accent: 'text-emerald-500 border-emerald-500/20 bg-emerald-500/10',
  },
  {
    title: 'Conversation Memory',
    description: 'Persistent chat history with session summaries, pinned conversations, and semantic search across all chats.',
    icon: MessageSquare,
    accent: 'text-amber-500 border-amber-500/20 bg-amber-500/10',
  },
  {
    title: 'Multi-LLM Support',
    description: 'Groq, Ollama, Google Gemini, and OpenAI. Switch providers per-session without re-indexing.',
    icon: Zap,
    accent: 'text-teal-500 border-teal-500/20 bg-teal-500/10',
  },
  {
    title: 'Auto Re-index',
    description: 'One-click repo refresh. Incremental updates keep your knowledge base in sync as code evolves.',
    icon: RefreshCw,
    accent: 'text-red-500 border-red-500/20 bg-red-500/10',
  },
];

const workflow = [
  { step: '01', title: 'Index', desc: 'Paste any GitHub URL. The pipeline clones, parses, chunks, and embeds your codebase.' },
  { step: '02', title: 'Ask', desc: 'Type natural-language questions in a thread-first chat workspace designed for long engineering sessions.' },
  { step: '03', title: 'Inspect', desc: 'Track retrieval mode, latency, and matched files from the compact right-side AI Inspector rail.' },
  { step: '04', title: 'Share', desc: 'Export chats in multiple formats and run health checks, security scans, and AI-generated code reviews.' },
];

export function FeatureSection() {
  return (
    <>
      {/* How it works */}
      <section className="bg-muted/30 border-y border-border px-4 py-20">
        <div className="mx-auto max-w-6xl">
          <div className="mb-12 text-center">
            <h2 className="text-3xl font-heading font-bold tracking-tight md:text-4xl">How it works</h2>
            <p className="mt-3 text-muted-foreground">From GitHub URL to production-grade insights in minutes.</p>
          </div>
          <div className="grid grid-cols-1 gap-0 md:grid-cols-4">
            {workflow.map((item, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.08, duration: 0.4 }}
                className="relative flex flex-col items-center px-6 py-8 text-center"
              >
                {i < workflow.length - 1 && (
                  <div className="absolute right-0 top-1/2 hidden h-px w-8 -translate-y-12 bg-border md:block" />
                )}
                <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-brand/30 bg-brand/10 text-2xl font-heading font-bold text-brand">
                  {item.step}
                </div>
                <h3 className="mb-2 text-base font-semibold">{item.title}</h3>
                <p className="text-sm leading-relaxed text-muted-foreground">{item.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Capabilities grid */}
      <section className="bg-background px-4 py-24">
        <div className="mx-auto max-w-6xl">
          <div className="mb-16 text-center">
            <div className="mb-3 inline-flex items-center rounded-full border border-border bg-muted/60 px-3 py-1 text-xs text-muted-foreground">
              Latest v2.0 experience
            </div>
            <h2 className="text-3xl font-heading font-bold tracking-tight md:text-4xl">
              Everything you need to understand your codebase
            </h2>
            <p className="mt-4 max-w-2xl mx-auto text-muted-foreground">
              From security audits to onboarding guides — Codebase Copilot covers the full lifecycle of repository intelligence.
            </p>
          </div>
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3">
            {features.map((feature, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: (i % 3) * 0.08, duration: 0.4 }}
                className="group rounded-[1.5rem] border border-border bg-card/80 p-6 shadow-sm shadow-black/5 transition-all duration-200 hover:border-brand/30 hover:shadow-md hover:shadow-brand/5 hover:-translate-y-0.5"
              >
                <div className={`mb-4 flex h-11 w-11 items-center justify-center rounded-xl border ${feature.accent}`}>
                  <feature.icon size={20} />
                </div>
                <h3 className="mb-2 text-base font-semibold">{feature.title}</h3>
                <p className="text-sm leading-relaxed text-muted-foreground">{feature.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Banner */}
      <section className="px-4 pb-24">
        <div className="mx-auto max-w-4xl">
          <motion.div
            initial={{ opacity: 0, scale: 0.97 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
            className="relative overflow-hidden rounded-[2rem] border border-brand/20 bg-gradient-to-br from-brand/10 via-emerald-500/5 to-teal-500/5 p-10 text-center shadow-lg shadow-brand/10"
          >
            <div className="absolute inset-0 bg-[linear-gradient(rgba(34,197,94,0.05)_1px,transparent_1px),linear-gradient(90deg,rgba(34,197,94,0.05)_1px,transparent_1px)] bg-[size:32px_32px] pointer-events-none" />
            <div className="relative z-10">
              <h2 className="text-3xl font-heading font-bold tracking-tight md:text-4xl">
                Ready to understand your codebase?
              </h2>
              <p className="mt-4 text-muted-foreground md:text-lg">
                Index your first repository in under 3 minutes. No credit card required.
              </p>
              <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
                <a href="/auth/sign-in">
                  <button className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-brand px-8 text-base font-semibold text-green-950 shadow-md shadow-brand/25 transition-all hover:bg-green-400 hover:-translate-y-0.5">
                    Start for free
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" /></svg>
                  </button>
                </a>
                <a href="/dashboard">
                  <button className="inline-flex h-12 items-center justify-center rounded-xl border border-border bg-background/70 px-8 text-base text-foreground transition-all hover:bg-accent">
                    View dashboard
                  </button>
                </a>
              </div>
            </div>
          </motion.div>
        </div>
      </section>
    </>
  );
}
