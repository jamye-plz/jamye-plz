import { apiGet, apiPost } from './client';
import type { Group } from '$lib/types/group.types';
import type { Invite } from '$lib/types/group.types';

export function listGroups(): Promise<Group[]> {
	return apiGet<Group[]>('/groups');
}

export function getGroup(id: string): Promise<Group> {
	return apiGet<Group>(`/groups/${id}`);
}

export function createGroup(name: string): Promise<Group> {
	return apiPost<Group>('/groups', { name });
}

export interface CreateInviteParams {
	expires_at?: string | null;
	max_uses?: number | null;
}

export function createInvite(groupId: string, params?: CreateInviteParams): Promise<Invite> {
	return apiPost<Invite>(`/groups/${groupId}/invites`, params ?? {});
}

export interface JoinResult {
	group_id: string;
	membership_id?: string;
	joined: boolean;
}

export function joinByCode(code: string): Promise<JoinResult> {
	return apiPost<JoinResult>(`/invites/${code}/join`);
}
