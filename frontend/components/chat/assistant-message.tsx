import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import type { MessageResponse } from "@/lib/types";
import { ModeBadge } from "@/components/chat/mode-badge";
import { RetrievedFilesChip } from "@/components/chat/retrieved-files-chip";

export function AssistantMessage({ message }: { message: MessageResponse }) {
  return (
    <div className="max-w-4xl rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] p-3">
      <div className="mb-2 flex items-center gap-2">
        <ModeBadge mode={message.query_mode} />
      </div>
      <article className="prose prose-invert prose-sm max-w-none prose-pre:bg-black/40">
        <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
          {message.content}
        </ReactMarkdown>
      </article>
      <div className="mt-2 space-y-2">
        <RetrievedFilesChip files={message.retrieved_files} />
        {message.latency_ms ? (
          <p className="font-mono text-[10px] text-[var(--text-secondary)]">Latency: {message.latency_ms} ms</p>
        ) : null}
      </div>
    </div>
  );
}

