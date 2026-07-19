import { apiGet, apiPost, apiPatch, apiDelete } from './client';
import type { Group, GroupMember } from '$lib/types/group.types';
import type { Invite } from '$lib/types/group.types';

export function listGroups(): Promise<Group[]> {
	return apiGet<Group[]>('/groups');
}

export function getMembers(groupId: string): Promise<GroupMember[]> {
	return apiGet<GroupMember[]>(`/groups/${groupId}/members`);
}

export function getGroup(id: string): Promise<Group> {
	return apiGet<Group>(`/groups/${id}`);
}

export function createGroup(name: string): Promise<Group> {
	return apiPost<Group>('/groups', { name });
}

/** Rename a group. Owner only — the backend rejects non-owners with 403. */
export function renameGroup(id: string, name: string): Promise<Group> {
	return apiPatch<Group>(`/groups/${id}`, { name });
}

/** Soft-delete a group. Owner only. */
export function deleteGroup(id: string): Promise<void> {
	return apiDelete<void>(`/groups/${id}`);
}

/**
 * Remove a member from a group. When the owner calls this with their own
 * `user_id`, the backend rejects it with 409 (owner must transfer ownership
 * before leaving). When a non-owner targets their own `user_id`, this is a
 * self-initiated leave.
 */
export function removeMember(groupId: string, userId: string): Promise<void> {
	return apiDelete<void>(`/groups/${groupId}/members/${userId}`);
}

/** Leave a group — a thin, readable alias over `removeMember` for self-removal call sites. */
export function leaveGroup(groupId: string, userId: string): Promise<void> {
	return removeMember(groupId, userId);
}

/** Transfer group ownership to another member. Owner only. */
export function transferOwnership(groupId: string, userId: string): Promise<void> {
	return apiPatch<void>(`/groups/${groupId}/members/${userId}`, { role: 'owner' });
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
