import { apiJson, apiStream, type AuthedFetch } from "@/lib/api/base";
import type { ChatListItem, CreateSessionRequest, CreateSessionResponse, MessageResponse, SendMessageRequest } from "@/lib/types";

export function createChatSession(authedFetch: AuthedFetch, body: CreateSessionRequest) {
  return apiJson<CreateSessionResponse>(authedFetch, "/api/chat/session", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function streamChatMessage(authedFetch: AuthedFetch, chatId: string, body: SendMessageRequest) {
  return apiStream(authedFetch, `/api/chat/${chatId}/message/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
}

export function getChatMessages(authedFetch: AuthedFetch, chatId: string) {
  return apiJson<MessageResponse[]>(authedFetch, `/api/chat/${chatId}/messages`);
}

export function getChatsForRepo(authedFetch: AuthedFetch, repoId: string) {
  return apiJson<ChatListItem[]>(authedFetch, `/api/chat/list?repo_id=${encodeURIComponent(repoId)}`);
}

export function deleteChat(authedFetch: AuthedFetch, chatId: string) {
  return apiJson<{ message: string }>(authedFetch, `/api/chat/${chatId}`, {
    method: "DELETE",
  });
}

