import type { MessageResponse, MetadataEvent } from "@/lib/types";
import { AssistantMessage } from "@/components/chat/assistant-message";
import { ModeBadge } from "@/components/chat/mode-badge";
import { RetrievedFilesChip } from "@/components/chat/retrieved-files-chip";

interface StreamingState {
  status: "idle" | "streaming" | "done" | "error";
  tokens: string;
  metadata: MetadataEvent | null;
  message?: string;
}

export function MessageList({
  messages,
  streaming,
}: {
  messages: MessageResponse[];
  streaming: StreamingState;
}) {
  return (
    <div className="space-y-4">
      {messages.map((message) =>
        message.role === "user" ? (
          <div key={message.id} className="ml-auto max-w-2xl rounded-lg bg-[var(--bg-elevated)] p-3 text-sm">
            {message.content}
          </div>
        ) : (
          <AssistantMessage key={message.id} message={message} />
        ),
      )}

      {streaming.status === "streaming" ? (
        <div className="max-w-4xl rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] p-3">
          <div className="mb-2 flex items-center gap-2">
            <ModeBadge mode={streaming.metadata?.query_mode} />
            <span className="text-xs text-[var(--text-secondary)]">Streaming...</span>
          </div>
          <p className="whitespace-pre-wrap text-sm">{streaming.tokens}</p>
          <div className="mt-2">
            <RetrievedFilesChip files={streaming.metadata?.retrieved_files} />
          </div>
        </div>
      ) : null}

      {streaming.status === "error" ? (
        <div className="rounded-md border border-[var(--error)]/50 bg-[var(--error)]/10 p-3 text-sm text-[var(--error)]">
          {streaming.message ?? "Streaming failed"}
        </div>
      ) : null}
    </div>
  );
}

