import { writable } from 'svelte/store';

/**
 * Bumped once from `+layout.svelte`'s `onRegisteredSW` callback, right after
 * the PWA service worker registration actually appears. Without this,
 * `PushReconciler` can run its once-per-user reclaim BEFORE the SW
 * registration exists (e.g. right after an unregister/rollback): reclaim
 * silently no-ops on the missing registration, and the `uid !==
 * lastReclaimed` latch then blocks any retry until a full page reload. This
 * pulse lets the reconciler re-run reclaim for the current user once the
 * registration that was missing before now exists — reclaim is idempotent,
 * so re-running it is harmless.
 *
 * Purely a "something changed" pulse — the number itself is meaningless,
 * only each increment matters. Mirrors `push-recovery-signal.ts`: no
 * `svelte/store` precedent otherwise exists in this repo (runes replaced
 * stores for local component state), but the writer here is a plain
 * `onMount` callback outside a shared reactive scope with the reader
 * component, so a tiny classic store is again the smallest cross-module fit.
 */
export const swRegisteredSignal = writable(0);

/** Call only from `+layout.svelte`'s `onRegisteredSW` callback. */
export function signalSwRegistered(): void {
	swRegisteredSignal.update((n) => n + 1);
}
