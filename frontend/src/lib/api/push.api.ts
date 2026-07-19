import { apiGet, apiPost, apiDelete } from './client';
import type { PushSubscriptionPayload } from '$lib/types/notification.types';

export function subscribePush(payload: PushSubscriptionPayload): Promise<void> {
	return apiPost<void>('/push/subscribe', payload);
}

/**
 * Unsubscribe on the server. Pass an `endpoint` to remove just this device's
 * subscription (so other devices keep receiving pushes); omit it to remove all
 * of the current user's subscriptions.
 */
export function unsubscribePush(endpoint?: string): Promise<void> {
	return apiDelete<void>('/push/subscribe', endpoint ? { endpoint } : undefined);
}

/** Re-register an already-present browser subscription for the current user. */
export function reconcilePush(sub: PushSubscription): Promise<void> {
	const keys = sub.toJSON().keys as { p256dh: string; auth: string };
	return subscribePush({ endpoint: sub.endpoint, p256dh: keys.p256dh, auth: keys.auth });
}

/**
 * Detach this browser's push subscription on logout so the next account to use
 * the browser doesn't inherit the previous user's active subscription row (the
 * server keys delivery by user_id, so a leftover row would keep sending the old
 * owner's pushes to whoever is now on this device). Best-effort: never throws.
 */
export async function detachPushOnLogout(): Promise<void> {
	try {
		if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;
		const reg = await navigator.serviceWorker.ready;
		const sub = await reg.pushManager.getSubscription();
		if (!sub) return;
		await unsubscribePush(sub.endpoint);
		await sub.unsubscribe();
	} catch {
		// Logout must proceed regardless of push cleanup failures.
	}
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
