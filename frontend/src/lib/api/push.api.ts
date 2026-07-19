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

/**
 * The active SW registration, or null when there is none. Uses
 * `getRegistration()` (which resolves to undefined without a registration)
 * rather than `navigator.serviceWorker.ready` — `ready` never settles when no
 * SW is registered (e.g. dev, where PWA dev mode is off), which would hang any
 * `await` on it.
 */
async function getActiveRegistration(): Promise<ServiceWorkerRegistration | null> {
	if (!('serviceWorker' in navigator) || !('PushManager' in window)) return null;
	return (await navigator.serviceWorker.getRegistration()) ?? null;
}

/** Whether an existing subscription was created under the given VAPID key. */
function subscriptionUsesKey(sub: PushSubscription, vapidPublicKey: string): boolean {
	const current = sub.options.applicationServerKey;
	if (!current) return false;
	const a = new Uint8Array(current as ArrayBuffer);
	const b = urlBase64ToUint8Array(vapidPublicKey);
	if (a.length !== b.length) return false;
	return a.every((byte, i) => byte === b[i]);
}

/** Re-register an already-present browser subscription for the current user. */
export function reconcilePush(sub: PushSubscription): Promise<void> {
	const keys = sub.toJSON().keys as { p256dh: string; auth: string };
	return subscribePush({ endpoint: sub.endpoint, p256dh: keys.p256dh, auth: keys.auth });
}

/**
 * Reconcile the current browser subscription for the active user, returning
 * whether push ends up enabled. If the browser holds a subscription created
 * under a *different* VAPID key (key rotation), it is dropped and recreated
 * with the current key — otherwise the backend (signing with the new private
 * key) would produce sends the push service rejects while the UI shows "on".
 */
export async function reconcileOrRecreate(vapidPublicKey: string): Promise<boolean> {
	const reg = await getActiveRegistration();
	if (!reg) return false;
	const existing = await reg.pushManager.getSubscription();
	if (!existing) return false;
	if (subscriptionUsesKey(existing, vapidPublicKey)) {
		await reconcilePush(existing);
		return true;
	}
	// Stale key — recreate under the current one.
	await existing.unsubscribe();
	const fresh = await requestAndSubscribe(vapidPublicKey);
	return fresh !== null;
}

/**
 * Detach this browser's push subscription on logout so the next account to use
 * the browser doesn't inherit the previous user's active subscription row (the
 * server keys delivery by user_id, so a leftover row would keep sending the old
 * owner's pushes to whoever is now on this device). Best-effort: never throws,
 * and never hangs when no SW is registered.
 */
export async function detachPushOnLogout(): Promise<void> {
	try {
		const reg = await getActiveRegistration();
		if (!reg) return;
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
	const reg = await getActiveRegistration();
	if (!reg) return null;

	const permission = await Notification.requestPermission();
	if (permission !== 'granted') return null;

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
