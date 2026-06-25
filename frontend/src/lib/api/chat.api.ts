import { apiGet, apiPost } from './client';
import type { ChatPage } from '$lib/types/chat.types';

export function listMessages(
	groupId: string,
	chatroomId: string,
	cursor?: string
): Promise<ChatPage> {
	const qs = cursor ? `?cursor=${encodeURIComponent(cursor)}` : '';
	return apiGet<ChatPage>(`/groups/${groupId}/chatrooms/${chatroomId}/messages${qs}`);
}

export function markChatroomRead(groupId: string, chatroomId: string): Promise<void> {
	return apiPost<void>(`/groups/${groupId}/chatrooms/${chatroomId}/read`);
}
