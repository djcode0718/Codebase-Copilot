"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { useChatMessages } from "@/hooks/use-chats";
import { useAuthedFetch } from "@/hooks/use-authed-fetch";
import { parseSSE } from "@/lib/sse";
import { streamChatMessage } from "@/lib/api/chat";
import { toErrorMessage } from "@/lib/api/error-message";
import type { ChatStreamEvent, MetadataEvent } from "@/lib/types";
import { ChatInput } from "@/components/chat/chat-input";
import { MessageList } from "@/components/chat/message-list";

type StreamState = {
  status: "idle" | "streaming" | "error" | "done";
  tokens: string;
  metadata: MetadataEvent | null;
  message?: string;
};

export default function ChatPage() {
  const params = useParams<{ repoId: string; chatId: string }>();
  const searchParams = useSearchParams();
  const repoId = params.repoId;
  const chatId = params.chatId;

  const queryClient = useQueryClient();
  const authedFetch = useAuthedFetch();
  const messagesQuery = useChatMessages(chatId);
  const [streaming, setStreaming] = useState<StreamState>({ status: "idle", tokens: "", metadata: null });

  const canSend = streaming.status !== "streaming";
  const prefill = searchParams.get("prefill") ?? "";

  const sendMessage = async (query: string) => {
    setStreaming({ status: "streaming", tokens: "", metadata: null });

    try {
      const response = await streamChatMessage(authedFetch, chatId, { query });

      for await (const event of parseSSE<ChatStreamEvent>(response)) {
        if (event.type === "token") {
          setStreaming((prev) => ({ ...prev, status: "streaming", tokens: prev.tokens + event.content }));
          continue;
        }

        if (event.type === "metadata") {
          setStreaming((prev) => ({ ...prev, metadata: event }));
          continue;
        }

        if (event.type === "error") {
          setStreaming((prev) => ({
            status: "error",
            tokens: prev.tokens,
            metadata: prev.metadata,
            message: event.message,
          }));
          return;
        }

        if (event.type === "done") {
          setStreaming((prev) => (prev.status === "error" ? prev : { ...prev, status: "done" }));
          await queryClient.invalidateQueries({ queryKey: ["chatMessages", chatId] });
          setTimeout(() => {
            setStreaming({ status: "idle", tokens: "", metadata: null });
          }, 0);
          return;
        }
      }
    } catch (error) {
      setStreaming({
        status: "error",
        tokens: "",
        metadata: null,
        message: toErrorMessage(error),
      });
    }
  };

  const chatTitle = useMemo(() => {
    const firstUser = messagesQuery.data?.find((message) => message.role === "user");
    return firstUser?.content.slice(0, 60) ?? "Chat";
  }, [messagesQuery.data]);

  return (
    <section className="flex h-full flex-col gap-4">
      <div className="flex items-center justify-between rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] p-3">
        <div>
          <p className="text-sm font-semibold">{chatTitle}</p>
          <p className="text-xs text-[var(--text-secondary)]">Rename endpoint is not available; title is read-only.</p>
        </div>
        <Link href={`/repos/${repoId}`} className="text-xs text-[var(--accent)]">
          Back to repository
        </Link>
      </div>

      <div className="flex-1 overflow-auto rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] p-4">
        {messagesQuery.isLoading ? <p className="text-sm text-[var(--text-secondary)]">Loading messages...</p> : null}
        {messagesQuery.error ? <p className="text-sm text-[var(--error)]">{toErrorMessage(messagesQuery.error)}</p> : null}
        <MessageList messages={messagesQuery.data ?? []} streaming={streaming} />
      </div>

      <ChatInput disabled={!canSend} onSend={sendMessage} initialValue={prefill} />
    </section>
  );
}
