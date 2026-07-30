'use client';
/**
 * app/settings/page.tsx
 */
import { useState } from 'react';
import { motion } from 'framer-motion';
import { Settings, User, Cpu, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { createClient } from '@/lib/supabase/client';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';

export default function SettingsPage() {
  const router = useRouter();
  const [apiBase, setApiBase] = useState(
    process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'
  );

  async function handleSignOut() {
    await createClient().auth.signOut();
    router.push('/auth/sign-in');
    toast.success('Signed out');
  }

  async function handleDeleteAccount() {
    if (!confirm('Delete your account and all data? This cannot be undone.')) return;
    toast.error('Account deletion requires backend support — contact admin.');
  }

  return (
    <div className="p-8 max-w-2xl">
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-8"
      >
        <h1 className="font-heading text-2xl font-bold flex items-center gap-2">
          <Settings size={20} />
          Settings
        </h1>
        <p className="text-muted-foreground text-sm mt-1">
          Configure your Codebase Copilot environment
        </p>
      </motion.div>

      {/* Profile section */}
      <motion.section
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
        className="bg-card border border-border rounded-xl p-6 mb-4"
      >
        <div className="flex items-center gap-2 mb-4">
          <User size={15} className="text-muted-foreground" />
          <h2 className="font-heading font-semibold text-sm">Account</h2>
        </div>
        <Button
          variant="outline"
          className="border-border cursor-pointer"
          onClick={handleSignOut}
        >
          Sign out
        </Button>
      </motion.section>

      {/* Backend config */}
      <motion.section
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="bg-card border border-border rounded-xl p-6 mb-4"
      >
        <div className="flex items-center gap-2 mb-4">
          <Cpu size={15} className="text-muted-foreground" />
          <h2 className="font-heading font-semibold text-sm">Backend</h2>
        </div>
        <div className="space-y-1.5">
          <Label>API Base URL</Label>
          <Input
            value={apiBase}
            onChange={(e) => setApiBase(e.target.value)}
            className="bg-background border-border font-code text-sm"
            placeholder="http://localhost:8000"
          />
          <p className="text-xs text-muted-foreground">
            Change via <code className="font-code">NEXT_PUBLIC_API_BASE_URL</code> in <code className="font-code">.env.local</code>
          </p>
        </div>
      </motion.section>

      {/* Danger zone */}
      <motion.section
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
        className="bg-destructive/5 border border-destructive/20 rounded-xl p-6"
      >
        <div className="flex items-center gap-2 mb-4">
          <AlertTriangle size={15} className="text-destructive" />
          <h2 className="font-heading font-semibold text-sm text-destructive">Danger zone</h2>
        </div>
        <Separator className="mb-4 bg-destructive/20" />
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium">Delete account</p>
            <p className="text-xs text-muted-foreground">
              Permanently deletes your account and all indexed repositories.
            </p>
          </div>
          <Button
            variant="outline"
            className="border-destructive/30 text-destructive hover:bg-destructive/10 cursor-pointer flex-shrink-0"
            onClick={handleDeleteAccount}
          >
            Delete account
          </Button>
        </div>
      </motion.section>
    </div>
  );
}
