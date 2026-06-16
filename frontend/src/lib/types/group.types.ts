export interface Group {
	id: string;
	name: string;
	owner_id: string;
	max_members: number;
	member_count: number;
	main_chatroom_id: string;
	created_at: string;
}

export interface GroupMember {
	user_id: string;
	nickname: string;
	avatar_url: string | null;
	role: 'owner' | 'member';
	joined_at: string;
}

export interface Invite {
	id: string;
	code: string;
	group_id: string;
	expires_at: string | null;
	max_uses: number | null;
	used_count: number;
	invite_url: string;
}
