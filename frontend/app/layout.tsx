/**
 * app/layout.tsx — Root layout
 * Sets up dark mode class, IBM Plex Sans + JetBrains Mono via next/font,
 * React Query provider, Supabase session provider, and Sonner toasts.
 */
import type { Metadata } from 'next';
import { IBM_Plex_Sans, JetBrains_Mono } from 'next/font/google';
import { Toaster } from '@/components/ui/sonner';
import Providers from '@/components/Providers';
import { CommandPalette } from '@/components/layout/CommandPalette';
import './globals.css';

const ibmPlexSans = IBM_Plex_Sans({
  subsets: ['latin'],
  weight: ['300', '400', '500', '600', '700'],
  variable: '--font-body',
  display: 'swap',
});

const jetBrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-code',
  display: 'swap',
});

export const metadata: Metadata = {
  title: {
    default: 'Codebase Copilot — Chat with any GitHub repository',
    template: '%s | Codebase Copilot',
  },
  description:
    'AI-powered RAG system. Index any GitHub repo and get grounded, inspectable answers backed by real code retrieval.',
  keywords: ['RAG', 'AI', 'code search', 'GitHub', 'LlamaIndex', 'developer tools'],
  openGraph: {
    title: 'Codebase Copilot',
    description: 'Chat with any GitHub repository. Every answer is grounded and inspectable.',
    type: 'website',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`dark ${ibmPlexSans.variable} ${jetBrainsMono.variable}`}
      suppressHydrationWarning
    >
      <body
        className="bg-background text-foreground antialiased min-h-screen"
        suppressHydrationWarning
      >
        <Providers>
          {children}
          <CommandPalette />
          <Toaster
            theme="dark"
            toastOptions={{
              style: {
                background: '#1E293B',
                border: '1px solid #334155',
                color: '#F8FAFC',
              },
            }}
          />
        </Providers>
      </body>
    </html>
  );
}
