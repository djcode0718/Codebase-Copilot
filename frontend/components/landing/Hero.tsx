'use client';
import { motion } from 'framer-motion';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { ArrowRight, Zap, Shield, Brain, GitBranch } from 'lucide-react';

function GithubIcon({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 2C6.477 2 2 6.484 2 12.021c0 4.428 2.865 8.185 6.839 9.504.5.092.682-.217.682-.483 0-.237-.009-.868-.013-1.703-2.782.605-3.369-1.342-3.369-1.342-.454-1.155-1.11-1.463-1.11-1.463-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0 1 12 6.844a9.59 9.59 0 0 1 2.504.337c1.909-1.296 2.747-1.026 2.747-1.026.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.579.688.481C19.138 20.203 22 16.447 22 12.021 22 6.484 17.522 2 12 2Z" />
    </svg>
  );
}

const stats = [
	{ value: '18+', label: 'Intelligence capabilities' },
	{ value: '< 2s', label: 'Avg retrieval latency' },
	{ value: '100%', label: 'Grounded responses' },
	{ value: '4 LLMs', label: 'Provider support' },
];

const techBadges = [
	{
		label: 'FastAPI',
		color: 'from-teal-500/20 to-teal-600/10 border-teal-500/30 text-teal-600 dark:text-teal-400',
	},
	{
		label: 'Next.js 15',
		color: 'from-slate-500/20 to-slate-600/10 border-slate-400/30 text-slate-600 dark:text-slate-300',
	},
	{
		label: 'Supabase',
		color: 'from-emerald-500/20 to-emerald-600/10 border-emerald-500/30 text-emerald-600 dark:text-emerald-400',
	},
	{
		label: 'LlamaIndex',
		color: 'from-violet-500/20 to-violet-600/10 border-violet-500/30 text-violet-600 dark:text-violet-400',
	},
	{ label: 'RAG', color: 'from-brand/20 to-brand/10 border-brand/30 text-brand' },
	{
		label: 'Python 3.10',
		color: 'from-blue-500/20 to-blue-600/10 border-blue-500/30 text-blue-600 dark:text-blue-400',
	},
];

