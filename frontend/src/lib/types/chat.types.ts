export type MessageType = 'text' | 'system';

export interface ChatMessage {
	id: string;
	chatroom_id: string;
	sender_id: string | null;
	sender_nickname?: string;
	sender_avatar_url?: string | null;
	body: string;
	type: MessageType;
	created_at: string;
	// For optimistic messages awaiting ack
	client_msg_id?: string;
	pending?: boolean;
}

export interface ChatPage {
	items: ChatMessage[];
	next_cursor: string | null;
}

// WebSocket protocol types
export type WsClientMessage =
	| { type: 'join_room'; chatroom_id: string }
	| { type: 'leave_room'; chatroom_id: string }
	| { type: 'send_message'; chatroom_id: string; body: string; client_msg_id: string };

export type WsServerMessage =
	| { type: 'message'; id: string; chatroom_id: string; sender_id: string; body: string; message_type: MessageType; created_at: string }
	| { type: 'message_ack'; client_msg_id: string; message_id: string }
	| { type: 'system'; chatroom_id: string; body: string }
	| { type: 'error'; code: string; detail: string };
