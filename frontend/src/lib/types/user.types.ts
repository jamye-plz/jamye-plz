export interface User {
	id: string;
	provider: string;
	nickname: string;
	avatar_url: string | null;
	created_at: string;
}