export function Hero({ signedIn }: { signedIn?: boolean }) {
	return (
		<section className="relative overflow-hidden px-4 pb-24 pt-20 sm:pt-28">
			{/* Background elements */}
			<div className="absolute inset-0 bg-[linear-gradient(rgba(51,65,85,0.07)_1px,transparent_1px),linear-gradient(90deg,rgba(51,65,85,0.07)_1px,transparent_1px)] bg-[size:56px_56px] pointer-events-none [mask-image:linear-gradient(to_bottom,white_20%,transparent)]" />
			<div className="absolute -top-32 left-1/2 -translate-x-1/2 h-[600px] w-[900px] rounded-full bg-brand/8 blur-3xl pointer-events-none" />
			<div className="absolute top-20 right-0 h-[300px] w-[300px] rounded-full bg-blue-500/6 blur-3xl pointer-events-none" />
			<div className="absolute top-40 left-0 h-[250px] w-[250px] rounded-full bg-violet-500/6 blur-3xl pointer-events-none" />

			<div className="relative z-10 mx-auto max-w-6xl">
				{/* Eyebrow badge */}
				<motion.div
					initial={{ opacity: 0, y: 12 }}
					animate={{ opacity: 1, y: 0 }}
					transition={{ duration: 0.4 }}
					className="flex justify-center mb-8"
				>
					<span className="inline-flex items-center gap-2 rounded-full border border-brand/30 bg-brand/8 px-4 py-1.5 text-xs font-medium text-brand shadow-sm">
						<span className="relative flex h-2 w-2">
							<span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand opacity-60" />
							<span className="relative inline-flex rounded-full h-2 w-2 bg-brand" />
						</span>
						Enterprise Repository Intelligence Platform · v2.0
					</span>
				</motion.div>

				{/* Headline */}
				<motion.div
					initial={{ opacity: 0, y: 20 }}
					animate={{ opacity: 1, y: 0 }}
					transition={{ duration: 0.5, delay: 0.05 }}
					className="text-center"
				>
					<h1 className="text-5xl font-heading font-bold tracking-tight leading-[1.1] md:text-7xl lg:text-[5.5rem]">
						Chat with your{' '}
						<span className="relative inline-block">
							<span className="bg-gradient-to-r from-brand via-emerald-400 to-teal-400 bg-clip-text text-transparent">
								Codebase
							</span>
							<span className="absolute -bottom-1 left-0 right-0 h-0.5 bg-gradient-to-r from-brand/60 via-emerald-400/60 to-teal-400/60 blur-sm" />
						</span>
						<br />
						<span className="text-foreground/80">like never before</span>
					</h1>

					<p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground md:text-xl leading-relaxed">
						AI-powered RAG system for any GitHub repository. Get grounded,
						inspectable answers backed by real code retrieval — with architecture
						discovery, security analysis, and health scoring built in.
					</p>
				</motion.div>

				{/* CTA Buttons */}
				<motion.div
					initial={{ opacity: 0, y: 16 }}
					animate={{ opacity: 1, y: 0 }}
					transition={{ duration: 0.5, delay: 0.15 }}
					className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row"
				>
					<Link href={signedIn ? '/dashboard' : '/auth/sign-in'}>
						<Button
							size="lg"
							className="group h-13 cursor-pointer bg-brand px-8 text-base font-semibold text-green-950 hover:bg-green-400 shadow-lg shadow-brand/25 transition-all duration-200"
						>
							{signedIn ? 'Open workspace' : 'Get started free'}
							<ArrowRight
								size={16}
								className="ml-2 transition-transform group-hover:translate-x-0.5"
							/>
						</Button>
					</Link>
					<Link href="https://github.com" target="_blank">
						<Button
							size="lg"
							variant="outline"
							className="h-13 cursor-pointer border-border px-8 text-base hover:bg-accent gap-2"
						>
							<GithubIcon size={16} />
							View on GitHub
						</Button>
					</Link>
				</motion.div>

				{/* Tech stack badges */}
				<motion.div
					initial={{ opacity: 0 }}
					animate={{ opacity: 1 }}
					transition={{ duration: 0.5, delay: 0.25 }}
					className="mt-8 flex flex-wrap justify-center gap-2"
				>
					{techBadges.map((badge) => (
						<span
							key={badge.label}
							className={`inline-flex items-center rounded-full border bg-gradient-to-br px-3 py-1 text-xs font-medium ${badge.color}`}
						>
							{badge.label}
						</span>
					))}
				</motion.div>

				{/* Stats bar */}
				<motion.div
					initial={{ opacity: 0, y: 20 }}
					animate={{ opacity: 1, y: 0 }}
					transition={{ duration: 0.5, delay: 0.35 }}
					className="mt-16 grid grid-cols-2 gap-4 md:grid-cols-4"
				>
					{stats.map((stat, i) => (
						<div
							key={i}
							className="rounded-2xl border border-border bg-card/60 backdrop-blur-sm px-6 py-5 text-center shadow-sm hover:border-brand/30 transition-colors"
						>
							<div className="text-3xl font-heading font-bold text-brand">
								{stat.value}
							</div>
							<div className="mt-1 text-xs text-muted-foreground">
								{stat.label}
							</div>
						</div>
					))}
				</motion.div>

				{/* Demo terminal */}
				<motion.div
					initial={{ opacity: 0, y: 24 }}
					animate={{ opacity: 1, y: 0 }}
					transition={{ duration: 0.6, delay: 0.45 }}
					className="mt-16 overflow-hidden rounded-[1.75rem] border border-border bg-card/80 shadow-2xl shadow-black/10 backdrop-blur-sm"
				>
					{/* Terminal title bar */}
					<div className="flex items-center gap-2 border-b border-border bg-muted/40 px-5 py-3">
						<span className="h-3 w-3 rounded-full bg-red-400/80" />
						<span className="h-3 w-3 rounded-full bg-amber-400/80" />
						<span className="h-3 w-3 rounded-full bg-brand/80" />
						<span className="ml-3 text-xs text-muted-foreground font-code">
							codebase-copilot — chat
						</span>
					</div>
					{/* Mock chat */}
					<div className="p-6 space-y-4 font-code text-sm">
						<div className="flex gap-3">
							<span className="shrink-0 h-7 w-7 rounded-full bg-blue-500/20 border border-blue-500/30 flex items-center justify-center text-[10px] font-bold text-blue-400">
								U
							</span>
							<div className="rounded-xl bg-muted/50 border border-border px-4 py-2.5 text-foreground/90">
								How does the streaming chat endpoint handle partial response
								persistence?
							</div>
						</div>
						<div className="flex gap-3">
							<span className="shrink-0 h-7 w-7 rounded-full bg-brand/20 border border-brand/30 flex items-center justify-center text-[10px] font-bold text-brand">
								AI
							</span>
							<div className="flex-1 rounded-xl bg-brand/5 border border-brand/20 px-4 py-2.5">
								<p className="text-foreground/90">
									The{' '}
									<code className="rounded px-1.5 py-0.5 bg-card border border-border text-brand text-xs">
										stream_message
									</code>{' '}
									endpoint in{' '}
									<code className="rounded px-1.5 py-0.5 bg-card border border-border text-brand text-xs">
										api/routers/chat.py
									</code>{' '}
									uses SSE to stream tokens. The assistant message is persisted
									after the{' '}
									<code className="rounded px-1.5 py-0.5 bg-card border border-border text-brand text-xs">
										done
									</code>{' '}
									event via{' '}
									<code className="rounded px-1.5 py-0.5 bg-card border border-border text-brand text-xs">
										save_message()
									</code>
									.
								</p>
								<div className="mt-2 flex gap-3 text-[10px] text-muted-foreground">
									<span className="flex items-center gap-1">
										<Zap size={10} className="text-brand" /> 340ms retrieval
									</span>
									<span className="flex items-center gap-1">
										<Brain size={10} className="text-violet-400" /> code_lookup
										mode
									</span>
									<span className="flex items-center gap-1">
										<GitBranch size={10} className="text-blue-400" /> 3 files
										matched
									</span>
								</div>
							</div>
						</div>
					</div>
				</motion.div>

				{/* Security note */}
				<motion.p
					initial={{ opacity: 0 }}
					animate={{ opacity: 1 }}
					transition={{ delay: 0.6 }}
					className="mt-6 flex items-center justify-center gap-1.5 text-xs text-muted-foreground"
				>
					<Shield size={11} className="text-brand" />
					All responses are grounded in real code. No hallucinations. JWT-protected
					APIs.
				</motion.p>
			</div>
		</section>
	);
}
