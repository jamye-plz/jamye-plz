import { apiGet, apiPost, apiDelete } from './client';
import { clearPushIntent, getPushIntent } from '$lib/push-intent';
import { signalPushRecovered } from '$lib/push-recovery-signal';
import type { PushSubscriptionPayload } from '$lib/types/notification.types';

/**
 * No service worker is registered, so there is nothing to subscribe against.
 * Signals a broken/absent SW — NOT a denied notification permission.
 */
export class NoServiceWorkerError extends Error {
	constructor() {
		super('No service worker registration');
		this.name = 'NoServiceWorkerError';
	}
}

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
 * Best-effort rollback for a subscription `recoverIntendedPush` just created
 * but must not keep — same pattern `requestAndSubscribe` uses for its own
 * rollback: race the server delete against a short timeout (never block on a
 * stalled/failed DELETE), then drop the local subscription — UNLESS intent
 * was restored while we waited. Only reachable from the marker-mismatch
 * path now (the getMe-based identity check is gone), so an intent-restored
 * skip can never preserve a DIFFERENT account's subscription.
 */
async function teardownRecoveredSub(sub: PushSubscription, userId: string): Promise<void> {
	await Promise.race([
		unsubscribePush(sub.endpoint).catch(() => {}),
		new Promise<void>((resolve) => setTimeout(resolve, 3000))
	]);
	// Re-read after the wait: the user may have toggled push back ON (up to
	// 3s to restore intent) while the DELETE/timeout race was in flight. If
	// so, the still-live browser subscription is wanted again — unsubscribing
	// it now would just force another recovery round trip for something the
	// user still wants. Any resulting row ambiguity self-heals on the next
	// app open via the existing reclaim/recovery path.
	if (getPushIntent() === userId) return;
	await sub.unsubscribe().catch(() => {});
}

/**
 * Silently re-subscribe when the CURRENT user previously expressed push
 * intent (settings toggle ON, or the reconcile backfill) but this browser
 * now holds no subscription — e.g. a `pushsubscriptionchange` rollback, or a
 * prior `requestAndSubscribe` whose registration POST failed. Never prompts:
 * permission is only READ here, never requested, so this can't surface a
 * permission dialog with no transient activation (iOS Safari would resolve
 * it 'denied' and burn the grant). Best-effort: every failure is swallowed
 * so the next authenticated app load simply retries.
 */
async function recoverIntendedPush(userId: string): Promise<void> {
	if (getPushIntent() !== userId) return; // no intent, or another account's
	// `window` guard first: this module is imported by push.api.ts consumers
	// that may run in non-browser contexts (SSR, tests) where `window` itself
	// is undefined — checking `'Notification' in window` there would throw.
	if (typeof window === 'undefined' || !('Notification' in window)) return;
	if (Notification.permission !== 'granted') {
		// Revoked (or never granted) at the browser level — stop retrying
		// forever. Re-enabling requires a fresh settings toggle, which is a
		// user gesture and can legitimately prompt.
		clearPushIntent();
		return;
	}
	try {
		const { public_key } = await getVapidPublicKey();
		// Empty key: push disabled/half-configured server-side, not the user
		// revoking intent — keep the marker so this retries once restored.
		if (!public_key) return;
		// Re-check: the user may have toggled push off (clearing the marker)
		// while we awaited the key — don't resurrect a subscription they just
		// disabled. The residual gap to requestAndSubscribe's own awaits is
		// accepted: worst case self-corrects on the next settings visit.
		if (getPushIntent() !== userId) return;
		// Re-check permission too: it can change during the key fetch await
		// above, and requestAndSubscribe's very first statement is an
		// unconditional permission request. Nothing awaits between this check
		// and that call, so a permission that dropped to 'default' or
		// 'denied' mid-fetch can never reach it and surface a real prompt
		// with no user gesture behind it.
		if (Notification.permission !== 'granted') {
			clearPushIntent();
			return;
		}
		// Bind the POST to this user server-side: passing userId as
		// expectedUserId makes the backend reject (403, writes nothing) if the
		// session cookie belongs to a DIFFERENT account by the time the POST
		// lands — e.g. a cross-tab logout->login racing this await. That
		// atomic server-side check supersedes a post-hoc client-side identity
		// verification: the server alone knows the true session identity at
		// the moment it would write. A 403 throws and is handled by the
		// existing rollback+rethrow inside requestAndSubscribe, then swallowed
		// by this function's own catch below — no extra handling needed here.
		const sub = await requestAndSubscribe(public_key, userId);
		if (!sub) return;
		// Final synchronous re-check: another tab may have toggled push off
		// (clearing the marker) at any point during the requestAndSubscribe
		// await. A cross-tab toggle-OFF must win over recovery, so tear the
		// just-created subscription back down (unless intent was restored in
		// the meantime — see teardownRecoveredSub) and skip the signal. This
		// runs in the same synchronous frame as the pulse below, so nothing
		// can invalidate intent between this check and the pulse itself.
		if (getPushIntent() !== userId) {
			await teardownRecoveredSub(sub, userId);
			return;
		}
		signalPushRecovered();
	} catch {
		// Key fetch, subscribe, or registration POST failed (including a 403
		// from a mismatched expected_user_id) — silent, the marker stays and
		// the next app load retries.
	}
}

