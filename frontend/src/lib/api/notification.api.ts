import { apiGet, apiPost } from './client';
import type { NotificationListResponse } from '$lib/types/notification.types';

export function listNotifications(): Promise<NotificationListResponse> {
	return apiGet<NotificationListResponse>('/notifications');
}

export function markNotificationRead(id: string): Promise<void> {
	return apiPost<void>(`/notifications/${id}/read`);
}
