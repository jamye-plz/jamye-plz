import { apiGet, apiPost, apiDelete } from './client';
import type { PushSubscriptionPayload } from '$lib/types/notification.types';

export function subscribePush(payload: PushSubscriptionPayload): Promise<void> {
	return apiPost<void>('/push/subscribe', payload);
}

export function unsubscribePush(): Promise<void> {
	return apiDelete<void>('/push/subscribe');
}

/** Fetch the server's VAPID public key. Empty string means push is disabled. */
export function getVapidPublicKey(): Promise<{ public_key: string }> {
	return apiGet<{ public_key: string }>('/push/vapid-public-key');
}

/**
 * Convert a base64url-encoded VAPID public key (backend/spec format) into the
 * Uint8Array that `PushManager.subscribe`'s `applicationServerKey` expects.
 * Passing the raw base64url string works in Chrome but throws in Safari, so
 * this conversion is mandatory for cross-browser support.
 */
export function urlBase64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
	const padding = '='.repeat((4 - (base64.length % 4)) % 4);
	const base64Safe = (base64 + padding).replace(/-/g, '+').replace(/_/g, '/');
	const rawData = atob(base64Safe);
	const outputArray = new Uint8Array(new ArrayBuffer(rawData.length));
	for (let i = 0; i < rawData.length; i++) {
		outputArray[i] = rawData.charCodeAt(i);
	}
	return outputArray;
}

/**
 * Request push permission and register a subscription with the given VAPID
 * public key (base64url-encoded). Returns the PushSubscription, or null if
 * the browser denies permission or lacks Push API support.
 */
export async function requestAndSubscribe(
	vapidPublicKey: string
): Promise<PushSubscription | null> {
	if (!('serviceWorker' in navigator) || !('PushManager' in window)) return null;

	const permission = await Notification.requestPermission();
	if (permission !== 'granted') return null;

	const reg = await navigator.serviceWorker.ready;
	const sub = await reg.pushManager.subscribe({
		userVisibleOnly: true,
		applicationServerKey: urlBase64ToUint8Array(vapidPublicKey)
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
