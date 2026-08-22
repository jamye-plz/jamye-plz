export type MessageType = 'text' | 'system';

/** Allowed chat attachment MIME types — must match backend storage.CHAT_MEDIA_MIME_TYPES. */
export const IMAGE_MIME_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif'] as const;
export const VIDEO_MIME_TYPES = ['video/mp4'] as const;
/** One per browser family: Chrome records webm/opus, iOS Safari mp4/AAC, Firefox ogg. */
export const AUDIO_MIME_TYPES = ['audio/webm', 'audio/mp4', 'audio/ogg'] as const;
export const CHAT_MEDIA_MIME_TYPES: readonly string[] = [
	...IMAGE_MIME_TYPES,
	...VIDEO_MIME_TYPES,
	...AUDIO_MIME_TYPES
];

/** Caps mirror the backend; the server re-validates, so these are UX only. */
export const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
export const MAX_VIDEO_BYTES = 50 * 1024 * 1024;
export const MAX_AUDIO_BYTES = 15 * 1024 * 1024;
export const MAX_MEDIA_PER_MESSAGE = 4;
/** Client-side recording cap. Opus at voice bitrate keeps 5 min around 1 MB. */
export const MAX_RECORDING_SECONDS = 300;

export function isVideo(contentType: string): boolean {
	return contentType.startsWith('video/');
}

export function isAudio(contentType: string): boolean {
	return contentType.startsWith('audio/');
}

export function maxBytesFor(contentType: string): number {
	if (isVideo(contentType)) return MAX_VIDEO_BYTES;
	if (isAudio(contentType)) return MAX_AUDIO_BYTES;
	return MAX_IMAGE_BYTES;
}

/** An attachment as returned by the server (url is a short-TTL presigned GET). */
export interface ChatMedia {
	id: string;
	url: string;
	content_type: string;
	width?: number | null;
	height?: number | null;
	byte_size?: number | null;
	duration?: number | null;
	filename?: string | null;
	/** Async STT (audio only): 'pending' | 'done' | 'failed'; null = disabled/not audio. */
	transcript?: string | null;
	transcript_status?: string | null;
}

/**
 * Placeholder for an attachment on a message that is still awaiting its ack.
 * The bytes are already uploaded, but only the server can issue a read URL, so
 * the bubble renders a correctly-sized skeleton until the real media arrives.
 */
export interface PendingMedia {
	content_type: string;
	width?: number | null;
	height?: number | null;
}

/** An attachment as sent to the server on the send_message frame. */
export interface ChatMediaInput {
	object_key: string;
	content_type: string;
	width?: number | null;
	height?: number | null;
	byte_size?: number | null;
	duration?: number | null;
	/** Original client-side name, restored on download. */
	filename?: string | null;
}

export interface ChatMessage {
	id: string;
	chatroom_id: string;
	sender_id: string | null;
	sender_nickname?: string;
	sender_avatar_url?: string | null;
	body: string;
	type: MessageType;
	created_at: string;
	/** Server always sends an array (empty when there are no attachments). */
	media?: ChatMedia[];
	// For optimistic messages awaiting ack
	client_msg_id?: string;
	pending?: boolean;
	/** Set only while pending — drives the skeleton until the ack brings real URLs. */
	pendingMedia?: PendingMedia[];
}

export interface ChatPage {
	items: ChatMessage[];
	next_cursor: string | null;
}

// WebSocket protocol types — must match backend/app/main.py /api/ws handler.
export type WsClientMessage =
	| { type: 'join'; chatroom_id: string }
	| { type: 'ping' }
	| {
			type: 'send_message';
			chatroom_id: string;
			body: string;
			client_msg_id: string;
			/** Omitted for text-only messages. Server allows an empty body when this is present. */
			media?: ChatMediaInput[];
	  }
	| { type: 'ack'; message_id: string };

export type WsServerMessage =
	| { type: 'pong' }
	| { type: 'joined'; chatroom_id: string }
	| {
			type: 'message';
			id: string;
			chatroom_id: string;
			sender_id: string | null;
			sender_nickname?: string | null;
			sender_avatar_url?: string | null;
			client_msg_id: string | null;
			body: string;
			msg_type: MessageType;
			created_at: string;
			media?: ChatMedia[];
	  }
	| { type: 'duplicate'; client_msg_id: string }
	| {
			/** Async STT result for an audio attachment (worker → Redis → backend bridge). */
			type: 'transcript';
			chatroom_id: string;
			message_id: string;
			media_id: string;
			status: 'done' | 'failed';
			transcript: string | null;
	  }
	| { type: 'system'; id?: string; chatroom_id?: string; body: string; created_at?: string }
	| { type: 'error'; detail: string };
