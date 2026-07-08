"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCreateChatSession, useDeleteChat, useChats } from "@/hooks/use-chats";
import { useRepo, useSuggestions } from "@/hooks/use-repos";
import { RepoHeader } from "@/components/repo/repo-header";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { toErrorMessage } from "@/lib/api/error-message";

export default function RepoDetailPage() {
  const params = useParams<{ repoId: string }>();
  const repoId = params.repoId;
  const router = useRouter();

  const repoQuery = useRepo(repoId);
  const chatsQuery = useChats(repoId);
  const suggestionsQuery = useSuggestions(repoId);
  const createChat = useCreateChatSession(repoId);
  const deleteChat = useDeleteChat(repoId);

  const createNewChat = async () => {
    const session = await createChat.mutateAsync();
    router.push(`/repos/${repoId}/chat/${session.chat_id}`);
  };

  const handleSuggestionClick = async (question: string) => {
    const session = await createChat.mutateAsync();
    router.push(`/repos/${repoId}/chat/${session.chat_id}?prefill=${encodeURIComponent(question)}`);
  };

  if (repoQuery.isLoading) {
    return <p className="text-sm text-[var(--text-secondary)]">Loading repository...</p>;
  }

  if (repoQuery.error || !repoQuery.data) {
    return <p className="text-sm text-[var(--error)]">{toErrorMessage(repoQuery.error)}</p>;
  }

  const repo = repoQuery.data;
  const canCreateChat = repo.status === "ready";

  return (
    <section className="space-y-4">
      <RepoHeader repo={repo} />

      <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] p-4">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-base font-semibold">Chats</h3>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => void createNewChat()}
              disabled={!canCreateChat || createChat.isPending}
              className="rounded-md bg-[var(--accent)] px-3 py-1.5 text-sm text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              New chat
            </button>
            <Link href={`/repos/${repoId}/eval`} className="rounded-md border border-[var(--border-subtle)] px-3 py-1.5 text-sm">
              Evaluation
            </Link>
          </div>
        </div>

        {!canCreateChat ? (
          <p className="mb-3 text-xs text-[var(--warning)]">New chat is disabled until repository status is ready.</p>
        ) : null}

        {chatsQuery.error ? <p className="mb-2 text-sm text-[var(--error)]">{toErrorMessage(chatsQuery.error)}</p> : null}

        <div className="space-y-2">
          {chatsQuery.data?.map((chat) => (
            <div key={chat.id} className="flex items-center justify-between rounded border border-[var(--border-subtle)] bg-[var(--bg-primary)] p-2">
              <Link href={`/repos/${repoId}/chat/${chat.id}`} className="flex-1 truncate text-sm">
                {chat.title ?? "Untitled chat"}
              </Link>
              <ConfirmDialog
                title="Delete chat"
                description="This removes all messages in the chat."
                confirmLabel="Delete"
                onConfirm={() => deleteChat.mutateAsync(chat.id).then(() => Promise.resolve())}
                trigger={<button className="text-xs text-[var(--text-secondary)] hover:text-[var(--error)]">Delete</button>}
              />
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] p-4">
        <h3 className="mb-2 text-base font-semibold">Suggested questions</h3>
        <div className="flex flex-wrap gap-2">
          {suggestionsQuery.data?.questions.map((question) => (
            <button
              key={question}
              type="button"
              onClick={() => void handleSuggestionClick(question)}
              disabled={!canCreateChat}
              className="rounded-full border border-[var(--border-subtle)] px-3 py-1 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] disabled:opacity-60"
            >
              {question}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
