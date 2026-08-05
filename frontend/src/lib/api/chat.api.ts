import { apiGet, apiPost } from './client';
import { uploadToPresignedUrl } from './upload';
import type { ChatMedia, ChatMediaInput, ChatPage } from '$lib/types/chat.types';

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
 * Same-origin URL that redirects to a signed, `Content-Disposition: attachment`
 * MinIO URL. Used as a plain `<a href>`: the HTML `download` attribute is
 * ignored cross-origin, so forcing the save has to happen in the signature.
 * Auth rides the httpOnly cookie, and the server re-checks membership per click.
 */
export function chatMediaDownloadUrl(groupId: string, chatroomId: string, mediaId: string): string {
	return `/api/groups/${groupId}/chatrooms/${chatroomId}/media/${mediaId}/download`;
}

/**
 * Reissue one attachment's viewing URL after its 10-minute signature expires.
 * Per-attachment rather than per-page: history pages in older messages as the
 * user scrolls, and refetching the newest page would not contain them at all.
 */
export function refreshChatMediaUrl(
	groupId: string,
	chatroomId: string,
	mediaId: string
): Promise<ChatMedia> {
	return apiGet<ChatMedia>(
		`/groups/${groupId}/chatrooms/${chatroomId}/media/${mediaId}/url`
	);
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
		duration: dimensions?.duration ?? null,
		// Original name — the server stores it and restores it on download.
		filename: file.name || null
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
