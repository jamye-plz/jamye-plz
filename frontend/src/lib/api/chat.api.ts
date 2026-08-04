import { apiGet, apiPost } from './client';
import { uploadToPresignedUrl } from './upload';
import type { ChatMediaInput, ChatPage } from '$lib/types/chat.types';

interface ChatPresignResponse {
	object_key: string;
	upload_url: string;
	expires_in: number;
}

export function presignChatMedia(
	groupId: string,
	chatroomId: string,
	contentType: string,
	byteSize: number
): Promise<ChatPresignResponse> {
	return apiPost<ChatPresignResponse>(`/groups/${groupId}/chatrooms/${chatroomId}/media/presign`, {
		content_type: contentType,
		byte_size: byteSize
	});
}

/**
 * Presign + PUT one file, returning the metadata the WS `send_message` frame
 * needs. `byte_size` must be the real `File.size`: it is bound into the
 * signature as Content-Length, so a mismatch makes MinIO reject the upload.
 */
export async function uploadChatMedia(
	groupId: string,
	chatroomId: string,
	file: File,
	dimensions?: { width?: number; height?: number; duration?: number }
): Promise<ChatMediaInput> {
	const { object_key, upload_url } = await presignChatMedia(
		groupId,
		chatroomId,
		file.type,
		file.size
	);
	await uploadToPresignedUrl(upload_url, file, file.type);
	return {
		object_key,
		content_type: file.type,
		width: dimensions?.width ?? null,
		height: dimensions?.height ?? null,
		byte_size: file.size,
		duration: dimensions?.duration ?? null
	};
}

export function listMessages(
	groupId: string,
	chatroomId: string,
	cursor?: string
): Promise<ChatPage> {
	const qs = cursor ? `?cursor=${encodeURIComponent(cursor)}` : '';
	return apiGet<ChatPage>(`/groups/${groupId}/chatrooms/${chatroomId}/messages${qs}`);
}

export function markChatroomRead(
	groupId: string,
	chatroomId: string,
	upTo?: string
): Promise<void> {
	// up_to = ISO timestamp of the newest message the client has rendered, so the
	// server records the receipt only up to what was actually seen.
	return apiPost<void>(`/groups/${groupId}/chatrooms/${chatroomId}/read`, {
		up_to: upTo ?? null
	});
}
