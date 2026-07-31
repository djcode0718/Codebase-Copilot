'use client';
/**
 * app/settings/page.tsx
 */
import { useState } from 'react';
import { motion } from 'framer-motion';
import { Settings, User, Cpu, AlertTriangle, SunMedium, MoonStar, Monitor } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { createClient } from '@/lib/supabase/client';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { useTheme } from 'next-themes';

export default function SettingsPage() {
  const router = useRouter();
  const { theme, setTheme, resolvedTheme } = useTheme();
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
    <div className="space-y-6">
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-[1.5rem] border border-border bg-card/80 p-6 shadow-lg shadow-black/5 backdrop-blur-sm"
      >
        <h1 className="font-heading text-2xl font-bold flex items-center gap-2">
          <Settings size={20} />
          Settings
        </h1>
        <p className="text-muted-foreground text-sm mt-1">
          Configure your Codebase Copilot environment and personalize your workspace.
        </p>
      </motion.div>

      <motion.section
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
        className="rounded-[1.5rem] border border-border bg-card/80 p-6 shadow-lg shadow-black/5 backdrop-blur-sm"
      >
        <div className="flex items-center gap-2 mb-4">
          <User size={15} className="text-muted-foreground" />
          <h2 className="font-heading font-semibold text-sm uppercase tracking-[0.18em] text-muted-foreground">Account</h2>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant="outline"
            className="border-border cursor-pointer"
            onClick={handleSignOut}
          >
            Sign out
          </Button>
          <p className="text-xs text-muted-foreground">Signed-in sessions are managed through Supabase auth.</p>
        </div>
      </motion.section>

      <motion.section
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="rounded-[1.5rem] border border-border bg-card/80 p-6 shadow-lg shadow-black/5 backdrop-blur-sm"
      >
        <div className="flex items-center gap-2 mb-4">
          <Cpu size={15} className="text-muted-foreground" />
          <h2 className="font-heading font-semibold text-sm uppercase tracking-[0.18em] text-muted-foreground">Backend</h2>
        </div>
        <div className="space-y-1.5">
          <Label>API Base URL</Label>
          <Input
            value={apiBase}
            onChange={(e) => setApiBase(e.target.value)}
            className="bg-background/70 border-border font-code text-sm"
            placeholder="http://localhost:8000"
          />
          <p className="text-xs text-muted-foreground">
            Change via <code className="font-code">NEXT_PUBLIC_API_BASE_URL</code> in <code className="font-code">.env.local</code>
          </p>
        </div>
      </motion.section>

      <motion.section
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.125 }}
        className="rounded-[1.5rem] border border-border bg-card/80 p-6 shadow-lg shadow-black/5 backdrop-blur-sm"
      >
        <div className="flex items-center gap-2 mb-4">
          <Monitor size={15} className="text-muted-foreground" />
          <h2 className="font-heading font-semibold text-sm uppercase tracking-[0.18em] text-muted-foreground">Appearance</h2>
        </div>
        <div className="grid gap-3 md:grid-cols-3">
          {[
            { key: 'light', label: 'Light', icon: SunMedium },
            { key: 'dark', label: 'Dark', icon: MoonStar },
            { key: 'system', label: 'System', icon: Monitor },
          ].map((option) => {
            const active = theme === option.key || (option.key === 'system' && !theme) || (option.key === 'system' && theme === 'system');
            return (
              <button
                key={option.key}
                type="button"
                onClick={() => setTheme(option.key)}
                className={`flex items-center gap-3 rounded-2xl border px-4 py-3 text-left transition-colors ${active ? 'border-brand bg-brand/5 text-foreground' : 'border-border bg-background/70 text-muted-foreground hover:bg-muted/70 hover:text-foreground'}`}
              >
                <option.icon size={16} className={active ? 'text-brand' : ''} />
                <div>
                  <p className="text-sm font-medium">{option.label}</p>
                  <p className="text-xs text-muted-foreground">{option.key === 'system' ? `Follows ${resolvedTheme ?? 'OS'} mode` : `Set the UI to ${option.label.toLowerCase()}`}</p>
                </div>
              </button>
            );
          })}
        </div>
      </motion.section>

      <motion.section
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
        className="rounded-[1.5rem] border border-destructive/20 bg-destructive/5 p-6 shadow-lg shadow-black/5"
      >
        <div className="flex items-center gap-2 mb-4">
          <AlertTriangle size={15} className="text-destructive" />
          <h2 className="font-heading font-semibold text-sm uppercase tracking-[0.18em] text-destructive">Danger zone</h2>
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
