"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createChatSession, deleteChat, getChatMessages, getChatsForRepo } from "@/lib/api/chat";
import { useAuthedFetch } from "@/hooks/use-authed-fetch";

export function useChats(repoId: string) {
  const authedFetch = useAuthedFetch();
  return useQuery({
    queryKey: ["chats", repoId],
    queryFn: () => getChatsForRepo(authedFetch, repoId),
    enabled: Boolean(repoId),
  });
}

export function useChatMessages(chatId: string) {
  const authedFetch = useAuthedFetch();
  return useQuery({
    queryKey: ["chatMessages", chatId],
    queryFn: () => getChatMessages(authedFetch, chatId),
    enabled: Boolean(chatId),
  });
}

export function useCreateChatSession(repoId: string) {
  const authedFetch = useAuthedFetch();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => createChatSession(authedFetch, { repo_id: repoId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["chats", repoId] });
    },
  });
}

export function useDeleteChat(repoId: string) {
  const authedFetch = useAuthedFetch();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (chatId: string) => deleteChat(authedFetch, chatId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["chats", repoId] });
    },
  });
}

