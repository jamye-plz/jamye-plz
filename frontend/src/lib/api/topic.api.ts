import { apiGet, apiPost, apiPatch, apiPut, apiFetch } from './client';
import type {
	Topic,
	TopicPage,
	TopicTag,
	TopicDates,
	PresignResponse
} from '$lib/types/topic.types';

export function listTopics(groupId: string, cursor?: string, date?: string): Promise<TopicPage> {
	const params = new URLSearchParams();
	if (cursor) params.set('cursor', cursor);
	if (date) params.set('date', date);
	const qs = params.toString();
	return apiGet<TopicPage>(`/groups/${groupId}/topics${qs ? `?${qs}` : ''}`);
}

export function getTopicDates(groupId: string): Promise<TopicDates> {
	return apiGet<TopicDates>(`/groups/${groupId}/topics/dates`);
}

export function getTopic(groupId: string, id: string): Promise<Topic> {
	return apiGet<Topic>(`/groups/${groupId}/topics/${id}`);
}

export function seedTopic(groupId: string, title: string): Promise<Topic> {
	return apiPost<Topic>(`/groups/${groupId}/topics`, { title });
}

export function enrichTopic(groupId: string, id: string, body: string): Promise<Topic> {
	return apiPatch<Topic>(`/groups/${groupId}/topics/${id}`, { body });
}

export function presignMedia(
	groupId: string,
	topicId: string,
	contentType: string,
	byteSize: number
): Promise<PresignResponse> {
	return apiPost<PresignResponse>(`/groups/${groupId}/topics/${topicId}/media/presign`, {
		content_type: contentType,
		byte_size: byteSize
	});
}

export function confirmMedia(
	groupId: string,
	topicId: string,
	objectKey: string,
	width: number | null,
	height: number | null,
	contentType: string
): Promise<Topic> {
	return apiPost<Topic>(`/groups/${groupId}/topics/${topicId}/media/confirm`, {
		object_key: objectKey,
		width,
		height,
		content_type: contentType
	});
}

export function putTags(groupId: string, topicId: string, tags: TopicTag[]): Promise<Topic> {
	return apiPut<Topic>(`/groups/${groupId}/topics/${topicId}/tags`, { tags });
}

/** Direct PUT to presigned MinIO URL (no /api prefix, no credentials header) */
export async function uploadToPresignedUrl(
	uploadUrl: string,
	file: Blob,
	contentType: string
): Promise<void> {
	const res = await fetch(uploadUrl, {
		method: 'PUT',
		body: file,
		headers: { 'Content-Type': contentType }
	});
	if (!res.ok) {
		throw new Error(`MinIO upload failed: ${res.status}`);
	}
}

// Re-export apiFetch for multipart — not used directly in this module but available
export { apiFetch };
