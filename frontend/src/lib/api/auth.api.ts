import { apiGet, apiPost, apiPatch } from './client';
import type { User } from '$lib/types/user.types';

export function getMe(): Promise<User> {
	return apiGet<User>('/me');
}

export function patchMe(payload: { nickname?: string; avatar_url?: string }): Promise<User> {
	return apiPatch<User>('/me', payload);
}

export function logout(): Promise<void> {
	return apiPost<void>('/auth/logout');
}

// OAuth login URLs — just redirect, no fetch needed
export function getOAuthLoginUrl(provider: 'kakao' | 'google'): string {
	return `/api/auth/${provider}`;
}
