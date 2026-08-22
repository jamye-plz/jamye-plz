<script lang="ts">
	// Headless: whenever an authenticated user is known (any page, not just
	// Settings), re-claim this browser's push subscription for them so a
	// previous account's subscription row can't keep delivering to whoever is
	// now signed in here (cross-account push). Runs inside the query provider.
	import { createQuery } from '@tanstack/svelte-query';
	import { getMe } from '$lib/api/auth.api';
	import { reclaimPushForCurrentUser } from '$lib/api/push.api';
	import { swRegisteredSignal } from '$lib/sw-ready-signal';

	const meQuery = createQuery(() => ({ queryKey: ['me'], queryFn: getMe, retry: false }));

	// Composite key, not just uid: if no SW registration existed yet when
	// reclaim last ran for this user, it silently no-opped (getActiveRegistration
	// returns null) and this latch would otherwise block any retry until a full
	// reload. Folding the SW-ready pulse into the key means a registration
	// appearing mid-session re-triggers reclaim for the SAME uid too — reclaim
	// is idempotent, so re-running it here is harmless.
	let lastReclaimedFor: string | null = null;
	$effect(() => {
		const uid = meQuery.data?.id;
		const swPulse = $swRegisteredSignal;
		if (!uid) return;
		const key = `${uid}:${swPulse}`;
		if (key !== lastReclaimedFor) {
			lastReclaimedFor = key;
			reclaimPushForCurrentUser(uid);
		}
	});
</script>
