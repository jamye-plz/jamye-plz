export type NotificationKind = 'new_topic' | 'chat_started' | 'system';

export interface AppNotification {
	id: string;
	user_id: string;
	kind: NotificationKind;
	title: string;
	body: string;
	/** URL to navigate on click */
	action_url: string | null;
	read: boolean;
	created_at: string;
}

export interface NotificationListResponse {
	items: AppNotification[];
	unread_count: number;
}

/** Web Push subscription payload sent to /api/push/subscribe */
export interface PushSubscriptionPayload {
	endpoint: string;
	p256dh: string;
	auth: string;
	/**
	 * Optional server-side binding check: when present, the backend rejects
	 * (403, writes nothing) if the session cookie belongs to a different
	 * user by the time the POST lands. Used only by the silent auto-recovery
	 * path (never by the explicit settings toggle) to atomically guard
	 * against a cross-tab account change racing the subscribe request.
	 */
	expected_user_id?: string;
}
