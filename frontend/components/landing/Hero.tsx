'use client';
import { motion } from 'framer-motion';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { PipelineVisual } from './PipelineVisual';

export function Hero() {
  return (
    <section className="relative pt-32 pb-20 px-4 text-center overflow-hidden">
      <div className="absolute inset-0 bg-[linear-gradient(rgba(51,65,85,0.15)_1px,transparent_1px),linear-gradient(90deg,rgba(51,65,85,0.15)_1px,transparent_1px)] bg-[size:48px_48px] pointer-events-none opacity-50 mask-image:linear-gradient(to_bottom,white,transparent)" />
      
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.4, 0, 0.2, 1] }}
        className="relative z-10 max-w-4xl mx-auto space-y-8"
      >
        <h1 className="text-5xl md:text-7xl font-heading font-bold tracking-tight text-foreground leading-tight">
          Chat with your <span className="text-brand">Codebase</span>
        </h1>
        <p className="text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto">
          AI-powered RAG system for any GitHub repository. Get grounded, inspectable answers backed by real code retrieval.
        </p>
        <div className="flex justify-center gap-4 pt-4">
          <Link href="/auth/sign-in">
            <Button size="lg" className="bg-brand text-green-950 hover:bg-green-400 font-semibold h-12 px-8 text-base cursor-pointer">
              Index a Repo
            </Button>
          </Link>
          <Link href="/dashboard">
            <Button size="lg" variant="outline" className="h-12 px-8 text-base border-border hover:bg-accent cursor-pointer">
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
