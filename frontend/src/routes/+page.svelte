<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { onMount } from 'svelte';

	onMount(() => {
		// Resume a pending invite redemption after login (see /invite/[code]).
		const pending = sessionStorage.getItem('pending_invite');
		if (pending) {
			sessionStorage.removeItem('pending_invite');
			goto(resolve(`/invite/${pending}`), { replaceState: true });
			return;
		}
		goto(resolve('/groups'));
	});
</script>
