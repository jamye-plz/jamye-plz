/**
 * Records that the signed-in user WANTS push notifications enabled on this
 * device. This is an INTENT record ("who wants push here"), NOT a
 * subscription-state cache — it says nothing about whether a live
 * PushSubscription currently exists. It is written only from main-thread
 * settings paths (the toggle, and the settings onMount backfill); the
 * service worker never writes it.
 *
 * Three possible stored values under the same key: `<userId>` (that user
 * currently wants push ON), `off:<userId>` (that user explicitly opted
 * OUT), or absent (unknown — a legacy user who never touched the toggle).
 * The off sentinel exists so a concurrent-tab backfill can't resurrect an
 * explicit opt-out (see settings/+page.svelte): recovery's `getPushIntent()
 * === userId` comparison never matches `off:<userId>`, so the sentinel is
 * inert for recovery by construction — only the settings backfill consults
 * `hasExplicitPushOptOut`.
 *
 * Framework-free on purpose: no `$app/*`, `$lib/*`, or svelte imports, so
 * this module is importable directly by `bun test`. Every accessor is a
 * no-op / returns null/false when `localStorage` is unavailable (SSR,
 * service worker, build) and swallows any thrown storage error (Safari
 * private mode, storage disabled).
 */
export const PUSH_INTENT_KEY = 'jamye:push-intent';

/** Prefix marking an explicit opt-out sentinel: `off:<userId>`. */
const OPT_OUT_PREFIX = 'off:';

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

/**
 * Record that `userId` explicitly turned push OFF on this device. Distinct
 * from `clearPushIntent`: a cleared marker is indistinguishable from a
 * legacy user who never had one, which lets a concurrent tab's backfill
 * silently re-set intent after an explicit opt-out. The sentinel makes the
 * opt-out durable and ordering-independent instead.
 */
export function setPushIntentOff(userId: string): void {
	if (typeof localStorage === 'undefined') return;
	try {
		localStorage.setItem(PUSH_INTENT_KEY, `${OPT_OUT_PREFIX}${userId}`);
	} catch {
		// Safari private mode / storage disabled — nothing we can do.
	}
}

/** Whether `userId` has explicitly opted out of push on this device. */
export function hasExplicitPushOptOut(userId: string): boolean {
	return getPushIntent() === `${OPT_OUT_PREFIX}${userId}`;
}
