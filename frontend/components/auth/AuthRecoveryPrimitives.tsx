import Link from 'next/link';
import { motion } from 'framer-motion';
import { CheckCircle2, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function AuthScreenMotion({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
    >
      {children}
    </motion.div>
  );
}

export function AuthSuccessPanel({
  message,
  ctaHref,
  ctaLabel,
}: {
  message: string;
  ctaHref: string;
  ctaLabel: string;
}) {
  return (
    <div className="rounded-2xl border border-border bg-background/60 px-4 py-8 text-center">
      <CheckCircle2 size={20} className="mx-auto text-brand" />
      <p className="mt-3 text-sm text-muted-foreground">{message}</p>
      <Button asChild variant="outline" className="mt-4 border-border">
        <Link href={ctaHref}>{ctaLabel}</Link>
      </Button>
    </div>
  );
}

export function AuthBusyLabel({ loading, idleLabel }: { loading: boolean; idleLabel: string }) {
  return (
    <>
      {loading ? <Loader2 size={16} className="animate-spin mr-2" /> : null}
      {idleLabel}
    </>
  );
}

