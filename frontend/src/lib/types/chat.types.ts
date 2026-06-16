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

// WebSocket protocol types — must match backend/app/main.py /api/ws handler.
export type WsClientMessage =
	| { type: 'join'; chatroom_id: string }
	| { type: 'send_message'; chatroom_id: string; body: string; client_msg_id: string }
	| { type: 'ack'; message_id: string };

export type WsServerMessage =
	| {
			type: 'message';
			id: string;
			chatroom_id: string;
			sender_id: string | null;
			client_msg_id: string | null;
			body: string;
			msg_type: MessageType;
			created_at: string;
	  }
	| { type: 'duplicate'; client_msg_id: string }
	| { type: 'system'; body: string }
	| { type: 'error'; detail: string };
