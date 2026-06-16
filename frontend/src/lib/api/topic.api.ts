import { apiGet, apiPost, apiPatch, apiPut, apiFetch } from './client';
import type { Topic, TopicPage, TopicTag, PresignResponse } from '$lib/types/topic.types';

export function listTopics(groupId: string, cursor?: string, date?: string): Promise<TopicPage> {
	const params = new URLSearchParams();
	if (cursor) params.set('cursor', cursor);
	if (date) params.set('date', date);
	const qs = params.toString();
	return apiGet<TopicPage>(`/groups/${groupId}/topics${qs ? `?${qs}` : ''}`);
}

export function getTopic(id: string): Promise<Topic> {
	return apiGet<Topic>(`/topics/${id}`);
}

export function seedTopic(groupId: string, title: string): Promise<Topic> {
	return apiPost<Topic>(`/groups/${groupId}/topics`, { title });
}

export function enrichTopic(id: string, body: string): Promise<Topic> {
	return apiPatch<Topic>(`/topics/${id}`, { body });
}

export function presignMedia(
	topicId: string,
	contentType: string,
	byteSize: number
): Promise<PresignResponse> {
	return apiPost<PresignResponse>(`/topics/${topicId}/media/presign`, {
		content_type: contentType,
		byte_size: byteSize
	});
}

export function confirmMedia(
	topicId: string,
	objectKey: string,
	width: number | null,
	height: number | null,
	contentType: string
): Promise<Topic> {
	return apiPost<Topic>(`/topics/${topicId}/media`, {
		object_key: objectKey,
		width,
		height,
		content_type: contentType
	});
}

export function putTags(topicId: string, tags: TopicTag[]): Promise<Topic> {
	return apiPut<Topic>(`/topics/${topicId}/tags`, { tags });
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
