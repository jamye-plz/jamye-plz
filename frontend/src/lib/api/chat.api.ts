import { apiGet } from './client';
import type { ChatPage } from '$lib/types/chat.types';

export function listMessages(
	groupId: string,
	chatroomId: string,
	cursor?: string
): Promise<ChatPage> {
	const qs = cursor ? `?cursor=${encodeURIComponent(cursor)}` : '';
	return apiGet<ChatPage>(`/groups/${groupId}/chatrooms/${chatroomId}/messages${qs}`);
}
