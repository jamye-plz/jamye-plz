<script lang="ts">
	// Headless: whenever an authenticated user is known (any page, not just
	// Settings), re-claim this browser's push subscription for them so a
	// previous account's subscription row can't keep delivering to whoever is
	// now signed in here (cross-account push). Runs inside the query provider.
	import { createQuery } from '@tanstack/svelte-query';
	import { getMe } from '$lib/api/auth.api';
	import { reclaimPushForCurrentUser } from '$lib/api/push.api';

	const meQuery = createQuery(() => ({ queryKey: ['me'], queryFn: getMe, retry: false }));

	let lastReclaimed: string | null = null;
	$effect(() => {
		const uid = meQuery.data?.id;
		if (uid && uid !== lastReclaimed) {
			lastReclaimed = uid;
			reclaimPushForCurrentUser();
		}
	});
</script>
