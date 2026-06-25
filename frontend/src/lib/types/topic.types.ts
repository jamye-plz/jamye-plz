export type TopicStatus = 'seed' | 'enriched';

export interface TopicTag {
	tag: string;
	source: 'ai' | 'user';
}

export interface TopicMedia {
	id: string;
	object_key: string;
	url: string;
	width: number | null;
	height: number | null;
	content_type: string;
}

export interface Topic {
	id: string;
	group_id: string;
	author_id: string;
	author_nickname: string;
	author_avatar_url: string | null;
	title: string;
	body: string | null;
	status: TopicStatus;
	tags: TopicTag[];
	media: TopicMedia[];
	chatroom_id: string;
	created_at: string;
	updated_at: string;
	unread: boolean;
}

export interface TopicPage {
	items: Topic[];
	next_cursor: string | null;
}

export interface TopicDates {
	dates: string[];
	today: string;
}

export interface PresignResponse {
	object_key: string;
	upload_url: string;
	expires_in: number;
}
