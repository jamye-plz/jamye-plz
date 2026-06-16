import { apiPost, apiDelete } from './client';
import type { PushSubscriptionPayload } from '$lib/types/notification.types';

export function subscribePush(payload: PushSubscriptionPayload): Promise<void> {
	return apiPost<void>('/push/subscribe', payload);
}

export function unsubscribePush(): Promise<void> {
	return apiDelete<void>('/push/subscribe');
}

/**
 * Helper: request push permission and register subscription.
 * Returns the PushSubscription or null if denied/unsupported.
 * TODO(oma-deferred): wire VAPID public key from env when backend is provisioned.
 */
export async function requestAndSubscribe(vapidPublicKey: string): Promise<PushSubscription | null> {
	if (!('serviceWorker' in navigator) || !('PushManager' in window)) return null;

	const permission = await Notification.requestPermission();
	if (permission !== 'granted') return null;

	const reg = await navigator.serviceWorker.ready;
	const sub = await reg.pushManager.subscribe({
		userVisibleOnly: true,
		applicationServerKey: vapidPublicKey
	});

	const raw = sub.toJSON();
	const keys = raw.keys as { p256dh: string; auth: string };
	await subscribePush({
		endpoint: sub.endpoint,
		p256dh: keys.p256dh,
		auth: keys.auth
	});

	return sub;
}