/**
 * Re-claim any existing browser push subscription for the CURRENT user.
 * Called on every authenticated app load (not just from Settings) so that when
 * a different account signs in on this browser — via a 401 re-login or the
 * OAuth flow that never touches Settings — the backend subscription row is
 * reassigned to them (upsert reassigns user_id), instead of the previous
 * user's pushes continuing to display here. Best-effort: never throws.
 */
export async function reclaimPushForCurrentUser(userId: string): Promise<void> {
	try {
		const reg = await getActiveRegistration();
		if (!reg) return;
		const existing = await reg.pushManager.getSubscription();
		if (!existing) {
			// Auto-recovery path (D4/T3): this is NOT a failed reclaim of an
			// existing subscription, so it must stay OUTSIDE the inner
			// try/catch below — a recovery failure must never trigger the
			// detachPushOnLogout teardown meant for that different case.
			await recoverIntendedPush(userId);
			return;
		}
		try {
			// The key fetch is INSIDE this handler: a transient 5xx/network failure
			// here is itself a failed reclaim and must trigger the same teardown,
			// otherwise a previous account's row stays bound to this browser.
			const { public_key } = await getVapidPublicKey();
			if (!public_key) {
				// VAPID temporarily disabled/half-configured: we can't recreate
				// under a key, but re-post the existing subscription so its backend
				// row is reassigned to the CURRENT user (no key needed). Otherwise a
				// previous account's row would deliver here once keys are restored.
				await reconcilePush(existing);
				return;
			}
			// Reassign to the current user, recreating the subscription if it was
			// signed under a rotated VAPID key (reconcileOrRecreate compares
			// applicationServerKey to the current public key).
			await reconcileOrRecreate(public_key);
		} catch {
			// Reclaim failed (key fetch or reconcile: transient 401/5xx/network):
			// tear the local subscription down so a PREVIOUS account's still-active
			// backend row can't keep delivering that user's pushes to whoever is
			// signed in here now. Better no push than cross-account push.
			await detachPushOnLogout();
		}
	} catch {
		// Best-effort — never throws.
	}
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
		// Server delete and browser unsubscribe are independent: if the server
		// call fails (transient 5xx/network) OR stalls (backend deploy/network
		// hang), we must STILL drop the live browser subscription and let logout
		// proceed — otherwise the logout button stays disabled and this device
		// keeps showing the previous account's pushes. Bound the server delete
		// with a short timeout; it is best-effort (a leftover row is pruned on
		// its next send once the browser subscription is gone).
		await Promise.race([
			unsubscribePush(sub.endpoint).catch(() => {}),
			new Promise<void>((resolve) => setTimeout(resolve, 3000))
		]);
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
 *
 * `expectedUserId` is optional and used only by the silent auto-recovery
 * path (never the explicit settings toggle): when set, the backend rejects
 * the POST with 403 (writing nothing) if the session cookie doesn't belong
 * to that user by the time it lands — an atomic guard against a cross-tab
 * account change racing this request.
 */
export async function requestAndSubscribe(
	vapidPublicKey: string,
	expectedUserId?: string
): Promise<PushSubscription | null> {
	// Ask for permission BEFORE any other await. iOS Safari (home-screen PWA)
	// only honours `requestPermission()` while the tap's transient activation is
	// still live; awaiting anything first can drop it, and the call then resolves
	// 'denied' without ever showing the prompt. Already-granted permission
	// resolves immediately, so the non-gesture callers (reconcile paths, which
	// only run when a subscription — hence a grant — already exists) are safe.
	const permission = await Notification.requestPermission();
	if (permission !== 'granted') return null;

	const reg = await getActiveRegistration();
	// Distinct from a permission refusal: the browser is willing, but the app has
	// no service worker to attach the subscription to. Callers must not report
	// this as "notifications are blocked" — that sends the user to browser
	// settings that are already correct.
	if (!reg) throw new NoServiceWorkerError();

	const sub = await reg.pushManager.subscribe({
		userVisibleOnly: true,
		applicationServerKey: urlBase64ToUint8Array(vapidPublicKey)
	});

	const raw = sub.toJSON();
	const keys = raw.keys as { p256dh: string; auth: string };
	try {
		await subscribePush({
			endpoint: sub.endpoint,
			p256dh: keys.p256dh,
			auth: keys.auth,
			expected_user_id: expectedUserId
		});
	} catch (err) {
		// Registration failed (rejected, or the server committed but the response
		// was lost). Roll the local subscription back so we never leave a live
		// browser subscription the UI reports as off — which would keep
		// delivering, or be silently reclaimed later. Both steps best-effort;
		// rethrow so the caller still surfaces the failure.
		await Promise.race([
			unsubscribePush(sub.endpoint).catch(() => {}),
			new Promise<void>((resolve) => setTimeout(resolve, 3000))
		]);
		await sub.unsubscribe().catch(() => {});
		throw err;
	}

	return sub;
}
