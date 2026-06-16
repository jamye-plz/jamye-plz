import { apiGet } from './client';
import type { ChatPage } from '$lib/types/chat.types';

export function listMessages(chatroomId: string, cursor?: string): Promise<ChatPage> {
	const qs = cursor ? `?cursor=${encodeURIComponent(cursor)}` : '';
	return apiGet<ChatPage>(`/chatrooms/${chatroomId}/messages${qs}`);
}
