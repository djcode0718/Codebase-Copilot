'use client';
import { motion } from 'framer-motion';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { PipelineVisual } from './PipelineVisual';

export function Hero() {
  return (
    <section className="relative overflow-hidden px-4 pb-20 pt-24 text-center sm:pt-28">
      <div className="absolute inset-0 bg-[linear-gradient(rgba(51,65,85,0.12)_1px,transparent_1px),linear-gradient(90deg,rgba(51,65,85,0.12)_1px,transparent_1px)] bg-[size:48px_48px] pointer-events-none opacity-50 [mask-image:linear-gradient(to_bottom,white,transparent)]" />
      <div className="absolute inset-x-0 top-0 mx-auto h-[34rem] w-[34rem] rounded-full bg-brand/10 blur-3xl pointer-events-none" />

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.4, 0, 0.2, 1] }}
        className="relative z-10 mx-auto max-w-5xl space-y-8"
      >
        <div className="inline-flex items-center gap-2 rounded-full border border-border bg-card/70 px-4 py-1.5 text-xs text-muted-foreground shadow-sm shadow-black/5 backdrop-blur-sm">
          Enterprise repository intelligence
        </div>
        <h1 className="text-5xl font-heading font-bold tracking-tight text-foreground leading-tight md:text-7xl">
          Chat with your <span className="text-brand">Codebase</span>
        </h1>
        <p className="mx-auto max-w-2xl text-lg text-muted-foreground md:text-xl">
          AI-powered RAG system for any GitHub repository. Get grounded, inspectable answers backed by real code retrieval.
        </p>
        <div className="flex flex-col justify-center gap-3 pt-4 sm:flex-row">
          <Link href="/auth/sign-in">
            <Button size="lg" className="h-12 cursor-pointer bg-brand px-8 text-base font-semibold text-green-950 hover:bg-green-400">
              Index a Repo
            </Button>
          </Link>
          <Link href="/dashboard">
            <Button size="lg" variant="outline" className="h-12 cursor-pointer border-border px-8 text-base hover:bg-accent">
              View Dashboard
            </Button>
          </Link>
        </div>
        
        <div className="pt-16">
          <PipelineVisual />
        </div>
      </motion.div>
    </section>
  );
}
