/**
 * Records that the signed-in user WANTS push notifications enabled on this
 * device. This is an INTENT record ("who wants push here"), NOT a
 * subscription-state cache — it says nothing about whether a live
 * PushSubscription currently exists. It is written only from main-thread
 * settings paths (the toggle, and the settings onMount backfill); the
 * service worker never writes it.
 *
 * Framework-free on purpose: no `$app/*`, `$lib/*`, or svelte imports, so
 * this module is importable directly by `bun test`. Every accessor is a
 * no-op / returns null when `localStorage` is unavailable (SSR, service
 * worker, build) and swallows any thrown storage error (Safari private
 * mode, storage disabled).
 */
export const PUSH_INTENT_KEY = 'jamye:push-intent';

/** The user id that last expressed push intent on this device, or null. */
export function getPushIntent(): string | null {
	if (typeof localStorage === 'undefined') return null;
	try {
		return localStorage.getItem(PUSH_INTENT_KEY);
	} catch {
		return null;
	}
}

/** Record that `userId` wants push enabled on this device. */
export function setPushIntent(userId: string): void {
	if (typeof localStorage === 'undefined') return;
	try {
		localStorage.setItem(PUSH_INTENT_KEY, userId);
	} catch {
		// Safari private mode / storage disabled — nothing we can do.
	}
}

/** Remove the push-intent marker from this device. */
export function clearPushIntent(): void {
	if (typeof localStorage === 'undefined') return;
	try {
		localStorage.removeItem(PUSH_INTENT_KEY);
	} catch {
		// Safari private mode / storage disabled — nothing we can do.
	}
}
