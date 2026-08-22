import { writable } from 'svelte/store';

/**
 * Bumped once by `recoverIntendedPush` (in `push.api.ts`) right after a
 * background re-subscribe actually succeeds, so an open /settings page can
 * flip its toggle to ON without a reload. Purely a "something changed"
 * pulse — the number itself is meaningless, only each increment matters.
 *
 * No `svelte/store` precedent exists elsewhere in this repo (runes replaced
 * stores for local component state), but the writer here lives outside
 * component scope, in a plain `.ts` API module — runes cannot cross that
 * boundary, so a tiny classic store is the smallest fit for this one
 * cross-module signal. Framework-light on purpose: no query cache entry to
 * invalidate, since subscription state was never a TanStack Query result.
 */
export const pushRecoverySignal = writable(0);

/** Call only from the recovery success path — never on failure or skip. */
export function signalPushRecovered(): void {
	pushRecoverySignal.update((n) => n + 1);
}
