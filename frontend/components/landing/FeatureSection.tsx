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
    <section className="py-24 px-4 bg-background">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-16">
          <h2 className="text-3xl font-heading font-bold">Why Codebase Copilot?</h2>
          <p className="text-muted-foreground mt-4">Built differently from standard AI chat interfaces.</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
          {features.map((feature, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1, duration: 0.5 }}
              className="p-6 rounded-2xl bg-card border border-border hover:border-brand/50 transition-colors"
            >
              <div className="w-12 h-12 rounded-lg bg-accent flex items-center justify-center mb-4 text-brand">
                <feature.icon size={24} />
              </div>
              <h3 className="text-lg font-semibold mb-2">{feature.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{feature.description}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
