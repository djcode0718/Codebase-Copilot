'use client';
import { motion } from 'framer-motion';
import { Search, Activity, Code2, LineChart } from 'lucide-react';

const features = [
  {
    title: 'Grounded Responses',
    description: 'Every answer is backed by exact chunks retrieved from your codebase. No hallucinations.',
    icon: Search,
  },
  {
    title: 'Live Indexing',
    description: 'Watch the RAG pipeline parse, embed, and store your code in real-time.',
    icon: Activity,
  },
  {
    title: 'AI Inspector',
    description: 'Peek under the hood. See the exact retrieval mode, matched files, and latency breakdown.',
    icon: Code2,
  },
  {
    title: 'Evaluations',
    description: 'Built-in ML metrics radar chart to measure hit rate, MRR, and relevancy.',
    icon: LineChart,
  },
];

export function FeatureSection() {
  return (
    <section className="bg-background px-4 py-24">
      <div className="mx-auto max-w-7xl">
        <div className="mb-16 text-center">
          <h2 className="text-3xl font-heading font-bold tracking-tight md:text-4xl">Why Codebase Copilot?</h2>
          <p className="mt-4 text-muted-foreground">Built differently from standard AI chat interfaces.</p>
        </div>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
          {features.map((feature, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1, duration: 0.5 }}
              className="rounded-[1.5rem] border border-border bg-card/80 p-6 shadow-sm shadow-black/5 transition-colors hover:border-brand/40 hover:shadow-lg hover:shadow-black/10"
            >
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl border border-brand/20 bg-brand/10 text-brand">
                <feature.icon size={24} />
              </div>
              <h3 className="mb-2 text-lg font-semibold">{feature.title}</h3>
              <p className="text-sm leading-relaxed text-muted-foreground">{feature.description}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
