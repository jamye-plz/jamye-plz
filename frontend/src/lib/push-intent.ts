/**
 * Records that the signed-in user WANTS push notifications enabled on this
 * device. This is an INTENT record ("who wants push here"), NOT a
 * subscription-state cache — it says nothing about whether a live
 * PushSubscription currently exists. It is written only from main-thread
 * settings paths (the toggle, and the settings onMount backfill); the
 * service worker never writes it.
 *
 * Two SEPARATE keys, not one:
 * - `PUSH_INTENT_KEY` — the user id that currently wants push ON.
 * - `PUSH_OPTOUT_KEY` — the user id that explicitly turned push OFF.
 *
 * They must live apart because the settings backfill (a non-gesture,
 * best-effort path) only ever writes the intent key. If opt-out were
 * encoded inside that same key (e.g. an `off:<userId>` value), the backfill
 * writing the intent key would itself be the act of clobbering an opt-out —
 * a read-then-write race across two open settings tabs, not something a
 * single key can be made atomic against from this module. Splitting the
 * keys removes the race structurally: the backfill physically cannot touch
 * where the opt-out lives. Readers (recovery, the backfill) give the
 * opt-out key precedence over the intent key.
 *
 * Framework-free on purpose: no `$app/*`, `$lib/*`, or svelte imports, so
 * this module is importable directly by `bun test`. Every accessor is a
 * no-op / returns null/false when `localStorage` is unavailable (SSR,
 * service worker, build) and swallows any thrown storage error (Safari
 * private mode, storage disabled).
 */
export const PUSH_INTENT_KEY = 'jamye:push-intent';

/** Separate key: the user id that explicitly opted OUT on this device. */
export const PUSH_OPTOUT_KEY = 'jamye:push-optout';

/** The user id that last expressed push intent on this device, or null. */
export function getPushIntent(): string | null {
	if (typeof localStorage === 'undefined') return null;
	try {
		return localStorage.getItem(PUSH_INTENT_KEY);
	} catch {
		return null;
	}
}

/**
 * Record that `userId` wants push enabled on this device. Also clears
 * `userId`'s OWN opt-out record (never another user's) — an explicit
 * toggle-ON gesture is a fresh decision that supersedes that same user's
 * prior opt-out. Best-effort: failures on either step are swallowed.
 */
export function setPushIntent(userId: string): void {
	if (typeof localStorage === 'undefined') return;
	try {
		localStorage.setItem(PUSH_INTENT_KEY, userId);
	} catch {
		// Safari private mode / storage disabled — nothing we can do.
	}
	try {
		if (localStorage.getItem(PUSH_OPTOUT_KEY) === userId) {
			localStorage.removeItem(PUSH_OPTOUT_KEY);
		}
	} catch {
		// Safari private mode / storage disabled — nothing we can do.
	}
}

/**
 * Record that `userId` wants push enabled on this device, WITHOUT touching
 * the opt-out key — for the settings backfill only (a non-gesture,
 * best-effort reconciliation), never the explicit toggle-ON gesture (that
 * stays on `setPushIntent`, which is allowed to clear the user's own
 * opt-out as part of a fresh decision). The backfill is a non-gesture
 * writer, so it gets a setter that physically cannot clear an opt-out;
 * combined with readers giving the opt-out key precedence over the intent
 * key, either ordering of backfill vs a concurrent tab's opt-out write
 * converges to opt-out. Best-effort: failure is swallowed.
 */
export function backfillPushIntent(userId: string): void {
	if (typeof localStorage === 'undefined') return;
	try {
		localStorage.setItem(PUSH_INTENT_KEY, userId);
	} catch {
		// Safari private mode / storage disabled — nothing we can do.
	}
}

/** Remove the push-intent marker from this device. Leaves opt-out alone. */
export function clearPushIntent(): void {
	if (typeof localStorage === 'undefined') return;
	try {
		localStorage.removeItem(PUSH_INTENT_KEY);
	} catch {
		// Safari private mode / storage disabled — nothing we can do.
	}
}

/**
 * Record that `userId` explicitly turned push OFF on this device, on its
 * OWN key so no other write path (in particular the settings backfill,
 * which only ever writes `PUSH_INTENT_KEY`) can ever overwrite it. Also
 * removes the (now stale) intent marker, best-effort.
 */
export function setPushIntentOff(userId: string): void {
	if (typeof localStorage === 'undefined') return;
	try {
		localStorage.setItem(PUSH_OPTOUT_KEY, userId);
	} catch {
		// Safari private mode / storage disabled — nothing we can do.
	}
	try {
		localStorage.removeItem(PUSH_INTENT_KEY);
	} catch {
		// Safari private mode / storage disabled — nothing we can do.
	}
}

/** Whether `userId` has explicitly opted out of push on this device. */
export function hasExplicitPushOptOut(userId: string): boolean {
	if (typeof localStorage === 'undefined') return false;
	try {
		return localStorage.getItem(PUSH_OPTOUT_KEY) === userId;
	} catch {
		return false;
	}
}

/**
 * Cross-tab counterpart to `push.api.ts`'s module-local `logoutGeneration`.
 * A logout in one tab must be observable to an in-flight recovery running in
 * ANOTHER tab, which a module-local counter (scoped to one JS realm) cannot
 * see. Storing the generation here closes that gap: the logout tab bumps it
 * BEFORE reading the subscription it is about to tear down, and recovery
 * rechecks it AFTER creating a subscription — so any interleaving of the two
 * is caught by one side or the other. The module-local counter remains as a
 * fallback layer for when storage itself is unavailable (Safari private
 * mode) — same-tab ordering still works without it.
 */
export const PUSH_LOGOUT_GEN_KEY = 'jamye:push-logout-gen';

/** The stored cross-tab logout generation, or `'0'` if unset/unavailable. */
export function readLogoutGeneration(): string {
	if (typeof localStorage === 'undefined') return '0';
	try {
		return localStorage.getItem(PUSH_LOGOUT_GEN_KEY) ?? '0';
	} catch {
		return '0';
	}
}

/** Increment the stored cross-tab logout generation. No-op without storage. */
export function bumpLogoutGeneration(): void {
	if (typeof localStorage === 'undefined') return;
	try {
		const current = parseInt(localStorage.getItem(PUSH_LOGOUT_GEN_KEY) ?? '0', 10) || 0;
		localStorage.setItem(PUSH_LOGOUT_GEN_KEY, String(current + 1));
	} catch {
		// Safari private mode / storage disabled — nothing we can do.
	}
}
